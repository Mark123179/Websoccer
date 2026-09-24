"""Offline, reproducible UnityFS -> small read-only browser mesh set.

Run explicitly: python scripts/export_dortmund_miniature.py
UnityPy is an export-only dependency; the web process never opens the bundle.
"""
import json
import struct
from collections import Counter
from pathlib import Path

import UnityPy
from UnityPy.helpers.MeshHelper import MeshHandler


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "attached_assets/dortmundv3_1790167703231.bundle"
DEST = ROOT / "stadium_editor/static/stadium_editor/dortmund_original"
PREFIXES = ("back1_", "back2_", "front1_", "front2_", "left1_", "left2_",
            "right1_", "right2_", "center3_", "C_", "st081_pitch_")
FEATURED_TEXTURES = {
    "au_seat", "st051_irpl003_bsm", "st051_pllr001_bsm",
    "st_coat_band_2018Sig_bsm",
}


def selected(name):
    return name.startswith(PREFIXES) or (
        name.startswith("st051_sc2018_") and "_stand_" in name
    )


def parent_chain(go):
    transform = next((c.read() for c in go.m_Components
                      if type(c.read()).__name__ == "Transform"), None)
    names = []
    rotations = []
    while transform:
        names.append(transform.m_GameObject.read().m_Name)
        # The selected stadium meshes have identity local transforms. Reject
        # any new variant rather than silently exporting at the wrong location.
        pos, scale, rot = transform.m_LocalPosition, transform.m_LocalScale, transform.m_LocalRotation
        assert max(abs(pos.x), abs(pos.y), abs(pos.z)) < 0.0001, names
        assert max(abs(scale.x - 1), abs(scale.y - 1), abs(scale.z - 1)) < 0.0001, names
        rotations.append((rot.x, rot.y, rot.z, rot.w))
        transform = transform.m_Father.read() if transform.m_Father else None
    # Parent-first quaternion composition, including rotated accessories.
    q = (0., 0., 0., 1.)
    for x, y, z, w in reversed(rotations):
        a, b, c, d = q
        q = (d*x + a*w + b*z - c*y, d*y - a*z + b*w + c*x,
             d*z + a*y - b*x + c*w, d*w - a*x - b*y - c*z)
    return names, q


def rotate(v, q):
    x, y, z = v
    a, b, c, d = q
    # Unit-quaternion rotation, no handedness conversion.
    tx, ty, tz = 2 * (b*z - c*y), 2 * (c*x - a*z), 2 * (a*y - b*x)
    return (x + d*tx + b*tz - c*ty,
            y + d*ty + c*tx - a*tz,
            z + d*tz + a*ty - b*tx)


def sourced_opaque_color(material, renderer):
    """Only annotate NoDraw when its saved PBR values support a solid preview.

    The Unity shader itself is unavailable here. This is source-derived color
    and blend-state evidence, not a reconstruction of that shader's output.
    """
    if not material.m_Name.startswith("NoDraw_"):
        return None
    colors = dict(material.m_SavedProperties.m_Colors)
    floats = dict(material.m_SavedProperties.m_Floats)
    color = colors.get("baseColorFactor")
    textures = dict(material.m_SavedProperties.m_TexEnvs)
    base = textures.get("baseColorTexture")
    if not (renderer.m_Enabled and material.m_CustomRenderQueue == 2000
            and color is not None and color.a >= 0.999
            and floats.get("_BUILTIN_SrcBlend") == 1
            and floats.get("_BUILTIN_DstBlend") == 0
            and floats.get("_AlphaClip") == 0
            and not (base and base.m_Texture)):
        raise ValueError(f"Unsupported NoDraw material state: {material.m_Name}")
    return "#" + "".join(f"{round(max(0, min(1, getattr(color, c))) * 255):02x}"
                         for c in "rgb")


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    env = UnityPy.load(str(SOURCE))
    meshes = []
    textures = set()
    data = bytearray()
    materials_used = Counter()
    for obj in env.objects:
        if obj.type.name != "MeshFilter":
            continue
        filt = obj.read()
        mesh = filt.m_Mesh.read()
        if not mesh or not selected(mesh.m_Name):
            continue
        go = filt.m_GameObject.read()
        chain, rotation = parent_chain(go)
        renderer = next((c.read() for c in go.m_Components
                         if type(c.read()).__name__ == "MeshRenderer"), None)
        if renderer is None:
            continue
        handler = MeshHandler(mesh)
        handler.process()
        vertices, uv = handler.m_Vertices, handler.m_UV0
        if not vertices:
            continue
        # Layout is one contiguous binary file; offsets are byte offsets.
        pos_offset = len(data)
        for v in vertices:
            data.extend(struct.pack("<fff", *rotate(v, rotation)))
        uv_offset = len(data)
        for i in range(len(vertices)):
            u, v = uv[i] if len(uv) == len(vertices) else (0, 0)
            data.extend(struct.pack("<ff", u, v))
        parts = []
        for i, triangles in enumerate(handler.get_triangles()):
            if not triangles:
                continue
            material_ptr = renderer.m_Materials[min(i, len(renderer.m_Materials) - 1)]
            material = material_ptr.read() if material_ptr else None
            material_name = material.m_Name if material else "unassigned"
            materials_used[material_name] += 1
            tex = None
            if material:
                for key, value in material.m_SavedProperties.m_TexEnvs:
                    if key not in ("baseColorTexture", "_BaseMap", "_MainTex"):
                        continue
                    t = value.m_Texture.read() if value.m_Texture else None
                    if t and t.m_Name in FEATURED_TEXTURES:
                        tex = t.m_Name
                        textures.add(t.m_Name)
                    break
            index_offset = len(data)
            for tri in triangles:
                data.extend(struct.pack("<III", *tri))
            part = {"indexOffset": index_offset, "indexCount": len(triangles) * 3,
                    "material": material_name, "texture": tex}
            if material and material_name.startswith("NoDraw_"):
                part["sourceOpaqueColor"] = sourced_opaque_color(material, renderer)
            parts.append(part)
        meshes.append({"name": mesh.m_Name, "pathId": str(filt.m_Mesh.path_id),
                       "hierarchy": "/".join(reversed(chain)), "vertexCount": len(vertices),
                       "positionOffset": pos_offset, "uvOffset": uv_offset,
                       "parts": parts})

    # Four representative actual base-color textures only. The remainder are
    # explicitly untextured preview geometry, not a Unity shader reconstruction.
    for obj in env.objects:
        if obj.type.name == "Texture2D" and obj.peek_name() in textures:
            tex = obj.read()
            image = tex.image
            image.thumbnail((512, 512))
            image.save(DEST / (tex.m_Name + ".webp"), "WEBP", quality=78)
    (DEST / "geometry.bin").write_bytes(data)
    seats_source = ROOT / "attached_assets/dortmundv3_1790167703232.json"
    sections = json.loads(seats_source.read_text(encoding="utf-8"))["sections"]
    back2 = [s["pos"] for name, section in sections.items()
             if name.startswith("C_back2_") for s in section["seats"]]
    manifest = {"format": "unity-mesh-binary-v1", "source": SOURCE.name,
                "coordinateSystem": "Unity local XYZ, hierarchy Y-180 applied; Three.js Y-up",
                "meshes": meshes, "textures": sorted(textures),
                "backUpperSeatBounds": [[min(p[i] for p in back2), max(p[i] for p in back2)]
                                        for i in range(3)],
                "seatsSource": seats_source.name}
    (DEST / "manifest.json").write_text(json.dumps(manifest, separators=(",", ":")), encoding="utf-8")
    print(f"{len(meshes)} original meshes; {len(materials_used)} materials; "
          f"{len(textures)} selected textures; {len(data) / 1048576:.1f} MiB geometry")


if __name__ == "__main__":
    main()