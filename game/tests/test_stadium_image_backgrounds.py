from unittest.mock import patch

from django.test import SimpleTestCase
from PIL import Image

from stadium_editor.image_backgrounds import ROOT, load_image_background


class StadiumImageBackgroundTests(SimpleTestCase):
    def test_pair_is_club_bound_and_loader_does_not_share_mutable_state(self):
        config = load_image_background(907)
        self.assertEqual(config["referenceSize"], [1024, 512])
        for profile in ("day", "night"):
            image = Image.open(ROOT / "907" / f"{profile}.webp")
            self.assertEqual(list(image.size), config["images"][profile]["size"])
            self.assertEqual(image.width / image.height, config["aspect"])
            self.assertIn(f"/907/{profile}.webp", config["images"][profile]["url"])
        config["pitchCorners"].clear()
        self.assertEqual(len(load_image_background(907)["pitchCorners"]), 4)

    def test_missing_club_or_files_fail_without_dortmund_fallback(self):
        for value in (915, "907", True, None, "../907"):
            with self.assertRaises(ValueError):
                load_image_background(value)
        with patch("pathlib.Path.is_file", return_value=False):
            with self.assertRaises(OSError):
                load_image_background(907)
