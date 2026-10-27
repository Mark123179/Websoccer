"""Private scene backup and strict comparison helpers; no restore/reset writes."""


def build_scene_snapshot(connection):
    from django.conf import settings
    from django.core.management.base import CommandError
    from django.db import transaction
    from game.models import ClubStadionumfeldState
    from stadium_editor.models import StadiumDesign, StadiumGeometry

    if "import_pilot" in settings.SETTINGS_MODULE:
        raise CommandError("Die Live-Sicherung darf nicht den Import-Pilot verwenden.")
    owns_transaction = not connection.in_atomic_block
    alias = connection.alias
    entries = {}
    unresolved = []
    with transaction.atomic(using=alias):
        if connection.vendor == "postgresql" and owns_transaction:
            with connection.cursor() as cursor:
                cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        specs = (
            (StadiumGeometry, "geometry", "stadium__club"),
            (StadiumDesign, "design", "stadium__club"),
            (ClubStadionumfeldState, "surroundings", "club"),
        )
        for model, key, relation in specs:
            for obj in model.objects.using(alias).select_related(relation).order_by("pk"):
                club = obj.club if relation == "club" else obj.stadium.club
                entry = entries.setdefault(club.pk, {
                    "identity": {"tm_id": club.transfermarkt_id, "fm_id": club.fm_inside_id},
                    "name": club.name,
                    "geometry": None, "design": None, "surroundings": None,
                })
                if not club.transfermarkt_id and not club.fm_inside_id:
                    unresolved.append({"club_name": club.name, "kind": key})
                # Local PK/FK values are not a license to reattach to a new club.
                entry[key] = {
                    field.name: getattr(obj, field.attname)
                    for field in model._meta.concrete_fields
                    if not field.primary_key and not field.is_relation
                }
        sequences = {}
        if connection.vendor == "postgresql":
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT c.relname FROM pg_class c
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE n.nspname = 'public' AND c.relkind = 'S'
                    ORDER BY c.relname
                """)
                for (name,) in cursor.fetchall():
                    quoted = connection.ops.quote_name(name)
                    cursor.execute(f"SELECT last_value, is_called FROM public.{quoted}")
                    sequences[name] = list(cursor.fetchone())
    return {
        "format": "WS_PRIVATE_SCENE_BACKUP_V1",
        "read_only": True,
        "contains_account_rows": False,
        "ready_for_reset": False,
        "sequences": sequences,
        "unresolved_identities": unresolved,
        "clubs": sorted(entries.values(), key=lambda row: (
            str(row["identity"]["tm_id"]), str(row["identity"]["fm_id"]), row["name"])),
        "warning": "Privat sichern. Keine automatische Rückübertragung, keine alten Spielwerte übernehmen.",
    }


def compare_previews(live, restored):
    """Accept only full PostgreSQL fingerprints, never matching empty reports."""
    for report in (live, restored):
        if (report.get("kind") != "read_only_reset_preview"
                or report.get("vendor") != "postgresql"
                or not report.get("tables")
                or report.get("blockers") != []
                or report.get("sql_ready") is not True):
            raise ValueError("Unvollständige oder blockierte PostgreSQL-Vorschau.")
        tables = report["tables"]
        if len({row["table"] for row in tables}) != len(tables):
            raise ValueError("Doppelte Tabellen in der Vorschau.")
        for row in tables:
            fingerprint = row.get("before")
            if (not isinstance(fingerprint, list) or len(fingerprint) != 2
                    or fingerprint[0] != row["rows"]
                    or not isinstance(fingerprint[1], str)
                    or len(fingerprint[1]) != 32):
                raise ValueError("Vollständiger Tabellen-Fingerprint fehlt.")
    for key in ("tables", "profile_keep_columns", "profile_reset", "delete_order"):
        if live.get(key) != restored.get(key) or key not in live:
            raise ValueError(f"Wiederherstellungsvergleich abweichend: {key}")


def compare_scenes(live, restored):
    for report in (live, restored):
        if (report.get("format") != "WS_PRIVATE_SCENE_BACKUP_V1"
                or report.get("read_only") is not True
                or report.get("unresolved_identities") != []
                or not isinstance(report.get("clubs"), list)
                or not isinstance(report.get("sequences"), dict)):
            raise ValueError("Unvollständige Szenensicherung oder ungeklärte Vereinsidentitäten.")
    if live != restored:
        raise ValueError("Szenen- oder Sequenzvergleich abweichend.")
