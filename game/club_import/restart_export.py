"""Read-only export of current imported facts, NOT a replay of old packages."""
from collections import Counter
from copy import deepcopy
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import zipfile

from django.core.serializers.json import DjangoJSONEncoder
from django.db import connection, transaction
from django.db.models import Q

from game import models as m
from .restart_schema import ANCHORS, FIELDS, FORMAT, MODELS, exclusions, structure
from .live_restart_inventory import build_inventory


class HandoffError(ValueError):
    pass


class LosslessEncoder(DjangoJSONEncoder):
    def default(self, value):
        # DjangoJSONEncoder truncates datetimes to milliseconds, including
        # ".000" which disappears after parsing. A transport must retain all
        # six fractional digits, not normalize away real source precision.
        if isinstance(value, datetime):
            return value.isoformat(timespec="microseconds")
        return super().default(value)


def canonical(value):
    return json.dumps(value, cls=LosslessEncoder, sort_keys=True,
                      ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def sha(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def validate_json(value):
    """Fail explicitly if opaque evidence tries to carry private/local data."""
    if isinstance(value, dict):
        forbidden = {
            "password", "password_hash", "token", "access_token", "api_key", "secret",
            "user_id", "manager_id", "created_by_id", "resolved_by_id", "player_id",
            "club_id", "package_id", "pk", "image", "image_url", "photo", "photo_url",
            "player_image_url", "player_image_cached_path",
        }
        local_fk = any(str(k).lower().endswith((
            "_club_id", "_player_id", "_person_id", "_package_id", "_user_id",
        )) for k in value)
        if local_fk or forbidden.intersection(str(k).lower() for k in value):
            raise HandoffError("Nicht freigegebene Account-/Bild-/lokale ID-Daten in JSON-Beleg.")
        for child in value.values():
            validate_json(child)
    elif isinstance(value, list):
        for child in value:
            validate_json(child)


def source_only_evidence(value):
    """Known legacy ownership notes contain a redundant workspace FK.

    Retain the already recorded TM identity and original name, not the local
    FK. Unknown local-ID shapes still fail validation rather than being dropped.
    """
    result = deepcopy(value)
    if isinstance(result, dict) and isinstance(result.get("preserved_owner"), dict):
        owner = result["preserved_owner"]
        if "owner_club_id" in owner:
            if not owner.get("owner_club_tm_id"):
                raise HandoffError("Eigentümerbeleg ohne stabile TM-Identität.")
            owner.pop("owner_club_id")
    return result


@contextmanager
def read_snapshot():
    owns = not connection.in_atomic_block
    with transaction.atomic():
        if connection.vendor == "postgresql" and owns:
            with connection.cursor() as cursor:
                cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        yield


def collect():
    """Follow the complete FK closure without broadening import-club membership."""
    imported = set(m.SourceImportRun.objects.filter(
        source="club_package", status="applied", club__isnull=False,
    ).values_list("club_id", flat=True))
    if not imported:
        raise HandoffError("Keine angewandten Vereinspakete vorhanden.")
    source_player_ids = {
        player["ids"]["tm"]["value"]
        for run in m.SourceImportRun.objects.filter(
            source="club_package", status="applied", club_id__in=imported)
        for player in run.package_data.get("players", [])
    }
    # Membership alone misses quarantines deliberately removed from a squad.
    # The old packages identify the selection only; NEVER supply field values.
    players = m.Player.objects.filter(
        Q(club_id__in=imported) | Q(owner_club_id__in=imported)
        | Q(transfermarkt_id__in=source_player_ids))
    present = set(players.values_list("transfermarkt_id", flat=True))
    if source_player_ids - present:
        raise HandoffError("Archiv-Spieler fehlen im aktuellen Bestand; keine Rekonstruktion aus Altpaketen.")
    groups = {name: {} for name in MODELS}

    def add(name, query):
        for obj in query.order_by("pk"):
            groups[name][obj.pk] = obj

    add("Club", m.Club.objects.filter(pk__in=imported))
    add("Player", players)
    pids = set(groups["Player"])
    add("SourceImportRun", m.SourceImportRun.objects.filter(
        source="club_package", status="applied", club_id__in=imported))
    for name, model in MODELS.items():
        if name in ANCHORS:
            continue
        query = model.objects.none()
        if name == "PlayerExternalId":
            # Historical person identities are added after their FK closure.
            query = model.objects.filter(player_id__in=pids)
        elif "player" in FIELDS[name]:
            query = model.objects.filter(player_id__in=pids)
        elif "club" in FIELDS[name]:
            query = model.objects.filter(club_id__in=imported)
        if name == "ClubRecord":
            query = query.filter(source="SEED")
        if name in ("ClubTrophy", "ClubTrophyEntry"):
            query = query.filter(origin="real")
        add(name, query)
    # Close all selected FKs, including historic holders, clubs referred to by
    # transfers, old provenance runs and leagues of referenced clubs.
    while True:
        before = sum(len(rows) for rows in groups.values())
        needed = {name: set() for name in MODELS}
        for name, rows in groups.items():
            for field in FIELDS[name]:
                f = MODELS[name]._meta.get_field(field)
                if f.is_relation:
                    target = f.related_model.__name__
                    if target not in groups:
                        raise HandoffError(f"Nicht freigegebene Relation: {name}.{field}")
                    needed[target].update(getattr(obj, f.attname) for obj in rows.values()
                                          if getattr(obj, f.attname) is not None)
        for name, ids in needed.items():
            add(name, MODELS[name].objects.filter(pk__in=ids - groups[name].keys()))
        add("PlayerExternalId", m.PlayerExternalId.objects.filter(
            person_id__in=groups["HistoricCoach"].keys()))
        # Every source identity for a supporting club/player must travel too.
        add("ClubExternalId", m.ClubExternalId.objects.filter(club_id__in=groups["Club"].keys()))
        add("PlayerExternalId", m.PlayerExternalId.objects.filter(player_id__in=groups["Player"].keys()))
        if sum(len(rows) for rows in groups.values()) == before:
            break
    return groups, imported


def encode_groups(groups):
    keys = {}

    def key(name, pk):
        if pk is None:
            return None
        if (name, pk) in keys:
            return keys[name, pk]
        obj = groups[name].get(pk)
        if obj is None:
            raise HandoffError(f"Fehlende Referenz in {name}.")
        if name in ("Club", "Player"):
            for field, provider in (("transfermarkt_id", "tm"), ("fm_inside_id", "fm"),
                                    ("api_football_id", "api")):
                if getattr(obj, field):
                    result = f"{name}:{provider}:{getattr(obj, field)}"
                    break
            else:
                raise HandoffError(f"{name} ohne belegte Quellidentität.")
        elif name == "League":
            result = "League:" + canonical([obj.country, obj.name, obj.competition_type, obj.level])
        elif name == "DataSource":
            result = f"DataSource:{obj.code}"
        elif name == "SourceImportRun":
            result = "SourceImportRun:" + sha([
                key("Club", obj.club_id), obj.source, obj.data_sha256,
                obj.imported_at, obj.applied_at,
            ])
        elif name == "HistoricCoach":
            if obj.linked_player_id:
                identity = ["linked-player", key("Player", obj.linked_player_id), obj.person_kind]
            else:
                ids = sorted([
                    [groups["DataSource"][ext.source_id].code, ext.identity_kind, ext.external_id]
                    for ext in groups["PlayerExternalId"].values()
                    if ext.person_id == pk and ext.external_id
                ])
                if ids:
                    identity = ids
                elif obj.fm_inside_id:
                    identity = ["fm", obj.person_kind, obj.fm_inside_id]
                else:
                    # A package-local person ref is evidence, not a global
                    # guessed identity. Match through an already persisted
                    # record->person relation and its package record key.
                    refs = sorted([
                        [key("Club", record.club_id), record.record_key,
                         key("SourceImportRun", record.package_id)]
                        for record in groups["ClubRecord"].values()
                        if record.holder_coach_id == pk and record.package_id
                    ])
                    if not refs:
                        raise HandoffError("Historische Person ohne belegte Quellreferenz.")
                    identity = ["record-holder", refs]
            result = "HistoricCoach:" + sha(identity)
        else:
            raise HandoffError(f"Kein Anker: {name}")
        keys[name, pk] = result
        return result

    def values(name, obj):
        result = {}
        for field in FIELDS[name]:
            f = MODELS[name]._meta.get_field(field)
            value = getattr(obj, f.attname)
            if f.is_relation:
                value = key(f.related_model.__name__, value)
            elif isinstance(value, (Decimal, date, datetime)):
                value = json.loads(canonical(value))
            if name == "ImportIssue" and field == "external_reference":
                value = source_only_evidence(value)
            if f.get_internal_type() == "JSONField":
                validate_json(value)
            result[field] = value
        return result

    tables = {}
    for name, rows in groups.items():
        encoded = []
        duplicates = Counter()
        for obj in rows.values():
            data = values(name, obj)
            identity = key(name, obj.pk) if name in ANCHORS else name + ":" + sha(data)
            duplicates[identity] += 1
            if name in ANCHORS and duplicates[identity] > 1:
                raise HandoffError(f"Mehrdeutige stabile Identität: {identity}")
            # Retain genuinely identical child rows as a multiset.
            encoded.append({"key": identity if name in ANCHORS else
                            f"{identity}:{duplicates[identity]}", "values": data})
        tables[name] = sorted(encoded, key=lambda row: row["key"])
    return tables, keys


def parity(tables):
    return {name: {"rows": len(rows), "sha256": sha(rows)} for name, rows in tables.items()}


def swiss_reconciliation(inventory):
    # Research is available; the previously supplied ZIPs need not be present
    # in a new task branch. Never claim that merged scripts equal imported data.
    from .swiss_winless_20261027 import RECORDS
    source = "attached_assets/schweiz_vereinspakete_2026-10-27_1793106969838.zip"
    source_sha = "4b0ae43e098ab953032ea8fcda679e9cd27ccb41c5a46f616e02e09ffe9b723d"
    open_records = {(260, "longest_unbeaten"), (527, "longest_win_streak_coach")}
    candidates = sorted(Path("attached_assets").glob("*schweiz_vereinspakete_*.zip"))
    archives = []
    for path in candidates:
        checksum = hashlib.sha256(path.read_bytes()).hexdigest()
        archives.append({"file": str(path), "sha256": checksum, "approved_bytes": checksum == source_sha})
    present = [c for c in inventory["clubs"] if c["league"] == "Super League"]
    return {
        "expected_clubs": 12, "current_imported_clubs": len(present),
        "documented_historical_source_counts_not_current_db": {
            "player_entries": 635, "unique_players": 631,
            "persons": 129, "records": 288, "titles": 369,
        },
        "expected_original_sha256": source_sha, "documented_original": source,
        "available_archives": archives,
        "source_status": "available" if any(a["approved_bytes"] for a in archives) else "missing",
        "current_state_status": "present" if len(present) == 12 else "missing_or_incomplete",
        "open_records": [{"club_tm": tm, "record_key": key} for tm, key in sorted(open_records)],
        "researched_winless": {str(tm): data for tm, data in RECORDS.items()},
        "gc_corrections": {
            "club_tm": 504, "biggest_defeat": "1:8", "date": "2004-09-12",
            "opponent_tm": 26, "youngest_player": "15 Jahre, 136 Tage", "debut": "1992-07-22",
        },
        "documents": [
            "docs/import-pilot/schweiz-2026-10-27.md",
            "docs/import-pilot/schweiz-rekordserien-zuerich-lausanne-2026-10-27.md",
            "docs/import-pilot/schweiz-serien-ohne-sieg-quellenpruefung.md",
        ],
        "note": "Quellen/Recherche getrennt vom tatsächlichen DB-Bestand; kein Nachimport ausgeführt.",
    }


def build_package():
    with read_snapshot():
        inventory = build_inventory()
        groups, imported = collect()
        tables, keys = encode_groups(groups)
        swiss = swiss_reconciliation(inventory)
        blockers = list(inventory["source_problems"])
        if swiss["current_state_status"] != "present":
            blockers.append("Zwölf Schweizer Vereinsstände fehlen im aktuellen DB-Bestand.")
        if swiss["source_status"] != "available":
            blockers.append("Originales Schweizer Lieferarchiv fehlt; keine vollständige Schweizer Übergabe möglich.")
        source_archives = []
        for run in groups["SourceImportRun"].values():
            source_archives.append({
                "run": keys["SourceImportRun", run.pk],
                "stored_package_canonical_sha256": sha(run.package_data),
                "source_data_sha256": run.data_sha256,
                "manifest": run.manifest,
                "stored_package_data": run.package_data,
                "note": "Nur Provenienz; aktuelle Tabellen sind die Übernahmewerte.",
            })
            validate_json(run.manifest)
            validate_json(run.package_data)
        return {
            "format": FORMAT,
            "inventory": inventory,
            "imported_clubs": sorted(keys["Club", pk] for pk in imported),
            "schema": structure(),
            "excluded_columns": exclusions(),
            "source_archives": sorted(source_archives, key=lambda row: row["run"]),
            "switzerland": swiss,
            "full_restart_ready": False,
            "blockers": blockers,
            "current_vs_archive": current_vs_archive(groups),
            "parity": parity(tables),
            "tables": tables,
        }


def current_vs_archive(groups):
    """Make post-import FM fixes visible without deriving any current value."""
    originals = {}
    ordered = sorted(groups["SourceImportRun"].values(),
                     key=lambda run: (run.applied_at or run.imported_at, run.imported_at))
    for run in ordered:
        for player in run.package_data.get("players", []):
            originals[player["ids"]["tm"]["value"]] = player
    differences = []
    ratings = {(row.player_id, row.source): row
               for row in groups["PlayerSourceRating"].values()}
    for player in groups["Player"].values():
        original = originals.get(player.transfermarkt_id)
        if not original:
            continue
        changes = {}
        old_fm = original["ids"]["fmi"]["value"]
        if old_fm != player.fm_inside_id:
            changes["fm_inside_id"] = {"archive": old_fm, "current": player.fm_inside_id}
        for source, section in (("FM", "fminside"), ("CMTRACKER", "cmtracker")):
            current = ratings.get((player.pk, source))
            old = original.get("ratings", {}).get(section)
            if current and old:
                for field in ("rating", "potential"):
                    if getattr(current, field) != old.get(field):
                        changes[f"{source}.{field}"] = {
                            "archive": old.get(field), "current": getattr(current, field),
                        }
        if changes:
            differences.append({
                "player_tm": player.transfermarkt_id,
                "changes": changes, "current_import_lock": player.import_lock,
                "current_import_lock_reasons": player.import_lock_reasons,
            })
    return sorted(differences, key=lambda row: row["player_tm"])


def write_package(path, package):
    """One portable, content-addressed ZIP, no database dump or binary assets."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = canonical(package).encode()
    with zipfile.ZipFile(path, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("current-state.json", payload)
        archive.writestr("SHA256SUMS", hashlib.sha256(payload).hexdigest() + "  current-state.json\n")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_package(path):
    with zipfile.ZipFile(path) as archive:
        if len(archive.namelist()) != 2 or set(archive.namelist()) != {"current-state.json", "SHA256SUMS"}:
            raise HandoffError("Unerwartete Dateien im Übernahmepaket.")
        if archive.getinfo("current-state.json").file_size > 512 * 1024 * 1024:
            raise HandoffError("Übernahmepaket überschreitet Größenlimit.")
        payload = archive.read("current-state.json")
        if archive.read("SHA256SUMS").decode() != hashlib.sha256(payload).hexdigest() + "  current-state.json\n":
            raise HandoffError("Paket-Prüfsumme stimmt nicht.")
    package = json.loads(payload)
    if package.get("format") != FORMAT or package.get("schema") != structure():
        raise HandoffError("Unbekanntes Format oder abweichendes Schema.")
    if set(package["tables"]) != set(MODELS) or parity(package["tables"]) != package["parity"]:
        raise HandoffError("Tabellenumfang oder Inhaltsprüfsummen weichen ab.")
    for name, rows in package["tables"].items():
        if len({row["key"] for row in rows}) != len(rows):
            raise HandoffError(f"Doppelte Übernahmeidentität: {name}")
        for row in rows:
            if set(row["values"]) != set(FIELDS[name]):
                raise HandoffError(f"Nicht freigegebene/fehlende Spalten: {name}")
            for field in FIELDS[name]:
                if MODELS[name]._meta.get_field(field).get_internal_type() == "JSONField":
                    validate_json(row["values"][field])
    for archive in package["source_archives"]:
        validate_json(archive["manifest"])
        if "stored_package_data" in archive:
            validate_json(archive["stored_package_data"])
            if sha(archive["stored_package_data"]) != archive["stored_package_canonical_sha256"]:
                raise HandoffError("Archiv-Provenienz stimmt nicht mit gespeichertem JSON überein.")
    return package
