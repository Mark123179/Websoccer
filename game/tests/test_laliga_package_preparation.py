from collections import defaultdict
import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.test import SimpleTestCase

from game.club_import.package_validation import read_package
from scripts import import_laliga_packages as batch


class LaLigaPreparationTests(SimpleTestCase):
    def test_approved_exceptions_preserve_sources_and_complete_league(self):
        original = batch.SOURCE.read_bytes()
        with TemporaryDirectory() as tmp, patch.object(batch, "OUTPUT", Path(tmp)):
            paths, provenance = batch.prepare()
            self.assertEqual(len(paths), 20)
            self.assertEqual(provenance["unique_players"], 930)
            self.assertEqual(provenance["source_totals"]["players"], 947)
            self.assertEqual(provenance["reciprocal_loans"], 17)
            rows = defaultdict(list)
            for path in paths:
                _, data = read_package(path)
                for player in data["players"]:
                    rows[player["ids"]["tm"]["value"]].append((player, data["gaps"]))
            for tm in batch.QUARANTINE:
                for player, gaps in rows[tm]:
                    self.assertIsNone(player["ids"]["fmi"]["value"])
                    self.assertIsNone(player["ratings"]["fminside"])
                    self.assertTrue(any(g["severity"] == "player_lock"
                                        and g["ref"] == f"tm:{tm}" for g in gaps))
            for tm, (owner, borrower) in batch.LOAN_OVERRIDES.items():
                self.assertEqual(len(rows[tm]), 2)
                for player, _ in rows[tm]:
                    self.assertEqual(player["squad"]["owner_club"], owner)
                    self.assertEqual(player["squad"]["loan_club"], borrower)
                    self.assertEqual(player["squad"]["team"], "u21")
            self.assertEqual(len(provenance["quarantine"]), 9)
            self.assertEqual(len(provenance["loan_exceptions"]), 4)
            self.assertEqual(hashlib.sha256(original).hexdigest(), batch.SOURCE_SHA)
            self.assertEqual(batch.SOURCE.read_bytes(), original)

    def test_changed_delivery_requires_new_approval(self):
        with TemporaryDirectory() as tmp:
            source = Path(tmp) / "changed.zip"
            source.write_bytes(b"changed source")
            with patch.object(batch, "SOURCE", source):
                with self.assertRaisesMessage(batch.PackageError, "approval must be reviewed"):
                    batch.prepare()
