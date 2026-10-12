"""Pitch contract and registration gates, without storage/database mutations."""
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import struct
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from stadium_editor.model_registry import model_manifest
from stadium_editor.pitch_validation import (
    PitchValidationError, measure_pitch, validate_pitch_geometry,
)


def source(length=105, width=68, line_width=0.16, extras=True):
    """Triangle ribbons, not a precomputed measurement claim."""
    points = []
    def rectangle(x0, z0, x1, z1):
        points.extend([(x0, 0, z0), (x1, 0, z0), (x1, 0, z1),
                       (x0, 0, z0), (x1, 0, z1), (x0, 0, z1)])
    d = line_width / 2
    for x in (-width / 2, width / 2):
        rectangle(x-d, -length/2, x+d, length/2)
    for z in (-length / 2, length / 2, 0):
        rectangle(-width/2, z-d, width/2, z+d)
    if extras:
        # Isolated behind-goal markings and corner geometry widen the overall
        # bounds; grass is deliberately much larger and must be ignored.
        rectangle(5, length/2+2, 5.16, length/2+3)
        rectangle(width/2-1, length/2-1, width/2+1, length/2+1)
    binary = b"".join(struct.pack("<fff", *p) for p in points)
    offset = len(binary)
    binary += struct.pack(f"<{len(points)}I", *range(len(points)))
    mesh = {"name": "lines", "positionOffset": 0, "uvOffset": 0,
            "vertexCount": len(points),
            "parts": [{"material": "000STADIUMLINE", "indexOffset": offset,
                       "indexCount": len(points), "color": [1, 1, 1], "texture": None}]}
    return {"meshes": [mesh], "geometrySha256": hashlib.sha256(binary).hexdigest()}, binary


class PitchTests(TestCase):
    def test_boundary_midpoints_ignore_line_width_and_extra_marks(self):
        for thickness in (0.08, 0.16, 0.24):
            manifest, binary = source(line_width=thickness)
            before = bytes(binary)
            result = validate_pitch_geometry(manifest, binary)
            self.assertAlmostEqual(result["lineCenterLengthMeters"], 105, places=4)
            self.assertAlmostEqual(result["lineCenterWidthMeters"], 68, places=4)
            self.assertEqual(binary, before)

    def test_larger_grass_does_not_change_measurement(self):
        manifest, binary = source()
        manifest["meshes"].append({"name": "grass", "parts": [{"material": "grass"}]})
        self.assertEqual(validate_pitch_geometry(manifest, binary)["lineCenterWidthMeters"], 68)

    def test_wrong_dimensions_fail_without_rescaling(self):
        for length, width in ((110, 68), (105, 70), (100, 64)):
            manifest, binary = source(length, width)
            with self.assertRaisesRegex(PitchValidationError, "Abweichende Spielfeldgröße"):
                validate_pitch_geometry(manifest, binary)
            self.assertAlmostEqual(measure_pitch(manifest, binary)["lineCenterLengthMeters"], length)

    def test_tolerance_is_not_a_rounding_acceptance(self):
        manifest, binary = source(105.01)
        validate_pitch_geometry(manifest, binary)
        manifest, binary = source(105.03)
        with self.assertRaisesRegex(PitchValidationError, "Abweichende"):
            validate_pitch_geometry(manifest, binary)

    def test_unknown_missing_incomplete_and_ambiguous_geometry_fail_closed(self):
        manifest, binary = source()
        missing = deepcopy(manifest)
        missing["meshes"][0]["parts"][0]["material"] = "unbekannt"
        with self.assertRaisesRegex(PitchValidationError, "nicht automatisch messbar"):
            validate_pitch_geometry(missing, binary)
        for damaged in (binary[:10], binary[:-4]):
            with self.assertRaisesRegex(PitchValidationError, "nicht automatisch messbar"):
                measure_pitch(manifest, damaged)
        manifest["meshes"][0]["parts"][0]["indexCount"] = 3
        with self.assertRaisesRegex(PitchValidationError, "nicht automatisch messbar"):
            measure_pitch(manifest, binary)

    def test_hash_claim_is_not_trusted(self):
        manifest, binary = source()
        manifest["geometrySha256"] = "0" * 64
        with self.assertRaisesRegex(PitchValidationError, "Prüfsumme"):
            validate_pitch_geometry(manifest, binary)

    def test_invalid_indices_and_nonfinite_positions_are_not_measurements(self):
        manifest, binary = source()
        bad = bytearray(binary)
        struct.pack_into("<I", bad, manifest["meshes"][0]["parts"][0]["indexOffset"], 999999)
        with self.assertRaisesRegex(PitchValidationError, "Dreiecksindex"):
            measure_pitch(manifest, bad)
        struct.pack_into("<f", bad, 0, float("nan"))
        with self.assertRaisesRegex(PitchValidationError, "nicht endliche"):
            measure_pitch(manifest, bad)

    def test_real_dortmund_original_and_quarter_turn(self):
        root = Path(__file__).parent / "static/stadium_editor/dortmund_original"
        manifest = json.loads((root / "manifest.json").read_text())
        binary = (root / "geometry.bin").read_bytes()
        result = measure_pitch(manifest, binary)
        self.assertAlmostEqual(result["lineCenterLengthMeters"], 105, places=3)
        self.assertAlmostEqual(result["lineCenterWidthMeters"], 68, places=3)
        # Source layout may be quarter-turned, but never scaled.
        transformed = bytearray(binary)
        for mesh in manifest["meshes"]:
            if any(p.get("material") == "000STADIUMLINE" for p in mesh["parts"]):
                for i in range(mesh["vertexCount"]):
                    offset = mesh["positionOffset"] + i * 12
                    x, y, z = struct.unpack_from("<fff", binary, offset)
                    struct.pack_into("<fff", transformed, offset, z, y, -x)
        self.assertAlmostEqual(measure_pitch(manifest, transformed)["lineCenterLengthMeters"], 105, places=3)
        # Other rotations are unsupported, not silently passed.
        for mesh in manifest["meshes"]:
            if any(p.get("material") == "000STADIUMLINE" for p in mesh["parts"]):
                for i in range(mesh["vertexCount"]):
                    offset = mesh["positionOffset"] + i * 12
                    x, y, z = struct.unpack_from("<fff", binary, offset)
                    struct.pack_into("<fff", transformed, offset,
                                     (x-z)/math.sqrt(2), y, (x+z)/math.sqrt(2))
        with self.assertRaisesRegex(PitchValidationError, "nicht automatisch messbar"):
            measure_pitch(manifest, transformed)

    def test_registration_rejects_before_storage_or_publication(self):
        from scripts.register_stadium_model import register
        for dimensions in ((110, 70), (105, 68)):
            geometry, binary = source(*dimensions)
            manifest = deepcopy(model_manifest(908))
            manifest.update(geometry, textures=[], assetSha256={"geometry.bin": geometry["geometrySha256"]})
            if dimensions == (105, 68):
                manifest["meshes"][0]["parts"][0]["material"] = "unknown"
            with TemporaryDirectory() as directory:
                package = Path(directory)
                (package / "models").mkdir()
                (package / "models/908.json").write_text(json.dumps(manifest))
                assets = package / "stadium-models/908" / manifest["assetVersion"]
                assets.mkdir(parents=True)
                (assets / "geometry.bin").write_bytes(binary)
                target = package / "registration.json"
                with patch("scripts.register_stadium_model.get_client") as storage, \
                     patch("scripts.register_stadium_model.manifest_path", return_value=target):
                    with self.assertRaises(PitchValidationError):
                        register(package, 908)
                    storage.assert_not_called()
                    self.assertFalse(target.exists())

    def test_valid_registration_publishes_only_after_storage_verification(self):
        from scripts.register_stadium_model import register
        geometry, binary = source()
        manifest = deepcopy(model_manifest(908))
        manifest.update(geometry, textures=[], assetSha256={"geometry.bin": geometry["geometrySha256"]})
        with TemporaryDirectory() as directory:
            package = Path(directory)
            (package / "models").mkdir()
            raw = json.dumps(manifest).encode()
            (package / "models/908.json").write_bytes(raw)
            assets = package / "stadium-models/908" / manifest["assetVersion"]
            assets.mkdir(parents=True)
            (assets / "geometry.bin").write_bytes(binary)
            target = package / "registration.json"
            with patch("scripts.register_stadium_model.get_client") as storage, \
                 patch("scripts.register_stadium_model.manifest_path", return_value=target):
                storage.return_value.exists.return_value = False
                storage.return_value.download_as_bytes.return_value = binary
                register(package, 908)
                self.assertEqual(target.read_bytes(), raw)
                storage.return_value.upload_from_bytes.assert_called_once()
