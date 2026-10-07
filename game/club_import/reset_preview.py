"""Read-only reset inventory. SQL is returned as text, never sent to the database."""
from django.apps import apps
from django.conf import settings
from django.core.management.base import CommandError
from scripts.copy_import_pilot_protected import KEEP_PROFILE, RESET_PROFILE, TABLES


PROFILE = "game_managerprofile"
LAND = "game_landkoeffizient"
TECHNICAL = {"django_migrations"}


def digest_query(quote, table, columns=None, where=""):
    selected = ", ".join(quote(c) for c in columns) if columns else "*"
    return (f"SELECT count(*), md5(coalesce(string_agg(d, '' ORDER BY d), '')) "
            f"FROM (SELECT md5(row_to_json(r)::text) AS d FROM "
            f"(SELECT {selected} FROM {quote(table)} {where}) r) fingerprints")


def build_preview(connection):
    if "import_pilot" in (settings.SETTINGS_MODULE or ""):
        raise CommandError("Die Reset-Vorschau darf nicht auf den Pilot zeigen.")
    if settings.IMPORT_PACKAGE_MODE:
        raise CommandError("Die Umstellungsvorschau erwartet den unveränderten Altmodus.")
    postgres = connection.vendor == "postgresql"
    quote = connection.ops.quote_name
    registry = {m._meta.db_table for m in apps.get_models(include_auto_created=True)
                if m._meta.managed and not m._meta.proxy and not m._meta.swapped}
    profile_model = apps.get_model("game", "ManagerProfile")
    profile_columns = {f.column for f in profile_model._meta.concrete_fields}
    classified = set(KEEP_PROFILE) | set(RESET_PROFILE) | {"updated_at"}
    blockers = []
    rows = []
    foreign_keys = []
    protected = set(TABLES) | TECHNICAL
    with connection.cursor() as cursor:
        # The entire inventory is one read-only snapshot; never autocommit writes.
        cursor.execute("BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY" if postgres else "BEGIN")
        try:
            if postgres:
                cursor.execute("SELECT current_schema()")
                if cursor.fetchone()[0] != "public":
                    raise CommandError("Nur public ist als Live-Zielschema vorgesehen; Pilot ausgeschlossen.")
            else:
                blockers.append("SQL-Entwurf nur für PostgreSQL; diese Vorschau ist kein Live-Nachweis.")
            tables = sorted(connection.introspection.table_names(cursor))
            if PROFILE in tables:
                profile_columns = {f.name for f in connection.introspection.get_table_description(cursor, PROFILE)}
            for missing in sorted(protected - set(tables)):
                blockers.append("Schutztabelle fehlt: " + missing)
            for field in sorted(profile_columns - classified):
                blockers.append("Nicht freigegebenes Profilfeld: " + field)
            for table in tables:
                cursor.execute(f"SELECT count(*) FROM {quote(table)}")
                count = cursor.fetchone()[0]
                action = ("profile_reset" if table == PROFILE else
                          "season_zero_only" if table == LAND else
                          "keep" if table in protected else
                          "delete" if table in registry else "unclassified")
                entry = {"table": table, "rows": count, "action": action}
                if action == "unclassified":
                    blockers.append("Nicht klassifizierte Tabelle: " + table)
                if postgres:
                    cursor.execute(digest_query(quote, table))
                    entry["before"] = list(cursor.fetchone())
                    if table == PROFILE:
                        cursor.execute(digest_query(quote, table, sorted(KEEP_PROFILE)))
                        entry["preserved"] = list(cursor.fetchone())
                    elif table == LAND:
                        cursor.execute(digest_query(quote, table, where="WHERE saison = '0'"))
                        entry["preserved"] = list(cursor.fetchone())
                    else:
                        entry["preserved"] = entry["before"]
                rows.append(entry)
            deleting = {r["table"] for r in rows if r["action"] == "delete"}
            for table in tables:
                for constraint in connection.introspection.get_constraints(cursor, table).values():
                    fk = constraint.get("foreign_key")
                    if fk and table in deleting and fk[0] in deleting:
                        foreign_keys.append((table, fk[0]))
                    if fk and fk[0] in deleting:
                        columns = constraint.get("columns", [])
                        if table in protected and not (table == PROFILE and columns == ["favourite_club_id"]):
                            blockers.append(f"Geschützter Fremdschlüssel: {table} -> {fk[0]}")
        finally:
            cursor.execute("ROLLBACK")
    # Child tables first. Self/cyclic relations require deferred constraints.
    remaining = set(deleting)
    order = []
    while remaining:
        leaves = sorted(t for t in remaining if not any(
            parent == t and child in remaining and child != parent
            for child, parent in foreign_keys))
        if not leaves:
            order.extend(sorted(remaining))
            break
        order.extend(leaves)
        remaining.difference_update(leaves)
    return {
        "kind": "read_only_reset_preview", "vendor": connection.vendor,
        "scope": "configured_database_not_verified_hetzner", "tables": rows,
        "profile_keep_columns": sorted(KEEP_PROFILE),
        "profile_reset": dict(RESET_PROFILE, updated_at="CURRENT_TIMESTAMP"),
        "delete_order": order,
        "blockers": blockers, "sql_ready": not blockers,
        "warnings": [
            "Keine Freigabe und kein ausgeführter Reset.",
            "Writer vor Live-Vorschau pausieren; neue Änderungen machen den Entwurf ungültig.",
            "Datenbank, Medien, Assets und Dortmund-Geometrie/Design vorher privat sichern.",
            "Keine Pilotdaten oder privaten Dumps als Importpaket übertragen.",
        ],
    }


def render_sql(plan, quote):
    if not plan["sql_ready"]:
        raise CommandError("Kein SQL-Entwurf bei offenen Schutz-/Schemafragen.")
    tables = [r["table"] for r in plan["tables"]]
    lines = [
        "-- ENTWURF: NICHT DURCH REPLIT AUSGEFUEHRT. Nur nach separater Reset-Freigabe.",
        "-- Ausschliesslich public; Writer pausieren; geprüfte private Sicherung erforderlich.",
        "BEGIN;", "SET LOCAL search_path TO public;", "SET LOCAL TIME ZONE 'UTC';",
        "SET CONSTRAINTS ALL DEFERRED;",
        "LOCK TABLE " + ", ".join(quote(t) for t in tables) + " IN ACCESS EXCLUSIVE MODE;",
    ]
    # Bind every row, not only table counts, to the snapshot approved by the operator.
    for row in plan["tables"]:
        count, digest = row["before"]
        query = digest_query(quote, row["table"])
        lines.append(f"DO $$ BEGIN IF (SELECT n <> {count} OR h <> '{digest}' "
                     f"FROM ({query}) snapshot(n,h)) THEN RAISE EXCEPTION "
                     f"'Vorschau veraltet: {row['table']}'; END IF; END $$;")
    assignments = ", ".join(f"{quote(k)} = {v}" for k, v in plan["profile_reset"].items())
    lines.append(f"UPDATE {quote(PROFILE)} SET {assignments};")
    lines.append(f"DELETE FROM {quote(LAND)} WHERE saison IS DISTINCT FROM '0';")
    for table in plan["delete_order"]:
        lines.append(f"DELETE FROM {quote(table)};")
    for row in plan["tables"]:
        action = row["action"]
        if action == "delete":
            lines.append(f"DO $$ BEGIN IF EXISTS (SELECT 1 FROM {quote(row['table'])}) "
                         f"THEN RAISE EXCEPTION 'Nicht leer: {row['table']}'; END IF; END $$;")
            continue
        columns = plan["profile_keep_columns"] if action == "profile_reset" else None
        where = "WHERE saison = '0'" if action == "season_zero_only" else ""
        query = digest_query(quote, row["table"], columns, where)
        count, digest = row["preserved"]
        lines.append(f"DO $$ BEGIN IF (SELECT n <> {count} OR h <> '{digest}' "
                     f"FROM ({query}) snapshot(n,h)) THEN RAISE EXCEPTION "
                     f"'Schutz verletzt: {row['table']}'; END IF; END $$;")
    lines += ["SET CONSTRAINTS ALL IMMEDIATE;", "COMMIT;"]
    return "\n".join(lines) + "\n"
