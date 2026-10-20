"""Offline regression fixtures for display-vs-native height alarms."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import shutil
from unittest import TestCase
from unittest.mock import patch

import numpy as np
from pyproj import Transformer
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import box

from scripts.check_koln_height_profiles import (
    LIMITS, evaluate, main, profiles_for, renderer_samples, run, spaced, summarize,
)
from scripts.koln_profile_sources import NativeDGM, model_projection
from game.tests.koln_ground_fixture import DIRECTORY, assert_ground_equal, load_ground, replay_ground


class RealGroundWitnessTests(TestCase):
    """Actual source pixels; no downloader, DB, live app or ignored files."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        for target in ("socket.socket.connect", "requests.sessions.Session.request"):
            blocker = patch(target, side_effect=AssertionError("Offline regression attempted network"))
            blocker.start()
            cls.addClassCleanup(blocker.stop)
        cls.fixture, cls.native = load_ground()
        cls.actual = replay_ground(cls.fixture, cls.native)

    def test_all_native_pixels_and_sample_georeferences_are_hash_bound(self):
        self.assertEqual(self.fixture["surface"], "bare_earth_not_bridge_deck")
        self.assertEqual(self.fixture["license"], "Datenlizenz Deutschland – Zero 2.0")
        self.assertEqual(self.fixture["verticalDatum"], "DHHN2016 / NHN (EPSG:7837)")
        source_evidence = json.loads(Path("docs/stadium/koln-height-evidence.json").read_text())
        originals = [s for s in source_evidence["sources"]["sources"] if s["file"].endswith(".tif")]
        self.assertEqual(self.fixture["sourceRasters"], originals)
        self.assertLess(sum(p.stat().st_size for p in DIRECTORY.iterdir()), 150_000)
        for case in self.fixture["cases"]:
            with self.subTest(case=case["id"]):
                for point, expected in zip(case["profile"]["points"], case["utmCoordinates"]):
                    np.testing.assert_allclose(self.native.project(*point), expected, rtol=0, atol=1e-8)
                for kind, rows in self.actual[case["id"]].items():
                    expected = case["expected"][kind]
                    # Local witness station starts at zero. Original station is
                    # retained in the evidence to locate it in the full run.
                    if case["role"] != "complete_bridge_ground_profile":
                        rows = [{k: v for k, v in r.items() if k != "station"} for r in rows]
                        expected = [{k: v for k, v in r.items() if k != "station"} for r in expected]
                    assert_ground_equal(self, rows, expected)

    def test_real_alarm_values_and_locations_survive_without_bridge_exemptions(self):
        evidence = json.loads(Path("docs/stadium/koln-bridge-height-evidence.json").read_text())
        full = self.fixture["fullRun"]
        self.assertFalse(full["ok"])
        self.assertEqual(full["limits"], {"height": LIMITS, "roads": {
            "maxGradeErrorPP": 20., "maxGradeChangeErrorPP": 20.}})
        self.assertEqual(len(full["violations"]), evidence["nativeGroundRun"]["violationCount"])
        self.assertEqual(full["counts"], {"profiles": 975, "samples": 107928,
                                         "roadSlopes": 35191, "roadGradeChanges": 34276})
        witnessed = []
        quantile = []
        for case in self.fixture["cases"]:
            if case["role"] == "complete_bridge_ground_profile":
                continue
            rows = self.actual[case["id"]]
            alarm = case["alarm"]
            if case["role"] == "percentile_rank_witness":
                quantile.append((case, abs(rows["samples"][0]["errorMeters"])))
                continue
            kind, key = {
                "maxAbsMeters": ("samples", "errorMeters"),
                "maxGradeErrorPP": ("roadSlopes", "gradeErrorPP"),
                "maxGradeChangeErrorPP": ("roadGradeChanges", "gradeChangeErrorPP"),
            }[alarm["metric"]]
            value = max(abs(row[key]) for row in rows[kind])
            self.assertAlmostEqual(value, alarm["value"], places=10)
            self.assertGreater(value, alarm["limit"])
            witnessed.append(alarm)
        # Rank witnesses certify the historical linear percentile calculation;
        # they do NOT stand in for a new percentile over the entire population.
        self.assertEqual(len(quantile), 2)
        (low, a), (high, b) = sorted(quantile, key=lambda item: item[0]["rank"])
        rank = .95 * (low["population"] - 1)
        self.assertEqual(low["fractionalRank"], rank)
        self.assertEqual(low["population"], high["population"])
        self.assertEqual((low["rank"], high["rank"]), (int(np.floor(rank)), int(np.ceil(rank))))
        value = a + (b-a) * (rank-low["rank"])
        self.assertAlmostEqual(value, low["alarm"]["value"], places=10)
        self.assertGreater(value, low["alarm"]["limit"])
        witnessed.append(low["alarm"])
        self.assertCountEqual(witnessed, full["violations"])

    def test_corrupt_missing_or_changed_ground_fails_explicitly(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / "fixture"
            shutil.copytree(DIRECTORY, directory)
            path = directory / "ground.json"
            path.write_bytes(path.read_bytes() + b" ")
            with self.assertRaisesRegex(ValueError, "fixture hash"):
                load_ground(directory)
            shutil.copyfile(DIRECTORY / path.name, path)
            raster = directory / self.fixture["sources"][0]["file"]
            raster.write_bytes(raster.read_bytes() + b"changed")
            with self.assertRaisesRegex(ValueError, "Source hash"):
                load_ground(directory)
            raster.unlink()
            with self.assertRaises(FileNotFoundError):
                load_ground(directory)
        with self.assertRaisesRegex(ValueError, "nodata|coverage"):
            self.native(1100, 1100)  # no full terrain hidden in the little crops


class NativeProfileTests(TestCase):
    def fixture(self, directory, values=None, resolution=1):
        path = directory / "native.tif"
        values = np.array(values if values is not None else
                          [[10, 20, 30], [30, 40, 50], [50, 60, 70]], dtype="float32")
        with rasterio.open(path, "w", driver="GTiff", height=values.shape[0],
                           width=values.shape[1], count=1, dtype="float32", crs="EPSG:25832",
                           transform=from_origin(100, 200, resolution, resolution), nodata=-9999) as ds:
            ds.write(values, 1)
        return {"sources": [{"file": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}]}

    def test_pixel_centres_bilinear_native_and_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            manifest = self.fixture(directory)
            sample = NativeDGM(directory, manifest, lambda x, z: (x, z))
            self.assertEqual(sample(100.5, 199.5), 10)
            self.assertEqual(sample(101., 199.), 25)
            with self.assertRaisesRegex(ValueError, "coverage"):
                sample(100, 200)  # raster corner != first pixel centre
            manifest["sources"][0]["sha256"] = "changed"
            with self.assertRaisesRegex(ValueError, "hash"):
                NativeDGM(directory, manifest, lambda x, z: (x, z))
            for values in ([[10, -9999, 30], [30, 40, 50], [50, 60, 70]],
                           [[10, float("nan"), 30], [30, 40, 50], [50, 60, 70]]):
                manifest = self.fixture(directory, values)
                sample = NativeDGM(directory, manifest, lambda x, z: (x, z))
                with self.assertRaisesRegex(ValueError, "nodata"):
                    sample(101, 199)
            manifest = self.fixture(directory, resolution=2)
            with self.assertRaisesRegex(ValueError, "native 1 m"):
                NativeDGM(directory, manifest, lambda x, z: (x, z))
            with self.assertRaisesRegex(ValueError, "No native"):
                NativeDGM(directory, {"sources": []}, lambda x, z: (x, z))

    def test_model_registration_roundtrip_and_changed_center(self):
        theta = .73
        lon, lat = 6.8, 50.9
        ev = {"centerLonLat": [lon, lat], "axisThetaDegrees": np.degrees(theta)}
        p = {"frame": {"fieldC": [0, 0], "axisTheta": theta},
             "calibration": {"surroundingsAxes": {"NORD": "+z", "WEST": "-x"}}}
        sources = {"centerUTM": Transformer.from_crs(4326, 25832, always_xy=True).transform(lon, lat)}
        project = model_projection(p, ev, sources)
        back = Transformer.from_crs(25832, 4326, always_xy=True)
        for x, z in ((0, 0), (-200, 350), (400, -150)):
            a, b = back.transform(*project(x, z))
            scale = 6371000*np.pi/180
            east, north = (a-lon)*scale*np.cos(np.radians(lat)), (b-lat)*scale
            self.assertAlmostEqual(z, east*np.cos(theta)+north*np.sin(theta), places=5)
            self.assertAlmostEqual(x, east*np.sin(theta)-north*np.cos(theta), places=5)
        sources["centerUTM"] = [0, 0]
        with self.assertRaisesRegex(ValueError, "different pitch"):
            model_projection(p, ev, sources)


class DisplayProfileTests(TestCase):
    def test_bridge_uses_renderer_triangle_not_bilinear_and_maps_roads(self):
        p = {"frame": {"fieldC": [0, 0], "axisTheta": 0},
             "calibration": {"surroundingsAxes": {"NORD": "+z", "WEST": "-x"}},
             "surroundings": {"roads": [{"p": [[7, 11], [13, 17]]}],
                              "groundElevation": {"origin": [0, 0], "step": 20,
                                                  "rows": 2, "cols": 2,
                                                  "values": [0, 0, 0, 4], "source": "fixture"}}}
        result = renderer_samples(p, [[10, 10], [15, 5], [5, 15]])
        self.assertEqual(result["offsets"], [2, 1, 1])
        self.assertEqual(result["roads"], [[[-11, 7], [-17, 13]]])
        del p["surroundings"]["groundElevation"]
        with self.assertRaises(Exception):
            renderer_samples(p, [])

    def test_profiles_include_between_supports_and_all_road_vertices_without_edits(self):
        p = {"surroundings": {"groundElevation": {"origin": [-200, -200], "step": 20,
                                                  "cols": 21, "rows": 21}}}
        ev = {"features": {"roads": [{"osm": "way/1", "tags": {"highway": "footway", "bridge": "yes"}}]}}
        before = deepcopy((p, ev))
        profiles = profiles_for(p, [[[0, 0], [3, 1], [4, 8]]], ev)
        self.assertTrue(all((q["points"][0][1]+200) % 20 != 0
                            for q in profiles if q["id"].startswith("cross-x")))
        road = profiles[-1]
        self.assertIn([3, 1], road["points"])
        self.assertEqual(road["sourceTags"], {"bridge": "yes"})
        self.assertTrue(all(np.linalg.norm(np.array(a)-b) <= 2.0000001
                            for a, b in zip(road["points"], road["points"][1:])))
        self.assertEqual((p, ev), before)
        self.assertEqual(spaced([[0, 0], [0, 0], [2, 0]]), [[0, 0], [2, 0]])

    def test_native_ridge_between_supports_and_model_zones_are_not_hidden(self):
        profiles = [{"id": "way-fixture", "kind": "road",
                     "points": [[x, 0] for x in range(-10, 71, 2)]}]
        # Endpoints of the 20 m display cell agree; the native interior does not.
        native = lambda x, z: 100 + max(0, 4-abs(x-10))
        before = deepcopy(profiles)
        samples, slopes, changes = evaluate(profiles, [0]*41, native, 100, 0,
                                           box(-8, -8, 0, 8), box(-4, -2, -2, 2))
        report = summarize(samples, slopes, changes)
        self.assertFalse(report["ok"])
        self.assertEqual(report["zones"]["transition"]["maxAbsMeters"], 4)
        self.assertTrue(any(v["metric"] == "maxGradeErrorPP" for v in report["violations"]))
        self.assertTrue(any(v["metric"] == "maxGradeChangeErrorPP" for v in report["violations"]))
        self.assertEqual(report["zones"]["modelApron"]["maxAbsMeters"], 0)
        self.assertEqual(report["zones"]["measured"]["maxAbsMeters"], 0)
        self.assertTrue(all(not (s["fromXZ"][0] < -4 and s["xz"][0] > -2) for s in slopes))
        self.assertEqual(profiles, before)

    def test_each_zone_fails_its_fixed_height_limits_and_equality_passes(self):
        for zone in LIMITS:
            samples = [{"zone": name, "kind": "cross", "errorMeters": 0, "xz": [0, 0]}
                       for name in LIMITS]
            samples[list(LIMITS).index(zone)]["errorMeters"] = 4
            report = summarize(samples, [], [])
            self.assertFalse(report["ok"])
            self.assertEqual({v["zone"] for v in report["violations"]}, {zone})
        samples = [{"zone": name, "kind": "cross", "errorMeters": LIMITS[name]["p95AbsMeters"]}
                   for name in LIMITS]
        self.assertTrue(summarize(samples, [], [])["ok"])
        with self.assertRaisesRegex(ValueError, "no visible samples"):
            summarize([], [], [])

    def test_cli_exit_codes_and_written_failure_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "report.json"
            for ok, expected in ((True, 0), (False, 1)):
                with patch("scripts.check_koln_height_profiles.run", return_value={"ok": ok}):
                    self.assertEqual(main(["--output", str(output)]), expected)
                    self.assertEqual(json.loads(output.read_text())["ok"], ok)
            with patch("scripts.check_koln_height_profiles.run", side_effect=ValueError("missing DGM")):
                self.assertEqual(main(["--output", str(output)]), 2)
                self.assertEqual(json.loads(output.read_text())["status"], "evidence_error")

    def test_full_offline_pipeline_with_native_tiff_and_actual_renderer(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            lon, lat = 6.8, 50.9
            east, north = Transformer.from_crs(4326, 25832, always_xy=True).transform(lon, lat)
            tif = directory / "native.tif"
            with rasterio.open(tif, "w", driver="GTiff", height=600, width=600, count=1,
                               dtype="float32", crs="EPSG:25832",
                               transform=from_origin(east-300, north+300, 1, 1), nodata=-9999) as ds:
                ds.write(np.full((600, 600), 100, dtype="float32"), 1)
            native_sha = hashlib.sha256(tif.read_bytes()).hexdigest()
            (directory / "raw.json").write_text("{}")
            p = {"frame": {"fieldC": [0, 0], "axisTheta": 0},
                 "calibration": {"surroundingsAxes": {"NORD": "+z", "WEST": "-x"}},
                 "surroundings": {
                     "groundLevel": 0, "groundCutout": [[-2, -2], [2, -2], [2, 2], [-2, 2]],
                     "groundElevation": {"origin": [-200, -200], "step": 20, "cols": 21,
                                         "rows": 21, "values": [0]*441, "source": "native test"},
                     "heightEvidence": {"terrainReferenceNHN": 100},
                     "roads": [{"p": [[-150, -10], [150, -10]]}]}}
            ev = {"centerLonLat": [lon, lat], "axisThetaDegrees": 0,
                  "rawSha256": hashlib.sha256(b"{}").hexdigest(),
                  "mappedStadiumModelCoordinates": [[-10, -10], [10, -10], [10, 10], [-10, 10]],
                  "features": {"roads": [{"osm": "way/1", "tags": {"highway": "footway"}}]}}
            sources = {"centerUTM": [east, north], "sources": [{"file": tif.name, "sha256": native_sha}]}
            paths = [directory / name for name in ("presentation.json", "evidence.json", "sources.json")]
            for path, value in zip(paths, ({"presentation": p}, ev, sources)):
                path.write_text(json.dumps(value))
            before = [path.read_bytes() for path in paths] + [tif.read_bytes()]
            report = run(*paths)
            self.assertTrue(report["ok"])
            self.assertTrue(all(report["zones"][zone]["count"] > 0 for zone in LIMITS))
            self.assertEqual([path.read_bytes() for path in paths]+[tif.read_bytes()], before)
            for invalid in (None, [{"index": 0, "osm": "way/1", "deckSource": "DGM1"}]):
                p["surroundings"]["heightEvidence"]["bridges"] = invalid
                paths[0].write_text(json.dumps({"presentation": p}))
                with self.assertRaisesRegex(ValueError, "Bridge evidence differs"):
                    run(*paths)
            del p["surroundings"]["heightEvidence"]["bridges"]
            p["surroundings"]["heightEvidence"]["terrainReferenceNHN"] = 99
            paths[0].write_text(json.dumps({"presentation": p}))
            with self.assertRaisesRegex(ValueError, "reference differs"):
                run(*paths)
