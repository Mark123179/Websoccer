from copy import deepcopy
import json
from pathlib import Path
from unittest import TestCase

from stadium_editor.natural_packages import load_natural_package, validate_natural_package
from stadium_editor.blueprints.v2.dortmund_preview import load_preview
from stadium_editor.surroundings import with_dortmund_mapped_trees


class NaturalPackageTests(TestCase):
    def test_dortmund_preserves_source_geometry_and_tree_calibration(self):
        package = load_natural_package("dortmund")
        original = with_dortmund_mapped_trees(load_preview(), club_id=3)
        source = original.get("surroundings") or original.get("bg")
        self.assertEqual(package["data"]["buildings"], [b["poly"] for b in source["buildings"]])
        for key in ("roads", "green", "trees"):
            self.assertEqual(package["data"][key], source[key])
        self.assertEqual(len(package["data"]["trees"]), 248)
        self.assertEqual(package["data"]["shrubs"], [])
        package["data"]["trees"].clear()
        self.assertEqual(len(load_natural_package("dortmund")["data"]["trees"]), 248)

    def test_invalid_calibration_coordinates_dimensions_and_source_are_rejected(self):
        source = load_natural_package("dortmund")
        for key, value in [("fieldC", [0, float("nan")]), ("axisTheta", True)]:
            data = deepcopy(source)
            data["frame"][key] = value
            with self.assertRaises(ValueError):
                validate_natural_package(data)
        for modify in [
            lambda p: p["data"]["buildingHeights"].pop(),
            lambda p: p["data"]["buildingHeights"].__setitem__(0, -1),
            lambda p: p["data"]["trees"].append([float("inf"), 0]),
            lambda p: p["data"]["roads"][0].__setitem__("w", 0),
            lambda p: p["data"]["sources"].__setitem__("trees", ""),
        ]:
            data = deepcopy(source)
            modify(data)
            with self.assertRaises(ValueError):
                validate_natural_package(data)
        for package_id in ("../dortmund", "/tmp/dortmund", "Dortmund", ""):
            with self.assertRaises(ValueError):
                load_natural_package(package_id)

    def test_license_manifest_and_prepared_resources_match(self):
        import hashlib
        root = Path(__file__).resolve().parents[2] / "stadium_editor/static/stadium_editor/natural_assets"
        manifest = json.loads((root / "provenance.json").read_text())
        for record in manifest["files"]:
            file = root / record["path"]
            self.assertEqual(file.stat().st_size, record["bytes"])
            self.assertEqual(hashlib.sha256(file.read_bytes()).hexdigest(), record["sha256"])
        self.assertTrue(any(a["id"] == "shrub_03" for a in manifest["assets"]))
