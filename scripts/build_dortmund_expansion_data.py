"""Build measurable, offline-only inputs for the read-only Dortmund expansion.

Seat templates come from the actual outermost occupied row of each upper-tier
Unity seat section. Roof clearance is measured from the exported roof and
pylon meshes, rather than an invented stadium diameter.
"""
import json
import math
from pathlib import Path

import numpy as np
import UnityPy
from UnityPy.helpers.MeshHelper import MeshHandler


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "stadium_editor/static/stadium_editor/dortmund_original"
SOURCE = ROOT / "attached_assets/dortmundv3_1790167703232.json"
CHAIR_SOURCE = ROOT / "attached_assets/Bleacher_1790167741678.bundle"
SIDES = ("back", "front", "left", "right")
SIDE_FRAME = {
    "back": (0, 1), "front": (0, -1),
    "left": (2, 1), "right": (2, -1),
}
ROW_DEPTH = .91
ROW_RISE = .43
ANCHOR_CLEARANCE = 4.0


def positions(entry, binary):
    return np.frombuffer(binary, dtype="<f4", count=3 * entry["vertexCount"],
                         offset=entry["positionOffset"]).reshape(-1, 3)


def in_mesh_frame(position):
    # JSON positions are in the unrotated section frame. MAIN's 90-degree Y
    # rotation is baked into exported meshes, not into this separate JSON.
    x, y, z = position
    return [z, y, -x]


def build():
    manifest = json.loads((ASSETS / "manifest.json").read_text())
    binary = (ASSETS / "geometry.bin").read_bytes()
    sections = json.loads(SOURCE.read_text())["sections"]
    roof = next(e for e in manifest["meshes"] if e["name"] == "center3_13.001")
    pylons = next(e for e in manifest["meshes"] if e["name"] == "center3_21.001")
    roof_vertices = positions(roof, binary)
    pylon_vertices = positions(pylons, binary)
    results = {}
    for side in SIDES:
        axis, sign = SIDE_FRAME[side]
        section_names = [name for name in sections if name.startswith(f"C_{side}2_")]
        if not section_names:
            raise ValueError(f"No upper tier seats for {side}")
        template = []
        all_seats = []
        for name in section_names:
            seats = sections[name]["seats"]
            all_seats.extend(seats)
            maximum = max(seat["pos"][1] for seat in seats)
            # Distinct source sections end at different heights; each section
            # contributes one measured outer row, never an inferred rectangle.
            top = [seat for seat in seats if seat["pos"][1] >= maximum - .16]
            # Filter single isolated geometry outliers, but retain short
            # sections and the original aisles between sections.
            if len(top) < 20:
                raise ValueError(f"Missing usable top row in {name}: {len(top)}")
            template.extend({"position": in_mesh_frame(seat["pos"]),
                             "rotation": (seat["rot"] + 90) % 360,
                             "color": seat["color"], "section": name}
                            for seat in top)
        roof_extent = max(float(sign * point[axis]) for point in roof_vertices)
        pylon_extent = max(float(sign * point[axis]) for point in pylon_vertices)
        seat_extent = max(float(sign * in_mesh_frame(seat["pos"])[axis])
                          for seat in all_seats)
        gap = pylon_extent - roof_extent
        if gap <= ANCHOR_CLEARANCE + ROW_DEPTH:
            raise ValueError(f"Roof/pylon clearance too small on {side}: {gap:.2f}")
        max_rows = math.floor((gap - ANCHOR_CLEARANCE) / ROW_DEPTH)
        # One action is always at least 1,000 physical seats; increments may
        # exceed 1,000 because an existing source row cannot be split in half.
        rows_per_step = math.ceil(1000 / len(template))
        if rows_per_step > max_rows:
            raise ValueError(f"No 1,000-seat step fits {side}")
        results[side] = {
            "axis": axis, "sign": sign, "sections": section_names,
            "sourceSeats": len(all_seats), "template": template,
            "roofExtent": round(roof_extent, 4),
            "pylonExtent": round(pylon_extent, 4),
            "seatExtent": round(seat_extent, 4),
            "rowsPerStep": rows_per_step,
            "maxRows": max_rows,
        }

    chair_mesh = next(obj.read() for obj in UnityPy.load(str(CHAIR_SOURCE)).objects
                      if obj.type.name == "Mesh" and obj.peek_name() == "MESH_Chair_Stadium")
    handler = MeshHandler(chair_mesh)
    handler.process()
    chair = {
        "source": chair_mesh.m_Name,
        "vertices": [[round(float(v), 7) for v in vertex] for vertex in handler.m_Vertices],
        "indices": [int(i) for triangle_group in handler.get_triangles()
                    for triangle in triangle_group for i in triangle],
    }
    data = {
        "format": "dortmund-expansion-v1", "baselineSeats": sum(
            len(section["seats"]) for section in sections.values()),
        "rowDepth": ROW_DEPTH, "rowRise": ROW_RISE,
        "clearance": ANCHOR_CLEARANCE, "limit": 120000,
        "seatSource": SOURCE.name, "chair": chair,
        "sides": results,
    }
    output = ASSETS / "expansion-data.json"
    output.write_text(json.dumps(data, separators=(",", ":")))
    print(f"Wrote {output} ({output.stat().st_size} bytes)")
    for side, info in results.items():
        print(side, "source-row", len(info["template"]),
              "step", info["rowsPerStep"], "rows, max", info["maxRows"],
              "roof/pylon", info["roofExtent"], info["pylonExtent"])


if __name__ == "__main__":
    build()