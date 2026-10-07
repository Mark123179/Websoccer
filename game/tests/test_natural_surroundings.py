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
        root = Path(__file__).resolve().parents[2] / "stadium_editor/blueprints/natural/sources"
        source = json.loads((root / "dortmund_scene.json").read_text())["surroundings"]
        mapped = json.loads((root / "dortmund_umfeld.json").read_text())
        self.assertEqual(package["data"]["buildings"], [b["poly"] for b in source["buildings"]])
        self.assertEqual(package["data"]["roads"], source["roads"])
        self.assertEqual(package["data"]["green"], [g["poly"] for g in mapped["grass"]])
        self.assertEqual(package["data"]["trees"], [t["p"] for t in mapped["trees"]])
        for key in ("parking", "forest", "scrub", "sports", "buildingsTagged"):
            self.assertEqual(package["data"][key], mapped[key])
        self.assertEqual(len(package["data"]["trees"]), 334)
        self.assertEqual(len(package["data"]["sports"]), 29)
        self.assertEqual(package["frame"]["sceneAxes"], "pitch-west-camera")
        self.assertEqual(package["frame"]["fieldC"], [0, 0])
        self.assertEqual(package["data"]["shrubs"], [])
        package["data"]["trees"].clear()
        self.assertEqual(len(load_natural_package("dortmund")["data"]["trees"]), 334)

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
            lambda p: p["data"]["parking"][0]["poly"].append([True, 0]),
            lambda p: p["data"]["parking"].append(deepcopy(p["data"]["parking"][0])),
            lambda p: p["data"]["sourceDetail"].__setitem__("licence", ""),
            lambda p: p["frame"].__setitem__("axisTheta", .1),
            lambda p: p["data"]["treeMetadata"][0].__setitem__("p", [0, 0]),
            lambda p: p["model"].__setitem__("mirrorAxis", "unknown"),
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
