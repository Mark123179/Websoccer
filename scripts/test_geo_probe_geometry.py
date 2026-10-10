"""Read-only regression checks; no Django database or application writes."""
import json
import unittest
from pathlib import Path

import numpy as np

from geo_probe_geometry import (
    frame_from_osm, ground_rays, lonlat_to_scene, polygon_mask,
    project_ground, scene_to_lonlat,
)

ROOT = Path(__file__).resolve().parents[1]


class GeoProbeGeometryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.camera = json.loads((ROOT /
            "generated-artifacts/stadium-main-stand-back-probe/camera_exact.json").read_text())
        cls.frame = json.loads((ROOT /
            "generated-artifacts/dortmund-site-study/source.json").read_text())["frame"]

    def test_half_turn_changes_map_not_camera(self):
        before = scene_to_lonlat(self.frame, 10, 110, False)
        after = scene_to_lonlat(self.frame, -10, -110, True)
        self.assertEqual(before, after)
        east = scene_to_lonlat(self.frame, 0, 110, True)
        west = scene_to_lonlat(self.frame, 0, 110, False)
        self.assertGreater(east[0], west[0])

    def test_map_roundtrip(self):
        for turn in (True, False):
            for point in ((0, 0), (52.5, 34), (-200, 120)):
                lon, lat = scene_to_lonlat(self.frame, *point, turn)
                np.testing.assert_allclose(
                    lonlat_to_scene(self.frame, lon, lat, turn), point, atol=1e-8)

    def test_pixel_center_ground_roundtrip(self):
        ground = ground_rays(self.camera)
        width, _ = self.camera["format"]
        for index in (0, width-1, len(ground[0])//2, len(ground[0])-1):
            x, y = project_ground(self.camera, ground[0, index], ground[2, index])
            np.testing.assert_allclose((x, y), (index % width+.5, index//width+.5), atol=1e-9)

    def test_field_polygon_matches_exported_corners(self):
        points = [(52.5, -34), (-52.5, -34), (-52.5, 34), (52.5, 34)]
        for point, corner in zip(points, self.camera["corners"]):
            np.testing.assert_allclose(project_ground(self.camera, *point),
                                       [corner["x"], corner["y"]], atol=1e-10)
        mask = polygon_mask(self.camera, points)
        self.assertEqual(mask.shape, (940, 1880))
        self.assertGreater(int(mask.sum()), 400000)

    def test_elversberg_camera_side_is_northeast(self):
        osm = json.loads((ROOT / "stadium_editor/blueprints/v2/elversberg.json").read_text())
        frame = frame_from_osm(osm, 1154632806, 31339206)
        center = scene_to_lonlat(frame, 0, 0, True)
        camera = scene_to_lonlat(frame, 0, 110, True)
        self.assertGreater(camera[0], center[0])
        self.assertGreater(camera[1], center[1])


if __name__ == "__main__":
    unittest.main()
