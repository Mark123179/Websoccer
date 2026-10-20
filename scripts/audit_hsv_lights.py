"""Audit HSV source spots against approved lamp triangles; no registry/DB writes.

Creates a new study directory. Never overwrites the approved HSV study/package.
"""
import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import sys

import numpy as np
import UnityPy
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.export_stadium_study_lights import world
from scripts.stadium_light_surfaces import (
    calibrate_intensity, closest_surface, rejection_reasons, select_representatives,
)
from stadium_editor.model_registry import validate_model_manifest
from stadium_editor.pitch_validation import validate_pitch_geometry

STUDY = ROOT / "generated-artifacts/hsv-study"
REGISTRY = ROOT / "stadium_editor/blueprints/v2/models/947.json"
# Already reviewed original lamp bank and texture tex_bm_56. Do not expand this
# to roof membranes, billboard emissives or arbitrary nearby model geometry.
LAMP_MESH = "-3439041506061313772"
LAMP_MATERIAL = "56"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def audit(out, browser_scale=1, *, baseline_path=None, expected_baseline_sha=None,
          assets_dir=None):
    if out.exists():
        raise ValueError("Output exists; choose a new directory, never overwrite a reviewed package")
    baseline_raw = (baseline_path or REGISTRY).read_bytes()
    if baseline_path is not None and expected_baseline_sha is None:
        raise ValueError("Explicit baseline requires its expected SHA256")
    if expected_baseline_sha is not None and digest(baseline_raw) != expected_baseline_sha:
        raise ValueError("Explicit baseline hash differs; registry remains untouched")
    baseline = json.loads(baseline_raw)
    source = ROOT / "attached_assets" / baseline["source"]
    if digest(source.read_bytes()) != baseline["sourceSha256"]:
        raise ValueError("Original HSV bundle hash differs from the registry")
    assets = assets_dir or STUDY / "source-export"
    binary = (assets / "geometry.bin").read_bytes()
    if digest(binary) != baseline["geometrySha256"]:
        raise ValueError("Reprepare missing/changed source-export from the original bundle")
    for name, expected in baseline["assetSha256"].items():
        if digest((assets / name).read_bytes()) != expected:
            raise ValueError(f"Baseline asset hash mismatch: {name}")
    triangles, refs = [], []
    for mesh in baseline["meshes"]:
        if mesh["pathId"] != LAMP_MESH:
            continue
        vertices = np.frombuffer(binary, "<f4", count=mesh["vertexCount"]*3,
                                 offset=mesh["positionOffset"]).reshape(-1, 3)
        for part_index, part in enumerate(mesh["parts"]):
            if part["material"] != LAMP_MATERIAL:
                continue
            ix = np.frombuffer(binary, "<u4", count=part["indexCount"],
                               offset=part["indexOffset"]).reshape(-1, 3)
            triangles.extend(vertices[ix])
            refs.extend({"meshPathId": mesh["pathId"], "meshName": mesh["name"],
                         "material": part["material"], "partIndex": part_index,
                         "triangleIndex": i, "vertexIndices": ids.tolist()}
                        for i, ids in enumerate(ix))
    if not triangles:
        raise ValueError("Approved HSV lamp surface is missing")
    triangles = np.asarray(triangles)
    tree = cKDTree(triangles.reshape(-1, 3))
    cache, rows = {}, []
    for obj in UnityPy.load(str(source)).objects:
        if obj.type.name != "Light":
            continue
        light = obj.read()
        if light.m_Type != 0 or not light.m_Enabled:
            continue
        go = light.m_GameObject.read()
        transform = next(c.read() for c in go.m_Components if c.type.name == "Transform")
        matrix = world(transform, cache)
        position = matrix[:3, 3]
        direction = matrix[:3, :3] @ np.array([0., 0., 1.])
        direction /= np.linalg.norm(direction)
        vertex_distance = float(tree.query(position)[0])
        distance, closest, index = closest_surface(position, triangles)
        rows.append({
            "id": str(obj.path_id), "name": go.m_Name,
            "position": position.tolist(), "direction": direction.tolist(),
            "color": [light.m_Color.r, light.m_Color.g, light.m_Color.b],
            "range": light.m_Range, "angle": light.m_SpotAngle,
            "intensity": light.m_Intensity, "sourceIntensity": light.m_Intensity,
            "meshDistance": distance, "vertexDistance": vertex_distance,
            "nearestLampMesh": {**refs[index], "closestPoint": closest,
                                "triangle": triangles[index].tolist(),
                                "distanceMetric": "point-to-triangle"},
            "vertexRejections": rejection_reasons(position, direction, vertex_distance),
            "surfaceRejections": rejection_reasons(position, direction, distance),
        })
    rows.sort(key=lambda row: row["id"])
    accepted = [row for row in rows if not row["surfaceRejections"]]
    old_accepted = [row for row in rows if not row["vertexRejections"]]
    if {row["id"] for row in old_accepted} != {
            id for fixture in baseline["fixtures"] for id in fixture["representedIds"]}:
        raise ValueError("Vertex-gate reconstruction differs from approved source-light evidence")
    if len(old_accepted) != baseline["verifiedFixtureCount"]:
        raise ValueError("Baseline light count differs")
    fixtures = select_representatives(accepted, baseline["calibration"]["standAxes"])
    assert 0 < len(fixtures) <= 12
    for fixture in fixtures:
        fixture.pop("vertexRejections")
        fixture.pop("surfaceRejections")
    fixtures = calibrate_intensity(fixtures, browser_scale)
    candidate = deepcopy(baseline)
    candidate["fixtures"], candidate["verifiedFixtureCount"] = fixtures, len(accepted)
    candidate["lightingRevision"] = {
        "baselineAssetVersion": baseline["assetVersion"],
        "baselineManifestSha256": digest(baseline_raw),
        "lampDistanceMetric": "point-to-triangle",
        "sourceIntensityPreserved": True,
        "browserIntensityScale": browser_scale,
        "browserCalibration": "unchanged: intensity * 8 * min(4, sqrt(group size))",
    }
    candidate.pop("assetVersion")
    candidate["assetVersion"] = digest(json.dumps(candidate, sort_keys=True).encode())[:16]
    validate_model_manifest(candidate)
    pitch = validate_pitch_geometry(candidate, binary)
    summary = {
        "enabledSpotlights": len(rows), "baselineAccepted": len(old_accepted),
        "surfaceAccepted": len(accepted), "runtimeSources": len(fixtures),
        "newlyAccepted": [r["id"] for r in accepted if r["vertexRejections"]],
        "surfaceRejectionCounts": dict(Counter(
            reason for row in rows for reason in row["surfaceRejections"])),
        "exclusiveSurfaceRejectionCounts": dict(Counter(
            "|".join(row["surfaceRejections"]) or "accepted" for row in rows)),
        "runtimeSourcesByStand": dict(Counter(f["stand"] for f in fixtures)),
        "baselineVersion": baseline["assetVersion"], "candidateVersion": candidate["assetVersion"],
        "baselineManifestSha256": digest(baseline_raw), "sourceSha256": baseline["sourceSha256"],
        "geometrySha256": baseline["geometrySha256"], "lampTriangles": len(triangles),
        "registryUnchanged": True, "candidateOnly": True,
        "browserIntensityScale": browser_scale,
    }
    # All checks precede output. New paths only, no asset upload and no DB access.
    out.mkdir(parents=True)
    def write(path, document):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n")
    write(out / "baseline-manifest.json", baseline)
    (out / "baseline-registry.json").write_bytes(baseline_raw)
    write(out / "manifest.json", candidate)
    write(out / "light-audit.json", {"summary": summary, "candidates": rows})
    write(out / "pitch-check.json", pitch)
    write(out / "package/models/947.json", candidate)
    target = out / "package/stadium-models/947" / candidate["assetVersion"]
    target.mkdir(parents=True)
    for name in candidate["assetSha256"]:
        shutil.copyfile(assets / name, target / name)
    # Reuse the exact, already-reviewed surroundings and camera.
    presentation = json.loads((STUDY / "osm-fresh/presentation.json").read_text())
    p = presentation["presentation"]
    p["modelUrl"] = f"/models/947/{candidate['assetVersion']}/manifest.json"
    write(out / "presentation.json", presentation)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--browser-scale", type=float, default=1,
                        help="HSV-only export multiplier; original Unity intensity is retained")
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--expected-baseline-sha256")
    parser.add_argument("--assets", type=Path)
    args = parser.parse_args()
    audit(args.out.resolve(), args.browser_scale, baseline_path=args.baseline,
          expected_baseline_sha=args.expected_baseline_sha256, assets_dir=args.assets)
