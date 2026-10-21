"""Offline fixture positions derived from explicitly reviewed source UV samples."""
import numpy as np


def verified_geometry_fixtures(meshes, binary, samples):
    """Require actual emitter triangles; never accept free-form light positions."""
    result, seen = [], set()
    lookup = {mesh["name"]: mesh for mesh in meshes}
    for sample in samples:
        mesh = lookup[sample["mesh"]]
        parts = [p for p in mesh["parts"] if p["material"] == sample["material"]]
        if len(parts) != 1 or not parts[0].get("texture"):
            raise ValueError("Fixture sample requires one textured source material")
        vertices = np.frombuffer(binary, "<f4", count=mesh["vertexCount"] * 3,
                                 offset=mesh["positionOffset"]).reshape(-1, 3)
        uv = np.frombuffer(binary, "<f4", count=mesh["vertexCount"] * 2,
                          offset=mesh["uvOffset"]).reshape(-1, 2)
        part = parts[0]
        indices = np.frombuffer(binary, "<u4", count=part["indexCount"],
                                offset=part["indexOffset"]).reshape(-1, 3)
        triangle_index = sample["triangle"]
        if not isinstance(triangle_index, int) or not 0 <= triangle_index < len(indices):
            raise ValueError("Fixture triangle is outside its source part")
        triangle = indices[triangle_index]
        point_uv = np.asarray(sample["uv"], dtype=float)
        weights = np.linalg.solve(np.vstack((uv[triangle].T, np.ones(3))),
                                  np.r_[point_uv, 1])
        if not np.isfinite(weights).all() or weights.min() < -1e-5:
            raise ValueError("Fixture UV sample lies outside its source triangle")
        position = weights @ vertices[triangle]
        a, b, c = vertices[triangle].astype(float)
        direction = np.cross(b - a, c - a)
        length = np.linalg.norm(direction)
        if not np.isfinite(length) or length < 1e-8:
            raise ValueError("Degenerate emitter source triangle")
        direction /= length
        if position[1] < 18 or direction[1] >= -.05:
            raise ValueError("Emitter source face is not elevated and downward-facing")
        hit = position - direction * position[1] / direction[1]
        if abs(hit[0]) > 40 or abs(hit[2]) > 60:
            raise ValueError("Emitter source normal does not illuminate the pitch")
        identity = tuple(np.round(position, 5))
        if identity in seen:
            raise ValueError("Duplicate emitter sample")
        seen.add(identity)
        result.append({
            "id": f"mesh-{mesh['pathId']}-{triangle_index}-{len(result)}",
            "name": f"{mesh['name']} UV emitter {len(result) + 1}",
            "position": position.tolist(), "direction": direction.tolist(),
            "color": [1., 1., 1.], "range": 180., "angle": 60., "intensity": 40.,
            "meshDistance": 0.,
            "sourceGeometry": {"mesh": mesh["name"], "material": sample["material"],
                               "triangle": triangle_index, "uv": point_uv.tolist()},
        })
    if not result:
        raise ValueError("No reviewed source emitter samples")
    return result
