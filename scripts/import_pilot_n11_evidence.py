"""Local N11 evidence and a private, schema-scoped v1 dump. Never restores data."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["DJANGO_SETTINGS_MODULE"] = "import_pilot.settings"
os.umask(0o077)

import django
django.setup()
from django.apps import apps
from django.conf import settings
from django.db import connection, transaction
from django.utils import timezone
from game import models as m
from game.club_import.runtime import visible_clubs, visible_leagues

V1 = "9d2b87c16389caf12693da07d7644df2c5f7d36e1e8c979b8651ead1e951676d"


def assert_local_pilot():
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_schema(),current_user,"
                       "inet_server_addr() IS NULL OR inet_server_addr() "
                       "IN ('127.0.0.1'::inet,'::1'::inet)")
        assert cursor.fetchone() == ("import_pilot", "import_pilot_role", True)
    assert settings.IMPORT_PACKAGE_MODE
    assert not settings.IMPORT_PACKAGE_IMAGE_CHECK_ENABLED


def capture():
    assert_local_pilot()
    issues = list(m.ImportIssue.objects.order_by("pk").values_list("pk", "resolution_status", "note"))
    club = m.Club.objects.get(transfermarkt_id=16)
    package = m.SourceImportRun.objects.filter(club=club, status="applied").order_by("-pk").first()
    tm_ids = [player["ids"]["tm"]["value"] for player in package.package_data["players"]]
    player_ids = list(m.Player.objects.filter(transfermarkt_id__in=tm_ids).values_list("pk", flat=True))
    tables = {}
    names = {model._meta.db_table for model in apps.get_app_config("game").get_models()
             if not model._meta.proxy}
    with connection.cursor() as cursor:
        for name in sorted(names):
            quoted = connection.ops.quote_name(name)
            cursor.execute(f"SELECT count(*),md5(coalesce(string_agg(digest,'' ORDER BY digest),'')) "
                           f"FROM (SELECT md5(row_to_json(t)::text) AS digest FROM {quoted} t) s")
            count, digest = cursor.fetchone()
            tables[name] = {"rows": count, "md5": digest}
    return {
        "at": timezone.now().isoformat(),
        "image_check_enabled": settings.IMPORT_PACKAGE_IMAGE_CHECK_ENABLED,
        "package_hashes": list(m.SourceImportRun.objects.filter(status="applied")
                               .order_by("pk").values_list("data_sha256", flat=True)),
        "issues": len(issues),
        "issue_status_text_sha256": hashlib.sha256(json.dumps(issues, ensure_ascii=False).encode()).hexdigest(),
        "open": m.ImportIssue.objects.filter(resolution_status="open").count(),
        "package_closed": m.ImportIssue.objects.filter(resolution_status="package").count(),
        "strengths": m.PlayerStrengthProfile.objects.filter(player_id__in=player_ids).count(),
        "locks": m.Player.objects.filter(pk__in=player_ids, import_lock=True).count(),
        "locked_players": list(m.Player.objects.filter(pk__in=player_ids, import_lock=True)
                               .order_by("display_name").values_list("display_name", flat=True)),
        "clubs": m.Club.objects.count(),
        "visible_clubs": visible_clubs().count(),
        "visible_leagues": visible_leagues().count(),
        "retirement_clubs": m.Club.objects.filter(name__iexact="Karrierende").count(),
        "tables": tables,
    }


def backup(test_log):
    log = Path(test_log).read_text()
    result = re.search(r"^Ran (\d+) tests in ([\d.]+)s$", log, re.M)
    assert result and re.search(r"^OK$", log, re.M), "Full suite must pass before backup/import."
    assert not re.search(r"^(FAILED|FAIL:|ERROR:)", log, re.M)
    stamp = timezone.now().strftime("%Y%m%dT%H%M%SZ")
    folder = ROOT / "backups" / "import-pilot"
    folder.mkdir(parents=True, exist_ok=True)
    archive = folder / f"bvb-v1-{stamp}.dump"
    db = settings.DATABASES["default"]
    # Only the pg_dump child receives credentials; neither argv nor logs contain them.
    child_env = dict(os.environ)
    for key, field in (("PGHOST", "HOST"), ("PGPORT", "PORT"), ("PGDATABASE", "NAME"),
                       ("PGUSER", "USER"), ("PGPASSWORD", "PASSWORD")):
        child_env[key] = str(db[field])
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            cursor.execute("SELECT pg_export_snapshot()")
            snapshot = cursor.fetchone()[0]
        evidence = capture()
        assert evidence["package_hashes"] == [V1]
        assert evidence["issues"] == 156
        subprocess.run(["pg_dump", "--format=custom", "--schema=import_pilot",
                        "--no-owner", "--no-privileges", "--snapshot=" + snapshot,
                        "--file=" + str(archive)], env=child_env, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    archive.chmod(0o600)
    listing = subprocess.run(["pg_restore", "--list", str(archive)], check=True,
                             capture_output=True, text=True).stdout
    assert "TABLE DATA import_pilot" in listing
    assert "TABLE DATA public" not in listing and "SCHEMA - public" not in listing
    evidence["full_suite"] = {"tests": int(result[1]), "seconds": float(result[2]), "result": "OK"}
    evidence["dump"] = {
        "path": str(archive.relative_to(ROOT)), "bytes": archive.stat().st_size,
        "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
        "mode": oct(archive.stat().st_mode & 0o777), "schema": "import_pilot",
        "archive_list_verified": True,
    }
    return evidence


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--backup-after-tests")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = backup(args.backup_after_tests) if args.backup_after_tests else capture()
    destination = ROOT / args.output
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({key: value for key, value in result.items() if key != "tables"},
                     ensure_ascii=False))
