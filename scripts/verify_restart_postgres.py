#!/usr/bin/env python3
"""Verify a checksum-pinned package in our own socket-only PostgreSQL cluster.

No Docker, source database access, live schema operations or credentials.
The cluster is created empty under /tmp, verified, stopped and removed.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", required=True, type=Path)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    if not re.fullmatch(r"[a-f0-9]{64}", args.expected_sha256):
        parser.error("SHA-256 muss aus genau 64 kleinen Hex-Zeichen bestehen.")
    actual_sha = hashlib.sha256(args.package.read_bytes()).hexdigest()
    if actual_sha != args.expected_sha256:
        parser.error("Paket-Prüfsumme weicht ab. Kein Prüfcluster erzeugt.")
    report = args.report.resolve()
    allowed = (ROOT / "generated-artifacts/live-restart").resolve()
    if allowed not in report.parents or report.suffix != ".json":
        parser.error("Prüfbericht muss unter generated-artifacts/live-restart/ liegen.")
    log_path = report.with_suffix(".log")
    if report.exists() or log_path.exists():
        parser.error("Prüfdateien existieren bereits; kein Überschreiben.")
    binaries = {name: shutil.which(name) for name in ("initdb", "pg_ctl", "createdb", "postgres")}
    if not all(binaries.values()):
        parser.error("Native PostgreSQL-Werkzeuge fehlen; kein Cluster erzeugt.")
    if os.geteuid() == 0:
        parser.error("Wegwerf-Prüfung nicht als root ausführen.")
    report.parent.mkdir(parents=True, exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix="ws-restart-pg-", dir="/tmp"))
    root.chmod(0o700)
    socket = root / "socket"
    socket.mkdir(mode=0o700)
    data = root / "data"
    marker = {
        "database": "ws_restart_verify", "user": "ws_restart_check",
        "port": "55439", "data_directory": str(data),
    }
    (root / "verification-only.json").write_text(json.dumps(marker))
    passfile = root / "empty-passfile"
    passfile.write_text("")
    passfile.chmod(0o600)
    env = dict(os.environ)
    # Never inherit a target, passfile or session option from the workspace.
    for key in list(env):
        if key.startswith("PG") or key in ("DATABASE_URL", "DJANGO_SETTINGS_MODULE"):
            env.pop(key)
    env.update({
        "DJANGO_SETTINGS_MODULE": "core.live_restart_postgres_verify_settings",
        "WS_RESTART_VERIFY_SOCKET": str(socket),
        "PGPASSFILE": str(passfile), "PGSERVICEFILE": str(passfile),
    })
    stopped = False
    try:
        with log_path.open("x") as log:
            def run(arguments):
                subprocess.run(arguments, cwd=ROOT, env=env, stdout=log,
                               stderr=subprocess.STDOUT, check=True, timeout=1800)

            run([binaries["initdb"], "-D", str(data), "-U", marker["user"],
                 "--no-locale", "--encoding=UTF8", "--auth-local=trust", "--auth-host=reject"])
            run([binaries["pg_ctl"], "-D", str(data), "-l", str(root / "postgres.log"),
                 "-o", f"-k {socket} -p 55439 -c listen_addresses=''", "-w", "start"])
            run([binaries["createdb"], "-h", str(socket), "-p", marker["port"],
                 "-U", marker["user"], marker["database"]])
            run([sys.executable, "-c",
                 "import django; django.setup(); "
                 "from django.conf import settings; from django.db import connection; "
                 "from game.club_import.restart_postgres_guard import assert_disposable_postgres; "
                 "assert_disposable_postgres(connection, settings)"])
            run([sys.executable, "manage.py", "migrate", "--noinput", "--verbosity=0"])
            # Migration seed rows are not the user's imported state. Clear them
            # ONLY after independently re-proving the disposable server identity.
            run([sys.executable, "-c",
                 "import django; django.setup(); "
                 "from django.conf import settings; from django.db import connection; "
                 "from django.core.management import call_command; "
                 "from game.club_import.restart_postgres_guard import assert_disposable_postgres; "
                 "assert_disposable_postgres(connection, settings); "
                 "call_command('flush', interactive=False, verbosity=0)"])
            run([sys.executable, "manage.py", "verify_live_restart_package", str(args.package.resolve()),
                 "--report", str(report)])
            verified = json.loads(report.read_text())
            if (verified.get("backend") != "postgresql"
                    or verified.get("all_tables_identical") is not True
                    or verified.get("schema_identical") is not True):
                raise RuntimeError("PostgreSQL-Parität nicht nachgewiesen.")
            verified["input_package_sha256"] = actual_sha
            verified["postgresql_binary_version"] = subprocess.check_output(
                [binaries["postgres"], "--version"], text=True, env=env).strip()
            verified["cluster"] = {
                "created_empty": True, "unix_socket_only": True,
                "source_database_connected": False,
                "actual_migrations_applied": True,
                "migration_seeds_cleared_only_in_disposable_cluster": True,
            }
            verified["scope"] = "local_disposable_postgresql_not_hetzner"
            report.write_text(json.dumps(verified, ensure_ascii=False, indent=2) + "\n")
    finally:
        status = subprocess.run([binaries["pg_ctl"], "-D", str(data), "status"],
                                env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if status.returncode == 0:
            result = subprocess.run(
                [binaries["pg_ctl"], "-D", str(data), "-m", "fast", "-w", "stop"],
                env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            stopped = result.returncode == 0
        else:
            stopped = status.returncode in (3, 4)
        if stopped:
            shutil.rmtree(root)
        else:
            print(f"Prüfcluster-Stopp ungeklärt; private Diagnose unter {root}.", file=sys.stderr)
    if not stopped:
        raise RuntimeError("Prüfcluster konnte nicht sicher gestoppt werden.")
    print(json.dumps({
        "report": str(report.relative_to(ROOT)), "input_sha256": actual_sha,
        "postgresql_parity": True, "cluster_stopped_and_removed": True,
        "full_restart_ready": False,
    }, indent=2))


if __name__ == "__main__":
    main()
