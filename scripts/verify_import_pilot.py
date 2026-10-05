"""Verify the technical pilot without writing to public or copying source rows.

Usage: python scripts/verify_import_pilot.py /tmp/import_pilot_baseline.json
The baseline contains only metadata, row counts and database-side fingerprints.
"""
import hashlib
import json
import os
import subprocess
import sys
import traceback
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

import psycopg2
from psycopg2 import sql

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def query(cursor, statement, params=None):
    cursor.execute(statement, params)
    return cursor.fetchall()


def source_fingerprints(names):
    fingerprints = {}
    with closing(psycopg2.connect(os.environ["DATABASE_URL"])) as maintenance, maintenance:
        maintenance.set_session(readonly=True, isolation_level="REPEATABLE READ")
        with maintenance.cursor() as cursor:
            for name in names:
                cursor.execute(
                    sql.SQL(
                        "SELECT count(*),md5(coalesce(string_agg(digest,'' ORDER BY digest),'')) "
                        "FROM (SELECT md5(row_to_json(t)::text) AS digest FROM public.{} t) s"
                    ).format(sql.Identifier(name))
                )
                count, digest = cursor.fetchone()
                fingerprints[name] = {"count": count, "digest": digest}
    return fingerprints


def negative_start(change):
    program = """
import json, sys
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
""" + change + """
import django
try:
    django.setup()
except ImproperlyConfigured as error:
    print(json.dumps({'rejected': True, 'reason': str(error)}))
except Exception as error:
    print(json.dumps({'rejected': False, 'error_type': type(error).__name__}))
    sys.exit(2)
else:
    print(json.dumps({'rejected': False}))
    sys.exit(1)
"""
    result = subprocess.run(
        [sys.executable, "-c", program],
        cwd=ROOT, env=dict(os.environ, DJANGO_SETTINGS_MODULE="import_pilot.settings"),
        capture_output=True, text=True, timeout=20,
    )
    if result.returncode != 0:
        raise RuntimeError("Negative startup check did not reject as expected.")
    return json.loads(result.stdout)


def verify(baseline_path):
    baseline = json.loads(Path(baseline_path).read_text())
    verification_before = source_fingerprints(baseline["tables"])
    os.environ["DJANGO_SETTINGS_MODULE"] = "import_pilot.settings"
    import django
    django.setup()
    from django.conf import settings
    from django.contrib.sessions.backends.db import SessionStore
    from django.core.files.base import ContentFile
    from django.core.files.storage import storages
    from django.core.cache import cache
    from django.db import connection
    from django.test import Client

    evidence = {"at": datetime.now(timezone.utc).isoformat()}
    with connection.cursor() as cursor:
        evidence["pilot_identity"] = query(
            cursor, "SELECT current_database(),current_user,session_user,"
            "current_setting('search_path'),current_schema()"
        )[0]
        evidence["role_attributes"] = query(
            cursor,
            "SELECT rolcanlogin,rolsuper,rolcreaterole,rolcreatedb,rolreplication,"
            "rolbypassrls,rolinherit,rolconfig FROM pg_roles WHERE rolname=current_user",
        )[0]
        evidence["role_memberships"] = query(
            cursor,
            "SELECT parent.rolname FROM pg_auth_members m "
            "JOIN pg_roles child ON child.oid=m.member "
            "JOIN pg_roles parent ON parent.oid=m.roleid WHERE child.rolname=current_user",
        )
        evidence["public_schema_create"] = query(
            cursor, "SELECT has_schema_privilege(current_user,'public','CREATE')"
        )[0][0]
        evidence["public_table_write_grants"] = query(
            cursor,
            """SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname='public' AND c.relkind IN ('r','p','v','m','f')
            AND has_table_privilege(current_user,c.oid,
                                   'INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')""",
        )
        evidence["public_column_write_grants"] = query(
            cursor,
            """SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname='public' AND c.relkind IN ('r','p','v','f')
            AND has_any_column_privilege(current_user,c.oid,'INSERT,UPDATE,REFERENCES')""",
        )
        evidence["public_sequence_write_grants"] = query(
            cursor,
            """SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname='public' AND c.relkind='S'
            AND has_sequence_privilege(current_user,c.oid,'USAGE,UPDATE')""",
        )
        evidence["public_executable_definers"] = query(
            cursor,
            """SELECT p.proname FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
            WHERE n.nspname='public' AND p.prosecdef
            AND has_function_privilege(current_user,p.oid,'EXECUTE')""",
        )
        evidence["pilot_schema"] = query(
            cursor,
            "SELECT n.nspname,pg_get_userbyid(n.nspowner),n.nspacl::text "
            "FROM pg_namespace n WHERE n.nspname='import_pilot'",
        )[0]
        names = query(
            cursor,
            "SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname='import_pilot' AND c.relkind IN ('r','p') ORDER BY c.relname",
        )
        assert {name for (name,) in names} == {"django_migrations", "django_session"}
        evidence["pilot_tables"] = {}
        for (name,) in names:
            cursor.execute(
                sql.SQL("SELECT count(*) FROM import_pilot.{}").format(sql.Identifier(name))
            )
            evidence["pilot_tables"][name] = cursor.fetchone()[0]
        evidence["pilot_migrations"] = query(
            cursor, "SELECT app,name FROM import_pilot.django_migrations ORDER BY app,name"
        )
        evidence["cross_schema_fks"] = query(
            cursor,
            """SELECT con.conname,dn.nspname FROM pg_constraint con
            JOIN pg_class src ON src.oid=con.conrelid
            JOIN pg_namespace sn ON sn.oid=src.relnamespace
            JOIN pg_class dst ON dst.oid=con.confrelid
            JOIN pg_namespace dn ON dn.oid=dst.relnamespace
            WHERE con.contype='f' AND sn.nspname='import_pilot'
            AND dn.nspname<>'import_pilot'""",
        )
    assert not evidence["public_schema_create"]
    for key in (
        "role_memberships", "public_table_write_grants", "public_column_write_grants",
        "public_sequence_write_grants", "public_executable_definers", "cross_schema_fks",
    ):
        assert not evidence[key], key
    assert evidence["pilot_tables"] == {"django_migrations": 1, "django_session": 0}

    # Only a synthetic pilot session; cleanup is mandatory even on a failed test.
    session = SessionStore()
    try:
        session["isolation_probe"] = True
        session.save()
        assert SessionStore(session_key=session.session_key).get("isolation_probe") is True
        evidence["pilot_session_roundtrip"] = True
    finally:
        if session.session_key:
            session.delete()

    filename = None
    try:
        filename = storages["default"].save("isolation-probe.txt", ContentFile(b"pilot probe"))
        resolved = Path(storages["default"].path(filename)).resolve()
        assert resolved.is_relative_to(settings.MEDIA_ROOT.resolve())
        assert not resolved.is_relative_to(Path(settings.ORIGINAL_ASSETS_ROOT).resolve())
        with storages["default"].open(filename) as uploaded:
            assert uploaded.read() == b"pilot probe"
        evidence["isolated_upload_roundtrip"] = True
    finally:
        if filename:
            storages["default"].delete(filename)

    reader = storages["original_assets"]
    image = next(Path(settings.ORIGINAL_ASSETS_ROOT).rglob("*.png"), None)
    assert image is not None, "No original image available for the read-only probe."
    name = str(image.relative_to(settings.ORIGINAL_ASSETS_ROOT))
    with reader.open(name, "rb") as asset:
        assert asset.read(8), "Original asset is empty."
    for operation in (
        lambda: reader.save("isolation-probe.txt", ContentFile(b"forbidden")),
        lambda: reader.delete(name),
        lambda: reader.open(name, "wb"),
    ):
        try:
            operation()
        except PermissionError:
            continue
        raise RuntimeError("Original asset storage allowed a write operation.")
    evidence["original_assets_read_only_storage"] = True
    evidence["uploads_remaining"] = len(list(settings.MEDIA_ROOT.rglob("*")))
    assert evidence["uploads_remaining"] == 0

    cache.set("isolation-probe", True, 30)
    try:
        assert cache.get("isolation-probe") is True
        evidence["pilot_cache"] = {
            "backend": settings.CACHES["default"]["BACKEND"],
            "location": settings.CACHES["default"]["LOCATION"],
            "prefix": settings.CACHES["default"]["KEY_PREFIX"],
        }
    finally:
        cache.delete("isolation-probe")
    evidence["cookies"] = {
        "session": settings.SESSION_COOKIE_NAME,
        "csrf": settings.CSRF_COOKIE_NAME,
        "csrf_uses_pilot_session": settings.CSRF_USE_SESSIONS,
        "signing_domain_separated_from_input":
            settings.SECRET_KEY != os.environ["PILOT_SECRET_KEY"],
        "key_fallbacks": len(settings.SECRET_KEY_FALLBACKS),
    }
    evidence["installed_apps"] = settings.INSTALLED_APPS
    evidence["prohibited_imports"] = [
        name for name in ("core", "game", "showauction", "stadium_editor", "celery")
        if name in sys.modules
    ]
    assert not evidence["prohibited_imports"]
    evidence["schedule_empty"] = not settings.CELERY_BEAT_SCHEDULE
    evidence["broker"] = settings.CELERY_BROKER_URL
    response = Client().get("/health/", HTTP_HOST="localhost")
    assert response.status_code == 200
    evidence["pilot_health"] = response.json()
    with connection.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM import_pilot.django_session")
        evidence["pilot_sessions_after_cleanup"] = cursor.fetchone()[0]
        assert evidence["pilot_sessions_after_cleanup"] == 0
    connection.close()

    evidence["negative_start"] = {
        "public_fallback": negative_start(
            "settings.DATABASES['default']['OPTIONS']['options']='-c search_path=import_pilot,public'\n"
        ),
        "user_fallback": negative_start(
            """settings.DATABASES['default']['OPTIONS']['options']='-c search_path="$user",import_pilot'\n"""
        ),
        # The local cluster's standard postgres database has no pilot schema.
        # Read-only metadata check there; no schema is renamed or dropped.
        "missing_schema": negative_start(
            "settings.DATABASES['default']['NAME']='postgres'\n"
        ),
        "maintenance_identity": negative_start(
            "import dj_database_url, os\n"
            "maintenance=dj_database_url.parse(os.environ['DATABASE_URL'])\n"
            "settings.DATABASES['default']['USER']=maintenance['USER']\n"
            "settings.DATABASES['default']['PASSWORD']=maintenance['PASSWORD']\n"
        ),
    }

    # Maintenance is used only for read-only before/after checks on the source.
    with closing(psycopg2.connect(os.environ["DATABASE_URL"])) as maintenance, maintenance:
        maintenance.set_session(readonly=True, isolation_level="REPEATABLE READ")
        with maintenance.cursor() as cursor:
            current = {}
            for name in baseline["tables"]:
                cursor.execute(
                    sql.SQL(
                        "SELECT count(*),md5(coalesce(string_agg(digest,'' ORDER BY digest),'')) "
                        "FROM (SELECT md5(row_to_json(t)::text) AS digest FROM public.{} t) s"
                    ).format(sql.Identifier(name))
                )
                count, digest = cursor.fetchone()
                current[name] = {"count": count, "digest": digest}
            evidence["public_table_count"] = len(current)
            evidence["public_changed_tables"] = [
                name for name in current if current[name] != baseline["tables"][name]
            ]
            evidence["initial_baseline_at"] = baseline["at"]
            evidence["public_differences_since_initial_baseline"] = {
                name: {
                    "before_count": baseline["tables"][name]["count"],
                    "after_count": current[name]["count"],
                    "content_fingerprint_equal":
                        baseline["tables"][name]["digest"] == current[name]["digest"],
                }
                for name in evidence["public_changed_tables"]
            }
            evidence["public_changed_tables_during_verification"] = [
                name for name in current if current[name] != verification_before[name]
            ]
            evidence["public_row_counts_unchanged"] = all(
                current[name]["count"] == baseline["tables"][name]["count"]
                for name in current
            )
            evidence["public_counts"] = {name: value["count"] for name, value in current.items()}
            comparisons = {
                "schema_acl": "SELECT n.nspname,n.nspowner,n.nspacl::text FROM pg_namespace n WHERE n.nspname='public'",
                "object_acls": "SELECT c.relname,c.relowner,c.relacl::text FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' ORDER BY c.relname",
                "roles": "SELECT rolname,rolsuper,rolinherit,rolcreaterole,rolcreatedb,rolcanlogin,rolreplication,rolbypassrls,rolconfig FROM pg_roles WHERE rolname<>'import_pilot_role' ORDER BY rolname",
                "constraints": "SELECT oid,pg_get_constraintdef(oid) FROM pg_constraint WHERE connamespace='public'::regnamespace ORDER BY oid",
            }
            evidence["unchanged_source_metadata"] = {
                key: json.loads(json.dumps(query(cursor, statement))) == baseline[key]
                for key, statement in comparisons.items()
            }
            evidence["existing_identity"] = query(
                cursor, "SELECT current_user,session_user,current_setting('search_path')"
            )[0]
            cursor.execute("SELECT count(*) FROM public.game_landkoeffizient WHERE saison='0'")
            evidence["landkoeffizient_saison_0"] = cursor.fetchone()[0]
    evidence["unchanged_source_files"] = {
        name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest
        for name, digest in baseline["files"].items()
    }
    evidence["existing_processes"] = baseline["processes"]
    evidence["existing_processes_still_running"] = all(
        Path(f"/proc/{process['pid']}").exists() for process in baseline["processes"]
    )
    job_processes = []
    for process in Path("/proc").iterdir():
        if not process.name.isdigit():
            continue
        try:
            args = (process / "cmdline").read_bytes().split(b"\0")
            # Exact argument matches avoid mistaking this verifier for a worker.
            if b"worker" not in args and b"beat" not in args:
                continue
            environment = dict(
                item.split(b"=", 1) for item in (process / "environ").read_bytes().split(b"\0")
                if b"=" in item
            )
            job_processes.append({
                "pid": int(process.name),
                "pilot": b"import_pilot" in b" ".join(args)
                or environment.get(b"DJANGO_SETTINGS_MODULE") == b"import_pilot.settings",
            })
        except (OSError, ValueError):
            continue
    evidence["worker_beat_processes"] = job_processes
    assert not any(process["pilot"] for process in job_processes)
    assert all(evidence["unchanged_source_files"].values())
    assert all(evidence["unchanged_source_metadata"].values())
    # The existing application deliberately remains running. Preserve and report
    # initial-baseline changes instead of falsely claiming a frozen source.
    assert not evidence["public_changed_tables_during_verification"], "Source changed during verification."
    assert evidence["existing_processes_still_running"]
    return evidence


if __name__ == "__main__":
    try:
        evidence = verify(sys.argv[1])
        destination = ROOT / "docs" / "import-pilot" / "evidence.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(evidence, indent=2, ensure_ascii=False))
        print(json.dumps(evidence, indent=2, ensure_ascii=False))
    except Exception as error:
        # Do not render connection strings, secret-bearing SQL or raw tracebacks.
        print(f"Pilot verification stopped ({type(error).__name__}).", file=sys.stderr)
        for frame in traceback.extract_tb(error.__traceback__):
            if Path(frame.filename).resolve() == Path(__file__).resolve():
                print(f"Verifier location: line {frame.lineno} in {frame.name}", file=sys.stderr)
        sys.exit(1)
