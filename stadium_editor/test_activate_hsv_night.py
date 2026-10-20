"""Activation failure gates, without database or external storage."""
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import Mock, patch

from scripts import activate_hsv_night as activation


class HSVActivationTests(TestCase):
    def exercise_activation(self, *, corrupt_old=False, corrupt_new=False):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "947.json"
            old = {"assetVersion": "26bbf1d9b445d255",
                   "assetSha256": {"geometry.bin": activation.sha(b"geometry")}}
            new = {"assetVersion": "fdea273ea50e8748", "textures": [],
                   "assetSha256": old["assetSha256"]}
            old_raw, new_raw = json.dumps(old).encode(), json.dumps(new).encode()
            target.write_bytes(old_raw)
            (root / "manifest.json").write_bytes(new_raw)
            # Deliberately different formatting, as produced by the auditor.
            (root / "baseline-manifest.json").write_text(json.dumps(old, indent=2))
            assets = root / "package/stadium-models/947" / new["assetVersion"]
            assets.mkdir(parents=True)
            (assets / "geometry.bin").write_bytes(b"geometry")
            old_key = f"stadium-models/947/{old['assetVersion']}/geometry.bin"
            new_key = f"stadium-models/947/{new['assetVersion']}/geometry.bin"
            objects = {old_key: b"corrupt" if corrupt_old else b"geometry"}
            client = Mock()
            client.exists.side_effect = lambda key: key in objects
            client.download_as_bytes.side_effect = lambda key: (
                b"corrupt" if corrupt_new and key == new_key else objects[key])
            client.upload_from_bytes.side_effect = lambda key, data: objects.update({key: data})
            with patch.object(activation, "manifest_path", return_value=target), \
                    patch.object(activation, "get_client", return_value=client), \
                    patch.object(activation, "BASELINE_SHA", activation.sha(old_raw)), \
                    patch.object(activation, "CANDIDATE_SHA", activation.sha(new_raw)), \
                    patch.object(activation, "verify", return_value=({}, old, new, {}, {})):
                if corrupt_old or corrupt_new:
                    with self.assertRaises(ValueError):
                        activation.activate(root, approved=True)
                    self.assertEqual(target.read_bytes(), old_raw)
                else:
                    activation.activate(root, approved=True)
                    self.assertEqual(target.read_bytes(), new_raw)
                    self.assertEqual(objects[old_key], b"geometry")
                    for manifest, raw in ((old, old_raw), (new, new_raw)):
                        self.assertEqual(objects[
                            f"stadium-model-revisions/947/{manifest['assetVersion']}/manifest.json"], raw)

    def test_activation_archives_exact_manifests_and_preserves_old_assets(self):
        self.exercise_activation()

    def test_corrupt_old_asset_prevents_activation(self):
        self.exercise_activation(corrupt_old=True)

    def test_corrupt_storage_readback_prevents_activation(self):
        self.exercise_activation(corrupt_new=True)

    def test_explicit_approval_required_before_io(self):
        with patch.object(activation, "manifest_path") as target:
            with self.assertRaises(ValueError):
                activation.activate(Path("unused"))
            target.assert_not_called()

    def test_wrong_baseline_aborts_before_storage_or_package_access(self):
        with TemporaryDirectory() as directory:
            target = Path(directory) / "947.json"
            target.write_bytes(b"unexpected")
            with patch.object(activation, "manifest_path", return_value=target), \
                    patch.object(activation, "get_client") as client:
                with self.assertRaises(ValueError):
                    activation.activate(Path("unused"), approved=True)
                client.assert_not_called()
            self.assertEqual(target.read_bytes(), b"unexpected")

    def test_existing_storage_object_is_read_back_and_never_overwritten(self):
        client = Mock()
        client.exists.return_value = True
        client.download_as_bytes.return_value = b"wrong"
        with self.assertRaises(ValueError):
            activation.store_verified(client, "new-version/geometry.bin", b"expected")
        client.upload_from_bytes.assert_not_called()

    def test_new_object_is_uploaded_and_fully_read_back(self):
        client = Mock()
        client.exists.return_value = False
        client.download_as_bytes.return_value = b"expected"
        activation.store_verified(client, "new-version/geometry.bin", b"expected")
        client.upload_from_bytes.assert_called_once_with("new-version/geometry.bin", b"expected")
        client.download_as_bytes.assert_called_once_with("new-version/geometry.bin")

    def test_switch_checks_baseline_and_replaces_complete_bytes(self):
        with TemporaryDirectory() as directory:
            target = Path(directory) / "947.json"
            target.write_bytes(b"baseline")
            digest = hashlib.sha256(b"baseline").hexdigest()
            with patch.object(activation, "BASELINE_SHA", digest):
                activation.switch_registry(target, b"candidate")
                self.assertEqual(target.read_bytes(), b"candidate")
                with self.assertRaises(ValueError):
                    activation.switch_registry(target, b"second candidate")
            self.assertEqual(list(Path(directory).iterdir()), [target])

    def test_changed_baseline_at_final_check_aborts_without_switch(self):
        with TemporaryDirectory() as directory:
            target = Path(directory) / "947.json"
            target.write_bytes(b"concurrent change")
            with patch.object(activation, "require_baseline",
                              side_effect=[b"baseline", ValueError("changed")]):
                with self.assertRaises(ValueError):
                    activation.switch_registry(target, b"candidate")
            self.assertEqual(target.read_bytes(), b"concurrent change")
            self.assertEqual(list(Path(directory).iterdir()), [target])
