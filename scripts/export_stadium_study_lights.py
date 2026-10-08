"""Offline source-light inspection. Never opens Unity in the web process."""
import hashlib
import json
from collections import Counter
from pathlib import Path

import numpy as np
import UnityPy
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "attached_assets/dortmundv3_1790167703231.bundle"
MODEL = ROOT / "stadium_editor/static/stadium_editor/dortmund_original"
DEST = ROOT / "stadium_editor/static/stadium_editor/study_assets"


def matrix(transform):
    p, q, s = transform.m_LocalPosition, transform.m_LocalRotation, transform.m_LocalScale
    result = np.eye(4)
    result[:3, :3] = Rotation.from_quat([q.x, q.y, q.z, q.w]).as_matrix() @ np.diag([s.x, s.y, s.z])
    result[:3, 3] = [p.x, p.y, p.z]
    return result


def world(transform, cache):
    key = transform.m_GameObject.path_id
    if key not in cache:
        parent = world(transform.m_Father.read(), cache) if transform.m_Father else np.eye(4)
        cache[key] = parent @ matrix(transform)
    return cache[key]


def main():
    manifest = json.loads((MODEL / "manifest.json").read_text())
    binary = (MODEL / "geometry.bin").read_bytes()
    vertices, refs = [], []
    for entry in manifest["meshes"]:
        for part in entry["parts"]:
            if "lght002" not in part["material"]:
                continue
            points = np.frombuffer(binary, "<f4", count=entry["vertexCount"] * 3,
                                   offset=entry["positionOffset"]).reshape(-1, 3)
            ids = np.unique(np.frombuffer(binary, "<u4", count=part["indexCount"], offset=part["indexOffset"]))
            vertices.extend(points[ids])
            refs.extend([{"mesh": entry["name"], "meshPathId": entry["pathId"],
                          "material": part["material"]}] * len(ids))
    tree = cKDTree(vertices)
    env, cache, records = UnityPy.load(str(SOURCE)), {}, []
    material_evidence = {}
    for obj in env.objects:
        if obj.type.name != "Material":
            continue
        material = obj.read()
        if material.m_Name != "st051_lght002.001":
            continue
        material_evidence[material.m_Name] = {
            "pathId": str(obj.path_id),
            "colorFactors": {name: [float(color.r), float(color.g), float(color.b), float(color.a)]
                            for name, color in material.m_SavedProperties.m_Colors},
            "textures": {name: value.m_Texture.read().m_Name if value.m_Texture else None
                         for name, value in material.m_SavedProperties.m_TexEnvs},
            "note": "Saved source factors are evidence, not a reconstruction of the Unity shader.",
        }
    types = Counter()
    for obj in env.objects:
        if obj.type.name != "Light":
            continue
        light = obj.read()
        types[light.m_Type] += 1
        go = light.m_GameObject.read()
        transform = next(c.read() for c in go.m_Components if type(c.read()).__name__ == "Transform")
        wm = world(transform, cache)
        position = wm[:3, 3]
        direction = wm[:3, :3] @ np.array([0., 0., 1.])
        direction /= np.linalg.norm(direction)
        names, current = [], transform
        while current:
            names.append(current.m_GameObject.read().m_Name)
            current = current.m_Father.read() if current.m_Father else None
        distance, index = tree.query(position)
        reaches_pitch = False
        if direction[1] < -.05:
            travel = -position[1] / direction[1]
            target = position + direction * travel
            reaches_pitch = (abs(target[0]) <= 34.080014 and abs(target[2]) <= 52.950013
                             and 0 < travel <= light.m_Range)
        # Both an actual source component and spatial agreement with the inner
        # rim lamp geometry are required; ExtraLights are not physical proof.
        verified = (light.m_Type == 0 and bool(light.m_Enabled) and
                    "LightBillboard" in names and distance <= 1.0 and reaches_pitch)
        record = {
            "id": str(obj.path_id), "name": go.m_Name, "sourceHierarchy": "/".join(reversed(names)),
            "sourceType": int(light.m_Type), "sourceEnabled": bool(light.m_Enabled),
            "componentLocalPosition": [float(getattr(transform.m_LocalPosition, axis)) for axis in "xyz"],
            "componentLocalRotation": [float(getattr(transform.m_LocalRotation, axis)) for axis in "xyzw"],
            "position": position.tolist(), "direction": direction.tolist(),
            "range": float(light.m_Range), "angle": float(light.m_SpotAngle),
            "intensity": float(light.m_Intensity),
            "color": [float(light.m_Color.r), float(light.m_Color.g), float(light.m_Color.b)],
            "nearestLampMesh": refs[index], "meshDistance": float(distance),
            "verified": bool(verified), "reachesPitch": bool(reaches_pitch),
        }
        records.append(record)
    records.sort(key=lambda item: item["id"])
    verified = [item for item in records if item["verified"]]
    result = {
        "version": 1, "club": "dortmund", "coordinateSystem": manifest["coordinateSystem"],
        "source": SOURCE.name, "sourceSha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "geometrySha256": hashlib.sha256(binary).hexdigest(),
        "sourceCounts": dict(types), "verifiedFixtures": verified, "candidates": records,
        "materialEvidence": material_evidence,
        "rule": "Enabled Unity Spot Light in LightBillboard; <=1m from st051_lght002 geometry; source ray intersects pitch within range.",
    }
    DEST.mkdir(parents=True, exist_ok=True)
    (DEST / "dortmund_lights.json").write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    print(json.dumps({"sourceLights": len(records), "verified": len(verified),
                      "types": dict(types), "nearestDistances": sorted(round(r["meshDistance"], 3)
                          for r in records if "LightBillboard" in r["sourceHierarchy"])[:8]}))


if __name__ == "__main__":
    main()
