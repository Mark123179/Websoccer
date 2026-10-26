from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from game.stadium_scene_context import ticker_scene_context
from stadium_editor import scene_service
from stadium_editor.management.commands.activate_allianz_presentation import Command


class AllianzRolloutTests(SimpleTestCase):
    def test_ticker_uses_fcb_scene_only_when_geometry_exists(self):
        stadium = SimpleNamespace(name="Allianz Arena")
        club = SimpleNamespace(pk=127, name="FC Bayern", fm_inside_id=915, stadium=stadium)
        with patch("game.stadium_scene_context.StadiumGeometry.objects") as rows:
            rows.filter.return_value.exists.return_value = True
            result = ticker_scene_context(club)
            self.assertEqual(result["renderer"], "unity-spatial")
            self.assertEqual(result["sceneUrl"], "/stadion/127/live-scene/")
            rows.filter.return_value.exists.return_value = False
            self.assertIsNone(ticker_scene_context(club))

    def test_source_colours_are_preserved_without_discarding_saved_designs(self):
        generated = {"palette":["#000000","#ffffff"],"blocks":[]}
        saved = {"palette":["#000000","#ff0000"],"blocks":[]}
        for fmi, design, expected in [
            (915, None, {}),
            (915, SimpleNamespace(design=saved), saved),
            (908, None, generated),
        ]:
            with self.subTest(fmi=fmi, saved=design is not None):
                stadium = SimpleNamespace(club=SimpleNamespace(fm_inside_id=fmi))
                row = SimpleNamespace(geometry={"blocks":[]}, steckbrief={})
                with patch.object(scene_service.StadiumGeometry.objects, "get", return_value=row), \
                     patch.object(scene_service.StadiumDesign.objects, "filter") as designs, \
                     patch.object(scene_service, "distribute_capacities", return_value={"blocks":[]}), \
                     patch.object(scene_service, "geometry_blocks", return_value=[]), \
                     patch.object(scene_service, "standard_design_for_geometry", return_value=generated), \
                     patch.object(scene_service, "build_live_scene", return_value={}), \
                     patch.object(scene_service, "model_manifest", return_value={"clubFmiId":fmi}), \
                     patch("stadium_editor.unity_runtime.unity_presentation", return_value={}) as build:
                    designs.return_value.first.return_value = design
                    scene_service.current_live_scene(stadium)
                # Source-backed clubs without saved paint all start with the
                # real original, never with a synthetic fallback recolouring.
                self.assertEqual(build.call_args.args[2], design.design if design is not None else {})

    def test_activation_is_dry_run_by_default(self):
        with patch("stadium_editor.management.commands.activate_allianz_presentation.model_manifest",
                   return_value={"clubFmiId":915}), \
             patch("stadium_editor.management.commands.activate_allianz_presentation.Stadium") as stadiums, \
             patch("stadium_editor.management.commands.activate_allianz_presentation.StadiumGeometry") as rows:
            stadiums.objects.select_related.return_value.get.return_value = SimpleNamespace(pk=30)
            rows.objects.filter.return_value.exists.return_value = False
            command = Command(stdout=StringIO())
            command.handle(apply=False)
            rows.objects.create.assert_not_called()
            self.assertIn("--apply", command.stdout.getvalue())
