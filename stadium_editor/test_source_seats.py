from copy import deepcopy
from unittest import TestCase

from stadium_editor.image_validation import InvalidImageData, normalize_design_payload
from stadium_editor.seat_design import seat_mode, source_seat_design


class SourceSeatContractTests(TestCase):
    def setUp(self):
        self.geometry = {"blocks": [
            {"id": 9, "tier": "MITTEL", "z0": 11.5, "z1": 20,
             "rows": 2, "seats": 3, "quad": [[0, 2], [2, 2], [2, 1], [0, 1]]},
        ]}

    def test_legacy_paint_stays_custom_but_no_design_is_original(self):
        self.assertEqual(seat_mode({}), "original")
        self.assertEqual(seat_mode({"blocks": [{"id": 9}]}), "custom")

    def test_mode_switch_keeps_painted_rows_and_source_geometry_separate(self):
        design = {"seat_mode": "original", "palette": ["#666666", "#ffd400"],
                  "blocks": [{"id": 9, "rle": [[3, 0], [3, 1]]}]}
        before = deepcopy(design)
        source = source_seat_design(self.geometry, design)
        self.assertEqual(source["mode"], "original")
        self.assertEqual(source["blocks"][0]["tier"], "MITTEL")
        self.assertEqual(source["blocks"][0]["rle"], [[3, 0], [3, 1]])
        source["mode"] = "custom"
        source["blocks"][0]["rle"][1][1] = 0
        self.assertEqual(design, before)

    def test_invalid_mode_cannot_be_persisted(self):
        with self.assertRaises(InvalidImageData):
            normalize_design_payload({"seat_mode": "unknown",
                                      "palette": ["#666666"], "blocks": []})

    def test_mode_preserved_by_normalizer(self):
        normalized = normalize_design_payload({
            "seat_mode": "original", "palette": ["#666666"],
            "blocks": [{"id": 9, "rle": [[6, 0]]}],
        })
        self.assertEqual(normalized["seat_mode"], "original")
