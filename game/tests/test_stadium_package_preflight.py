from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.test import SimpleTestCase

from stadium_editor.package_preflight import inspect_package
from stadium_editor.surroundings_ground import validated_ground_fields

ROOT = Path(__file__).resolve().parents[2]


class StadiumPackagePreflightTests(SimpleTestCase):
    hole = [[-10, -10], [10, -10], [10, 10], [-10, 10]]

    def test_python_numeric_checks_run_before_node(self):
        with patch("stadium_editor.package_preflight.subprocess.run") as run:
            for value in [True, "7.7", None, float("nan"), float("inf"), 31, 10**400]:
                with self.subTest(value=str(value)):
                    report = inspect_package({"groundLevel": value})
                    self.assertFalse(report["ok"])
                    self.assertTrue(report["terrainDeclared"])
                    self.assertEqual(report["findings"][0]["code"], "invalid_terrain")
            run.assert_not_called()
        with self.assertRaises(ValueError):
            validated_ground_fields({"groundLevel": 0, "groundCutout": [[0, 0], [10**400, 1], [1, 0]]})

    def test_geometry_projection_matches_runtime_precedence_and_reports_source_index(self):
        geometry = {
            "meta": {"fieldC": [0, 0], "axisTheta": 0}, "blocks": [],
            "bg": {"buildings": [
                {"poly": [[30, -30], [32, -30], [32, -32], [30, -32]], "h": 12},
                {"poly": [[0, 0], [2, 0], [2, 2], [0, 2]], "h": 9},
            ], "trees": [[0, 0]]},
            "surroundings": {
                "groundLevel": 7.7, "groundCutout": self.hole,
                "buildings": [[[100, 100], [102, 100], [102, 102]]],
            },
        }
        before = deepcopy(geometry)
        report = inspect_package(geometry)
        self.assertFalse(report["ok"])
        self.assertEqual([f["path"] for f in report["findings"]],
                         ["bg.buildings[1].poly", "bg.trees[0]"])
        self.assertEqual(geometry, before)

    def test_wrapper_source_paths_and_valid_baseline(self):
        report = inspect_package({"data": {"groundLevel": 7.7, "groundCutout": self.hole,
                                          "trees": [[0, 0]]}, "frame": {}})
        self.assertEqual(report["findings"][0]["path"], "data.trees[0]")
        self.assertEqual(inspect_package({}), {"ok": True, "terrainDeclared": False, "findings": []})
        self.assertFalse(inspect_package({}, axes=None)["ok"])
        self.assertFalse(inspect_package({}, frame=None)["ok"])

    def test_editor_meta_frame_without_background_or_blocks_is_not_ignored(self):
        geometry = {
            "meta": {"fieldC": [100, 100], "axisTheta": 1.2},
            "surroundings": {
                "groundLevel": 7.7, "groundCutout": self.hole,
                "trees": [[200, 200], [100, 100]],
            },
        }
        before = deepcopy(geometry)
        report = inspect_package(geometry)
        self.assertFalse(report["ok"])
        self.assertTrue(report["terrainDeclared"])
        self.assertEqual([f["path"] for f in report["findings"]], ["surroundings.trees[1]"])
        self.assertEqual(geometry, before)
        runtime = {"frame": geometry["meta"], "surroundings": geometry["surroundings"]}
        self.assertEqual(inspect_package(runtime), report)

    def test_early_failure_report_shape(self):
        for package in [None, [], {"data": None}, {"groundLevel": 31}]:
            with self.subTest(package=package):
                report = inspect_package(package)
                self.assertEqual(set(report), {"ok", "terrainDeclared", "findings"})
                self.assertFalse(report["ok"])
        with patch("stadium_editor.package_preflight.subprocess.run",
                   side_effect=FileNotFoundError):
            report = inspect_package({"groundLevel": 0})
            self.assertTrue(report["terrainDeclared"])
            self.assertEqual(set(report), {"ok", "terrainDeclared", "findings"})

    def test_checker_failure_is_not_success(self):
        with patch("stadium_editor.package_preflight.subprocess.run",
                   side_effect=FileNotFoundError):
            self.assertEqual(inspect_package({})["findings"][0]["code"], "checker_failed")

    def test_cli_is_read_only_and_has_clear_exit_status(self):
        with TemporaryDirectory() as directory:
            folder = Path(directory)
            source = folder / "surroundings.json"
            manifest = folder / "manifest.json"
            source.write_text(json.dumps({
                "groundLevel": 7.7, "groundCutout": self.hole, "trees": [[0, 0]],
            }))
            manifest.write_text(json.dumps({"calibration": {"surroundingsAxes": {
                "NORD": "-z", "WEST": "+x",
            }}}))
            before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.iterdir()}
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts/check_stadium_package.py"),
                 "--source", str(source), "--manifest", str(manifest), "--json"],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(result.returncode, 1, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["findings"][0]["path"], "trees[0]")
            self.assertEqual(before, {
                p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.iterdir()
            })
            source.write_text("{}")
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts/check_stadium_package.py"),
                 "--source", str(source)], capture_output=True, text=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("keine Quelländerungen, Registrierung oder Uploads", result.stdout)
