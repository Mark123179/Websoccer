"""BVB read-only presentation, club scope and physical source parity."""
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase
from django.urls import reverse

from game.stadium_scene_context import ticker_scene_context
from stadium_editor.dortmund_runtime import runtime_presentation


class DortmundSharedSceneTests(SimpleTestCase):
    def setUp(self):
        self.stadium = SimpleNamespace(club_id=3, capacity_total=81365, name="Signal Iduna Park")
        self.geometry = {
            "meta": {"fieldC": [20, 40], "axisTheta": .2},
            "blocks": [{"id": 9, "stand": "NORD"}],
            "surroundings": {"source": "BVB mapped source", "trees": [[22, 42]],
                "roads": [{"p": [[1, 2], [3, 4]], "w": 4}],
                "green": [[[0, 0], [8, 0], [0, 8]]],
                "buildings": [{"poly": [[0, 0], [4, 0], [0, 4]], "h": 12, "id": "osm-7"}]},
        }

    def test_current_map_and_frame_are_exact_and_inputs_are_not_mutated(self):
        before = deepcopy(self.geometry)
        design = {"palette": ["#000000", "#ffee00"], "blocks": [{"id": 9, "rle": [[4, 1]]}]}
        result = runtime_presentation(self.stadium, self.geometry, design)
        self.assertEqual(self.geometry, before)
        self.assertEqual(result["frame"], before["meta"])
        for key in ("trees", "green", "roads", "source"):
            self.assertEqual(result["surroundings"][key], before["surroundings"][key])
        self.assertEqual(result["surroundings"]["buildingHeights"], [12])
        self.assertEqual(result["surroundings"]["buildingIds"], ["osm-7"])
        self.assertEqual(result["designColors"], {"NORD": "#ffee00"})
        self.assertEqual(result["capacity"], 81365)
        self.assertNotIn("imageBackground", result)

    def test_bvb_viewer_points_to_its_own_live_scene_without_photos(self):
        club = SimpleNamespace(pk=3, name="BVB", fm_inside_id=907, stadium=self.stadium)
        with patch("game.stadium_scene_context.StadiumGeometry.objects") as rows:
            rows.filter.return_value.exists.return_value = True
            result = ticker_scene_context(club)
        self.assertEqual(result["renderer"], "dortmund-spatial")
        self.assertEqual(result["sceneUrl"], reverse("stadium_live_scene", args=[3]))
        self.assertTrue(result["spatial"])
        self.assertNotIn("imageBackground", result)

    def test_other_clubs_do_not_receive_bvb_and_missing_scene_fails_closed(self):
        self.assertIsNone(ticker_scene_context(SimpleNamespace(fm_inside_id=915)))
        club = SimpleNamespace(pk=3, name="BVB", fm_inside_id=907, stadium=self.stadium)
        with patch("game.stadium_scene_context.StadiumGeometry.objects") as rows:
            rows.filter.return_value.exists.return_value = False
            self.assertIsNone(ticker_scene_context(club))
