"""Offline height provenance and runtime opt-in contract (no external services)."""
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase
from shapely.geometry import box

from scripts.refine_koln_heights import select_height
from stadium_editor.surroundings_ground import validated_ground_fields
from stadium_editor.package_preflight import inspect_package
from stadium_editor.unity_runtime import unity_presentation


class MeasuredGroundTests(SimpleTestCase):
    def setUp(self):
        self.grid = {"origin": [-600, -600], "step": 100, "cols": 13, "rows": 13,
                     "values": [0] * 169, "source": "Explicit test evidence"}
        self.data = {"groundLevel": 2.1, "groundCutout": [[-10,-10],[10,-10],[10,10],[-10,10]],
                     "groundElevation": self.grid,
                     "heightQuality": "mixed, individual evidence", "heightEvidence": {"buildings": []}}

    def test_validation_and_preflight_reject_bad_grid_without_fallback(self):
        before = deepcopy(self.data)
        result = validated_ground_fields(self.data)
        self.assertEqual(result["groundElevation"], self.grid)
        result["groundElevation"]["values"][0] = 99
        self.assertEqual(self.data, before)
        for field, value in [("source",""),("cols",True),("cols",258),("step",False),
                             ("values",[0]),("values",[float("nan")]*169)]:
            bad = {**self.data,"groundElevation":{**self.grid,field:value}}
            with self.subTest(field=field,value=str(value)[:20]):
                with self.assertRaises(ValueError):
                    validated_ground_fields(bad)
                self.assertFalse(inspect_package(bad)["ok"])
        self.assertFalse(inspect_package({"groundElevation":self.grid})["ok"])

    @patch("stadium_editor.dortmund_runtime.with_dortmund_mapped_trees",
           side_effect=lambda g, **kwargs:g)
    def test_runtime_retains_heights_provenance_and_does_not_mutate_geometry(self,_):
        geometry = {"meta":{},"blocks":[],"surroundings":self.data}
        before = deepcopy(geometry)
        stadium = SimpleNamespace(club_id=999,club=SimpleNamespace(fm_inside_id=916),capacity_total=50000)
        manifest = {"clubFmiId":916,"assetVersion":"unchanged","stadiumName":"Köln",
                    "sourceSha256":"test","calibration":{}}
        result = unity_presentation(stadium,geometry,{},manifest)
        self.assertEqual(result["surroundings"]["groundElevation"],self.grid)
        self.assertEqual(result["surroundings"]["heightQuality"],self.data["heightQuality"])
        self.assertEqual(result["surroundings"]["heightEvidence"],self.data["heightEvidence"])
        self.assertEqual(geometry,before)

    def test_only_unique_symmetric_laser_matches_are_accepted(self):
        footprint = box(0,0,10,10)
        candidate = {"footprint":footprint,"height":7.62,"heightUnit":"urn:adv:uom:m",
                     "attributes":{"DatenquelleDachhoehe":"1000"}}
        chosen,reason = select_height(footprint,[candidate])
        self.assertIsNone(reason)
        self.assertEqual(chosen[0]["height"],7.62)
        for rows in [[],[candidate,candidate],[{**candidate,"footprint":box(0,0,20,20)}],
                     [{**candidate,"footprint":box(0,0,3,3)}],
                     [{**candidate,"attributes":{"DatenquelleDachhoehe":"3000"}}],
                     [{**candidate,"height":0}]]:
            chosen,reason = select_height(footprint,rows)
            self.assertIsNone(chosen)
            self.assertTrue(reason)
