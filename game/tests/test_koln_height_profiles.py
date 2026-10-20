"""Offline regression fixtures for display-vs-native height alarms."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
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
