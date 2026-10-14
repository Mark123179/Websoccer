from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from stadium_editor.dortmund_runtime import runtime_presentation
from stadium_editor.surroundings_ground import validated_ground_fields


class SurroundingsGroundTests(SimpleTestCase):
    hole = [[-10, -10], [10, -10], [10, 10], [-10, 10]]

    def test_valid_and_closed_polygon(self):
        data = {"groundLevel": 7.7, "groundCutout": self.hole + [self.hole[0]]}
        before = deepcopy(data)
        self.assertEqual(validated_ground_fields(data),
                         {"groundLevel": 7.7, "groundCutout": self.hole})
        self.assertEqual(data, before)
        self.assertEqual(validated_ground_fields({}), {})
        self.assertEqual(validated_ground_fields({"groundLevel": 0}), {"groundLevel": 0})

    def test_invalid_declarations(self):
        for data in [
            {"groundCutout": self.hole},
            *({"groundLevel": v} for v in [None, True, "7.7", float("inf"), float("nan"), 31, 7.7]),
            *({"groundLevel": 7.7, "groundCutout": p} for p in [
                [[0, 0], [1, 1], [2, 2]],
                [[0, 0], [1, 1], [0, 1], [1, 0]],
                [[0, 0], [1, 0], [1, 1], [0, 0], [0, 1]],
                [[0, 0], [2, 0], [1, 0], [1, 1], [0, 1]],
                [[0, 0], [True, 1], [1, 0]],
            ]),
        ]:
            with self.subTest(data=data), self.assertRaises(ValueError):
                validated_ground_fields(data)

    @patch("stadium_editor.dortmund_runtime.with_dortmund_mapped_trees",
           side_effect=lambda geometry, **kwargs: geometry)
    def test_projection_is_opt_in_read_only_and_has_no_club_specific_switch(self, _):
        geometry = {"meta": {}, "blocks": [], "bg": {"green": [self.hole]},
                    "surroundings": {"groundLevel": 7.7, "groundCutout": self.hole}}
        before = deepcopy(geometry)
        stadium = SimpleNamespace(club_id=999, capacity_total=30660)
        data = runtime_presentation(stadium, geometry, {})
        self.assertEqual(data["surroundings"]["groundLevel"], 7.7)
        self.assertEqual(data["surroundings"]["groundCutout"], self.hole)
        self.assertEqual(data["surroundings"]["green"], [self.hole])
        self.assertEqual(geometry, before)
        data["surroundings"]["groundCutout"][0][0] = 999
        self.assertEqual(geometry, before)
        del geometry["surroundings"]
        data = runtime_presentation(stadium, geometry, {})
        self.assertNotIn("groundLevel", data["surroundings"])
        self.assertNotIn("groundCutout", data["surroundings"])
