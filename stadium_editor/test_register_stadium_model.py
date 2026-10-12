"""Registration failure tests: synthetic package, temporary registry, no database."""
from contextlib import redirect_stdout
import hashlib
from io import StringIO
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, Mock, patch

from django.test import SimpleTestCase

from scripts import register_stadium_model as command
from . import model_registry as registry


class RegistrationTests(SimpleTestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.package = self.root / "package"
        self.models = self.root / "registry"
        self.models.mkdir()
        self.fmi = 999001
        self.version = "synthetic-v1"
        self.payloads = {
            "geometry.bin": b"synthetic geometry",
            "first.webp": b"synthetic first texture",
            "last.webp": b"synthetic last texture",
        }
        digests = {name: hashlib.sha256(data).hexdigest()
                   for name, data in self.payloads.items()}
        self.manifest = {
            "format": "unity-mesh-binary-v1", "clubFmiId": self.fmi,
            "stadiumName": "Synthetic stadium", "source": "test fixture",
            "sourceSha256": "a" * 64, "geometrySha256": digests["geometry.bin"],
            "assetVersion": self.version, "textures": ["first.webp", "last.webp"],
            "assetSha256": digests,
            "meshes": [{"name": "test", "positionOffset": 0, "uvOffset": 0,
                        "vertexCount": 3, "parts": [
                            {"color": [1, 1, 1], "texture": "first.webp",
                             "indexOffset": 0, "indexCount": 3}]}],
            "fixtures": [{"position": [0, 1, 0], "direction": [0, -1, 0],
                          "color": [1, 1, 1], "range": 10, "angle": 60,
                          "intensity": 1, "meshDistance": 0,
                          "representedIds": ["test-light"]}],
            "verifiedFixtureCount": 1, "seatView": {"position": [0, 1, 0]},
            "limits": [], "sourceEvidence": {},
            "calibration": {
                "roofMinHeight": 10, "tickerRotationY": 0,
                "skipMeshPrefixes": [], "crowdPrefix": "crowd", "pitchPrefix": "pitch",
                "tickerFrontCut": {"normal": [1, 0, 0], "constant": 0},
                "standAxes": {"+x": "NORD", "-x": "SUED", "+z": "OST", "-z": "WEST"},
                "orbitDefault": {"azimuth": 0, "elevation": 30, "distance": 50},
            },
        }
        self.package_manifest = self.package / "models" / f"{self.fmi}.json"
        self.package_manifest.parent.mkdir(parents=True)
        self.raw = json.dumps(self.manifest).encode()
        self.package_manifest.write_bytes(self.raw)
        self.assets = self.package / "stadium-models" / str(self.fmi) / self.version
        self.assets.mkdir(parents=True)
        for name, data in self.payloads.items():
            (self.assets / name).write_bytes(data)
        self.target = self.models / f"{self.fmi}.json"
        # An unrelated valid registration must survive every failure unchanged.
        other = dict(self.manifest, clubFmiId=self.fmi + 1)
        (self.models / f"{self.fmi + 1}.json").write_text(json.dumps(other))
        self.baseline = self.snapshot()
        self.remote = {}
        self.client = Mock(spec=["exists", "upload_from_bytes", "download_as_bytes"])
        self.client.exists.side_effect = lambda key: key in self.remote
        self.client.upload_from_bytes.side_effect = self.upload
        self.client.download_as_bytes.side_effect = lambda key: self.remote[key]
        for patcher in (
            patch.object(registry, "MODEL_DIR", self.models),
            patch.object(command, "get_client", return_value=self.client),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        registry.model_manifest.cache_clear()
        self.addCleanup(registry.model_manifest.cache_clear)

    def key(self, name):
        return f"stadium-models/{self.fmi}/{self.version}/{name}"

    def upload(self, key, data):
        self.remote[key] = data

    def snapshot(self):
        return {p.name: p.read_bytes() for p in self.models.iterdir()}

    def register(self):
        with redirect_stdout(StringIO()):
            command.register(self.package, self.fmi)

    def assert_unregistered(self):
        self.assertEqual(self.snapshot(), self.baseline)
        registry.model_manifest.cache_clear()
        self.assertIsNone(registry.model_manifest(self.fmi))
        self.assertEqual(registry.registered_fmi_ids(), [self.fmi + 1])

    def test_success_verifies_all_remote_bytes_before_publication_and_repeats(self):
        # Include a cached miss: successful registration must become visible in-process.
        self.assertIsNone(registry.model_manifest(self.fmi))

        def download(key):
            self.assertFalse(self.target.exists())
            return self.remote[key]

        self.client.download_as_bytes.side_effect = download
        self.register()
        self.assertEqual(self.target.read_bytes(), self.raw)
        self.assertEqual(registry.model_manifest(self.fmi), self.manifest)
        self.assertEqual(self.remote, {self.key(n): d for n, d in self.payloads.items()})
        self.assertEqual(self.client.upload_from_bytes.call_count, len(self.payloads))
        self.assertEqual(self.client.download_as_bytes.call_count, len(self.payloads))
        registered = self.snapshot()
        self.client.upload_from_bytes.reset_mock()
        self.client.download_as_bytes.side_effect = lambda key: self.remote[key]
        self.register()
        self.assertEqual(self.snapshot(), registered)
        self.client.upload_from_bytes.assert_not_called()
        self.assertEqual(self.client.download_as_bytes.call_count, 2 * len(self.payloads))

    def test_each_corrupt_or_missing_local_asset_stops_before_storage_access(self):
        for name, data in self.payloads.items():
            for missing in (False, True):
                with self.subTest(name=name, missing=missing):
                    asset = self.assets / name
                    if missing:
                        asset.unlink()
                    else:
                        asset.write_bytes(b"corrupt")
                    with self.assertRaises((ValueError, FileNotFoundError)):
                        self.register()
                    command.get_client.assert_not_called()
                    self.assert_unregistered()
                    asset.write_bytes(data)

    def test_invalid_manifest_and_wrong_club_stop_before_storage_access(self):
        for changes in ({"calibration": {}}, {"clubFmiId": self.fmi + 2}):
            with self.subTest(changes=changes):
                self.package_manifest.write_text(json.dumps(dict(self.manifest, **changes)))
                with self.assertRaises(ValueError):
                    self.register()
                command.get_client.assert_not_called()
                self.assert_unregistered()

    def test_storage_failures_never_publish_or_change_existing_registration(self):
        for operation in ("exists", "upload_from_bytes", "download_as_bytes", "checksum"):
            for name in self.payloads:
                for existing in (False, True):
                    with self.subTest(operation=operation, name=name, existing=existing):
                        self.remote.clear()
                        if existing:
                            self.target.write_bytes(self.raw)
                        before = self.snapshot()
                        key = self.key(name)

                        def fail(chosen, original):
                            def run(actual, *args):
                                if actual == chosen:
                                    raise OSError("synthetic storage failure")
                                return original(actual, *args)
                            return run

                        if operation == "checksum":
                            def corrupt(actual, data):
                                self.remote[actual] = b"corrupt" if actual == key else data
                            method, effect = "upload_from_bytes", corrupt
                        else:
                            method = operation
                            original = {"exists": lambda k: k in self.remote,
                                        "upload_from_bytes": self.upload,
                                        "download_as_bytes": lambda k: self.remote[k]}[method]
                            effect = fail(key, original)
                        with patch.object(self.client, method, side_effect=effect):
                            with self.assertRaises((OSError, ValueError)):
                                self.register()
                        self.assertEqual(self.snapshot(), before)
                        if existing:
                            self.target.unlink()
                        self.assert_unregistered()

    def test_conflicting_existing_registration_is_never_overwritten(self):
        self.target.write_bytes(json.dumps(dict(self.manifest, stadiumName="Existing")).encode())
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "keine automatische Überschreibung"):
            self.register()
        self.assertEqual(self.snapshot(), before)
        command.get_client.assert_not_called()

    def test_corrupt_existing_remote_assets_are_never_overwritten(self):
        for name in self.payloads:
            with self.subTest(name=name):
                self.remote.clear()
                key = self.key(name)
                self.remote[key] = b"existing corrupt object"
                self.client.upload_from_bytes.reset_mock()
                with self.assertRaisesRegex(ValueError, "Gespeicherte Asset"):
                    self.register()
                self.assertEqual(self.remote[key], b"existing corrupt object")
                self.assertNotIn(key, [call.args[0]
                                      for call in self.client.upload_from_bytes.call_args_list])
                self.assert_unregistered()

    def test_partial_upload_can_be_retried_without_overwriting_verified_assets(self):
        key = self.key("last.webp")
        with patch.object(self.client, "upload_from_bytes", side_effect=lambda k, d:
                          (_ for _ in ()).throw(OSError("upload failed"))
                          if k == key else self.upload(k, d)):
            with self.assertRaises(OSError):
                self.register()
        self.assert_unregistered()
        already_uploaded = set(self.remote)
        self.assertTrue(already_uploaded)
        self.client.upload_from_bytes.reset_mock()
        self.register()
        self.assertEqual(self.target.read_bytes(), self.raw)
        self.assertEqual({call.args[0] for call in self.client.upload_from_bytes.call_args_list},
                         {self.key(name) for name in self.payloads} - already_uploaded)

    def test_manifest_write_failure_leaves_no_partial_registration(self):
        real_temporary = command.tempfile.NamedTemporaryFile
        partial_files = []

        def temporary_file(*args, **kwargs):
            file = real_temporary(*args, **kwargs)
            def partial_write(data):
                file.write(data[:20])
                file.flush()
                partial = Path(file.name)
                self.assertEqual(partial.read_bytes(), self.raw[:20])
                self.assertFalse(self.target.exists())
                partial_files.append(partial)
                raise OSError("disk full")
            wrapper = MagicMock(wraps=file)
            wrapper.name = file.name
            wrapper.write.side_effect = partial_write
            wrapper.__enter__.return_value = wrapper
            wrapper.__exit__.side_effect = lambda *exc: file.close()
            return wrapper

        with patch.object(command.tempfile, "NamedTemporaryFile", temporary_file):
            with self.assertRaisesRegex(OSError, "disk full"):
                self.register()
        self.assertEqual(len(partial_files), 1)
        self.assertFalse(partial_files[0].exists())
        self.assert_unregistered()

    def test_flush_or_publication_failure_leaves_registry_unchanged(self):
        for operation in ("fsync", "link"):
            with self.subTest(operation=operation):
                with patch.object(command.os, operation, side_effect=OSError("disk failure")):
                    with self.assertRaises(OSError):
                        self.register()
                self.assert_unregistered()

    def test_publication_is_complete_and_waits_for_all_verified_assets(self):
        real_link = os.link

        def link(source, target):
            self.assertFalse(self.target.exists())
            self.assertEqual(Path(source).read_bytes(), self.raw)
            self.assertEqual(self.client.download_as_bytes.call_count, len(self.payloads))
            real_link(source, target)
            self.assertEqual(self.target.read_bytes(), self.raw)

        with patch.object(command.os, "link", side_effect=link):
            self.register()
        self.assertEqual(set(self.snapshot()), set(self.baseline) | {self.target.name})

    def test_concurrent_registration_is_not_overwritten_or_silently_accepted(self):
        real_link = os.link
        for identical in (False, True):
            with self.subTest(identical=identical):
                concurrent = self.raw if identical else json.dumps(
                    dict(self.manifest, stadiumName="Concurrent registration")).encode()

                def link(source, target):
                    self.target.write_bytes(concurrent)
                    real_link(source, target)

                with patch.object(command.os, "link", side_effect=link):
                    if identical:
                        self.register()
                    else:
                        with self.assertRaisesRegex(ValueError, "keine automatische Überschreibung"):
                            self.register()
                self.assertEqual(self.target.read_bytes(), concurrent)
                self.assertEqual(set(self.snapshot()), set(self.baseline) | {self.target.name})
                self.target.unlink()

    def test_local_change_after_preflight_is_not_uploaded(self):
        key = self.key("last.webp")
        def exists(actual):
            if actual == key:
                (self.assets / "last.webp").write_bytes(b"changed after preflight")
            return actual in self.remote

        self.client.exists.side_effect = exists
        with self.assertRaisesRegex(ValueError, "Asset-Prüfsumme"):
            self.register()
        self.assertNotIn(key, self.remote)
        self.assertNotIn(key, [call.args[0]
                              for call in self.client.upload_from_bytes.call_args_list])
        self.assert_unregistered()
