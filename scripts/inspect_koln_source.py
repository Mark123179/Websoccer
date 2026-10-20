"""Offline source inventory for the uploaded Cologne Unity stadium."""
from collections import Counter
import json
from pathlib import Path

import numpy as np
import UnityPy
from UnityPy.helpers.MeshHelper import MeshHandler

from scripts.export_stadium_study_lights import world

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "generated-artifacts/koln-study"
BUNDLE = ROOT / "attached_assets/koln_1792488328918.bundle"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    env, cache, meshes, lights, materials = UnityPy.load(str(BUNDLE)), {}, [], [], {}
    for obj in env.objects:
        if obj.type.name == "Material":
            mat = obj.read()
            materials[str(obj.path_id)] = {
                "name": mat.m_Name,
                "textures": {key: value.m_Texture.read().m_Name if value.m_Texture else None
                             for key, value in mat.m_SavedProperties.m_TexEnvs},
                "floats": dict(mat.m_SavedProperties.m_Floats),
            }
        if obj.type.name not in ("MeshFilter", "Light"):
            continue
        item = obj.read()
        go = item.m_GameObject.read()
        transform = next(c.read() for c in go.m_Components if c.type.name == "Transform")
        matrix = world(transform, cache)
        chain, t = [], transform
        while t:
            chain.append(t.m_GameObject.read().m_Name)
            t = t.m_Father.read() if t.m_Father else None
        if obj.type.name == "Light":
            direction = matrix[:3, :3] @ np.array([0., 0., 1.])
            direction /= np.linalg.norm(direction)
            lights.append({
                "id": str(obj.path_id), "name": go.m_Name, "chain": chain,
                "enabled": item.m_Enabled, "type": item.m_Type,
                "position": matrix[:3, 3].tolist(), "direction": direction.tolist(),
            })
            continue
        renderer = next((c.read() for c in go.m_Components if c.type.name == "MeshRenderer"), None)
        if renderer is None:
            continue
        mesh = item.m_Mesh.read()
        h = MeshHandler(mesh)
        h.process()
        if not h.m_Vertices:
            continue
        vertices = np.asarray(h.m_Vertices) @ matrix[:3, :3].T + matrix[:3, 3]
        meshes.append({
            "name": mesh.m_Name, "go": go.m_Name, "id": str(item.m_Mesh.path_id),
            "chain": chain, "enabled": renderer.m_Enabled,
            "bounds": [vertices.min(0).tolist(), vertices.max(0).tolist()],
            "vertices": len(vertices),
            "materials": [p.read().m_Name for p in renderer.m_Materials],
        })
    (OUT / "source-inventory.json").write_text(json.dumps(
        {"meshes": meshes, "lights": lights, "materials": materials}, indent=2))
    print("Mesh roots:", Counter(m["chain"][-2] if len(m["chain"]) > 1 else m["chain"][0]
                                  for m in meshes))
    print("Mesh groups:", Counter(m["name"].split("_")[0] for m in meshes))
    print("Light types:", Counter(l["type"] for l in lights))
    for m in meshes:
        if any(n in ("MAIN", "EXTRA", "PITCH2021", "AUDIAREA", "MESH_CROWD") for n in m["chain"]):
            print(m["name"], [[round(x, 2) for x in bound] for bound in m["bounds"]],
                  m["materials"], "/".join(reversed(m["chain"])))


if __name__ == "__main__":
    main()
