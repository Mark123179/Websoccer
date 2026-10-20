"""Offline guards for HSV artwork, without storage or game-data writes."""
import json

from django.test import SimpleTestCase
import numpy as np

from scripts.correct_hsv_seating import artwork, OUT, digest


class HSVSeatingArtworkTests(SimpleTestCase):
    def test_diamond_has_symmetric_white_border_black_ring_and_white_core(self):
        z = np.array([0., 0., 0., 10.5, -10.5, 15.])
        y = np.array([5.8, 7.5, 8.6, 5.8, 5.8, 5.8])
        white, black = artwork(z, y)
        self.assertTrue(white[0])
        self.assertTrue(black[1])
        self.assertTrue(white[2])
        self.assertTrue(white[3])
        self.assertTrue(white[4])
        self.assertFalse(white[5] or black[5])

    def test_empty_seats_are_not_an_accidental_white_backdrop(self):
        white, black = artwork(np.array([20., -20., 0.]), np.array([30., 30., 23.]))
        self.assertFalse(white.any())
        self.assertFalse(black.any())

    def test_photo_has_two_upper_diamonds(self):
        white, black = artwork(np.array([-43., 43.]), np.array([28.3, 28.3]))
        self.assertTrue(white.all())
        self.assertFalse(black.any())

    def test_prepared_package_changes_only_the_crowd_texture(self):
        if not (OUT / "baseline-manifest.json").exists():
            self.skipTest("Optional locally prepared HSV review package is absent")
        baseline = json.loads((OUT / "baseline-manifest.json").read_bytes())
        candidate = json.loads((OUT / "osm-fresh/manifest.json").read_bytes())
        for field in baseline:
            if field not in ("assetVersion", "assetSha256"):
                self.assertEqual(candidate[field], baseline[field], field)
        changes = [key for key in baseline["assetSha256"]
                   if baseline["assetSha256"][key] != candidate["assetSha256"][key]]
        self.assertEqual(changes, ["texture--8009233366261755537.webp"])
        for name, checksum in candidate["assetSha256"].items():
            self.assertEqual(digest((OUT / "source-export" / name).read_bytes()), checksum, name)
