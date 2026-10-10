"""Offline regression tests; never touch Django or live club data."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from verify_elversberg_blueprint_study import CAMERA, canonical_pitch, verify


class BlueprintStudyVerificationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        contract = json.loads(CAMERA.read_text())
        self.size = contract["format"]
        self.camera = contract["states"][0]
        self.pitch = canonical_pitch(self.size, self.camera["corners"])
        # Include a wider boundary, as an actual field-protection mask does.
        from PIL import ImageDraw
        mask = Image.new("L", tuple(self.size))
        ImageDraw.Draw(mask).polygon(
            [(p["x"], p["y"]) for p in self.camera["corners"]], fill=255)
        mask.save(self.directory / "field.png")
        states = []
        for roof in (True, False):
            base = np.full((self.size[1], self.size[0], 3), 24 + int(roof), dtype=np.uint8)
            baseline = f"baseline-{roof}.png"
            Image.fromarray(base).save(self.directory / baseline)
            for style, tint in (("spatial", 42), ("flat", 32)):
                rendered = base.copy()
                rendered[~(np.asarray(mask) > 127)] = [8, tint, 40]
                name = f"{style}-{roof}.png"
                Image.fromarray(rendered).save(self.directory / name)
                states.append({
                    "style": style, "roof": roof, "image": name,
                    "baseline": baseline, "fieldMask": "field.png",
                    **copy.deepcopy(self.camera),
                })
        self.manifest = {"format": self.size, "camera": self.camera, "states": states}
        self.save_manifest()

    def save_manifest(self):
        (self.directory / "manifest.json").write_text(json.dumps(self.manifest))

    def test_valid_four_state_comparison(self):
        report = verify(self.directory)
        self.assertEqual(report["status"], "passed")
        self.assertEqual(len(report["states"]), 4)
        self.assertTrue(all(s["changed_protected_pixels"] == 0 for s in report["states"]))

    def test_camera_drift_is_rejected(self):
        self.manifest["states"][0]["projection"][0] += .001
        self.save_manifest()
        with self.assertRaisesRegex(ValueError, "abweichende Kamera"):
            verify(self.directory)

    def test_missing_variant_is_rejected(self):
        self.manifest["states"].pop()
        self.save_manifest()
        with self.assertRaisesRegex(ValueError, "vier"):
            verify(self.directory)

    def test_pitch_pixel_change_is_rejected(self):
        path = self.directory / self.manifest["states"][0]["image"]
        with Image.open(path) as image:
            pixels = np.array(image)
        y, x = np.argwhere(self.pitch)[len(np.argwhere(self.pitch)) // 2]
        pixels[y, x] = [255, 0, 255]
        Image.fromarray(pixels).save(path)
        with self.assertRaisesRegex(ValueError, "Feldpixel verändert"):
            verify(self.directory)

    def test_empty_mask_is_rejected(self):
        Image.new("L", tuple(self.size)).save(self.directory / "field.png")
        with self.assertRaisesRegex(ValueError, "vollständige Spielfeld"):
            verify(self.directory)

    def test_thumbnail_instead_of_native_png_is_rejected(self):
        path = self.directory / self.manifest["states"][0]["image"]
        Image.new("RGB", (940, 470)).save(path)
        with self.assertRaisesRegex(ValueError, "natives PNG"):
            verify(self.directory)

    def test_transparent_final_image_is_rejected(self):
        path = self.directory / self.manifest["states"][0]["image"]
        Image.new("RGBA", tuple(self.size), (0, 0, 0, 100)).save(path)
        with self.assertRaisesRegex(ValueError, "deckend"):
            verify(self.directory)

    def test_escape_from_output_directory_is_rejected(self):
        self.manifest["states"][0]["image"] = "../outside.png"
        self.save_manifest()
        with self.assertRaisesRegex(ValueError, "verlässt"):
            verify(self.directory)


if __name__ == "__main__":
    unittest.main()
