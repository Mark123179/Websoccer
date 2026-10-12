"""Offline source-model export. No registry, database or storage writes."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import UnityPy
from UnityPy.helpers.MeshHelper import MeshHandler
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.export_stadium_study_lights import world
from stadium_editor.pitch_validation import PitchValidationError, validate_pitch_geometry

def export_model(SOURCE, seats_path, fmi, name, DEST, calibration):
    env = UnityPy.load(str(SOURCE))
    cache, binary, meshes, tex_refs, lamps = {}, bytearray(), [], {}, []
    for obj in env.objects:
        if obj.type.name != "MeshFilter":
            continue
        filt = obj.read()
        go = filt.m_GameObject.read()
        renderer = next((c.read() for c in go.m_Components
                         if c.type.name == "MeshRenderer"), None)
        if renderer is None or not renderer.m_Enabled:
            continue
        transform = next(c.read() for c in go.m_Components if c.type.name == "Transform")
        chain, t = [], transform
        while t:
            chain.append(t.m_GameObject.read().m_Name)
            t = t.m_Father.read() if t.m_Father else None
        # Model, crowd and pitch only. No distant backgrounds or duplicate
        # accessory scenes; preserve each selected object's actual hierarchy.
        if not any(n in ("MAIN", "AUDIAREA", "PITCH2021", "MESH_CROWD") for n in chain):
            continue
        mesh = filt.m_Mesh.read()
        h = MeshHandler(mesh)
        h.process()
        if not h.m_Vertices:
            continue
        matrix = world(transform, cache)
        vertices = np.array(h.m_Vertices)
        vertices = vertices @ matrix[:3, :3].T + matrix[:3, 3]
        positions = np.asarray(vertices, dtype="<f4")
        po = len(binary)
        binary.extend(positions.tobytes())
        uv = np.asarray(h.m_UV0, dtype="<f4")
        if len(uv) != len(vertices):
            uv = np.zeros((len(vertices), 2), dtype="<f4")
        uo = len(binary)
        binary.extend(uv.tobytes())
        parts = []
        for i, tris in enumerate(h.get_triangles()):
            if not tris:
                continue
            mat = renderer.m_Materials[min(i, len(renderer.m_Materials) - 1)].read()
            colors = dict(mat.m_SavedProperties.m_Colors)
            floats = dict(mat.m_SavedProperties.m_Floats)
            color = colors.get("baseColorFactor") or colors.get("_BaseColor") or colors.get("_Color")
            rgb = [max(0, min(1, getattr(color, k))) for k in "rgb"] if color else [0.55]*3
            texture = None
            for key, value in mat.m_SavedProperties.m_TexEnvs:
                if key in ("baseColorTexture", "_BaseMap", "_MainTex") and value.m_Texture:
                    pointer = value.m_Texture
                    texture = f"texture-{pointer.path_id}.webp"
                    tex_refs[texture] = pointer
                    break
            ix = np.asarray(tris, dtype="<u4").reshape(-1)
            if len(ix) % 3 or int(ix.max()) >= len(vertices):
                raise ValueError("Invalid source triangle indices")
            offset = len(binary)
            binary.extend(ix.tobytes())
            part = {"material": mat.m_Name, "color": rgb, "texture": texture,
                    "indexOffset": offset, "indexCount": len(ix)}
            parts.append(part)
            if any(s in mat.m_Name.lower() for s in ("lght", "lamp", "light_bulb", "light_floodlight")):
                lamps.extend(vertices[np.unique(ix)])
        if not parts:
            continue
        meshes.append({"name": mesh.m_Name, "pathId": str(filt.m_Mesh.path_id),
                       "hierarchy": chain, "positionOffset": po, "uvOffset": uo,
                       "vertexCount": len(vertices), "parts": parts,
                       "bounds": [vertices.min(axis=0).tolist(), vertices.max(axis=0).tolist()]})
    # Validate the captured source geometry before decoding textures or writing
    # any package files. Never adapt dimensions to make an invalid source pass.
    geometry_hash = hashlib.sha256(binary).hexdigest()
    validate_pitch_geometry({"meshes": meshes, "geometrySha256": geometry_hash}, binary)
    DEST.mkdir(parents=True, exist_ok=True)
    for name, pointer in tex_refs.items():
        image = pointer.read().image
        image.thumbnail((1024, 1024))
        image.save(DEST / name, "WEBP", quality=86)
    if not lamps:
        raise ValueError("No actual lamp-material geometry found")
    tree = cKDTree(np.asarray(lamps))
    lights = []
    for obj in env.objects:
        if obj.type.name != "Light":
            continue
        light = obj.read()
        if light.m_Type != 0 or not light.m_Enabled:
            continue
        go = light.m_GameObject.read()
        transform = next(c.read() for c in go.m_Components if c.type.name == "Transform")
        matrix = world(transform, cache)
        point = matrix[:3, 3]
        direction = matrix[:3, :3] @ np.array([0., 0., 1.])
        direction /= np.linalg.norm(direction)
        # Verify actual roof fixtures, directed towards the playing surface.
        distance = float(tree.query(point)[0])
        if point[1] < 18 or direction[1] >= -.05 or distance > 2:
            continue
        hit = point - direction * point[1] / direction[1]
        if abs(hit[0]) > 40 or abs(hit[2]) > 60:
            continue
        lights.append({"id": str(obj.path_id), "name": go.m_Name,
                       "position": point.tolist(), "direction": direction.tolist(),
                       "color": [light.m_Color.r, light.m_Color.g, light.m_Color.b],
                       "range": light.m_Range, "angle": light.m_SpotAngle,
                       "intensity": light.m_Intensity, "meshDistance": distance})
    if not lights:
        raise ValueError("No source-verified pitch-directed roof lights")
    # Spatial coverage selection of actual source lights, not invented points.
    selected = [min(lights, key=lambda f: f["id"])]
    while len(selected) < min(12, len(lights)):
        candidates = [f for f in lights if f not in selected]
        selected.append(max(candidates, key=lambda f: min(np.linalg.norm(
            np.array(f["position"]) - np.array(s["position"])) for s in selected)))
    for fixture in selected:
        fixture["representedIds"] = [f["id"] for f in lights if min(selected, key=lambda s:
            np.linalg.norm(np.array(f["position"]) - np.array(s["position"]))) is fixture]
    binary_path = DEST / "geometry.bin"
    binary_path.write_bytes(binary)
    manifest = {"format": "unity-mesh-binary-v1", "clubFmiId": fmi, "stadiumName": name,
                "calibration": calibration,
                "source": SOURCE.name, "sourceSha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
                 "geometrySha256": geometry_hash,
                "meshes": meshes, "textures": list(tex_refs), "fixtures": selected,
                "verifiedFixtureCount": len(lights),
                "limits": ["Source meshes and UVs; simplified browser materials, not original Unity shaders.",
                           "Provided lightmap indices and probes retained as evidence; no full baked-lighting reconstruction."]}
    manifest["assetSha256"] = {
        name: hashlib.sha256((DEST / name).read_bytes()).hexdigest()
        for name in ["geometry.bin", *manifest["textures"]]
    }
    manifest["sourceEvidence"] = {}
    for path in sorted(SOURCE.parent.glob("*.json")):
        document = json.loads(path.read_text())
        manifest["sourceEvidence"][path.name] = {
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "count": document.get("total_seats", document.get("probeCount", document.get("lightmapCount")))
            if isinstance(document, dict) else len(document) if isinstance(document, list) else None,
        }
    seats = json.loads(seats_path.read_text())["seats"]
    index, seat = min(enumerate(seats), key=lambda item:
                      abs(item[1]["pos"][2]+75) + 3*abs(item[1]["pos"][0]) +
                      abs(item[1]["pos"][1]-12))
    x, y, z = seat["pos"]
    manifest["seatView"] = {"position": [z, y, -x], "sourceIndex": index,
                            "sourceFrameRotationY": 90}
    manifest["assetVersion"] = hashlib.sha256(
        json.dumps(manifest, sort_keys=True).encode()).hexdigest()[:16]
    from stadium_editor.model_registry import validate_model_manifest
    validate_model_manifest(manifest)
    (DEST / "manifest.json").write_text(json.dumps(manifest, separators=(",", ":")))
    print(json.dumps({"meshes": len(meshes), "textures": len(tex_refs),
                      "verifiedLights": len(lights), "runtimeLights": len(selected),
                      "binaryMB": round(len(binary)/1024**2, 2)}))
    for m in meshes:
        if m["name"].startswith("center"):
            print(m["name"], [round(m["bounds"][j][1], 1) for j in (0, 1)],
                  sorted({p["material"] for p in m["parts"]})[:4])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--seats", type=Path, required=True)
    parser.add_argument("--fmi", type=int, required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--calibration", type=Path, required=True,
                        help="JSON-Datei mit dem vollständigen calibration-Block")
    args = parser.parse_args()
    calibration = json.loads(args.calibration.read_text())
    if args.fmi <= 0 or not args.name.strip():
        parser.error("--fmi muss positiv sein; --name darf nicht leer sein")
    required = {"roofMinHeight", "skipMeshPrefixes", "crowdPrefix", "pitchPrefix",
                "tickerRotationY", "tickerFrontCut", "standAxes", "orbitDefault"}
    if not isinstance(calibration, dict) or not required <= calibration.keys():
        parser.error("--calibration muss den vollständigen calibration-Block enthalten")
    try:
        export_model(args.bundle, args.seats, args.fmi, args.name, args.out, calibration)
    except PitchValidationError as error:
        print(f"Modell-Export abgebrochen: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
