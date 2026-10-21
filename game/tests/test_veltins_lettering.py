"""Offline lettering coverage; no dependence on generated review assets."""
from copy import deepcopy
from unittest import TestCase

import numpy as np
from PIL import Image

from scripts import correct_veltins_lettering as correction


class VeltinsLetteringTests(TestCase):
    def test_glyphs_stay_in_original_atlas_registration(self):
        mask = correction.lettering_mask()
        rows, columns = np.where(mask > .5)
        self.assertEqual(mask.shape, (2048, 2048))
        self.assertGreaterEqual(columns.min(), 155 * 4)
        self.assertLess(columns.max(), 371 * 4)
        self.assertGreaterEqual(rows.min(), 109 * 4)
        self.assertLess(rows.max(), 141 * 4)

    def test_artwork_is_deterministic_with_separate_letter_components(self):
        first = correction.lettering_mask()
        self.assertTrue(np.array_equal(first, correction.lettering_mask()))
        occupied = (first > .5).any(axis=0)
        starts = occupied & ~np.r_[False, occupied[:-1]]
        self.assertEqual(starts.sum(), 11)

    def test_only_original_letter_patch_is_painted_and_geometry_unchanged(self):
        vertices = np.array([[-50, 1, -54], [-50, 12, -54],
                             [-50, 12, 54], [-50, 1, 54]], dtype="<f4")
        uv = np.array([[.2, .2], [.8, .2], [.8, .8], [.2, .8]], dtype="<f4")
        indices = np.array([0, 1, 2, 0, 2, 3], dtype="<u4")
        binary = vertices.tobytes() + uv.tobytes() + indices.tobytes()
        mesh = {"name": "C_front1_C1-FolkHome", "vertexCount": 4, "positionOffset": 0,
                "uvOffset": len(vertices.tobytes()), "parts": [{
                    "texture": correction.TEXTURE, "indexCount": 6,
                    "indexOffset": len(vertices.tobytes()) + len(uv.tobytes()),
                }]}
        manifest = {"meshes": [mesh]}
        before = deepcopy(manifest)
        image = Image.new("RGB", (512, 512), (10, 20, 30))
        corrected, painted = correction.corrected_texture(manifest, binary, image)
        pixels = np.asarray(corrected)
        self.assertEqual(manifest, before)
        self.assertGreater(painted.sum(), 70_000)
        self.assertTrue(np.all(pixels[~painted] == [10, 20, 30]))
        self.assertTrue(np.any(np.all(pixels[painted] == [241, 244, 247], axis=1)))

    def test_other_stands_cannot_be_selected(self):
        with self.assertRaisesRegex(ValueError, "Insufficient"):
            correction.corrected_texture({"meshes": [{"name": "C_back1_C1-FolkHome"}]},
                                         b"", Image.new("RGB", (512, 512)))
