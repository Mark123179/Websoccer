"""Offline height provenance and runtime opt-in contract (no external services)."""
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase
from shapely.geometry import box

from scripts.refine_koln_heights import select_height, lod_buildings
from scripts.koln_building_parts import component_group
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

    def test_parts_do_not_grant_a_single_height_and_preserve_every_residual(self):
        from shapely.geometry import Polygon
        from shapely.ops import unary_union
        polygon = box(0, 0, 30, 10)
        def candidate(identity, shape, base, height):
            return {"id": identity, "file": "test.gml", "footprint": shape,
                    "height": height, "heightUnit": "urn:adv:uom:m", "baseNHN": base,
                    "baseMaxNHN": base, "roofNHN": base+height, "roofMinNHN": base+height,
                    "srsName": "urn:adv:crs:ETRS89_UTM32*DE_DHHN2016_NH",
                    "attributes": {"DatenquelleDachhoehe": "1000", "DatenquelleBodenhoehe": "1100"}}
        rows = [candidate("a", box(0,0,10,10), 60, 8),
                candidate("b", box(9.999,0,20,10), 62, 10)]
        chosen, _ = select_height(polygon, rows)
        self.assertIsNone(chosen)
        before = deepcopy(rows)
        group = component_group(0, "way/73467119", polygon, rows, lambda x,y:(x,y))
        self.assertEqual(rows, before)
        self.assertEqual([p["baseNHN"] for p in group["parts"]], [60,62])
        self.assertGreater(group["ambiguousAreaEditor"], 0)
        shapes = [Polygon(p) for part in group["parts"] for p in part["polygons"]]
        residual = [Polygon(p) for p in group["residualPolygons"]]
        self.assertLess(unary_union(shapes+residual).symmetric_difference(polygon).area, 1e-8)
        self.assertAlmostEqual(sum(p.area for p in shapes+residual), polygon.area)
        self.assertIsNone(component_group(0, "way/unrelated", polygon, rows, lambda x,y:(x,y)))
        for field,value in [("heightUnit",None),("baseMaxNHN",61),("roofNHN",99),
                            ("srsName","EPSG:25832"),("attributes",{"DatenquelleDachhoehe":"3000"})]:
            bad=deepcopy(rows);bad[0][field]=value
            with self.subTest(field=field), self.assertRaises(ValueError):
                component_group(0, "way/73467119", polygon, bad, lambda x,y:(x,y))

    def test_lod_parser_keeps_component_nhn_and_rejects_conflicting_tile_duplicates(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        xml = """<core:CityModel xmlns:core="http://www.opengis.net/citygml/1.0"
          xmlns:b="http://www.opengis.net/citygml/building/1.0"
          xmlns:g="http://www.opengis.net/gml">
          <g:boundedBy><g:Envelope srsName="urn:adv:crs:ETRS89_UTM32*DE_DHHN2016_NH"/></g:boundedBy>
          <b:Building g:id="parent"><b:consistsOfBuildingPart><b:BuildingPart g:id="part">
          <b:measuredHeight uom="urn:adv:uom:m">9</b:measuredHeight>
          <b:boundedBy><b:GroundSurface><g:Polygon><g:exterior><g:LinearRing>
          <g:posList>0 0 60 10 0 60 10 10 60 0 10 60 0 0 60</g:posList>
          </g:LinearRing></g:exterior></g:Polygon></b:GroundSurface></b:boundedBy>
          <b:boundedBy><b:RoofSurface><g:Polygon><g:exterior><g:LinearRing>
          <g:posList>0 0 68 10 0 69 10 10 69 0 10 68 0 0 68</g:posList>
          </g:LinearRing></g:exterior></g:Polygon></b:RoofSurface></b:boundedBy>
          </b:BuildingPart></b:consistsOfBuildingPart></b:Building></core:CityModel>"""
        with TemporaryDirectory() as tmp:
            a,b=Path(tmp)/"a.gml",Path(tmp)/"b.gml"
            a.write_text(xml);b.write_text(xml)
            rows,rejected=lod_buildings([a,b])
            self.assertEqual(rejected,[])
            self.assertEqual(len(rows),1)
            self.assertEqual(rows[0]["id"],"part")
            self.assertEqual((rows[0]["baseNHN"],rows[0]["baseMaxNHN"],
                              rows[0]["roofMinNHN"],rows[0]["roofNHN"]),(60,60,68,69))
            b.write_text(xml.replace(" 60"," 61"))
            with self.assertRaisesRegex(ValueError,"Conflicting tile duplicate"):
                lod_buildings([a,b])

    @patch("stadium_editor.dortmund_runtime.with_dortmund_mapped_trees",
           side_effect=lambda g, **kwargs:g)
    def test_component_contract_survives_runtime_and_legacy_projection(self, _):
        from stadium_editor.surroundings_data import project_surroundings
        contract = {"version":1,"groups":[{"osm":"way/73467119"}]}
        data = {**self.data, "buildingParts":contract}
        geometry = {"meta":{},"blocks":[],"surroundings":data,
                    "bg":{"buildings":[{"poly":[[30,30],[40,30],[40,40]],"h":6,"id":"way/73467119"}]}}
        before = deepcopy(geometry)
        projected, _ = project_surroundings(geometry)
        self.assertEqual(projected["buildingParts"],contract)
        self.assertEqual(projected["buildingIds"],["way/73467119"])
        stadium = SimpleNamespace(club_id=999,club=SimpleNamespace(fm_inside_id=916),capacity_total=50000)
        manifest = {"clubFmiId":916,"assetVersion":"unchanged","stadiumName":"Köln",
                    "sourceSha256":"test","calibration":{}}
        result = unity_presentation(stadium,geometry,{},manifest)
        self.assertEqual(result["surroundings"]["buildingParts"],contract)
        result["surroundings"]["buildingParts"]["groups"].clear()
        self.assertEqual(geometry,before)
