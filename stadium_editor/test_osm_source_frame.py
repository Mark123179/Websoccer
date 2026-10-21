"""Offline coverage for displaced roll-out pitches and duplicate arena roofs."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from scripts.build_mainz_osm_review import build


class SourceGeographicFrameTests(TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.study = Path(temporary.name)
        self.out = self.study / "osm-fresh"
        self.out.mkdir()
        nodes = [
            {"type": "node", "id": i + 1, "lon": x, "lat": y}
            for i, (x, y) in enumerate([
                (7, 51), (7.001, 51), (7.001, 51.002), (7, 51.002),
                (7.0002, 51.0002), (7.0008, 51.0002),
                (7.0008, 51.0018), (7.0002, 51.0018),
            ])
        ]
        self.raw = {"elements": nodes + [
            {"type": "way", "id": 10, "nodes": [1, 2, 3, 4, 1],
             "tags": {"building": "stadium"}},
            {"type": "way", "id": 11, "nodes": [5, 6, 7, 8, 5],
             "tags": {"building": "roof"}},
        ]}
        self.calibration = {"surroundingsAxes": {"NORD": "+z", "WEST": "-x"}}
        (self.out / "fetch.json").write_text("{}")
        (self.study / "manifest.json").write_text(json.dumps({
            "calibration": self.calibration, "assetVersion": "before", "limits": [],
        }))
        (self.study / "presentation.json").write_text(json.dumps({
            "presentation": {"calibration": self.calibration},
        }))

    def run_build(self, **options):
        (self.out / "raw.json").write_text(json.dumps(self.raw))
        with patch("scripts.build_mainz_osm_review.inspect_package",
                   return_value={"ok": True, "findings": []}), redirect_stdout(StringIO()):
            build(study=self.study, out=self.out, pitch_id=10, stadium_id=10,
                  stadium_building_id=None, stadium_wikidata=None, fmi=920,
                  opening={"groundLevel": 0, "groundCutout": [[-1, -1], [1, -1], [0, 1]],
                           "method": "test fixture"}, **options)
        return json.loads((self.out / "evidence.json").read_text())

    def test_default_frame_remains_pitch_derived(self):
        evidence = self.run_build()
        self.assertNotIn("frameReference", evidence)
        self.assertAlmostEqual(evidence["centerLonLat"][0], 7.0005)
        self.assertAlmostEqual(evidence["centerLonLat"][1], 51.001)

    def test_explicit_arena_center_and_axis_are_preserved(self):
        reference = {"centerLonLat": [7.0004, 51.0009],
                     "axisEastNorth": [0, 1], "method": "mapped arena footprint"}
        evidence = self.run_build(frame_reference=reference, north_axis=True)
        self.assertEqual(evidence["centerLonLat"], reference["centerLonLat"])
        self.assertEqual(evidence["pitchAxisEastNorth"], [0, 1])
        self.assertEqual(evidence["frameReference"], reference)

    def test_only_explicitly_reviewed_roof_is_not_duplicated(self):
        evidence = self.run_build(represented_stadium_roofs=(11,))
        self.assertEqual(evidence["counts"]["buildings"], 0)
        self.assertTrue(any(note["osm"] == "way/11" for note in evidence["selectionNotes"]))

    def test_only_explicitly_reviewed_stand_building_is_not_duplicated(self):
        for element in self.raw["elements"]:
            if element["type"] == "way" and element["id"] == 11:
                element["tags"]["building"] = "stadium"
        evidence = self.run_build(represented_stadium_buildings=(11,))
        self.assertEqual(evidence["counts"]["buildings"], 0)
        self.assertTrue(any(note["osm"] == "way/11" for note in evidence["selectionNotes"]))

    def test_other_buildings_cannot_be_excluded_as_stadium_stands(self):
        with self.assertRaisesRegex(ValueError, "not part"):
            self.run_build(represented_stadium_buildings=(11,))

    def test_non_roof_and_roof_outside_stadium_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "not inside"):
            self.run_build(represented_stadium_roofs=(10,))
        self.raw["elements"][4]["lon"] = 7.01
        with self.assertRaisesRegex(ValueError, "not inside"):
            self.run_build(represented_stadium_roofs=(11,))

    def test_zero_axis_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Invalid geographic"):
            self.run_build(frame_reference={
                "centerLonLat": [7, 51], "axisEastNorth": [0, 0]})
