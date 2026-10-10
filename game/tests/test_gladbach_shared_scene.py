"""Club scope, immutable assets and read-only source presentation."""
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase, RequestFactory
from django.http import Http404

from stadium_editor.gladbach_runtime import gladbach_presentation
from stadium_editor.model_assets import model_asset, model_manifest
from game.stadium_scene_context import ticker_scene_context


class GladbachSharedSceneTests(SimpleTestCase):
    def setUp(self):
        self.club = SimpleNamespace(pk=13, fm_inside_id=908, name="Gladbach")
        self.stadium = SimpleNamespace(club_id=13, club=self.club,
                                     name="Borussia-Park", capacity_total=54042)
        self.club.stadium = self.stadium
        self.geometry = {"meta": {"fieldC": [-10.4,11.3], "axisTheta":1.0472},
                         "blocks":[{"id":9, "stand":"NORD"}],
                         "bg":{"green":[[[0,0],[2,0],[0,2]]],
                               "roads":[{"p":[[1,2],[3,4]],"w":4}],
                               "buildings":[[[0,0],[1,0],[0,1]]]}}

    def test_own_map_frame_capacity_and_saved_colors_without_mutation(self):
        design={"palette":["#000000","#ff0000"],"blocks":[{"id":9,"rle":[[4,1]]}]}
        before=deepcopy((self.geometry,design))
        result=gladbach_presentation(self.stadium,self.geometry,design)
        self.assertEqual((self.geometry,design),before)
        self.assertEqual(result["renderer"],"unity-spatial")
        self.assertEqual(result["capacity"],54042)
        self.assertEqual(result["frame"],self.geometry["meta"])
        self.assertEqual(result["surroundings"]["roads"],self.geometry["bg"]["roads"])
        self.assertEqual(result["designColors"],{"NORD":"#ff0000"})
        self.assertNotIn("imageBackground",result)

    def test_ticker_uses_only_its_club_scene(self):
        with patch("game.stadium_scene_context.StadiumGeometry.objects") as rows:
            rows.filter.return_value.exists.return_value=True
            context=ticker_scene_context(self.club)
            self.assertEqual(context["renderer"],"unity-spatial")
            self.assertEqual(context["sceneUrl"],"/stadion/13/live-scene/")
            rows.filter.return_value.exists.return_value=False
            self.assertIsNone(ticker_scene_context(self.club))

    def test_wrong_club_cannot_receive_original_model(self):
        self.club.fm_inside_id=915
        with self.assertRaises(ValueError):
            gladbach_presentation(self.stadium,self.geometry,{})

    def test_asset_route_is_versioned_allowlisted_and_read_only(self):
        version=model_manifest()["assetVersion"]
        request=RequestFactory().get("/")
        for fmi, token, name in [
            (907,version,"manifest.json"),(908,"wrong","manifest.json"),
            (908,version,"../geometry.bin"),(908,version,"secrets.json"),
        ]:
            with self.assertRaises(Http404):
                model_asset(request,fmi,token,name)
        response=model_asset(request,908,version,"manifest.json")
        self.assertEqual(response.status_code,200)
        self.assertIn("immutable",response["Cache-Control"])
        response.close()
        self.assertEqual(model_asset(RequestFactory().post("/"),908,version,"manifest.json").status_code,405)

    def test_actual_source_lights_are_finite_and_near_fixture_geometry(self):
        import math
        manifest=model_manifest()
        self.assertEqual(len(manifest["fixtures"]),12)
        self.assertGreaterEqual(manifest["verifiedFixtureCount"],12)
        ids=[]
        for fixture in manifest["fixtures"]:
            self.assertLessEqual(fixture["meshDistance"],2)
            self.assertTrue(all(math.isfinite(v) for v in fixture["position"]+fixture["direction"]))
            self.assertAlmostEqual(sum(v*v for v in fixture["direction"]),1)
            ids.extend(fixture["representedIds"])
        self.assertEqual(len(ids),len(set(ids)))
        self.assertEqual(len(ids),manifest["verifiedFixtureCount"])
