"""N22 protected copy only; no business models, migrations or game imports.

Source: local workspace database, one read-only REPEATABLE READ transaction.
Target: guarded direct pilot connection, one atomic transaction, empty-target gate.
Sensitive rows pass only through an in-memory COPY buffer; never log their values.
"""
import hashlib
import io
import json
import os
import sys
import traceback
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

import psycopg2
from psycopg2 import sql

ROOT = Path(__file__).resolve().parent.parent
PARAMETERS = (
    "game_economyparameter", "game_countrynetwork", "game_stadionumfeldconfig",
    "game_datasource", "game_strengthformulasettings", "game_strengthmodifierrule",
    "game_mediaoutlet", "showauction_showauctionpreset", "game_storysettings",
    "game_neutralvenue", "game_landkoeffizient",
)
TABLES = (
    "django_content_type", "auth_permission", "auth_user", "auth_group",
    "auth_user_groups", "auth_user_user_permissions", "auth_group_permissions",
    "game_managerprofile", "game_referee", "game_sponsor",
) + PARAMETERS
KEEP_PROFILE = {
    "id", "user_id", "name", "trainer_type", "nationality_flag", "nationality_name",
    "member_since", "birth_date", "profile_image", "name_confirmed", "residence",
    "visibility_settings",
}
RESET_PROFILE = {
    "level": "1", "xp": "0", "xp_max": "800", "highscore": "'–'",
    "active_title": "NULL", "title_progress": "'{}'::jsonb",
    "season_score": "0", "previous_season_score": "0",
    "inactivity_season_count": "0", "inactivity_streak": "0",
    "transfer_ban_until": "NULL", "login_streak": "0", "login_points_today": "0",
    "login_last_date": "NULL", "login_day14_awarded": "false",
    "login_day30_awarded": "false", "login_day30_money_paid": "false",
    "last_seen": "NULL", "favourite_club_id": "NULL",
}
METADATA_QUERIES = {
    "schema_acl": "SELECT nspname,nspowner,nspacl::text FROM pg_namespace WHERE nspname='public'",
    "object_acls": "SELECT c.relname,c.relowner,c.relacl::text FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' ORDER BY c.relname",
    "roles": "SELECT rolname,rolsuper,rolinherit,rolcreaterole,rolcreatedb,rolcanlogin,rolreplication,rolbypassrls,rolconfig FROM pg_roles ORDER BY rolname",
    "constraints": "SELECT oid,pg_get_constraintdef(oid) FROM pg_constraint WHERE connamespace='public'::regnamespace ORDER BY oid",
}
CT_QUERY = sql.SQL(
    "SELECT row_number() OVER(ORDER BY app_label,model)::integer AS id,"
    "app_label,model FROM public.django_content_type"
)
PERMISSION_QUERY = sql.SQL(
    "SELECT row_number() OVER(ORDER BY ct.app_label,ct.model,p.codename)::integer AS id,"
    "p.name,nct.id AS content_type_id,p.codename FROM public.auth_permission p "
    "JOIN public.django_content_type ct ON ct.id=p.content_type_id "
    "JOIN ({ct}) nct ON nct.app_label=ct.app_label AND nct.model=ct.model"
).format(ct=CT_QUERY)


def rows(cursor, query, params=None):
    cursor.execute(query, params)
    return cursor.fetchall()


def fingerprint(cursor, selection):
    cursor.execute(sql.SQL(
        "SELECT count(*),md5(coalesce(string_agg(digest,'' ORDER BY digest),'')) "
        "FROM (SELECT md5(row_to_json(t)::text) digest FROM ({}) t) s"
    ).format(selection))
    return cursor.fetchone()


def source_state(cursor):
    names = [r[0] for r in rows(cursor,
        "SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE n.nspname='public' AND c.relkind IN ('r','p') ORDER BY c.relname")]
    state = {
        "tables": {name: fingerprint(cursor, sql.SQL("SELECT * FROM public.{}").format(
            sql.Identifier(name))) for name in names},
        "metadata": {key: rows(cursor, query) for key, query in METADATA_QUERIES.items()},
    }
    sequence_names = rows(cursor,
        "SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE n.nspname='public' AND c.relkind='S' ORDER BY c.relname")
    state["sequences"] = {name: rows(cursor, sql.SQL(
        "SELECT last_value,is_called FROM public.{}").format(sql.Identifier(name)))
        for (name,) in sequence_names}
    return state


def existing_files():
    result = {}
    for directory in ("core", "game", "showauction", "stadium_editor"):
        for path in (ROOT / directory).rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts:
                result[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    for name in ("manage.py", ".replit"):
        path = ROOT / name
        if path.exists():
            result[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def existing_processes():
    result = {}
    for path in Path("/proc").iterdir():
        if path.name.isdigit():
            try:
                command = (path / "cmdline").read_bytes()
                if b"manage.py" in command and b"runserver" in command:
                    result[int(path.name)] = hashlib.sha256(command).hexdigest()
            except OSError:
                pass
    if not result:
        raise RuntimeError("Existing application server is not running.")
    return result


def selection(name, columns, stamp):
    expressions = []
    for column in columns:
        expression = sql.Identifier("s", column)
        if name == "game_managerprofile" and column in RESET_PROFILE:
            expression = sql.SQL(RESET_PROFILE[column])
        elif name == "game_managerprofile" and column == "updated_at":
            expression = sql.Literal(stamp)
        elif name in {"auth_user_user_permissions", "auth_group_permissions"} and column == "permission_id":
            expression = sql.Identifier("np", "id")
        expressions.append(sql.SQL("{} AS {}").format(expression, sql.Identifier(column)))
    base = sql.SQL("public.{}").format(sql.Identifier(name))
    suffix = sql.SQL("")
    if name == "django_content_type":
        base = sql.SQL("({})").format(CT_QUERY)
    elif name == "auth_permission":
        base = sql.SQL("({})").format(PERMISSION_QUERY)
    elif name in {"auth_user_user_permissions", "auth_group_permissions"}:
        suffix = sql.SQL(
            " JOIN public.auth_permission op ON op.id=s.permission_id"
            " JOIN public.django_content_type oct ON oct.id=op.content_type_id"
            " JOIN ({ct}) nct ON nct.app_label=oct.app_label AND nct.model=oct.model"
            " JOIN ({perm}) np ON np.content_type_id=nct.id AND np.codename=op.codename"
        ).format(ct=CT_QUERY, perm=PERMISSION_QUERY)
    elif name == "game_landkoeffizient":
        suffix = sql.SQL(" WHERE s.saison='0'")
    return sql.SQL("SELECT {} FROM {} s{}").format(
        sql.SQL(",").join(expressions), base, suffix)


def copy_protected():
    if not (os.environ.get("REPL_ID") or os.environ.get("REPLIT_DEV_DOMAIN")):
        raise RuntimeError("Workspace only.")
    if os.environ.get("DJANGO_SETTINGS_MODULE", "import_pilot.settings") != "import_pilot.settings":
        raise RuntimeError("Existing application settings are forbidden.")
    sys.path.insert(0, str(ROOT))
    os.environ["DJANGO_SETTINGS_MODULE"] = "import_pilot.settings"
    import django
    django.setup()
    from django.apps import apps
    from django.db import connection, transaction

    files_before = existing_files()
    processes_before = existing_processes()
    evidence = {"authorization": "N18–N22 + explicit permission-metadata approval",
                "started_at": datetime.now(timezone.utc).isoformat(), "tables": {}}
    with closing(psycopg2.connect(os.environ["DATABASE_URL"])) as source, source:
        source.set_session(readonly=True, isolation_level="REPEATABLE READ")
        with source.cursor() as read:
            assert rows(read, "SELECT inet_server_addr() IS NULL OR inet_server_addr() "
                        "IN ('127.0.0.1'::inet,'::1'::inet)")[0][0], "Non-local source."
            evidence["snapshot"], stamp = rows(read,
                "SELECT pg_current_snapshot()::text,transaction_timestamp()")[0]
            evidence["source_snapshot_at"] = stamp.isoformat()
            source_before = source_state(read)
            assert not rows(read, "SELECT p.id FROM public.game_managerprofile p "
                "LEFT JOIN public.auth_user u ON u.id=p.user_id WHERE u.id IS NULL"), "Orphan profiles."
            columns = {name: [r[0] for r in rows(read,
                "SELECT column_name FROM information_schema.columns WHERE table_schema='public' "
                "AND table_name=%s ORDER BY ordinal_position", (name,))] for name in TABLES}
            assert all(columns.values()), "Missing protected source table."
            definitions = {}
            extra_indexes = {}
            for name in TABLES:
                attributes = rows(read,
                    "SELECT a.attname,format_type(a.atttypid,a.atttypmod),a.attnotnull,a.attidentity "
                    "FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid "
                    "JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' "
                    "AND c.relname=%s AND a.attnum>0 AND NOT a.attisdropped ORDER BY a.attnum",
                    (name,))
                parts = []
                for column, datatype, not_null, identity in attributes:
                    assert "public." not in datatype, "Source-specific type."
                    parts.append(sql.SQL("{} {}{}{}").format(
                        sql.Identifier(column), sql.SQL(datatype),
                        sql.SQL(" GENERATED BY DEFAULT AS IDENTITY" if identity else ""),
                        sql.SQL(" NOT NULL" if not_null else "")))
                constraints = rows(read,
                    "SELECT con.conname,pg_get_constraintdef(con.oid) FROM pg_constraint con "
                    "JOIN pg_class c ON c.oid=con.conrelid JOIN pg_namespace n ON n.oid=c.relnamespace "
                    "WHERE n.nspname='public' AND c.relname=%s AND con.contype IN ('p','u','c')",
                    (name,))
                for constraint, definition in constraints:
                    assert "public." not in definition, "Source-specific constraint."
                    parts.append(sql.SQL("CONSTRAINT {} {}").format(
                        sql.Identifier(constraint), sql.SQL(definition)))
                definitions[name] = sql.SQL(",").join(parts)
                extra_indexes[name] = rows(read,
                    "SELECT pg_get_indexdef(i.indexrelid) FROM pg_index i "
                    "JOIN pg_class c ON c.oid=i.indrelid JOIN pg_namespace n ON n.oid=c.relnamespace "
                    "WHERE n.nspname='public' AND c.relname=%s AND NOT EXISTS "
                    "(SELECT 1 FROM pg_constraint con WHERE con.conindid=i.indexrelid)",
                    (name,))
            assert set(columns["game_managerprofile"]) == KEEP_PROFILE | set(RESET_PROFILE) | {"updated_at"}
            content_types = rows(read, "SELECT app_label,model FROM public.django_content_type")
            loaded = {(model._meta.app_label, model._meta.model_name) for model in apps.get_models()}
            missing = [key for key in content_types if key not in loaded]
            evidence["permissions"] = {
                "metadata_only": True, "missing_model_content_types": len(missing),
                "missing_model_permissions": rows(read,
                    "SELECT count(*) FROM public.auth_permission p JOIN public.django_content_type c "
                    "ON c.id=p.content_type_id WHERE NOT (c.app_label='sessions' AND c.model='session')")[0][0],
                "content_type_ids_remapped": rows(read, sql.SQL(
                    "SELECT count(*) FROM public.django_content_type s JOIN ({}) t "
                    "USING(app_label,model) WHERE s.id<>t.id").format(CT_QUERY))[0][0],
                "permission_ids_remapped": rows(read, sql.SQL(
                    "SELECT count(*) FROM public.auth_permission s "
                    "JOIN public.django_content_type c ON c.id=s.content_type_id "
                    "JOIN ({ct}) tc USING(app_label,model) JOIN ({p}) t "
                    "ON t.content_type_id=tc.id AND t.codename=s.codename WHERE s.id<>t.id"
                ).format(ct=CT_QUERY, p=PERMISSION_QUERY))[0][0],
            }
            with transaction.atomic(), connection.cursor() as write:
                write.execute("SET LOCAL lock_timeout='3s'")
                write.execute("SET LOCAL statement_timeout='60s'")
                evidence["pilot_identity"] = rows(write,
                    "SELECT current_user,session_user,current_setting('search_path'),current_schema()")[0]
                assert evidence["pilot_identity"] == (
                    "import_pilot_role", "import_pilot_role", "import_pilot", "import_pilot")
                existing = {r[0] for r in rows(write,
                    "SELECT table_name FROM information_schema.tables WHERE table_schema='import_pilot'")}
                assert existing == {"django_session", "django_migrations"}, "Pilot target is not technical-only."
                assert rows(write, "SELECT count(*) FROM import_pilot.django_session")[0][0] == 0
                migration_before = fingerprint(write, sql.SQL("SELECT * FROM import_pilot.django_migrations"))
                for name in TABLES:
                    # DDL is rebuilt from read-only catalog metadata. LIKE public.*
                    # needs source SELECT, which this role deliberately does not have.
                    # Do not weaken isolation by granting it. No source defaults/FKs/triggers.
                    write.execute(sql.SQL(
                        "CREATE TABLE import_pilot.{} ({})"
                    ).format(sql.Identifier(name), definitions[name]))
                    for index_number, (definition,) in enumerate(extra_indexes[name]):
                        _, separator, tail = definition.partition(" USING ")
                        assert separator and "public." not in tail, "Source-specific index."
                        write.execute(sql.SQL("CREATE INDEX {} ON import_pilot.{} USING {}").format(
                            sql.Identifier(name + "_pilot_ix_" + str(index_number)),
                            sql.Identifier(name), sql.SQL(tail)))
                    selected = selection(name, columns[name], stamp)
                    expected = fingerprint(read, selected)
                    with io.StringIO() as buffer:
                        read.copy_expert(sql.SQL("COPY ({}) TO STDOUT").format(
                            selected).as_string(read), buffer)
                        buffer.seek(0)
                        write.copy_expert(sql.SQL("COPY import_pilot.{} ({}) FROM STDIN").format(
                            sql.Identifier(name), sql.SQL(",").join(map(sql.Identifier, columns[name]))
                        ).as_string(write.cursor), buffer)
                    actual = fingerprint(write, sql.SQL("SELECT {} FROM import_pilot.{}").format(
                        sql.SQL(",").join(map(sql.Identifier, columns[name])), sql.Identifier(name)))
                    assert actual == expected, "Copied content mismatch."
                    # Never silently lose permission assignments through inner joins.
                    if name != "game_landkoeffizient":
                        assert expected[0] == source_before["tables"][name][0]
                    evidence["tables"][name] = {
                        "source_total": source_before["tables"][name][0],
                        "copied": actual[0], "expected_content_equal": actual == expected,
                        "mode": "profile-reset" if name == "game_managerprofile" else
                                "natural-key-metadata" if name in {
                                    "django_content_type", "auth_permission",
                                    "auth_user_user_permissions", "auth_group_permissions"} else
                                "saison-0-only" if name == "game_landkoeffizient" else "full",
                    }
                    identities = rows(read,
                        "SELECT a.attname FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid "
                        "JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' "
                        "AND c.relname=%s AND a.attidentity<>'' AND NOT a.attisdropped", (name,))
                    for (column,) in identities:
                        write.execute(sql.SQL(
                            "SELECT setval(pg_get_serial_sequence(%s,%s),"
                            "coalesce(max({}),1),max({}) IS NOT NULL) FROM import_pilot.{}"
                        ).format(sql.Identifier(column), sql.Identifier(column), sql.Identifier(name)),
                            ("import_pilot." + name, column))
                fks = rows(read,
                    "SELECT s.relname,con.conname,d.relname,"
                    "ARRAY(SELECT attname FROM pg_attribute WHERE attrelid=s.oid "
                    "AND attnum=ANY(con.conkey) ORDER BY array_position(con.conkey,attnum)),"
                    "ARRAY(SELECT attname FROM pg_attribute WHERE attrelid=d.oid "
                    "AND attnum=ANY(con.confkey) ORDER BY array_position(con.confkey,attnum)) "
                    "FROM pg_constraint con JOIN pg_class s ON s.oid=con.conrelid "
                    "JOIN pg_class d ON d.oid=con.confrelid JOIN pg_namespace n ON n.oid=s.relnamespace "
                    "WHERE con.contype='f' AND n.nspname='public' AND s.relname=ANY(%s)",
                    (list(TABLES),))
                for table, constraint, target, local_columns, remote_columns in fks:
                    if target not in TABLES:
                        assert table == "game_managerprofile" and local_columns == ["favourite_club_id"]
                        continue
                    write.execute(sql.SQL(
                        "ALTER TABLE import_pilot.{} ADD CONSTRAINT {} FOREIGN KEY ({}) "
                        "REFERENCES import_pilot.{} ({}) DEFERRABLE INITIALLY DEFERRED"
                    ).format(sql.Identifier(table), sql.Identifier(constraint),
                             sql.SQL(",").join(map(sql.Identifier, local_columns)),
                             sql.Identifier(target), sql.SQL(",").join(map(sql.Identifier, remote_columns))))
                write.execute("ALTER TABLE import_pilot.game_managerprofile ADD CONSTRAINT "
                              "pilot_no_legacy_favourite_club CHECK (favourite_club_id IS NULL)")
                write.execute("SET CONSTRAINTS ALL IMMEDIATE")
                evidence["cross_schema_fks"] = rows(write,
                    "SELECT con.conname FROM pg_constraint con "
                    "JOIN pg_class s ON s.oid=con.conrelid JOIN pg_namespace sn ON sn.oid=s.relnamespace "
                    "JOIN pg_class d ON d.oid=con.confrelid JOIN pg_namespace dn ON dn.oid=d.relnamespace "
                    "WHERE con.contype='f' AND sn.nspname='import_pilot' AND dn.nspname<>'import_pilot'")
                assert not evidence["cross_schema_fks"]
                evidence["sequence_references_to_public"] = rows(write,
                    "SELECT table_name,column_name FROM information_schema.columns "
                    "WHERE table_schema='import_pilot' AND column_default LIKE '%%public.%%'")
                assert not evidence["sequence_references_to_public"]
                assert fingerprint(write, sql.SQL("SELECT * FROM import_pilot.django_migrations")) == migration_before
                evidence["migrations_unchanged"] = True
                evidence["installed_apps"] = list(apps.app_configs)
                assert not any(name in sys.modules for name in ("game", "core", "showauction", "stadium_editor"))
                evidence["no_game_imports"] = True
            evidence["copy_committed_at"] = datetime.now(timezone.utc).isoformat()
    # Fresh source transaction: detect activity rather than confuse repeatable reads with proof.
    with closing(psycopg2.connect(os.environ["DATABASE_URL"])) as source, source:
        source.set_session(readonly=True, isolation_level="REPEATABLE READ")
        with source.cursor() as read:
            source_after = source_state(read)
    evidence["source_verification"] = {
        "table_count": len(source_before["tables"]),
        "changed_tables": [name for name, value in source_before["tables"].items()
                           if source_after["tables"].get(name) != value],
        "metadata_unchanged": source_before["metadata"] == source_after["metadata"],
        "sequences_unchanged": source_before["sequences"] == source_after["sequences"],
        "files_unchanged": files_before == existing_files(),
        "processes_unchanged": processes_before == existing_processes(),
    }
    # Reconnect invokes the full database role/public-write guard again after copying.
    connection.close()
    connection.ensure_connection()
    with connection.cursor() as verify:
        evidence["committed_row_counts"] = {
            name: rows(verify, sql.SQL("SELECT count(*) FROM import_pilot.{}").format(
                sql.Identifier(name)))[0][0] for name in TABLES}
        evidence["pilot_sessions"] = rows(verify, "SELECT count(*) FROM import_pilot.django_session")[0][0]
    assert all(evidence["committed_row_counts"][name] == item["copied"]
               for name, item in evidence["tables"].items())
    evidence["post_copy_role_guard_passed"] = True
    connection.close()
    destination = ROOT / "docs/import-pilot/copy-evidence.json"
    destination.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(evidence, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    try:
        copy_protected()
    except Exception as error:
        # No SQL, connection parameters, account data or exception detail in logs.
        print(f"Protected copy stopped ({type(error).__name__}).", file=sys.stderr)
        for frame in traceback.extract_tb(error.__traceback__):
            if Path(frame.filename).resolve() == Path(__file__).resolve():
                print(f"Copy location: line {frame.lineno} in {frame.name}", file=sys.stderr)
        sys.exit(1)
