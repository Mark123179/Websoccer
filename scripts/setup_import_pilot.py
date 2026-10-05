"""Explicit Replit-only setup of the approved role/schema and session infrastructure.

Never a startup hook or a production migration. Workspace secrets are consumed
internally and are never rendered in console output.
"""
import os
import sys
from contextlib import closing
from pathlib import Path

import psycopg2


def prepare():
    if not (os.environ.get("REPL_ID") or os.environ.get("REPLIT_DEV_DOMAIN")):
        raise RuntimeError("Setup is restricted to the Replit development workspace.")
    for key in ("DATABASE_URL", "PILOT_DB_PASSWORD", "PILOT_SECRET_KEY"):
        if not os.environ.get(key):
            raise RuntimeError(f"Missing required workspace secret: {key}")
    if any(len(os.environ[key]) < 32 for key in ("PILOT_DB_PASSWORD", "PILOT_SECRET_KEY")):
        raise RuntimeError("Pilot secrets must contain at least 32 characters.")
    if os.environ["PILOT_DB_PASSWORD"] == os.environ["PILOT_SECRET_KEY"]:
        raise RuntimeError("Use independent pilot secrets.")
    if os.environ.get("DJANGO_SETTINGS_MODULE", "import_pilot.settings") != "import_pilot.settings":
        raise RuntimeError("Refusing an existing application settings context.")

    # Validate settings, including credential separation, before any DDL.
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    os.environ["DJANGO_SETTINGS_MODULE"] = "import_pilot.settings"
    from django.conf import settings

    settings.DATABASES
    with closing(psycopg2.connect(os.environ["DATABASE_URL"])) as maintenance, maintenance:
        with maintenance.cursor() as cursor:
            cursor.execute(
                "SELECT inet_server_addr() IS NULL OR "
                "inet_server_addr() IN ('127.0.0.1'::inet, '::1'::inet)"
            )
            if not cursor.fetchone()[0]:
                raise RuntimeError("Refusing a non-local database; Hetzner is out of scope.")
            cursor.execute("SET LOCAL lock_timeout = '3s'")
            cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = 'import_pilot_role'")
            if cursor.fetchone():
                raise RuntimeError("Pilot role already exists; inspect rather than overwrite.")
            cursor.execute("SELECT 1 FROM pg_namespace WHERE nspname = 'import_pilot'")
            if cursor.fetchone():
                raise RuntimeError("Pilot schema already exists; inspect rather than overwrite.")
            cursor.execute(
                "CREATE ROLE import_pilot_role LOGIN NOSUPERUSER NOCREATEDB "
                "NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS PASSWORD %s",
                (os.environ["PILOT_DB_PASSWORD"],),
            )
            cursor.execute("ALTER ROLE import_pilot_role SET search_path = import_pilot")
            cursor.execute("CREATE SCHEMA import_pilot AUTHORIZATION import_pilot_role")
            cursor.execute("REVOKE ALL ON SCHEMA import_pilot FROM PUBLIC")

    # Close maintenance access before opening the direct restricted connection.
    import django
    from django.core.management import call_command

    django.setup()
    call_command("migrate", "sessions", interactive=False, verbosity=0)
    settings.MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
    print("Created pilot role/schema and session/migration infrastructure only.")


if __name__ == "__main__":
    try:
        prepare()
    except RuntimeError as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
    except Exception as error:
        # Database tracebacks can expose connection strings or sensitive SQL.
        print(
            f"Pilot setup stopped ({type(error).__name__}); "
            "inspect pilot metadata before retrying.",
            file=sys.stderr,
        )
        sys.exit(1)
