"""Offline evidence checks for one completed height/sight deliverable."""
import hashlib
import json
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from geo_probe_geometry import lonlat_to_scene, polygon_mask

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "generated-artifacts/elversberg-height-visibility"
BASE = ROOT / "generated-artifacts/stadium-main-stand-back-probe"


class HeightEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs = json.loads((OUT / "height_inputs.json").read_text())
        cls.render = json.loads((OUT / "render_verification.json").read_text())
        cls.report = json.loads((OUT / "height_visibility.json").read_text())
        cls.keep = polygon_mask(cls.inputs["camera"],
                                [(-52.5, -34), (52.5, -34), (52.5, 34), (-52.5, 34)])

    def test_approved_camera_and_roof_states(self):
        approved = json.loads((ROOT / "generated-artifacts/stadium-middle-probe/verification.json").read_text())["states"][0]
        self.assertEqual(self.inputs["camera"]["projection"], approved["projection"])
        self.assertEqual(self.inputs["camera"]["worldInverse"], approved["pose"])
        self.assertEqual(self.inputs["camera"]["corners"], approved["corners"])
        for a, b in zip(self.render["fieldCorners"], approved["corners"]):
            for axis in ("x", "y"):
                self.assertAlmostEqual(a[axis], b[axis], places=9)
        states = self.render["baselineStates"]
        self.assertEqual(len(states), 2)
        self.assertEqual(next(s for s in states if not s["roof"])["visibleRoofMeshes"], 0)
        self.assertGreater(next(s for s in states if s["roof"])["visibleRoofMeshes"], 0)

    def test_no_source_positions_changed(self):
        osm = json.loads((ROOT / "stadium_editor/blueprints/v2/elversberg.json").read_text())
        ways = {e["id"]: e for e in osm["elements"] if e["type"] == "way"}
        for o in self.inputs["objects"]:
            polygon = [list(lonlat_to_scene(self.inputs["frame"], p["lon"], p["lat"], True))
                       for p in ways[o["osm_id"]]["geometry"][:-1]]
            self.assertEqual(o["polygon"], polygon)

    def test_exact_pitch_pixels_in_every_delivered_picture(self):
        self.assertEqual(int(self.keep.sum()), 416792)
        for roof in ("roof", "no_roof"):
            original = np.asarray(Image.open(BASE / f"elversberg_{roof}.png").convert("RGB"))
            for prefix in ("height_envelopes", "lidl_assumed_6m"):
                image = np.asarray(Image.open(OUT / f"{prefix}_{roof}.png").convert("RGB"))
                self.assertTrue(np.array_equal(original[self.keep], image[self.keep]))

    def test_sources_unchanged(self):
        for path, digest in self.inputs["provenance"]["sha256"].items():
            self.assertEqual(hashlib.sha256((ROOT / path).read_bytes()).hexdigest(), digest, path)

    def test_lidl_not_silently_assigned_candidate_height(self):
        lidl = next(o for o in self.inputs["objects"] if o["osm_id"] == 53864241)
        self.assertFalse(lidl["matched"])
        self.assertIsNone(lidl["measured_height_m"])
        self.assertIsNone(lidl["height_envelope_m"])
        self.assertNotIn(53864241, self.render["objects"])
        self.assertLess(lidl["best_iou"], .04)

    def test_measured_landmarks_and_occlusion_order(self):
        self.assertEqual(self.inputs["matching"]["page_member_counts"], [200, 20])
        for state in self.report["states"].values():
            self.assertLess(state["stadium_occupancy_pixel_mismatch"], self.keep.size * .0015)
            for o in state["landmarks"]:
                for kind in ("roof_pixels", "facade_pixels"):
                    self.assertLessEqual(o["with_measured_neighbours"][kind], o["with_stadium"][kind])
                    self.assertLessEqual(o["with_stadium"][kind], o["alone"][kind])
                    self.assertGreater(o["with_measured_neighbours"][kind], 0)
                self.assertEqual(o["with_measured_neighbours"]["raw_field_overlap_pixels"], 0)
            self.assertEqual(set(state["lidl_assumed_height_sweep_m"]), {"3", "6", "9", "12"})

    def test_report_explicitly_limits_its_claim(self):
        text = (OUT / "report.html").read_text()
        for phrase in ("Bedingte Geometrieprüfung", "keine Freigabe",
                       "keine belastbare Höhenzuordnung", "Geländehöhen",
                       "Baumkronen", "Keine KI-Erstellung", "kein produktiver Einbau"):
            self.assertIn(phrase, text)
        self.assertNotIn("https://imgs", text)


if __name__ == "__main__":
    unittest.main()
