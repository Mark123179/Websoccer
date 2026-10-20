"""Source-light evidence gates; synthetic inputs, no DB, storage or Unity assets."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

import numpy as np

from scripts.audit_hsv_lights import audit
from scripts.stadium_light_surfaces import (
    calibrate_intensity, closest_surface, rejection_reasons, select_representatives,
)


class LampSurfaceTests(TestCase):
    def test_interior_is_near_even_when_all_vertices_are_far(self):
        face = [[[0, 20, 0], [20, 20, 0], [0, 20, 20]]]
        distance, point, index = closest_surface([5, 21, 5], face)
        self.assertEqual((distance, point, index), (1, [5, 20, 5], 0))
        self.assertGreater(np.linalg.norm(np.array(face[0])-[5, 21, 5], axis=1).min(), 2)

    def test_surface_does_not_inflate_the_2m_tolerance(self):
        face = [[[0, 20, 0], [20, 20, 0], [0, 20, 20]]]
        for height, accepted in ((22, True), (22.0001, False)):
            distance, _, _ = closest_surface([5, height, 5], face)
            reasons = rejection_reasons([5, height, 5], [0, -1, 0], distance)
            self.assertEqual(not reasons, accepted)

    def test_outside_projection_checks_closed_edges_not_infinite_plane(self):
        distance, point, _ = closest_surface([12, 20, 12],
                                            [[[0, 20, 0], [20, 20, 0], [0, 20, 20]]])
        self.assertAlmostEqual(distance, 8**.5)
        self.assertEqual(point, [10, 20, 10])

    def test_nearest_face_and_exact_vertex(self):
        face = [[0, 20, 0], [1, 20, 0], [0, 20, 1]]
        distance, point, index = closest_surface([0, 30, 0], [face, np.array(face)+[0, 10, 0]])
        self.assertEqual((distance, point, index), (0, [0, 30, 0], 1))

    def test_collapsed_faces_remain_segments_or_points(self):
        for face, expected in (
            ([[0, 20, 0], [10, 20, 0], [10, 20, 0]], (1, [5, 20, 0])),
            ([[5, 20, 0]]*3, (1, [5, 20, 0])),
        ):
            distance, point, _ = closest_surface([5, 21, 0], [face])
            self.assertEqual((distance, point), expected)

    def test_nonfinite_and_empty_inputs_fail_explicitly(self):
        for triangles in ([], [[[0, 0, 0], [1, 0, 0], [0, np.nan, 0]]]):
            with self.assertRaises(ValueError):
                closest_surface([0, 0, 0], triangles)

    def test_distance_is_rigid_frame_invariant(self):
        triangles = np.array([[[0, 20, 0], [20, 20, 0], [0, 20, 20]]])
        p = np.array([5, 21, 5])
        rotation = np.array([[0, 0, 1], [0, 1, 0], [-1, 0, 0]])
        translation = np.array([100, -5, 80])
        d, point, _ = closest_surface(p, triangles)
        transformed, closest, _ = closest_surface(p@rotation.T+translation,
                                                  triangles@rotation.T+translation)
        self.assertAlmostEqual(d, transformed)
        np.testing.assert_allclose(np.array(point)@rotation.T+translation, closest)

    def test_all_original_rejection_gates_are_independent(self):
        self.assertEqual(rejection_reasons([100, 10, 0], [0, -1, 0], 5),
                         ["below_roof_18m", "lamp_distance_over_2m", "axis_misses_pitch_envelope"])
        self.assertEqual(rejection_reasons([0, 30, 0], [0, 1, 0], 0), ["not_downward"])
        self.assertEqual(rejection_reasons([0, 30, 0], [0, -.05, 0], 0), ["not_downward"])


class RepresentativeTests(TestCase):
    AXES = {"+x": "WEST", "-x": "OST", "+z": "SUED", "-z": "NORD"}

    def lights(self):
        rows = []
        for axis in ("x", "z"):
            for sign in (-1, 1):
                for along in range(-30, 31, 10):
                    point = [sign*70, 35, along] if axis == "x" else [along, 35, sign*90]
                    rows.append({"id": str(len(rows)), "position": point,
                                 "direction": [0, -1, 0], "intensity": 60, "angle": 147})
        return rows

    def test_up_to_three_per_side_twelve_total_and_exact_source_provenance(self):
        rows = self.lights()
        selected = select_representatives(rows, self.AXES)
        self.assertEqual(len(selected), 12)
        for stand in self.AXES.values():
            self.assertEqual(sum(s["stand"] == stand for s in selected), 3)
        by_id = {r["id"]: r for r in rows}
        for s in selected:
            for field in ("position", "direction", "angle", "intensity"):
                self.assertEqual(s[field], by_id[s["id"]][field])
            self.assertTrue(s["representedIds"])
            self.assertNotIn("representedIds", by_id[s["id"]])  # input not mutated
        represented = [id for s in selected for id in s["representedIds"]]
        self.assertEqual(len(represented), len(set(represented)))
        self.assertEqual(set(represented), set(by_id))

    def test_input_order_does_not_change_selection_or_partition(self):
        rows = self.lights()
        self.assertEqual(select_representatives(rows, self.AXES),
                         select_representatives(rows[::-1], self.AXES))

    def test_coincident_components_do_not_create_fake_positions_or_empty_groups(self):
        rows = [{"id": str(i), "position": [70, 35, 0]} for i in range(5)]
        selected = select_representatives(rows, self.AXES)
        self.assertEqual(len(selected), 1)
        self.assertEqual(set(selected[0]["representedIds"]), {str(i) for i in range(5)})

    def test_existing_review_package_cannot_be_overwritten(self):
        with TemporaryDirectory() as root:
            sentinel = Path(root) / "manifest.json"
            sentinel.write_text("reviewed")
            with self.assertRaisesRegex(ValueError, "never overwrite"):
                audit(Path(root))
            self.assertEqual(sentinel.read_text(), "reviewed")

    def test_browser_calibration_preserves_source_and_is_idempotent(self):
        fixture = {"sourceIntensity": 60, "intensity": 60, "position": [70, 35, 0],
                   "direction": [-1, -1, 0], "angle": 147, "range": 180}
        once = calibrate_intensity([fixture], 8)
        self.assertEqual(once, calibrate_intensity(once, 8))
        self.assertEqual(once[0]["intensity"], 480)
        self.assertEqual(once[0]["sourceIntensity"], 60)
        for field in ("position", "direction", "angle", "range"):
            self.assertEqual(once[0][field], fixture[field])
        self.assertEqual(fixture["intensity"], 60)

    def test_browser_calibration_rejects_missing_source_and_invalid_scale(self):
        for scale in (0, -1, float("nan"), float("inf"), 129, True):
            with self.assertRaises(ValueError):
                calibrate_intensity([{"sourceIntensity": 60}], scale)
        with self.assertRaises(KeyError):
            calibrate_intensity([{"intensity": 480}], 8)
