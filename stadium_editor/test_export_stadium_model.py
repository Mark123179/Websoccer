"""Offline export gates: synthetic Unity sources, no database or storage."""
from contextlib import redirect_stderr, redirect_stdout
import hashlib
from io import StringIO
import json
from pathlib import Path
import struct
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

import numpy as np

from scripts import export_stadium_model as command
from stadium_editor.model_registry import model_manifest
from stadium_editor.pitch_validation import PitchValidationError
from stadium_editor.test_pitch_validation import source


def pointer(value, kind, path_id=1):
    return SimpleNamespace(
        read=lambda: value, type=SimpleNamespace(name=kind), path_id=path_id,
    )


class OfflineExportTests(TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.bundle = self.root / "source.bundle"
        self.bundle.write_bytes(b"synthetic Unity source")
        self.seats = self.root / "seats.json"
        self.seats.write_text(json.dumps({"seats": [{"pos": [0, 12, -75]}]}))
        self.calibration = model_manifest(908)["calibration"]
        self.out = self.root / "export"
        # Any accidental storage/DB import fails, also under plain unittest.
        guard = patch.dict("sys.modules", {
            "game.object_storage_backend": None,
            "replit.object_storage": None,
            "django.db": None,
        })
        guard.start()
        self.addCleanup(guard.stop)

    def unity_source(self, length=105, width=68, material="000STADIUMLINE"):
        manifest, binary = source(length, width)
        mesh = manifest["meshes"][0]
        vertices = list(struct.iter_unpack(
            "<fff", binary[:mesh["vertexCount"] * 12],
        ))
        # A real fixture-material triangle and a downward source light keep the
        # valid case on the complete exporter path, not just the pitch helper.
        vertices.extend([(0, 20, 0), (0.1, 20, 0), (0, 20, 0.1)])
        mesh_data = SimpleNamespace(m_Name="source-mesh")
        handler = Mock()
        handler.m_Vertices = vertices
        handler.m_UV0 = [(0, 0)] * len(vertices)
        handler.get_triangles.return_value = [
            list(range(mesh["vertexCount"])),
            list(range(mesh["vertexCount"], len(vertices))),
        ]
        image = Mock()
        image.save.side_effect = lambda path, *a, **kw: path.write_bytes(b"texture")
        texture = Mock(path_id=7)
        texture.read.return_value = SimpleNamespace(image=image)

        def mat(name):
            return pointer(SimpleNamespace(
                m_Name=name,
                m_SavedProperties=SimpleNamespace(
                    m_Colors=[], m_Floats=[],
                    m_TexEnvs=[("_MainTex", SimpleNamespace(m_Texture=texture))],
                ),
            ), "Material")

        renderer = SimpleNamespace(m_Enabled=True, m_Materials=[mat(material), mat("lamp")])
        go = SimpleNamespace(m_Name="PITCH2021")
        transform = SimpleNamespace(m_GameObject=pointer(go, "GameObject"), m_Father=None)
        go.m_Components = [pointer(renderer, "MeshRenderer"), pointer(transform, "Transform")]
        filt = SimpleNamespace(m_GameObject=pointer(go, "GameObject"),
                               m_Mesh=pointer(mesh_data, "Mesh"))
        light_go = SimpleNamespace(m_Name="source-light")
        light_transform = SimpleNamespace()
        light_go.m_Components = [pointer(light_transform, "Transform")]
        light = SimpleNamespace(
            m_Type=0, m_Enabled=True, m_GameObject=pointer(light_go, "GameObject"),
            m_Color=SimpleNamespace(r=1, g=1, b=1),
            m_Range=100, m_SpotAngle=60, m_Intensity=1,
        )
        light_world = np.eye(4)
        light_world[:3, 3] = [0, 20, 0]
        light_world[:3, 2] = [0, -1, 0]
        world = lambda t, cache: light_world if t is light_transform else np.eye(4)
        env = SimpleNamespace(objects=[
            pointer(filt, "MeshFilter"), pointer(light, "Light", 2),
        ])
        return env, handler, world, texture

    def export(self, fixture):
        env, handler, world, texture = fixture
        with patch.object(command.UnityPy, "load", return_value=env), \
             patch.object(command, "MeshHandler", return_value=handler), \
             patch.object(command, "world", side_effect=world), \
             redirect_stdout(StringIO()):
            command.export_model(self.bundle, self.seats, 908, "Teststadion",
                                 self.out, self.calibration)

    def snapshot(self):
        return {p.relative_to(self.out): p.read_bytes()
                for p in self.out.rglob("*") if p.is_file()}

    def test_wrong_dimensions_rejected_before_texture_read_or_output(self):
        for length, width in ((110, 68), (105, 70), (100, 64)):
            with self.subTest(length=length, width=width):
                fixture = self.unity_source(length, width)
                with self.assertRaisesRegex(
                    PitchValidationError,
                    rf"{length:.3f} × {width:.3f} m.*Keine automatische Skalierung",
                ):
                    self.export(fixture)
                fixture[3].read.assert_not_called()
                self.assertFalse(self.out.exists())

    def test_unmeasurable_source_leaves_existing_output_untouched(self):
        self.out.mkdir()
        (self.out / "manifest.json").write_bytes(b"existing package")
        (self.out / "texture-7.webp").write_bytes(b"existing texture")
        before = self.snapshot()
        fixture = self.unity_source(material="grass-texture-only")
        with self.assertRaisesRegex(PitchValidationError, "nicht automatisch messbar"):
            self.export(fixture)
        fixture[3].read.assert_not_called()
        self.assertEqual(self.snapshot(), before)

    def test_full_export_with_texture_preserves_stadium_name(self):
        fixture = self.unity_source()
        self.export(fixture)

        manifest = json.loads((self.out / "manifest.json").read_text())
        self.assertEqual(manifest["stadiumName"], "Teststadion")
        self.assertEqual(manifest["textures"], ["texture-7.webp"])
        self.assertEqual((self.out / "texture-7.webp").read_bytes(), b"texture")
        fixture[3].read.assert_called_once_with()
        self.assertEqual(manifest["geometrySha256"],
                         hashlib.sha256((self.out / "geometry.bin").read_bytes()).hexdigest())
        self.assertEqual(manifest["verifiedFixtureCount"], 1)

    def test_coincident_source_spotlights_share_one_runtime_position(self):
        fixture = self.unity_source()
        env = fixture[0]
        source_light = env.objects[-1].read()
        env.objects.extend(pointer(source_light, "Light", identity) for identity in range(3, 22))
        self.export(fixture)
        manifest = json.loads((self.out / "manifest.json").read_text())
        self.assertEqual(manifest["verifiedFixtureCount"], 20)
        self.assertEqual(len(manifest["fixtures"]), 1)
        self.assertEqual(set(manifest["fixtures"][0]["representedIds"]),
                         {str(identity) for identity in range(2, 22)})

    def test_valid_export_is_byte_identical_to_ungated_export(self):
        fixture = self.unity_source()
        with patch.object(command, "validate_pitch_geometry"):
            self.export(fixture)
        before = self.snapshot()
        self.assertEqual(set(before), {
            Path("manifest.json"), Path("geometry.bin"), Path("texture-7.webp"),
        })
        # Compare the complete output against the unchanged exporter path.
        for path in self.out.iterdir():
            path.unlink()
        self.export(fixture)
        self.assertEqual(self.snapshot(), before)
        manifest = json.loads(before[Path("manifest.json")])
        self.assertEqual(manifest["geometrySha256"],
                         hashlib.sha256(before[Path("geometry.bin")]).hexdigest())

    def test_cli_reports_both_rejections_without_traceback(self):
        calibration = self.root / "calibration.json"
        calibration.write_text(json.dumps(self.calibration))
        argv = ["export_stadium_model.py", "--bundle", str(self.bundle),
                "--seats", str(self.seats), "--fmi", "908", "--name", "Teststadion",
                "--out", str(self.out), "--calibration", str(calibration)]
        for fixture, message in (
            (self.unity_source(110), "Abweichende Spielfeldgröße: 110.000 × 68.000 m"),
            (self.unity_source(material="unknown"), "Spielfeld nicht automatisch messbar"),
        ):
            env, handler, world, texture = fixture
            stderr = StringIO()
            with patch("sys.argv", argv), \
                 patch.object(command.UnityPy, "load", return_value=env), \
                 patch.object(command, "MeshHandler", return_value=handler), \
                 patch.object(command, "world", side_effect=world), \
                 redirect_stderr(stderr):
                self.assertEqual(command.main(), 1)
            self.assertIn("Modell-Export abgebrochen", stderr.getvalue())
            self.assertIn(message, stderr.getvalue())
            self.assertNotIn("Traceback", stderr.getvalue())
            texture.read.assert_not_called()
            self.assertFalse(self.out.exists())
