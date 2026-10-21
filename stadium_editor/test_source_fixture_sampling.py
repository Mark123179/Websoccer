from copy import deepcopy
from unittest import TestCase

import numpy as np

from stadium_editor.source_fixture_sampling import verified_geometry_fixtures


class SourceFixtureSamplingTests(TestCase):
    def setUp(self):
        points = np.array([[-1, 22, -1], [1, 22, -1], [-1, 20, 1]], dtype="<f4")
        uv = np.array([[0, 0], [1, 0], [0, 1]], dtype="<f4")
        indices = np.array([0, 1, 2], dtype="<u4")
        self.binary = points.tobytes() + uv.tobytes() + indices.tobytes()
        self.meshes = [{
            "name": "actual-tower", "pathId": "123", "vertexCount": 3,
            "positionOffset": 0, "uvOffset": points.nbytes,
            "parts": [{"material": "verified-emitter-atlas", "texture": "lamps.webp",
                       "indexOffset": points.nbytes + uv.nbytes, "indexCount": 3}],
        }]
        self.sample = {"mesh": "actual-tower", "material": "verified-emitter-atlas",
                       "triangle": 0, "uv": [.25, .25]}

    def test_position_and_direction_come_from_actual_source_triangle(self):
        result = verified_geometry_fixtures(self.meshes, self.binary, [self.sample])
        np.testing.assert_allclose(result[0]["position"], [-.5, 21.5, -.5])
        np.testing.assert_allclose(result[0]["direction"], [0, -2 ** -.5, -2 ** -.5])
        self.assertEqual(result[0]["meshDistance"], 0)
        self.assertEqual(result[0]["sourceGeometry"]["mesh"], "actual-tower")

    def test_samples_outside_triangle_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "outside"):
            verified_geometry_fixtures(self.meshes, self.binary,
                                       [{**self.sample, "uv": [.9, .9]}])

    def test_untextured_or_wrong_material_is_rejected(self):
        meshes = deepcopy(self.meshes)
        meshes[0]["parts"][0]["texture"] = None
        with self.assertRaisesRegex(ValueError, "textured"):
            verified_geometry_fixtures(meshes, self.binary, [self.sample])

    def test_duplicate_samples_are_not_counted_twice(self):
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            verified_geometry_fixtures(self.meshes, self.binary, [self.sample, self.sample])

    def test_upward_source_face_is_rejected(self):
        binary = self.binary[:-12] + np.array([0, 2, 1], dtype="<u4").tobytes()
        with self.assertRaisesRegex(ValueError, "downward"):
            verified_geometry_fixtures(self.meshes, binary, [self.sample])

    def test_nonfinite_samples_and_empty_evidence_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "outside"):
            verified_geometry_fixtures(self.meshes, self.binary,
                                       [{**self.sample, "uv": [float("nan"), .25]}])
        with self.assertRaisesRegex(ValueError, "No reviewed"):
            verified_geometry_fixtures(self.meshes, self.binary, [])

    def test_sampling_does_not_mutate_geometry(self):
        before = deepcopy(self.meshes)
        verified_geometry_fixtures(self.meshes, self.binary, [self.sample])
        self.assertEqual(self.meshes, before)
