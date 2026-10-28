"""Import oracle restricted to a new, isolated SQLite database.

This is deliberately NOT a production importer. It cannot write to PostgreSQL
or to the regular workspace database. It never calls model save hooks.
"""
from collections import Counter
from pathlib import Path
import json

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import connection, transaction
from django.utils import timezone

from .restart_export import HandoffError, canonical, parity, sha
from .restart_schema import FIELDS, MODELS, structure


def assert_isolated(require_empty=True):
    root = (Path(settings.BASE_DIR) / "generated-artifacts" / "live-restart").resolve()
    db = Path(connection.settings_dict["NAME"]).resolve()
    if (not getattr(settings, "LIVE_RESTART_VERIFY_ONLY", False)
            or connection.vendor != "sqlite"
            or root not in db.parents or db.suffix != ".sqlite3"):
        raise HandoffError("Replay ausschließlich in einer isolierten SQLite-Prüfdatei erlaubt.")
    if require_empty and any(model.objects.exists() for model in MODELS.values()):
        raise HandoffError("Prüfdatenbank enthält bereits Übernahmedaten; kein Überschreiben erlaubt.")


def replay(package):
    assert_isolated()
    if structure() != package["schema"]:
        raise HandoffError("Prüfschema weicht ab.")
    keys = {}
    # Destination IDs are deliberately generated independently, above every
    # common source sequence. The bundle contains no source surrogate PKs.
    next_pk = 10_000_000
    with transaction.atomic():
        with connection.cursor() as cursor:
            for name, model in MODELS.items():
                rows = package["tables"][name]
                columns = list(model._meta.local_concrete_fields)
                sql = "INSERT INTO {} ({}) VALUES ({})".format(
                    connection.ops.quote_name(model._meta.db_table),
                    ", ".join(connection.ops.quote_name(f.column) for f in columns),
                    ", ".join(["%s"] * len(columns)),
                )
                batch = []
                for row in rows:
                    next_pk += 1
                    keys[name, row["key"]] = next_pk
                    values = {}
                    for f in columns:
                        if f.primary_key:
                            value = next_pk
                        elif f.name in row["values"]:
                            value = row["values"][f.name]
                            if f.is_relation and value is not None:
                                target = (f.related_model.__name__, value)
                                if target not in keys:
                                    raise HandoffError(f"Nicht auflösbare Referenz: {name}.{f.name}")
                                value = keys[target]
                        elif name == "Club" and f.name == "budget":
                            value = 0  # explicitly NOT a copied workspace balance
                        elif getattr(f, "auto_now", False) or getattr(f, "auto_now_add", False):
                            value = timezone.now()
                        else:
                            value = f.get_default()
                        values[f.attname] = value
                    # Field conversions preserve dates, Decimal scale and JSON.
                    obj = model(**values)
                    batch.append([f.get_db_prep_save(getattr(obj, f.attname), connection)
                                  for f in columns])
                    if len(batch) == 500:
                        cursor.executemany(sql, batch)
                        batch.clear()
                if batch:
                    cursor.executemany(sql, batch)
        # Restore archival JSON as provenance ONLY. No field from it is applied
        # to players/clubs; all current values above come from current tables.
        # Keeping it allows a combined isolated export to retain provenance of
        # the original workspace, without connecting back to that database.
        for archive in package["source_archives"]:
            pk = keys.get(("SourceImportRun", archive["run"]))
            if pk is None:
                raise HandoffError("Provenienz ohne zugehörigen Paketlauf.")
            changes = {"manifest": archive["manifest"]}
            if "stored_package_data" in archive:
                if sha(archive["stored_package_data"]) != archive["stored_package_canonical_sha256"]:
                    raise HandoffError("Archiv-Provenienz stimmt nicht.")
                changes["package_data"] = archive["stored_package_data"]
            MODELS["SourceImportRun"].objects.filter(pk=pk).update(**changes)
        connection.check_constraints()
        actual = {}
        reverse = {(name, pk): key for (name, key), pk in keys.items()}
        for name, model in MODELS.items():
            encoded = []
            for obj in model.objects.order_by("pk"):
                data = {}
                for field in FIELDS[name]:
                    f = model._meta.get_field(field)
                    value = getattr(obj, f.attname)
                    if f.is_relation and value is not None:
                        value = reverse[f.related_model.__name__, value]
                    data[field] = value
                # Normalize exactly as the source serializer.
                encoded.append({
                    "key": reverse[name, obj.pk],
                    "values": json.loads(canonical(data)),
                })
            actual[name] = sorted(encoded, key=lambda row: row["key"])
        comparisons = {}
        expected = parity(package["tables"])
        observed = parity(actual)
        for name in MODELS:
            comparisons[name] = {
                "expected": expected[name], "observed": observed[name],
                "identical": actual[name] == package["tables"][name],
            }
        if any(not result["identical"] for result in comparisons.values()):
            bad = []
            for name, result in comparisons.items():
                if result["identical"]:
                    continue
                differing = Counter(
                    field
                    for expected_row, actual_row in zip(package["tables"][name], actual[name])
                    for field in FIELDS[name]
                    if expected_row["values"][field] != actual_row["values"][field]
                )
                bad.append(f"{name}: {dict(differing)}")
            raise HandoffError("Inhaltsparität fehlgeschlagen: " + "; ".join(bad))
        # Schema/field equality is separate from the entire row/content check.
        return {
            "format": "WS_RESTART_PARITY_V1",
            "isolated": True, "backend": connection.vendor,
            "production_import_executed": False, "reset_executed": False,
            "schema_identical": structure() == package["schema"],
            "foreign_key_check": "passed", "all_tables_identical": True,
            "table_comparisons": comparisons,
            "generated_destination_pk_start": 10_000_001,
            "source_pks_in_bundle": False,
            "destination_accounts": get_user_model().objects.count(),
            "content_sha256": sha(actual),
            "acceptance": acceptance(actual, package["imported_clubs"]),
            "blockers": package["blockers"],
            "full_restart_ready": False,
            "limitations": [
                "SQLite-Prüftransport, kein PostgreSQL-Server-Restore.",
                "Kein produktiver Importpfad freigegeben oder ausgeführt.",
                "Ausgeschlossene Spiel-/Account-/Bilddaten sind nicht Teil der Parität.",
                "Schweizer Quellenbestand und tatsächlicher DB-Bestand separat beachten.",
            ],
        }


def acceptance(tables, imported_clubs):
    players = tables["Player"]
    imported = set(imported_clubs)
    roster = [row for row in players if row["values"]["club"] in imported
              or row["values"]["owner_club"] in imported]
    sample = next((row for row in players
                   if row["values"]["transfermarkt_id"] == 796297), None)
    sample_values = None
    if sample:
        values = sample["values"]
        sample_values = {
            "tm_id": 796297,
            "main_positions": [values[f"main_position_{i}"] for i in range(1, 4)
                               if values[f"main_position_{i}"]],
            "secondary_positions": [values[f"secondary_position_{i}"] for i in range(1, 4)
                                    if values[f"secondary_position_{i}"]],
            "market_value_points": sum(row["values"]["player"] == sample["key"]
                                       for row in tables["PlayerMarketValueSnapshot"]),
            "transfer_history_rows": sum(row["values"]["player"] == sample["key"]
                                         for row in tables["PlayerTransferHistory"]),
        }
    return {
        "imported_clubs": len(imported), "roster_players": len(roster),
        "locked_players": sum(row["values"]["import_lock"] for row in roster),
        "null_source_potentials": dict(Counter(
            row["values"]["source"] for row in tables["PlayerSourceRating"]
            if row["values"]["potential"] is None)),
        "jobe_tm_796297": sample_values,
        "loan_state_sha256": sha([
            {field: row["values"][field] for field in (
                "transfermarkt_id", "club", "owner_club", "owner_club_tm_id",
                "loan_club", "loan_club_tm_id", "loan_status", "loan_until",
                "squad_team", "import_lock", "import_lock_reasons")}
            for row in players
        ]),
    }
