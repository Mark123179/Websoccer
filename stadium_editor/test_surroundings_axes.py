"""The optional source-model surroundings mapping never changes older models."""
from copy import deepcopy

from django.test import SimpleTestCase

from . import model_registry as registry


class SurroundingsAxesTests(SimpleTestCase):
    def test_registered_models_and_mirrored_surroundings_are_valid(self):
        for fmi in registry.registered_fmi_ids():
            with self.subTest(fmi=fmi):
                manifest = registry.model_manifest(fmi)
                registry.validate_model_manifest(manifest)
                axes = manifest["calibration"].get("surroundingsAxes")
                if fmi in (912, 91013388):
                    self.assertEqual(axes, {"NORD": "-z", "WEST": "-x"})
                else:
                    self.assertIsNone(axes)

    def test_invalid_axes_are_rejected(self):
        manifest = deepcopy(registry.model_manifest(912))
        for invalid in (
            None, [], {}, {"NORD": "-z"}, {"NORD": "-z", "WEST": "-z"},
            {"NORD": "+z", "WEST": "-x"}, {"NORD": "-z", "WEST": "+x"},
            {"NORD": "-z", "WEST": "-x", "OST": "+x"},
        ):
            with self.subTest(invalid=invalid):
                manifest["calibration"]["surroundingsAxes"] = invalid
                with self.assertRaisesRegex(ValueError, "surroundingsAxes"):
                    registry.validate_model_manifest(manifest)
