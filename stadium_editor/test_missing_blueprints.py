from contextlib import ExitStack
from io import StringIO
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from stadium_editor.management.commands.import_stadium_editor_geometry import Command


class MissingBlueprintCommandTests(SimpleTestCase):
    def run_command(self, *, exists=False, dry_run=False, blueprint=True, error=None):
        stadium = SimpleNamespace(pk=7, name="Arena", club=SimpleNamespace(name="FC Test"))
        geometry = MagicMock()
        geometry.objects.filter.return_value.exists.return_value = exists
        geometry.objects.get_or_create.return_value = (SimpleNamespace(), True)
        stadiums = MagicMock()
        stadiums.objects.select_related.return_value.order_by.return_value = [stadium]
        output = StringIO()
        with ExitStack() as stack:
            root = "stadium_editor.management.commands.import_stadium_editor_geometry."
            stack.enter_context(patch(root + "Stadium", stadiums))
            stack.enter_context(patch(root + "StadiumGeometry", geometry))
            stack.enter_context(patch(root + "load_blueprints", return_value={"fctest": {"blocks": []}} if blueprint else {}))
            normalise = stack.enter_context(patch(root + "normalise_block_types", return_value={"blocks": []}))
            atomic = stack.enter_context(patch(root + "transaction.atomic"))
            scene = stack.enter_context(patch("stadium_editor.scene_service.current_live_scene", side_effect=error))
            command = Command(stdout=output)
            if error:
                with self.assertRaisesRegex(ValueError, "invalid scene"):
                    command.handle(source=None, stadium=None, dry_run=dry_run, missing_only=True)
            else:
                command.handle(source=None, stadium=None, dry_run=dry_run, missing_only=True)
        return geometry, normalise, scene, atomic, output.getvalue()

    def test_existing_geometry_is_not_normalised_or_written(self):
        geometry, normalise, scene, _, output = self.run_command(exists=True)
        normalise.assert_not_called()
        geometry.objects.get_or_create.assert_not_called()
        geometry.objects.update_or_create.assert_not_called()
        scene.assert_not_called()
        self.assertIn("1 unverändert", output)

    def test_dry_run_does_not_write_or_build_a_persisted_scene(self):
        geometry, _, scene, atomic, output = self.run_command(dry_run=True)
        geometry.objects.get_or_create.assert_not_called()
        scene.assert_not_called()
        atomic.assert_not_called()
        self.assertIn("1 geprüft", output)

    def test_missing_geometry_uses_create_only_and_validates_full_scene(self):
        geometry, _, scene, atomic, _ = self.run_command()
        geometry.objects.get_or_create.assert_called_once()
        geometry.objects.update_or_create.assert_not_called()
        scene.assert_called_once()
        atomic.assert_called_once()

    def test_no_matching_source_is_skipped_without_fallback(self):
        geometry, normalise, scene, _, output = self.run_command(blueprint=False)
        normalise.assert_not_called()
        geometry.objects.get_or_create.assert_not_called()
        scene.assert_not_called()
        self.assertIn("1 ohne passende Blaupause", output)

    def test_invalid_live_scene_propagates_out_of_atomic_block(self):
        _, _, scene, atomic, _ = self.run_command(error=ValueError("invalid scene"))
        scene.assert_called_once()
        self.assertIs(atomic.return_value.__exit__.call_args.args[0], ValueError)
