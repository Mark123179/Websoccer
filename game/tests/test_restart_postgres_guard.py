import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import MagicMock

from django.test import SimpleTestCase

from game.club_import.restart_export import HandoffError
from game.club_import.restart_postgres_guard import assert_disposable_postgres


class DisposablePostgresGuardTests(SimpleTestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="ws-restart-pg-", dir="/tmp")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.expected = {
            "database": "ws_restart_verify", "user": "ws_restart_check",
            "port": "55439", "data_directory": str(self.root / "data"),
        }
        (self.root / "verification-only.json").write_text(json.dumps(self.expected))
        self.settings = SimpleNamespace(
            LIVE_RESTART_VERIFY_ONLY=True, LIVE_RESTART_VERIFY_POSTGRES=True,
            SETTINGS_MODULE="core.live_restart_postgres_verify_settings")
        self.connection = MagicMock()
        self.connection.vendor = "postgresql"
        self.connection.settings_dict = {
            "NAME": "ws_restart_verify", "USER": "ws_restart_check",
            "PORT": "55439", "HOST": str(self.root / "socket"),
        }
        self.cursor = self.connection.cursor.return_value.__enter__.return_value
        self.cursor.fetchone.return_value = (
            "ws_restart_verify", "ws_restart_check", str(self.root / "data"), "55439", None)

    def test_only_matching_socket_cluster_is_accepted_with_read_only_identity_query(self):
        assert_disposable_postgres(self.connection, self.settings)
        self.cursor.execute.assert_called_once()
        self.assertTrue(self.cursor.execute.call_args.args[0].strip().startswith("SELECT"))

    def test_ordinary_settings_or_wrong_flag_rejected_before_connecting(self):
        for field, value in (
            ("LIVE_RESTART_VERIFY_ONLY", False), ("LIVE_RESTART_VERIFY_POSTGRES", False),
            ("SETTINGS_MODULE", "core.settings"), ("SETTINGS_MODULE", "import_pilot.settings"),
        ):
            with self.subTest(field=field, value=value):
                settings = SimpleNamespace(**vars(self.settings))
                setattr(settings, field, value)
                with self.assertRaises(HandoffError):
                    assert_disposable_postgres(self.connection, settings)
        self.connection.cursor.assert_not_called()

    def test_workspace_or_remote_targets_rejected_before_connecting(self):
        original = dict(self.connection.settings_dict)
        for field, value in (
            ("NAME", "workspace"), ("USER", "workspace_owner"), ("PORT", "5432"),
            ("HOST", "database.example.test"), ("HOST", "/var/run/postgresql"),
        ):
            with self.subTest(field=field):
                self.connection.settings_dict = dict(original, **{field: value})
                with self.assertRaises(HandoffError):
                    assert_disposable_postgres(self.connection, self.settings)
        self.connection.cursor.assert_not_called()

    def test_missing_or_changed_marker_is_rejected_without_connection(self):
        marker = self.root / "verification-only.json"
        marker.unlink()
        with self.assertRaises(HandoffError):
            assert_disposable_postgres(self.connection, self.settings)
        marker.write_text(json.dumps(dict(self.expected, database="production")))
        with self.assertRaises(HandoffError):
            assert_disposable_postgres(self.connection, self.settings)
        self.connection.cursor.assert_not_called()

    def test_actual_server_identity_must_match_not_just_client_configuration(self):
        valid = ("ws_restart_verify", "ws_restart_check", str(self.root / "data"), "55439", None)
        for index, replacement in (
            (0, "production"), (1, "source_owner"), (2, "/var/lib/postgresql/data"),
            (3, "5432"), (4, "127.0.0.1"),
        ):
            actual = list(valid)
            actual[index] = replacement
            self.cursor.fetchone.return_value = actual
            with self.subTest(index=index), self.assertRaises(HandoffError):
                assert_disposable_postgres(self.connection, self.settings)

    def test_runner_refuses_wrong_checksum_before_creating_cluster(self):
        root = Path(__file__).resolve().parents[2]
        package = self.root / "input.zip"
        package.write_bytes(b"test-input")
        result = subprocess.run(
            [sys.executable, str(root / "scripts/verify_restart_postgres.py"),
             "--package", str(package), "--expected-sha256", hashlib.sha256(b"other").hexdigest(),
             "--report", str(self.root / "must-not-exist.json")],
            text=True, capture_output=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("Paket-Prüfsumme", result.stderr)
        self.assertFalse((self.root / "must-not-exist.json").exists())
