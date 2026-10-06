"""N33 read-only comparison of OLD column values across additive migrations.

Exports only column names/counts/digests, never row values or credentials.
The accepted normal last_seen activity is excluded, not other profile fields.
"""
import json
import os
import sys
from pathlib import Path

import psycopg2
from psycopg2 import sql

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scripts.copy_import_pilot_protected import fingerprint


def capture(previous=None):
    result = {}
    with psycopg2.connect(os.environ["DATABASE_URL"]) as connection:
        connection.set_session(readonly=True, isolation_level="REPEATABLE READ")
        with connection.cursor() as cursor:
            cursor.execute("SELECT inet_server_addr() IS NULL OR inet_server_addr() "
                           "IN ('127.0.0.1'::inet,'::1'::inet)")
            if not cursor.fetchone()[0]:
                raise RuntimeError("Only local Replit public auditing is authorized.")
            if previous is None:
                cursor.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' "
                               "ORDER BY tablename")
                tables = [row[0] for row in cursor.fetchall()]
            else:
                tables = previous
            for table in tables:
                if previous is None:
                    cursor.execute("SELECT column_name FROM information_schema.columns "
                                   "WHERE table_schema='public' AND table_name=%s "
                                   "ORDER BY ordinal_position", (table,))
                    columns = [row[0] for row in cursor.fetchall()]
                    if table == "game_managerprofile":
                        columns.remove("last_seen")
                    cursor.execute(sql.SQL("SELECT max(id) FROM public.{}").format(
                        sql.Identifier(table))) if "id" in columns else None
                    old_max = cursor.fetchone()[0] if "id" in columns else None
                else:
                    columns = previous[table]["columns"]
                    old_max = previous[table]["old_max_id"]
                query = sql.SQL("SELECT {} FROM public.{}").format(
                    sql.SQL(",").join(map(sql.Identifier, columns)), sql.Identifier(table))
                # New standard model metadata/migration rows are authorized by N33.
                if table in ("auth_permission", "django_content_type", "django_migrations"):
                    query += (sql.SQL(" WHERE id <= {}").format(sql.Literal(old_max))
                              if old_max is not None else sql.SQL(" WHERE FALSE"))
                count, digest = fingerprint(cursor, query)
                result[table] = {"columns": columns, "old_max_id": old_max,
                                 "rows": count, "digest": digest}
    return result


if __name__ == "__main__":
    destination = Path(sys.argv[1])
    if "--compare" in sys.argv:
        baseline = json.loads(destination.read_text())
        after = capture(baseline)
        changed = [table for table in baseline if baseline[table] != after[table]]
        result = {"old_tables": len(baseline), "changed_tables": changed,
                  "excluded_activity_column": "game_managerprofile.last_seen"}
        destination.with_name("n33-public-comparison.json").write_text(
            json.dumps(result, indent=2) + "\n")
        print(json.dumps(result))
    else:
        before = capture()
        destination.write_text(json.dumps(before, indent=2) + "\n")
        print(json.dumps({"baseline_old_tables": len(before)}))
