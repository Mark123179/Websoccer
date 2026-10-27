import copy
import json
import subprocess
import tempfile
from unittest.mock import MagicMock, patch
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from game.club_import.live_restart_safety import (
    build_scene_snapshot, compare_previews, compare_scenes,
)
from game.models import Club, ClubStadionumfeldState, League, Stadium
from stadium_editor.models import StadiumDesign, StadiumGeometry


class LiveRestartSceneBackupTests(TestCase):
    def setUp(self):
        league = League.objects.create(name="Scene backup league", country="Test")
        self.club = Club.objects.create(
            name="Scene backup club", league=league, budget=0, founded_year=1900,
            transfermarkt_id=99887766, fm_inside_id=99887766)
        self.stadium = Stadium.objects.create(club=self.club, name="Test", city="Test")

    def test_all_scene_types_are_exported_without_writes_or_local_ids(self):
        StadiumGeometry.objects.create(stadium=self.stadium, geometry={"mesh": "test"})
        StadiumDesign.objects.create(stadium=self.stadium, design={"seats": [1, 2]})
        ClubStadionumfeldState.objects.create(club=self.club)
        with CaptureQueriesContext(connection) as queries:
            report = build_scene_snapshot(connection)
        self.assertFalse(any(q["sql"].lstrip().upper().startswith(
            ("UPDATE ", "DELETE ", "INSERT ", "TRUNCATE ", "ALTER ", "DROP ", "CREATE "))
            for q in queries))
        row = next(row for row in report["clubs"] if row["identity"]["tm_id"] == 99887766)
        self.assertEqual(row["geometry"]["geometry"], {"mesh": "test"})
        self.assertEqual(row["design"]["design"], {"seats": [1, 2]})
        self.assertIsNotNone(row["surroundings"])
        self.assertNotIn("stadium", row["geometry"])
        self.assertNotIn("id", row["design"])
        self.assertNotIn("club", row["surroundings"])
        self.assertFalse(report["ready_for_reset"])
        self.assertEqual(report["unresolved_identities"], [])

    def test_identityless_scenes_are_retained_but_block_comparison(self):
        self.club.transfermarkt_id = None
        self.club.fm_inside_id = None
        self.club.save(update_fields=["transfermarkt_id", "fm_inside_id"])
        StadiumDesign.objects.create(stadium=self.stadium, design={"keep": True})
        report = json.loads(json.dumps(build_scene_snapshot(connection), default=str))
        self.assertTrue(report["unresolved_identities"])
        self.assertTrue(report["clubs"][0]["design"]["design"]["keep"])
        with self.assertRaises(ValueError):
            compare_scenes(report, report)

    def test_command_is_read_only_and_rejects_unsafe_restore_targets(self):
        output = StringIO()
        call_command("live_restart_scene_backup", stdout=output)
        self.assertTrue(json.loads(output.getvalue())["read_only"])
        for target in ("production", "public", "pilot", "import_restore_check_;DROP"):
            with self.subTest(target=target), self.assertRaises(CommandError):
                call_command("live_restart_scene_backup", restore_check_name=target)
        with self.assertRaises(TypeError):
            call_command("live_restart_scene_backup", apply=True)

    def test_restore_snapshot_registers_only_isolated_alias_and_cleans_it_up(self):
        from game.management.commands import live_restart_scene_backup as command
        fake_source = MagicMock()
        fake_source.vendor = "postgresql"
        fake_source.settings_dict = {"NAME": "live_database", "ENGINE": "postgresql"}
        fake_connections = MagicMock()
        fake_connections.__contains__.return_value = False
        fake_connections.databases = {}
        target = MagicMock()
        fake_connections.__getitem__.return_value = target
        with patch.object(command, "connection", fake_source), \
                patch.object(command, "connections", fake_connections), \
                patch.object(command, "build_scene_snapshot", return_value={"read_only": True}) as build:
            output = StringIO()
            command.Command(stdout=output).handle(restore_check_name="import_restore_check_proof")
        build.assert_called_once_with(target)
        target.close.assert_called_once()
        self.assertEqual(fake_connections.databases, {})
        fake_connections.__delitem__.assert_called_once_with("_live_restart_scene_check")


class LiveRestartComparisonTests(TestCase):
    def preview(self):
        return {
            "kind": "read_only_reset_preview", "vendor": "postgresql",
            "tables": [{"table": "auth_user", "rows": 2, "action": "keep",
                        "before": [2, "a" * 32], "preserved": [2, "a" * 32]}],
            "profile_keep_columns": ["user_id"], "profile_reset": {"xp": "0"},
            "delete_order": [], "blockers": [], "sql_ready": True,
        }

    def test_full_match_passes_and_scopes_may_differ(self):
        live, restored = self.preview(), self.preview()
        live["scope"] = "configured_database_not_verified_hetzner"
        restored["scope"] = "isolated_restore_check_not_live"
        compare_previews(live, restored)

    def test_count_match_with_content_difference_fails(self):
        live, restored = self.preview(), self.preview()
        restored["tables"][0]["before"][1] = "b" * 32
        with self.assertRaises(ValueError):
            compare_previews(live, restored)

    def test_incomplete_or_blocked_or_wrong_database_reports_fail(self):
        for change in (
            {"tables": []}, {"blockers": ["unclassified"]}, {"sql_ready": False},
            {"vendor": "sqlite"}, {"profile_reset": {}},
            {"tables": [{"table": "auth_user", "rows": 2, "action": "keep"}]},
        ):
            with self.subTest(change=change), self.assertRaises(ValueError):
                restored = self.preview()
                restored.update(change)
                compare_previews(self.preview(), restored)

    def test_sequence_or_scene_difference_fails(self):
        live = {"format": "WS_PRIVATE_SCENE_BACKUP_V1", "read_only": True,
                "unresolved_identities": [], "clubs": [],
                "sequences": {"auth_user_id_seq": [5, True]}}
        compare_scenes(live, copy.deepcopy(live))
        restored = copy.deepcopy(live)
        restored["sequences"]["auth_user_id_seq"][0] = 6
        with self.assertRaises(ValueError):
            compare_scenes(live, restored)

    def test_comparison_cli_needs_no_django_or_database(self):
        root = Path(__file__).resolve().parents[2]
        scene = {"format": "WS_PRIVATE_SCENE_BACKUP_V1", "read_only": True,
                 "unresolved_identities": [], "clubs": [], "sequences": {}}
        with tempfile.TemporaryDirectory() as folder:
            files = []
            for number, data in enumerate((self.preview(), self.preview(), scene, scene)):
                path = Path(folder) / f"{number}.json"
                path.write_text(json.dumps(data))
                files.append(str(path))
            # -S suppresses site-packages, proving the host needs no Django.
            import sys
            result = subprocess.run(
                [sys.executable, "-S", str(root / "scripts/compare_live_restart_backups.py"), *files],
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Kein Reset", result.stdout)
            Path(files[1]).write_text("{}")
            result = subprocess.run(
                [sys.executable, "-S", str(root / "scripts/compare_live_restart_backups.py"), *files],
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)

    def test_server_script_mocked_roundtrip_keeps_live_untouched_and_stops_on_drift(self):
        """Orchestration check only, explicitly not a real PostgreSQL restore."""
        import os
        import shutil
        import sys
        root = Path(__file__).resolve().parents[2]
        scene = {"format": "WS_PRIVATE_SCENE_BACKUP_V1", "read_only": True,
                 "unresolved_identities": [], "clubs": [], "sequences": {"test_seq": [7, True]}}
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            repo = base / "repo"
            for directory in ("scripts", "game/club_import", "bin"):
                (repo / directory).mkdir(parents=True)
            for relative in (
                "scripts/prepare_live_restart_server.sh",
                "scripts/compare_live_restart_backups.py",
                "game/club_import/live_restart_safety.py",
            ):
                shutil.copyfile(root / relative, repo / relative)
            (repo / ".env").write_text("DUMMY_TEST_CONFIG=not-a-secret\n")
            (base / "preview.json").write_text(json.dumps(self.preview()))
            (base / "scene.json").write_text(json.dumps(scene))
            docker = repo / "bin/docker"
            docker.write_text(f"#!{sys.executable}\n" + '''
import io, json, os, sys, tarfile
from pathlib import Path
base = Path(os.environ["RESTART_MOCK_ROOT"])
args = sys.argv[1:]
with (base / "docker-calls.jsonl").open("a") as log:
    log.write(json.dumps(args) + "\\n")
joined = " ".join(args)
if "ps --status running --services" in joined:
    print("db\\nredis" + ("\\nweb" if os.environ.get("RESTART_MOCK_RUNNING") else ""))
elif "pg_dump" in joined:
    sys.stdout.buffer.write(b"MOCK PRIVATE DUMP")
elif "pg_restore" in joined:
    sys.stdin.buffer.read()
    print("MOCK RESTORE")
elif "createdb" in joined:
    assert args[-1].startswith("import_restore_check_")
elif "run" in args:
    assert "PGOPTIONS=-c default_transaction_read_only=on" in args
    if "preview_club_reset" in args:
        data = json.loads((base / "preview.json").read_text())
        if "--restore-check-name" in args and os.environ.get("RESTART_MOCK_DRIFT"):
            data["tables"][0]["before"][1] = "b" * 32
        print(json.dumps(data))
    elif "live_restart_scene_backup" in args:
        print((base / "scene.json").read_text())
    elif args[-1] in ("assets", "media"):
        kind = args[-1]
        with tarfile.open(fileobj=sys.stdout.buffer, mode="w|gz") as archive:
            data = b"MOCK FILE"
            member = tarfile.TarInfo(kind + "/test-file")
            member.size = len(data)
            archive.addfile(member, io.BytesIO(data))
    else:
        print(json.dumps({"assets": "/mock/assets", "media": "/mock/media"}))
else:
    raise SystemExit("Unexpected docker operation")
''')
            docker.chmod(0o700)
            git = repo / "bin/git"
            git.write_text("#!/bin/sh\nprintf 'mock-code-version\\n'\n")
            git.chmod(0o700)
            env = dict(os.environ, PATH=str(repo / "bin") + ":" + os.environ["PATH"],
                       RESTART_MOCK_ROOT=str(base), WS_PRIVATE_BACKUP_ROOT=str(base / "private"))
            script = str(repo / "scripts/prepare_live_restart_server.sh")
            args = ["bash", script, "--writers-paused", "--backup-and-verify"]
            result = subprocess.run(args, env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            backup = next((base / "private").iterdir())
            self.assertEqual(backup.stat().st_mode & 0o777, 0o700)
            self.assertTrue((backup / "restore-check.txt").exists())
            self.assertTrue((backup / "checksums.txt").exists())
            self.assertEqual((repo / ".env").read_text(), "DUMMY_TEST_CONFIG=not-a-secret\n")
            calls = [json.loads(line) for line in (base / "docker-calls.jsonl").read_text().splitlines()]
            self.assertFalse(any(any(op in call for op in (
                "psql", "dropdb", "stop", "up", "migrate", "flush")) for call in calls))
            drift_env = dict(env, RESTART_MOCK_DRIFT="1")
            result = subprocess.run(args, env=drift_env, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Kein Reset", result.stderr)
            self.assertEqual(len(list((base / "private").iterdir())), 2)
            result = subprocess.run(
                args, env=dict(env, RESTART_MOCK_RUNNING="1"), capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("web läuft noch", result.stderr)
            self.assertEqual(len(list((base / "private").iterdir())), 2)
