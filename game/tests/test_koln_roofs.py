"""Offline roof evidence, clipping and rejection; never needs a network or DB."""
from copy import deepcopy

from django.test import SimpleTestCase
from shapely.geometry import box, Polygon
from shapely.ops import unary_union

from scripts.koln_roof_surfaces import clipped_roofs, roof_plane
from scripts.install_koln_roofs import apply_roof_package, digest


class RoofSurfaceTests(SimpleTestCase):
    def setUp(self):
        self.ring = [[0,0,68], [10,0,70], [10,10,70], [0,10,68], [0,0,68]]
        self.c = {"id": "official-part", "file": "tile.gml", "baseNHN": 60,
                  "roofNHN": 70, "roofMinNHN": 68,
                  "roofSurfaces": [{"surfaceId": "roof", "polygonId": "polygon",
                                    "ringsUTM": [self.ring]}]}

    def test_clip_keeps_source_identity_plane_and_existing_partition(self):
        footprint = box(2,0,9,10).difference(box(4,4,6,6))
        before = deepcopy(self.c)
        roofs = clipped_roofs(self.c, footprint, lambda x,y: (x,y))
        self.assertEqual(self.c, before)
        self.assertEqual(roofs[0]["sourceRingsUTM"], [self.ring])
        self.assertEqual(roofs[0]["lodId"], "official-part")
        shapes = [Polygon([[x,y] for x,y,z in p]) for r in roofs for p in r["polygons"]]
        self.assertLess(unary_union(shapes).symmetric_difference(footprint).area, 1e-8)
        for r in roofs:
            for p in r["polygons"]:
                for x,y,z in p:
                    self.assertAlmostEqual(z, 68+x*.2)

    def test_invalid_roofs_never_become_flat_fallbacks(self):
        mutations = [
            lambda c: c.update(roofSurfaces=[]),
            lambda c: c["roofSurfaces"].append(deepcopy(c["roofSurfaces"][0])),
            lambda c: c["roofSurfaces"][0]["ringsUTM"][0][1].__setitem__(2, float("nan")),
            lambda c: c["roofSurfaces"][0]["ringsUTM"][0][1].__setitem__(2, 69),
            lambda c: c["roofSurfaces"][0]["ringsUTM"][0].pop(),
            lambda c: c.update(roofNHN=69),
        ]
        for mutate in mutations:
            c = deepcopy(self.c)
            mutate(c)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                clipped_roofs(c, box(0,0,10,10), lambda x,y: (x,y))
        with self.assertRaisesRegex(ValueError, "Incomplete"):
            clipped_roofs(self.c, box(0,0,11,10), lambda x,y: (x,y))
        with self.assertRaises(ValueError):
            roof_plane([[[0,0,60], [0,0,70], [0,10,70], [0,10,60], [0,0,60]]])

    def test_overlay_is_roof_only_idempotent_and_requires_exact_baseline(self):
        from unittest.mock import patch
        contract = {"version": 1, "referenceNHN": 60, "verticalDatum": "datum",
                    "groups": [{"osm": "way/one", "parts": [{"lodId": "a", "polygons": [1]},
                                                          {"lodId": "b", "polygons": [2]}],
                                "residualPolygons": [3]}]}
        package = {"version": 1, "referenceNHN": 60, "verticalDatum": "datum",
                   "baselinePartsSha256": digest(contract),
                   "parts": {identity: {"roofStatus": "rejected_retained_envelope",
                                        "roofRejection": "test rejection"} for identity in ("a", "b")}}
        data = {"buildingParts": contract, "heightEvidence": {"terrainReferenceNHN": 60},
                "groundElevation": {"values": [1]}, "buildingHeights": [9],
                "buildings": [[1]], "roads": [[2]], "trees": [[3]]}
        before = deepcopy(data)
        with patch("stadium_editor.package_preflight.inspect_package", return_value={"ok": True}):
            result = apply_roof_package(data, package)
            self.assertEqual(data, before)
            self.assertEqual({k:v for k,v in result.items() if k != "buildingParts"},
                             {k:v for k,v in data.items() if k != "buildingParts"})
            self.assertEqual(apply_roof_package(result, package), result)
            mutations = [
                lambda d: d["buildingParts"]["groups"][0]["residualPolygons"].append(4),
                lambda d: d["buildingParts"]["groups"][0]["parts"][0].update(lodId="other"),
                lambda d: d["buildingParts"].update(referenceNHN=61),
                lambda d: d.pop("buildingParts"),
            ]
            for mutate in mutations:
                bad = deepcopy(data)
                mutate(bad)
                with self.assertRaises(ValueError):
                    apply_roof_package(bad, package)
            bad = deepcopy(package)
            bad["parts"]["a"]["height"] = 99
            with self.assertRaises(ValueError):
                apply_roof_package(data, bad)
