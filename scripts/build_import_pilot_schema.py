"""N28 T1 only: adopt protected copies via the REAL migration graph.

No package reader, public mutations, scene access, uploader, fake migrations,
worker, or live host. Backups are pilot-owned tables and survive any failure.
"""
import io
import json
import os
import sys
from pathlib import Path

from psycopg2 import sql

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scripts.copy_import_pilot_protected import TABLES, fingerprint, rows

PREFIX = "t1_saved_"
EVIDENCE = ROOT / "docs/import-pilot/t1-schema-evidence.json"


def ident(name):
    return sql.Identifier("import_pilot", name)


def run():
    if not (os.environ.get("REPL_ID") or os.environ.get("REPLIT_DEV_DOMAIN")):
        raise RuntimeError("Replit workspace only.")
    os.environ["DJANGO_SETTINGS_MODULE"] = "import_pilot.settings"
    import django
    django.setup()
    from django.core.management import call_command
    from django.db import connection, transaction
    connection.ensure_connection()
    evidence = {"authorization": "N28–N31", "protected": {}, "phases": []}
    with transaction.atomic(), connection.cursor() as cur:
        identity = rows(cur, "SELECT current_user,session_user,current_schema(),"
                        "current_setting('search_path')")[0]
        if identity != ("import_pilot_role", "import_pilot_role", "import_pilot", "import_pilot"):
            raise RuntimeError("Wrong schema/role.")
        evidence["identity"] = identity
        names = {r[0] for r in rows(cur,
            "SELECT tablename FROM pg_tables WHERE schemaname='import_pilot'")}
        resume = "--resume-restoration" in sys.argv
        if resume:
            evidence = json.loads(EVIDENCE.read_text())
            if {n for n in names if n.startswith(PREFIX)} != {PREFIX + n for n in TABLES}:
                raise RuntimeError("Incomplete protected backups.")
            if not rows(cur, "SELECT 1 FROM django_migrations "
                        "WHERE app='game' AND name='0187_import_rebuild_n28_n31'"):
                raise RuntimeError("Resume requires fully applied schema migration.")
            for name in TABLES:
                expected = evidence["protected"][name]
                if fingerprint(cur, sql.SQL("SELECT * FROM {}").format(ident(PREFIX + name))) != (
                        expected["before_rows"], expected["before_fingerprint"]):
                    raise RuntimeError("Protected backup changed.")
        elif any(name.startswith(PREFIX) for name in names):
            raise RuntimeError("Existing T1 backups: inspect/recover, do not rerun.")
        elif names != set(TABLES) | {"django_session", "django_migrations"}:
            raise RuntimeError("Unexpected initial pilot tables.")
        for name in (() if resume else TABLES):
            columns = [r[0] for r in rows(cur,
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema='import_pilot' AND table_name=%s ORDER BY ordinal_position",
                (name,))]
            count, digest = fingerprint(cur, sql.SQL("SELECT * FROM {}").format(ident(name)))
            evidence["protected"][name] = {"columns": columns, "before_rows": count,
                                          "before_fingerprint": digest}
            owned_sequences = rows(cur,
                "SELECT s.relname FROM pg_class s JOIN pg_namespace n ON n.oid=s.relnamespace "
                "JOIN pg_depend d ON d.objid=s.oid AND d.deptype IN ('a','i') "
                "WHERE n.nspname='import_pilot' AND s.relkind='S' AND d.refobjid=%s::regclass",
                ("import_pilot." + name,))
            indexes = rows(cur,
                "SELECT c.relname,c.oid FROM pg_index i JOIN pg_class c ON c.oid=i.indexrelid "
                "WHERE i.indrelid=%s::regclass", ("import_pilot." + name,))
            for index_name, oid in indexes:
                cur.execute(sql.SQL("ALTER INDEX {} RENAME TO {}").format(
                    ident(index_name), sql.Identifier("t1_saved_ix_" + str(oid))))
            for sequence_name, in owned_sequences:
                cur.execute(sql.SQL("ALTER SEQUENCE {} RENAME TO {}").format(
                    ident(sequence_name), sql.Identifier(PREFIX + sequence_name)))
            cur.execute(sql.SQL("ALTER TABLE {} RENAME TO {}").format(
                ident(name), sql.Identifier(PREFIX + name)))
    if not resume:
        evidence["phases"].append("protected tables/indexes/sequences isolated in pilot")
    EVIDENCE.write_text(json.dumps(evidence, indent=2) + "\n")
    output = io.StringIO()
    try:
        if not resume:
            call_command("migrate", interactive=False, verbosity=1, stdout=output)
    except Exception:
        # Progress only: migration names, never SQL or copied values.
        progress = [line.strip() for line in output.getvalue().splitlines()
                    if "Applying " in line]
        print("Last migration progress: " + (progress[-1] if progress else "none"))
        raise
    evidence["phases"].append("all standard migrations applied, no fake")
    with transaction.atomic(), connection.cursor() as cur:
        cur.execute("SET LOCAL lock_timeout='10s'")
        generated_ct = rows(cur, "SELECT app_label,model FROM django_content_type")
        generated_permissions = rows(cur,
            "SELECT ct.app_label,ct.model,p.codename,p.name FROM auth_permission p "
            "JOIN django_content_type ct ON ct.id=p.content_type_id")
        active = [r[0] for r in rows(cur,
            "SELECT tablename FROM pg_tables WHERE schemaname='import_pilot' "
            "AND tablename NOT LIKE 't1_saved_%%' "
            "AND tablename NOT IN ('django_migrations','django_session') ORDER BY tablename")]
        # One explicit all-target statement; no CASCADE into unrelated schemas.
        cur.execute(sql.SQL("TRUNCATE {} RESTART IDENTITY").format(
            sql.SQL(",").join(ident(name) for name in active)))
        cur.execute("SET CONSTRAINTS ALL DEFERRED")
        for name in TABLES:
            columns = evidence["protected"][name]["columns"]
            projection = sql.SQL(",").join(map(sql.Identifier, columns))
            cur.execute(sql.SQL("INSERT INTO {} ({}) SELECT {} FROM {}").format(
                ident(name), projection, projection, ident(PREFIX + name)))
        # Reset sequences before adding naturally keyed new model metadata.
        for name in active:
            sequences = rows(cur,
                "SELECT s.oid::regclass::text,a.attname FROM pg_class s "
                "JOIN pg_namespace n ON n.oid=s.relnamespace "
                "JOIN pg_depend d ON d.objid=s.oid AND d.deptype IN ('a','i') "
                "JOIN pg_attribute a ON a.attrelid=d.refobjid AND a.attnum=d.refobjsubid "
                "WHERE n.nspname='import_pilot' AND s.relkind='S' AND d.refobjid=%s::regclass",
                ("import_pilot." + name,))
            for sequence, column in sequences:
                cur.execute(sql.SQL("SELECT setval(%s,coalesce(max({}),1),count(*)>0) FROM {}")
                            .format(sql.Identifier(column), ident(name)), (sequence,))
        for app_label, model in generated_ct:
            cur.execute("INSERT INTO django_content_type(app_label,model) VALUES(%s,%s) "
                        "ON CONFLICT(app_label,model) DO NOTHING", (app_label, model))
        for app_label, model, codename, name in generated_permissions:
            cur.execute(
                "INSERT INTO auth_permission(content_type_id,codename,name) "
                "SELECT id,%s,%s FROM django_content_type WHERE app_label=%s AND model=%s "
                "ON CONFLICT(content_type_id,codename) DO NOTHING",
                (codename, name, app_label, model))
        # Explicit natural-key permission remapping, even though preserved IDs
        # currently agree. Never rely on that as the assignment contract.
        for table in ("auth_user_user_permissions", "auth_group_permissions"):
            cur.execute(sql.SQL(
                "UPDATE {} a SET permission_id=np.id FROM {} saved "
                "JOIN {} op ON op.id=saved.permission_id "
                "JOIN {} oct ON oct.id=op.content_type_id "
                "JOIN django_content_type nct ON nct.app_label=oct.app_label AND nct.model=oct.model "
                "JOIN auth_permission np ON np.content_type_id=nct.id AND np.codename=op.codename "
                "WHERE a.id=saved.id").format(
                    ident(table), ident(PREFIX + table), ident(PREFIX + "auth_permission"),
                    ident(PREFIX + "django_content_type")))
        evidence["empty_business_tables"] = {}
        for name in active:
            count = rows(cur, sql.SQL("SELECT count(*) FROM {}").format(ident(name)))[0][0]
            if name not in TABLES:
                if count != 0:
                    raise RuntimeError("Nonempty business table.")
                evidence["empty_business_tables"][name] = count
        for name in TABLES:
            columns = evidence["protected"][name]["columns"]
            projection = sql.SQL(",").join(
                sql.SQL("a.{}").format(sql.Identifier(c)) for c in columns)
            # New ContentTypes/default permissions are allowed additions; old
            # copied rows must remain byte-identical, not just equal in count.
            query = sql.SQL("SELECT {} FROM {} a JOIN {} saved ON a.id=saved.id").format(
                projection, ident(name), ident(PREFIX + name))
            count, digest = fingerprint(cur, query)
            expected = evidence["protected"][name]
            if (count, digest) != (expected["before_rows"], expected["before_fingerprint"]):
                raise RuntimeError("Protected fingerprint mismatch: " + name)
            expected.update(after_original_rows=count, after_fingerprint=digest,
                            total_rows=rows(cur, sql.SQL("SELECT count(*) FROM {}")
                                            .format(ident(name)))[0][0])
        bad_profiles = rows(cur,
            "SELECT count(*) FROM game_managerprofile WHERE level<>1 OR xp<>0 OR xp_max<>800 "
            "OR favourite_club_id IS NOT NULL OR active_title IS NOT NULL")[0][0]
        if bad_profiles:
            raise RuntimeError("N19 profile start values changed.")
        evidence["profile_start_values"] = {"level": 1, "xp": 0, "xp_max": 800,
                                            "invalid_profiles": bad_profiles}
        evidence["permission_assignments"] = {"natural_key_remapped": True,
            "user_assignments": rows(cur, "SELECT count(*) FROM auth_user_user_permissions")[0][0],
            "group_assignments": rows(cur, "SELECT count(*) FROM auth_group_permissions")[0][0]}
        cur.execute("SET CONSTRAINTS ALL IMMEDIATE")
    evidence["phases"].append("seed rows removed and all protected originals restored/verified")
    # Backups survive through schema/evidence verification. Removed separately
    # only after this script's results and public comparison have been checked.
    evidence["backups_retained_until_verification"] = True
    evidence["migrations"] = rows(connection.cursor(),
        "SELECT app,name FROM django_migrations ORDER BY app,name")
    EVIDENCE.write_text(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps({"status": "T1 schema built",
                      "business_tables_zero": len(evidence["empty_business_tables"]),
                      "protected_tables_verified": len(TABLES),
                      "migration": "game/0187_import_rebuild_n28_n31"}))


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:
        print("T1 stopped safely: " + type(exc).__name__, file=sys.stderr)
        # No SQL/connection details/copied row values in logs.
        import traceback
        for frame in traceback.extract_tb(exc.__traceback__):
            if frame.filename == __file__:
                print("T1 location: " + str(frame.lineno), file=sys.stderr)
        sys.exit(1)
