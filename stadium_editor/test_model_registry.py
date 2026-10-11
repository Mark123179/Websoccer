"""Registry, routing and integrity checks; no real club or game writes."""
from copy import deepcopy
import hashlib
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.http import Http404
from django.test import RequestFactory, SimpleTestCase

from . import model_registry as registry
from .model_assets import model_asset, verified_model_asset
from .scene_service import current_live_scene
from .unity_runtime import unity_presentation


class RegistryTests(SimpleTestCase):
    def setUp(self):
        self.manifest = deepcopy(registry.model_manifest(908))
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.patcher = patch.object(registry, "MODEL_DIR", self.root)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        registry.model_manifest.cache_clear()
        self.addCleanup(registry.model_manifest.cache_clear)

    def write(self, fmi, **patches):
        m = deepcopy(self.manifest)
        m.update(clubFmiId=fmi, **patches)
        (self.root / f"{fmi}.json").write_text(json.dumps(m))
        return m

    def test_all_required_fields_are_validated(self):
        fields = ["clubFmiId", "stadiumName", "source", "sourceSha256", "geometrySha256",
                  "assetVersion", "assetSha256", "meshes", "textures", "fixtures",
                  "verifiedFixtureCount", "seatView", "limits", "sourceEvidence", "calibration"]
        for field in fields:
            with self.subTest(field=field):
                m = deepcopy(self.manifest)
                del m[field]
                with self.assertRaisesRegex(ValueError, field):
                    registry.validate_model_manifest(m)
        for field in self.manifest["calibration"]:
            with self.subTest(calibration=field):
                m = deepcopy(self.manifest)
                del m["calibration"][field]
                with self.assertRaisesRegex(ValueError, field):
                    registry.validate_model_manifest(m)

    def test_missing_nested_fields_and_wrong_types(self):
        changes = [("roofMinHeight", True), ("tickerRotationY", float("nan")),
                   ("skipMeshPrefixes", [""]), ("crowdPrefix", ""),
                   ("pitchPrefix", None), ("tickerFrontCut", {"normal": [0, 0, 0], "constant": 32}),
                   ("standAxes", {"+x": "NORD"}), ("orbitDefault", {"azimuth": 0, "elevation": 0})]
        for field, value in changes:
            with self.subTest(field=field):
                m = deepcopy(self.manifest)
                m["calibration"][field] = value
                with self.assertRaisesRegex(ValueError, field):
                    registry.validate_model_manifest(m)
        for field, value in [("clubFmiId", True), ("assetVersion", "../bad"),
                             ("textures", ["../bad"]), ("sourceSha256", "bad")]:
            with self.subTest(field=field):
                m = deepcopy(self.manifest)
                m[field] = value
                with self.assertRaisesRegex(ValueError, field):
                    registry.validate_model_manifest(m)

    def test_invalid_manifest_is_not_registered_and_warns(self):
        self.write(999, calibration={})
        with self.assertLogs(registry.logger, level="WARNING") as logs:
            self.assertIsNone(registry.model_manifest(999))
        self.assertIn("roofMinHeight", logs.output[0])
        self.assertEqual(registry.registered_fmi_ids(), [])

    def test_registry_is_sorted_cached_and_identity_bound(self):
        self.write(1002)
        self.write(1001)
        self.assertEqual(registry.registered_fmi_ids(), [1001, 1002])
        self.assertIs(registry.model_manifest(1001), registry.model_manifest(1001))
        self.assertIsNone(registry.model_manifest(2000))
        self.write(1003, stadiumName="Test")
        m = json.loads((self.root / "1003.json").read_text())
        m["clubFmiId"] = 9000
        (self.root / "1003.json").write_text(json.dumps(m))
        with self.assertLogs(registry.logger, level="WARNING"):
            self.assertIsNone(registry.model_manifest(1003))

    def test_optional_material_fields_are_strict_and_backwards_compatible(self):
        registry.validate_model_manifest(self.manifest)
        for field, good, bad_values in (
            ("transparent", True, (1, "true", None)),
            ("alphaTest", 0.03, (-1, 1.01, True, float("nan"))),
            ("uvProjection", [0, 0, -0.01, 0.5, 0.02, 0, 0, 0.5],
             ([], [0] * 7, [0] * 9, [True] * 8, [float("inf")] * 8)),
        ):
            m = deepcopy(self.manifest)
            m["meshes"][0]["parts"][0][field] = good
            registry.validate_model_manifest(m)
            for bad in bad_values:
                with self.subTest(field=field, value=bad):
                    m["meshes"][0]["parts"][0][field] = bad
                    with self.assertRaisesRegex(ValueError, field):
                        registry.validate_model_manifest(m)

    def test_optional_roof_prefixes_reject_invalid_values(self):
        m = deepcopy(self.manifest)
        m["calibration"]["roofMeshPrefixes"] = ["roof_"]
        registry.validate_model_manifest(m)
        for value in ("roof_", [""], [None], None):
            m["calibration"]["roofMeshPrefixes"] = value
            with self.assertRaisesRegex(ValueError, "roofMeshPrefixes"):
                registry.validate_model_manifest(m)
    def test_arbitrary_registered_club_uses_unity_and_calibration(self):
        self.write(1002)
        stadium = SimpleNamespace(club=SimpleNamespace(fm_inside_id=1002), club_id=500, capacity_total=20)
        with patch("stadium_editor.scene_service.StadiumGeometry.objects.get",
                   return_value=SimpleNamespace(geometry={"blocks": []}, steckbrief={})), \
             patch("stadium_editor.scene_service.StadiumDesign.objects") as designs, \
             patch("stadium_editor.scene_service.build_live_scene", return_value={"blocks": []}), \
             patch("stadium_editor.unity_runtime.runtime_presentation", return_value={"surroundings": {}}):
            designs.filter.return_value.first.return_value = SimpleNamespace(design={})
            scene = current_live_scene(stadium)
        self.assertEqual(scene["presentation"]["renderer"], "unity-spatial")
        self.assertEqual(scene["presentation"]["calibration"], self.manifest["calibration"])
        self.assertIn("/1002/", scene["presentation"]["modelUrl"])
        self.assertEqual(scene["presentation"]["stadium"], self.manifest["stadiumName"])

    def test_unregistered_has_no_presentation_and_dortmund_keeps_precedence(self):
        self.write(907)
        for fmi in (907, 5000):
            stadium = SimpleNamespace(club=SimpleNamespace(fm_inside_id=fmi))
            with patch("stadium_editor.scene_service.StadiumGeometry.objects.get",
                       return_value=SimpleNamespace(geometry={"blocks": []}, steckbrief={})), \
                 patch("stadium_editor.scene_service.StadiumDesign.objects") as designs, \
                 patch("stadium_editor.scene_service.build_live_scene", return_value={"blocks": []}), \
                 patch("stadium_editor.dortmund_runtime.runtime_presentation",
                       return_value={"renderer": "dortmund-spatial"}) as bvb:
                designs.filter.return_value.first.return_value = SimpleNamespace(design={})
                scene = current_live_scene(stadium)
            if fmi == 907:
                self.assertEqual(scene["presentation"]["renderer"], "dortmund-spatial")
                bvb.assert_called_once()
            else:
                self.assertNotIn("presentation", scene)
                bvb.assert_not_called()

    def test_presentation_rejects_wrong_club(self):
        with self.assertRaisesRegex(ValueError, "clubFmiId"):
            unity_presentation(SimpleNamespace(club=SimpleNamespace(fm_inside_id=1002)), {}, {}, self.manifest)

    def test_check_command_checks_assets_without_writes(self):
        self.write(1002)
        output = StringIO()
        with patch("stadium_editor.management.commands.check_stadium_model.verified_model_asset",
                   return_value=(b"data", "test/source")) as verify:
            call_command("check_stadium_model", fmi=1002, assets=True, stdout=output)
        self.assertEqual(verify.call_count, 1 + len(self.manifest["textures"]))
        self.assertTrue(all(call.kwargs == {"cache": False} for call in verify.call_args_list))
        self.assertIn("keine Schreibzugriffe", output.getvalue())
        self.assertEqual(list(self.root.iterdir()), [self.root / "1002.json"])

    def test_check_command_reports_invalid_manifest_and_corruption(self):
        self.write(1002, calibration={})
        with self.assertRaisesRegex(CommandError, "roofMinHeight"):
            call_command("check_stadium_model", fmi=1002, stdout=StringIO())
        self.write(1002)
        with patch("stadium_editor.management.commands.check_stadium_model.verified_model_asset",
                   side_effect=ValueError("corrupt")):
            with self.assertRaisesRegex(CommandError, "geometry.bin"):
                call_command("check_stadium_model", fmi=1002, assets=True, stdout=StringIO())


class ModelAssetTests(SimpleTestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.data = b"verified stadium bytes"
        self.manifest = {"clubFmiId": 1002, "assetVersion": "test-version",
                         "textures": ["test.webp"],
                         "assetSha256": {"geometry.bin": hashlib.sha256(self.data).hexdigest(),
                                         "test.webp": hashlib.sha256(self.data).hexdigest()}}
        self.asset = self.root / "stadium-models/1002/test-version/geometry.bin"
        self.asset.parent.mkdir(parents=True)
        self.asset.write_bytes(self.data)
        self.request = RequestFactory().get("/stadion/model-assets/")

    def test_404_for_unregistered_version_and_foreign_name(self):
        for manifest, fmi, version, name in [
            (None, 5000, "test-version", "geometry.bin"),
            (self.manifest, 1002, "wrong", "geometry.bin"),
            (self.manifest, 1002, "test-version", "foreign.webp"),
            (self.manifest, 1002, "test-version", "../geometry.bin"),
        ]:
            with patch("stadium_editor.model_assets.model_manifest", return_value=manifest):
                with self.assertRaises(Http404):
                    model_asset(self.request, fmi, version, name)

    def test_correct_asset_served_only_after_verification(self):
        with patch("stadium_editor.model_assets.model_manifest", return_value=self.manifest), \
             patch("game.asset_urls.assets_root", return_value=str(self.root)):
            response = model_asset(self.request, 1002, "test-version", "geometry.bin")
            try:
                self.assertEqual(b"".join(response.streaming_content), self.data)
                self.assertEqual(response["X-Content-Type-Options"], "nosniff")
            finally:
                response.close()

    def test_corrupt_asset_is_not_served(self):
        self.asset.write_bytes(b"corrupt")
        with patch("stadium_editor.model_assets.model_manifest", return_value=self.manifest), \
             patch("game.asset_urls.assets_root", return_value=str(self.root)):
            with self.assertRaisesRegex(ValueError, "geometry.bin"):
                model_asset(self.request, 1002, "test-version", "geometry.bin")

    def test_storage_check_ignores_cache_and_writes_nothing(self):
        self.asset.unlink()
        with patch("game.asset_urls.assets_root", return_value=str(self.root)), \
             patch("game.object_storage_backend.get_client") as client:
            client.return_value.download_as_bytes.return_value = self.data
            data, source = verified_model_asset(self.manifest, "geometry.bin", cache=False)
        self.assertEqual(data, self.data)
        self.assertEqual(source, "stadium-models/1002/test-version/geometry.bin")
        client.return_value.download_as_bytes.assert_called_once_with(source)
        self.assertFalse(self.asset.exists())

    def test_corrupt_cache_is_not_served(self):
        from tempfile import TemporaryDirectory
        self.asset.unlink()
        with TemporaryDirectory() as cache:
            directory = Path(cache) / "1002/test-version"
            directory.mkdir(parents=True)
            (directory / "geometry.bin").write_bytes(b"corrupt")
            real_path = Path
            def paths(value):
                return real_path(cache) if value == "/tmp/stadium-model-assets" else real_path(value)
            with patch("game.asset_urls.assets_root", return_value=str(self.root)), \
                 patch("stadium_editor.model_assets.Path", side_effect=paths):
                with self.assertRaisesRegex(ValueError, "geometry.bin"):
                    verified_model_asset(self.manifest, "geometry.bin")
