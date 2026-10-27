from copy import deepcopy
import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import zipfile

from django.test import SimpleTestCase

from game.club_import.package_validation import read_package
from scripts import import_swiss_packages as batch


class SwissPreparationTests(SimpleTestCase):
    def test_only_approved_records_and_info_gaps_change(self):
        original = batch.SOURCE.read_bytes()
        with TemporaryDirectory() as tmp, patch.object(batch, "OUTPUT", Path(tmp)):
            paths, provenance = batch.prepare()
            self.assertEqual(len(paths), 12)
            self.assertEqual(provenance["unique_players"], 631)
            self.assertEqual(provenance["reciprocal_loans"], 4)
            self.assertEqual(provenance["source_totals"], {
                "players": 635, "persons": 129, "records": 288, "titles": 369})
            self.assertEqual(len(provenance["record_changes"]), 6)
            self.assertEqual(
                {row["player_tm"]: row["preserved_owner_tm"]
                 for row in provenance["owner_exceptions"]},
                {1133978: 985, 978438: 3})
            with zipfile.ZipFile(batch.SOURCE) as outer:
                for path in paths:
                    _, source = read_package(outer.read(path.name))
                    _, projected = read_package(path)
                    for key in ("club", "stadium", "players", "persons", "titles"):
                        self.assertEqual(projected[key], source[key], (path.name, key))
                    expected = deepcopy(source)
                    batch.revise_records(expected)
                    self.assertEqual(projected, expected)
                    self.assertEqual(
                        [g for g in projected["gaps"] if g["severity"] == "player_lock"],
                        [g for g in source["gaps"] if g["severity"] == "player_lock"])
                    if source["club"]["ids"]["tm"]["value"] == 163:
                        self.assertEqual(projected["club"]["country"], "Liechtenstein")
                    if source["club"]["ids"]["tm"]["value"] == 504:
                        records = {r["key"]: r for r in projected["records"]}
                        self.assertEqual(records["biggest_defeat"]["value_display"], "1:8")
                        self.assertEqual(records["biggest_defeat"]["opponent"]["tm_id"], 26)
                        self.assertEqual(records["youngest_player"]["date"], "1992-07-22")
                        self.assertEqual(records["youngest_player"]["value_numeric"], 5615)
            self.assertEqual(batch.SOURCE.read_bytes(), original)
            self.assertEqual(hashlib.sha256(original).hexdigest(), batch.SOURCE_SHA)

    def test_changed_source_stops_before_projection(self):
        with TemporaryDirectory() as tmp:
            source = Path(tmp) / "changed.zip"
            source.write_bytes(b"changed")
            with patch.object(batch, "SOURCE", source):
                with self.assertRaisesMessage(batch.PackageError, "approval must be reviewed"):
                    batch.prepare()
