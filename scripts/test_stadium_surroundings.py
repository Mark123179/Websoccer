"""Offline tests for profiles, frozen packs and returned-image diagnostics."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from build_stadium_surroundings_pack import prompts
from review_stadium_surroundings import (
    MANUAL_FIELDS, check_expansion, read_plate, review, structure_check, verify_pack,
)
from surroundings_contract import (
    ROOT, background_registration, camera_for, composite, load_profile,
    read_json, source_geometry, validate_export, visibility_masks,
)

BASE = ROOT / "generated-artifacts/stadium-main-stand-back-probe"
PACKS = ROOT / "generated-artifacts/stadium-surroundings"


def structure_fixture():
    image = Image.new("RGB", (512, 256), "#c8cfbd")
    draw = ImageDraw.Draw(image)
    for x, y, w, h in [(20, 40, 65, 37), (123, 80, 37, 90),
                       (275, 23, 85, 67), (420, 155, 53, 25)]:
        draw.rectangle((x, y, x+w, y+h), fill="#193a43")
    draw.line([(15, 215), (180, 200), (365, 140), (490, 90)], fill="#172f48", width=7)
    return image


class SurroundingsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.export = read_json(BASE / "verification.json")
        cls.approved = read_json(ROOT / "generated-artifacts/stadium-middle-probe/verification.json")["states"][0]
        cls.profile = load_profile(ROOT / "docs/stadium/surroundings-profiles/elversberg.json")

    def test_profile_rejects_unknown_adapter(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = copy.deepcopy(self.profile)
            p["model_adapter"] = "generic-stadium"
            path = Path(tmp) / "profile.json"
            path.write_text(json.dumps(p))
            with self.assertRaisesRegex(ValueError, "Unsupported model"):
                load_profile(path)

    def test_model_orientation_checked(self):
        changed = copy.deepcopy(self.profile)
        changed["rear_stand"] = "NORD"
        with self.assertRaisesRegex(ValueError, "orientation"):
            validate_export(changed, self.export, self.approved)

    def test_missing_or_duplicate_state_rejected(self):
        changed = copy.deepcopy(self.export)
        changed["states"].append(next(s for s in changed["states"] if s["club"] == "elversberg" and s["variant"] == "day"))
        with self.assertRaisesRegex(ValueError, "duplicate"):
            validate_export(self.profile, changed, self.approved)

    def test_camera_change_rejected(self):
        changed = copy.deepcopy(self.export)
        next(s for s in changed["states"] if s["club"] == "elversberg")["projection"][0] += .01
        with self.assertRaisesRegex(ValueError, "camera changed"):
            validate_export(self.profile, changed, self.approved)

    def test_prompt_limits_and_no_guessed_lidl_height(self):
        for club in ("dortmund", "elversberg"):
            profile = load_profile(ROOT / f"docs/stadium/surroundings-profiles/{club}.json")
            day, night = prompts(profile)
            self.assertLessEqual(len(day), 15000)
            self.assertLessEqual(len(night), 15000)
        giant = copy.deepcopy(self.profile)
        giant["priority_features"][0]["note"] = "x"*16000
        with self.assertRaisesRegex(ValueError, "15000"):
            prompts(giant)

    def test_ground_registration_excludes_current_roof_and_model(self):
        camera = camera_for(self.export)
        geometry = source_geometry(self.profile, camera)
        before = background_registration(camera, geometry["frame"])
        export = copy.deepcopy(self.export)
        export["states"][0]["visibleRoofMeshes"] = 999
        export["states"][0]["orientation"]["roofSegmentsAdded"] = 100
        self.assertEqual(before, background_registration(camera_for(export), geometry["frame"]))
        changed = copy.deepcopy(camera)
        changed["position"][0] += 1
        self.assertNotEqual(before, background_registration(changed, geometry["frame"]))

    def test_photo_roof_remnants_outside_ground_footprint_removed(self):
        from PIL import ImageFilter
        manifest, _, _ = verify_pack(PACKS / "dortmund")
        geometry = source_geometry(manifest["profile"], manifest["camera"])
        footprint_only = np.asarray(Image.fromarray(
            ((geometry["site"] | geometry["pitch"])*255).astype("uint8")
        ).filter(ImageFilter.MaxFilter(11))) > 128
        final_mask = np.asarray(Image.open(PACKS/"dortmund"/"02_unknown_stadium_ground_mask.png")) > 128
        final_reference = np.asarray(Image.open(PACKS/"dortmund"/"01_background_reference.png"))
        # Fixed samples from visually identified roof/pylon imagery in the
        # original registered photo, not points chosen from the new polygon.
        for x, y in ((930, 195), (1335, 196), (1820, 335), (1760, 270)):
            self.assertFalse(footprint_only[y, x], "Must reproduce the former footprint-only gap")
            self.assertTrue(final_mask[y, x], "Source stadium imagery escaped removal")
            np.testing.assert_array_equal(final_reference[y, x], [104, 112, 119])
        all_photo_pixels = geometry["projected_photo_removal"]
        self.assertTrue(np.any(all_photo_pixels & ~geometry["site"]))
        self.assertTrue(np.all(final_mask[all_photo_pixels]))
        self.assertTrue(np.all(final_reference[all_photo_pixels] == [104, 112, 119]))

    def test_changed_orthophoto_requires_removal_recalibration(self):
        profile = load_profile(ROOT / "docs/stadium/surroundings-profiles/dortmund.json")
        profile["photo_stadium_removal"]["source_sha256"] = "wrong"
        with self.assertRaisesRegex(ValueError, "Photo source changed"):
            source_geometry(profile, camera_for(self.export))

    def test_pilot_visibility_matches_original_audit(self):
        audit = read_json(BASE / "geo_verification.json")
        for club in ("dortmund", "elversberg"):
            manifest, pitch, images = verify_pack(PACKS / club)
            geometry = source_geometry(manifest["profile"], manifest["camera"])
            for roof in (True, False):
                masks = visibility_masks(geometry, images[(roof, "silhouette")])
                original = audit[club]["states"][f"{club}_{'roof' if roof else 'no_roof'}"]["pixels"]
                self.assertEqual({k: int(m.sum()) for k, m in masks.items()}, original)
                self.assertEqual(int(pitch.sum()), 416792)

    def test_composite_preserves_each_original_field(self):
        for club in ("dortmund", "elversberg"):
            manifest, pitch, images = verify_pack(PACKS / club)
            plate = Image.new("RGB", tuple(manifest["camera"]["format"]), "magenta")
            for roof in (True, False):
                for time in ("day", "night"):
                    original = images[(roof, time)]
                    output = composite(plate, original, images[(roof, "silhouette")], pitch)
                    np.testing.assert_array_equal(np.asarray(output)[pitch], np.asarray(original)[pitch])

    def test_bad_dimensions_and_alpha_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.png"
            Image.new("RGB", (20, 10)).save(path)
            with self.assertRaisesRegex(ValueError, "dimensions"):
                read_plate(path, [1880, 940])
            Image.new("RGBA", (20, 10), (0, 0, 0, 0)).save(path)
            with self.assertRaisesRegex(ValueError, "opaque"):
                read_plate(path, [20, 10])

    def test_huge_global_night_translation_detected_despite_brightness(self):
        day = structure_fixture()
        dark = (np.asarray(day).astype(float)*.25).astype(np.uint8)
        shifted = Image.fromarray(np.roll(dark, 24, axis=1))
        self.assertEqual(structure_check(day, shifted)["status"], "shift_detected")

    def test_brightness_alone_not_rejected_or_approved(self):
        day = structure_fixture()
        night = Image.fromarray((np.asarray(day)*.25).astype(np.uint8))
        self.assertEqual(structure_check(day, night)["status"], "manual_review_required")

    def test_uniform_images_require_manual_review(self):
        blank = Image.new("RGB", (512, 256), "gray")
        self.assertEqual(structure_check(blank, blank)["status"], "insufficient_structure")

    def test_duplicate_expansion_not_accepted(self):
        manifest, _, images = verify_pack(PACKS / "elversberg")
        with self.assertRaisesRegex(ValueError, "identical"):
            check_expansion(manifest, manifest, images, images)

    def test_eight_composites_with_registered_expansion_fixture(self):
        # Synthetic coverage fixture, explicitly NOT a real stadium expansion.
        import hashlib
        import shutil
        from surroundings_contract import file_sha
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            expanded = root / "expansion-fixture"
            shutil.copytree(PACKS/"elversberg", expanded)
            manifest = read_json(expanded/"manifest.json")
            for state in manifest["states"]:
                if state.get("variant", "day") != "day":
                    continue
                evidence = state["imageEvidence"]["silhouette"]
                filename = expanded/"checks"/evidence["file"]
                image = Image.open(filename).convert("L")
                ImageDraw.Draw(image).rectangle((10, 10, 100, 40), fill=255)
                image.save(filename)
                data = filename.read_bytes()
                evidence["sha256"] = hashlib.sha256(data).hexdigest()
                evidence["bindingSha256"] = hashlib.sha256(
                    evidence["contextJson"].encode()+b"\0"+data).hexdigest()
                manifest["files"]["checks/"+evidence["file"]] = file_sha(filename)
            (expanded/"manifest.json").write_text(json.dumps(manifest))
            plate = root/"fixture.png"
            Image.new("RGB", (1880, 940), "#293b4c").save(plate)
            manual = root/"manual.json"
            manual.write_text(json.dumps({key: True for key in MANUAL_FIELDS}))
            report = review(PACKS/"elversberg", plate, plate, root/"review", manual, expanded)
            self.assertEqual(report["status"], "ready_for_separate_integration_decision")
            self.assertEqual(len(report["acceptance_matrix"]), 8)
            self.assertTrue(all(row["pitch_pixels_exact"] for row in report["acceptance_matrix"]))
            # Camera, frame and background reuse survive the fixture geometry change.
            self.assertEqual(manifest["background_registration"], report["background_registration"])

    def test_expansion_cannot_change_registration(self):
        manifest, _, images = verify_pack(PACKS / "elversberg")
        changed = copy.deepcopy(manifest)
        changed["background_registration"] = "wrong"
        with self.assertRaisesRegex(ValueError, "another locality"):
            check_expansion(manifest, changed, images, images)

    def test_returned_fixture_cannot_silently_become_approved(self):
        # This is a uniform test plate, not a Higgsfield or user image.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image_path = root / "fixture.png"
            Image.new("RGB", (1880, 940), "#345678").save(image_path)
            manual_path = root / "manual.json"
            manual_path.write_text(json.dumps({key: True for key in MANUAL_FIELDS}))
            report = review(PACKS/"elversberg", image_path, image_path, root/"review", manual_path)
            self.assertEqual(report["status"], "awaiting_manual_review_and_or_expansion")
            self.assertEqual(len(report["acceptance_matrix"]), 8)
            self.assertEqual(sum(c["status"] == "awaiting_expansion_render" for c in report["acceptance_matrix"]), 4)

    def test_pack_tamper_rejected(self):
        import shutil
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)/"pack"
            shutil.copytree(PACKS/"dortmund", dest)
            (dest/"prompt_day.txt").write_text("changed")
            with self.assertRaisesRegex(ValueError, "Changed pack"):
                verify_pack(dest)


if __name__ == "__main__":
    unittest.main()
