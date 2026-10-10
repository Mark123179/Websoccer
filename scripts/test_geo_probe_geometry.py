"""Read-only regression checks; no Django database or application writes."""
import json
import copy
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from probe_image_evidence import verify_probe_image
import build_dortmund_geo_probe

from geo_probe_geometry import (
    frame_from_osm, ground_rays, lonlat_to_scene, polygon_mask,
    project_ground, scene_to_lonlat,
)

ROOT = Path(__file__).resolve().parents[1]


class GeoProbeGeometryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # The read-only geometry tests also work before the bridge writes camera_exact.
        export = json.loads((ROOT /
            "generated-artifacts/stadium-main-stand-back-probe/verification.json").read_text())
        state = export["states"][0]
        cls.camera = {**export["fitted"], "projection": state["projection"],
                      "worldInverse": state["pose"], "corners": state["corners"]}
        cls.frame = json.loads((ROOT /
            "generated-artifacts/dortmund-site-study/source.json").read_text())["frame"]

    def test_half_turn_changes_map_not_camera(self):
        before = scene_to_lonlat(self.frame, 10, 110, False)
        after = scene_to_lonlat(self.frame, -10, -110, True)
        self.assertEqual(before, after)
        east = scene_to_lonlat(self.frame, 0, 110, True)
        west = scene_to_lonlat(self.frame, 0, 110, False)
        self.assertGreater(east[0], west[0])

    def test_map_roundtrip(self):
        for turn in (True, False):
            for point in ((0, 0), (52.5, 34), (-200, 120)):
                lon, lat = scene_to_lonlat(self.frame, *point, turn)
                np.testing.assert_allclose(
                    lonlat_to_scene(self.frame, lon, lat, turn), point, atol=1e-8)

    def test_pixel_center_ground_roundtrip(self):
        ground = ground_rays(self.camera)
        width, _ = self.camera["format"]
        for index in (0, width-1, len(ground[0])//2, len(ground[0])-1):
            x, y = project_ground(self.camera, ground[0, index], ground[2, index])
            np.testing.assert_allclose((x, y), (index % width+.5, index//width+.5), atol=1e-9)

    def test_field_polygon_matches_exported_corners(self):
        points = [(52.5, -34), (-52.5, -34), (-52.5, 34), (52.5, 34)]
        for point, corner in zip(points, self.camera["corners"]):
            np.testing.assert_allclose(project_ground(self.camera, *point),
                                       [corner["x"], corner["y"]], atol=1e-10)
        mask = polygon_mask(self.camera, points)
        self.assertEqual(mask.shape, (940, 1880))
        self.assertGreater(int(mask.sum()), 400000)

    def test_elversberg_camera_side_is_northeast(self):
        osm = json.loads((ROOT / "stadium_editor/blueprints/v2/elversberg.json").read_text())
        frame = frame_from_osm(osm, 1154632806, 31339206)
        center = scene_to_lonlat(frame, 0, 0, True)
        camera = scene_to_lonlat(frame, 0, 110, True)
        self.assertGreater(camera[0], center[0])
        self.assertGreater(camera[1], center[1])


class GeoProbeImageEvidenceTests(unittest.TestCase):
    """Real PNGs and the real JS exporter/bridge; all writes are temporary."""

    @classmethod
    def setUpClass(cls):
        generated = ROOT / "generated-artifacts"
        generated.mkdir(exist_ok=True)
        cls.fixture_tmp = tempfile.TemporaryDirectory(prefix="mask-evidence-", dir=generated)
        cls.addClassCleanup(cls.fixture_tmp.cleanup)
        cls.fixture = Path(cls.fixture_tmp.name)
        cls.export = {"fitted": {"format": [1880, 940], "position": [0, 50, 110]},
                      "states": []}
        for index, (club, roof) in enumerate(
                (c, r) for c in ("dortmund", "elversberg") for r in (True, False)):
            state = {"club": club, "roof": roof, "variant": "day",
                     "orientation": {"modelTurnDegrees": 180, "rearStand": "WEST"},
                     "projection": list(range(16)), "pose": list(range(16)),
                     "corners": [{"x": 100, "y": 100}], "visibleRoofMeshes": int(roof)}
            cls.export["states"].append(state)
            stem = f"{club}_{'roof' if roof else 'no_roof'}"
            for role in ("render", "silhouette"):
                image = Image.new("RGB" if role == "render" else "L", (1880, 940))
                ImageDraw.Draw(image).rectangle(
                    (10 + index * 80, 10, 60 + index * 80, 80),
                    fill=(30 + index * 40, 200, 70) if role == "render" else 255)
                image.save(cls.fixture / f"{stem}{'_silhouette' if role == 'silhouette' else ''}.png")
        (cls.fixture / "verification.json").write_text(json.dumps(cls.export))
        # Produce evidence with the SAME helper called by the browser exporter.
        script = """
          import fs from 'node:fs';
          import {writeProbeImage} from './scripts/probe_image_evidence.mjs';
          const dir=process.argv[1];
          const data=JSON.parse(fs.readFileSync(`${dir}/verification.json`));
          for(const state of data.states){
            state.imageEvidence={};
            const stem=`${state.club}_${state.roof?'roof':'no_roof'}`;
            for(const role of ['render','silhouette']){
              const bytes=fs.readFileSync(`${dir}/${stem}${role==='silhouette'?'_silhouette':''}.png`);
              state.imageEvidence[role]=writeProbeImage(dir,state,data.fitted,role,bytes);
            }
          }
          fs.writeFileSync(`${dir}/verification.json`,JSON.stringify(data));
        """
        subprocess.run(["node", "--input-type=module", "-e", script, str(cls.fixture)],
                       cwd=ROOT, check=True, capture_output=True, text=True)
        cls.export = json.loads((cls.fixture / "verification.json").read_text())
        (cls.fixture / "approved.json").write_text(json.dumps({"states": [cls.export["states"][0]]}))

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(
            prefix="mask-regression-", dir=ROOT / "generated-artifacts")
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        shutil.copytree(self.fixture, self.directory, dirs_exist_ok=True)
        self.export = copy.deepcopy(type(self).export)
        (self.directory / "verification.json").write_text(json.dumps(self.export))

    def bridge_result(self):
        (self.directory / "verification.json").write_text(json.dumps(self.export))
        script = """
          import {verifyGeoExport} from './scripts/export_dortmund_geo_probe.mjs';
          verifyGeoExport(process.argv[1], `${process.argv[1]}/approved.json`);
        """
        return subprocess.run(
            ["node", "--input-type=module", "-e", script, str(self.directory)],
            cwd=ROOT, capture_output=True, text=True)

    def assert_rejected(self, message, role="silhouette", state=None):
        state = state or self.export["states"][0]
        with self.assertRaisesRegex(ValueError, message):
            verify_probe_image(self.directory, state, self.export["fitted"], role)
        result = self.bridge_result()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(message, result.stderr)
        self.assertFalse((self.directory / "camera_exact.json").exists())

    def test_fresh_pngs_match_in_javascript_and_python(self):
        before = {p.name: p.read_bytes() for p in self.directory.iterdir()}
        for state in self.export["states"]:
            for role in ("render", "silhouette"):
                self.assertEqual(verify_probe_image(
                    self.directory, state, self.export["fitted"], role).size, (1880, 940))
        self.assertEqual(self.bridge_result().returncode, 0)
        # Validation itself is read-only; the fixture manifest rewrite is byte-identical.
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.directory.iterdir()})

    def test_stale_rotated_silhouette_same_filename(self):
        path = self.directory / "dortmund_roof_silhouette.png"
        with Image.open(path) as image:
            stale = image.transpose(Image.Transpose.ROTATE_180)
        stale.save(path)
        self.assert_rejected("Image content mismatch")

    def test_silhouettes_swapped_between_clubs_or_roofs(self):
        for source in ("dortmund_no_roof", "elversberg_roof"):
            with self.subTest(source=source):
                shutil.copyfile(self.directory / f"{source}_silhouette.png",
                                self.directory / "dortmund_roof_silhouette.png")
                self.assert_rejected("Image content mismatch")

    def test_old_render_same_filename(self):
        shutil.copyfile(self.directory / "dortmund_no_roof.png",
                        self.directory / "dortmund_roof.png")
        self.assert_rejected("Image content mismatch", role="render")

    def test_state_context_cannot_relabel_an_image(self):
        for field, replacement in (
                ("club", "elversberg"), ("roof", False), ("variant", "night"),
                ("orientation", {"modelTurnDegrees": 180, "rearStand": "OST"})):
            with self.subTest(field=field):
                state = copy.deepcopy(self.export["states"][0])
                state[field] = replacement
                with self.assertRaisesRegex(ValueError, "Image context mismatch"):
                    verify_probe_image(self.directory, state, self.export["fitted"], "silhouette")
        self.export["states"][0]["orientation"]["rearStand"] = "OST"
        self.assert_rejected("Image context mismatch")

    def test_same_camera_parity_does_not_excuse_old_camera_evidence(self):
        # All four states and approved reference agree, but evidence still belongs
        # to the previous camera. Matrix/corner parity on its own would pass.
        for key in ("projection", "pose", "corners"):
            with self.subTest(key=key):
                data = copy.deepcopy(type(self).export)
                for state in data["states"]:
                    if key == "corners":
                        state[key][0]["x"] += 1
                    else:
                        state[key][0] += 1
                self.export = data
                (self.directory / "approved.json").write_text(
                    json.dumps({"states": [data["states"][0]]}))
                self.assert_rejected("Image context mismatch")

    def test_camera_position_is_bound(self):
        self.export["fitted"]["position"][0] += 1
        self.assert_rejected("Image context mismatch")

    def test_context_rewrite_without_new_byte_binding_is_rejected(self):
        state = self.export["states"][0]
        state["orientation"]["rearStand"] = "OST"
        for evidence in state["imageEvidence"].values():
            context = json.loads(evidence["contextJson"])
            context["orientation"] = state["orientation"]
            evidence["contextJson"] = json.dumps(context, separators=(",", ":"))
        self.assert_rejected("Image content mismatch")

    def test_export_without_evidence_is_not_silently_accepted(self):
        del self.export["states"][0]["imageEvidence"]
        self.assert_rejected("Missing image evidence")

    def test_incorrect_byte_binding_is_rejected(self):
        self.export["states"][0]["imageEvidence"]["silhouette"]["bindingSha256"] = "0" * 64
        self.assert_rejected("Image content mismatch")

    def test_map_audit_rejects_stale_mask_before_writing_outputs(self):
        state = self.export["states"][0]
        camera = {**self.export["fitted"], "projection": state["projection"],
                  "worldInverse": state["pose"], "corners": state["corners"],
                  "modelTurnDegrees": 180}
        (self.directory / "camera_exact.json").write_text(json.dumps(camera))
        temporary_root = self.directory / "audit-root"
        approved_dir = temporary_root / "generated-artifacts/stadium-middle-probe"
        approved_dir.mkdir(parents=True)
        shutil.copyfile(self.directory / "approved.json", approved_dir / "verification.json")
        shutil.copyfile(self.directory / "elversberg_roof_silhouette.png",
                        self.directory / "dortmund_roof_silhouette.png")
        before = {p.name: p.read_bytes() for p in self.directory.iterdir() if p.is_file()}
        with patch.object(build_dortmund_geo_probe, "ROOT", temporary_root), \
                patch.object(build_dortmund_geo_probe, "OUT", self.directory):
            with self.assertRaisesRegex(ValueError, "Image content mismatch"):
                build_dortmund_geo_probe.main()
        self.assertEqual(before, {
            p.name: p.read_bytes() for p in self.directory.iterdir() if p.is_file()})


if __name__ == "__main__":
    unittest.main()
