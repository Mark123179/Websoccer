"""Read-only Veltins source preparation; no storage, registry or ORM writes.

Run after export_stadium_model.py with the reviewed EXTRA root included.
Source crowd envelopes are schematic editor blocks, not official block topology.
"""
from copy import deepcopy
import hashlib
import json
import math
import os
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.spatial import cKDTree
from shapely.geometry import Polygon

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
import django
django.setup()

from game.models import Club, Stadium
from stadium_editor.capacity import distribute_capacities
from stadium_editor.contracts import geometry_blocks
from stadium_editor.live_scene import build_live_scene, standard_design_for_geometry
from stadium_editor.model_registry import validate_model_manifest
from stadium_editor.pitch_validation import validate_pitch_geometry
from stadium_editor.seed import normalise_block_types
from scripts.build_mainz_osm_review import bowl_opening, build

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "generated-artifacts/veltins-study"
SOURCE = OUT / "source-export"
SEATS = ROOT / "attached_assets/veltins_1792605561177.json"
STADIUM_WAY = 147192563
ROLLOUT_PITCH = 331441037


def write(name, document):
    (OUT / name).write_text(json.dumps(document, ensure_ascii=False, indent=2))


def editor_geometry(stadium, manifest, binary, presentation):
    """Source crowd hull strips; capacity still comes exclusively from Stadium."""
    crowd = [m for m in manifest["meshes"] if m["name"].startswith("C_")]
    points = np.unique(np.vstack([
        np.frombuffer(binary, "<f4", count=m["vertexCount"] * 3,
                      offset=m["positionOffset"]).reshape(-1, 3) for m in crowd
    ]), axis=0)
    theta = presentation["frame"]["axisTheta"]

    def project(x, z):
        return [z * math.cos(theta) + x * math.sin(theta),
                z * math.sin(theta) - x * math.cos(theta)]

    blocks, evidence = [], []
    for stand in ("NORD", "SUED", "OST", "WEST"):
        end = stand in ("NORD", "SUED")
        radial, tangent = (2, 0) if end else (0, 2)
        sign = 1 if stand in ("NORD", "OST") else -1
        dominant = (np.abs(points[:, radial]) >= np.abs(points[:, tangent]) if end else
                    np.abs(points[:, radial]) > np.abs(points[:, tangent]))
        mask = (points[:, radial] * sign > 0) & dominant
        for tier, low, high in (("UNTER", -100, 16.3), ("OBER", 16.3, 100)):
            selected = points[mask & (points[:, 1] >= low) & (points[:, 1] < high)]
            if len(selected) < 4:
                continue
            boundaries = np.linspace(selected[:, tangent].min() - .01,
                                     selected[:, tangent].max() + .01, 5)
            for i in range(4):
                strip = selected[(selected[:, tangent] >= boundaries[i]) &
                                 (selected[:, tangent] < boundaries[i + 1])]
                if len(strip) < 4:
                    continue
                t0, t1 = (float(strip[:, tangent].min() - .2),
                          float(strip[:, tangent].max() + .2))
                r0, r1 = (float(np.abs(strip[:, radial]).min() - .2),
                          float(np.abs(strip[:, radial]).max() + .2))
                def point(t, r):
                    return project(t, sign * r) if end else project(sign * r, t)
                blocks.append({
                    "id": len(blocks), "stand": stand, "tier": tier, "type": "SITZ",
                    "quad": [point(t0, r1), point(t1, r1), point(t1, r0), point(t0, r0)],
                    "rows": max(1, math.ceil((r1 - r0) / .8)),
                    "seats": max(1, math.ceil((t1 - t0) / .5)),
                    "z0": float(strip[:, 1].min()), "z1": float(strip[:, 1].max()),
                })
                evidence.append({"blockId": blocks[-1]["id"], "stand": stand,
                                 "tier": tier, "sourceVertices": len(strip)})
    assert sum(row["sourceVertices"] for row in evidence) == len(points)
    osm = json.loads((OUT / "osm-fresh/evidence.json").read_text())
    geometry = {
        "version": 2, "physical_grid": "v2", "homeStand": "NORD", "mainStand": "WEST",
        "meta": {"name": stadium.name, "club": stadium.club.name,
                 **deepcopy(presentation["frame"])},
        "outline": [project(x, z) for x, z in osm["mappedStadiumModelCoordinates"]],
        "blocks": blocks, "roofs": [],
        "source": "Veltins original crowd mesh envelopes + fresh OpenStreetMap",
        "surroundings": deepcopy(presentation["surroundings"]),
        "bg": deepcopy(presentation["surroundings"]),
    }
    bg = geometry["bg"]
    bg["buildings"] = [{"poly": poly, "h": height, "id": identity}
                       for poly, height, identity in zip(
                           bg["buildings"], bg["buildingHeights"], bg["buildingIds"], strict=True)]
    geometry = normalise_block_types(stadium, geometry)
    effective = distribute_capacities(stadium, geometry)
    trusted = {b["id"]: b for b in geometry_blocks(effective)}
    for block in effective["blocks"]:
        block.update(trusted[block["id"]])
    build_live_scene(stadium, geometry, standard_design_for_geometry(stadium, effective))
    assert sum(b["capacity"] for b in effective["blocks"]) == stadium.capacity_total
    write("editor-envelope-evidence.json", {
        "method": "Actual source crowd vertices, two height bands, four tangent strips per side.",
        "limits": "Schematic source envelopes, not official numbered block boundaries.",
        "sourceCrowdVertices": len(points), "blocks": evidence,
        "economicCapacityUnchanged": stadium.capacity_total,
    })
    return geometry


def prepare():
    club = Club.objects.get(fm_inside_id=920, transfermarkt_id=33)
    stadium = Stadium.objects.get(club=club)
    assert "schalke" in club.name.casefold() and "veltins" in stadium.name.casefold()
    manifest = json.loads((SOURCE / "manifest.json").read_text())
    binary = (SOURCE / "geometry.bin").read_bytes()
    assert hashlib.sha256(binary).hexdigest() == manifest["geometrySha256"]
    # Walls and façade ventilation remain body. Roof skins, equipment, trusses,
    # hanging scoreboard and their EXTRA-root translucent layers follow the roof.
    fixed = {"center3_1", "center3_2", "center3_3", "center3_detail_1", "center3_detail_3"}
    roofs = []
    for mesh in manifest["meshes"]:
        if mesh["name"].startswith("center3") and mesh["name"] not in fixed:
            roofs.append(mesh["name"])
            mesh["sourceMeshName"] = mesh["name"]
            mesh["name"] = "DACH_" + mesh["name"]
        for part in mesh["parts"]:
            if part["material"] == "000STADIUMLINE":
                part["texture"], part["transparent"] = None, False
                part.pop("alphaTest", None)
            elif part["texture"]:
                image = Image.open(SOURCE / part["texture"])
                if "A" in image.getbands() and image.getchannel("A").getextrema()[0] < 255:
                    part.update(transparent=True, alphaTest=.02)
    crowd = {m["name"]: m for m in manifest["meshes"] if m["name"].startswith("C_")}
    seats = json.loads(SEATS.read_text())["seats"]
    groups = {}
    for seat in seats:
        groups.setdefault(seat["section"], []).append(seat["pos"])
    scores = {}
    for degrees in (0, 90, 180, 270):
        angle = math.radians(degrees)
        matrix = np.array([[math.cos(angle), 0, math.sin(angle)], [0, 1, 0],
                           [-math.sin(angle), 0, math.cos(angle)]])
        scores[str(degrees)] = {
            name: float(np.abs(np.array([(np.asarray(rows) @ matrix.T).min(0),
                                        (np.asarray(rows) @ matrix.T).max(0)])
                               - crowd[name]["bounds"]).mean())
            for name, rows in groups.items() if name in crowd}
    best = min(scores, key=lambda k: np.mean(list(scores[k].values())))
    assert best == "90", scores
    points = np.array([[s["pos"][2], s["pos"][1], -s["pos"][0]] for s in seats])
    crowd_points = np.vstack([
        np.frombuffer(binary, "<f4", count=m["vertexCount"] * 3,
                      offset=m["positionOffset"]).reshape(-1, 3) for m in crowd.values()])
    distances = cKDTree(crowd_points).query(points)[0]
    candidates = [i for i, s in enumerate(seats) if s["section"] in crowd and distances[i] < .8]
    assert candidates
    index = min(candidates, key=lambda i: abs(points[i, 2] + 75) +
                3 * abs(points[i, 0]) + abs(points[i, 1] - 12))
    manifest["seatView"] = {"position": points[index].tolist(), "sourceIndex": index,
                            "sourceFrameRotationY": 90}
    manifest["limits"].extend([
        "Original stadium roof state retained; no retractable-roof animation or invented roof geometry.",
        "Roof skins/trusses, roof lights and hanging scoreboard follow the roof switch; facade retained.",
        "Fan groups and source section envelopes are not official numbered seating blocks.",
        "Unity baked lightmaps and probes are evidence only; browser uses the existing runtime lighting.",
        "Geographic orientation: source left crowd (+z) is the north/home end; right (-z) south/guest.",
    ])
    manifest["assetVersion"] = hashlib.sha256(
        json.dumps({k: v for k, v in manifest.items() if k != "assetVersion"},
                   sort_keys=True).encode()).hexdigest()[:16]
    validate_model_manifest(manifest)
    write("manifest.json", manifest)
    write("pitch-check.json", validate_pitch_geometry(manifest, binary))
    write("seat-alignment.json", {
        "sourceSeatPoints": len(seats), "errorsByRotation": scores, "selectedRotation": 90,
        "unmatchedSeatSections": sorted(set(groups) - set(crowd)),
        "unmatchedCrowdSections": sorted(set(crowd) - set(groups)),
        "distanceQuantilesMeters": np.quantile(distances, [0, .5, .9, .99, 1]).tolist(),
        "economicCapacityNotDerivedFromSeats": True,
    })
    write("roof-evidence.json", {"roofMeshes": roofs, "fixedFacade": sorted(fixed),
                                "includedExtraRoot": True})
    opening = bowl_opening(manifest, binary, level=1.3)
    opening["groundLevel"] = 0
    opening["method"] += (
        " Protective envelope sampled at +1.3m (lowest seating) while the flat "
        "schematic terrain remains at model y=0; avoids half-pitch floating-point clipping."
    )
    raw = json.loads((OUT / "osm-fresh/raw.json").read_text())
    nodes = {e["id"]: e for e in raw["elements"] if e["type"] == "node"}
    way = next(e for e in raw["elements"] if e["type"] == "way" and e["id"] == STADIUM_WAY)
    assert way["tags"]["wikidata"] == "Q150961"
    ll = np.array([[nodes[n]["lon"], nodes[n]["lat"]] for n in way["nodes"][:-1]])
    origin = ll.mean(0)
    meters = np.array([math.cos(math.radians(origin[1])), 1]) * 6371000 * math.pi / 180
    rectangle = Polygon((ll - origin) * meters).minimum_rotated_rectangle
    corners = np.asarray(rectangle.exterior.coords[:-1])
    edges = np.roll(corners, -1, axis=0) - corners
    axis = max(edges, key=np.linalg.norm)
    if axis[1] < 0:
        axis = -axis
    reference = {
        "centerLonLat": (np.asarray(rectangle.centroid.coords[0]) / meters + origin).tolist(),
        "axisEastNorth": (axis / np.linalg.norm(axis)).tolist(),
        "method": "Center and long axis of the mapped arena footprint minimum rotated rectangle.",
        "stadiumWay": STADIUM_WAY,
        "axisCheck": "Official north home curve and south guest entrance; northward long axis.",
        "officialPlan": "https://veltins-arena.de/app/uploads/2026/07/VELTINS-Arena_Plan_2026.pdf",
        "limits": "Mapped footprint registration, not a surveyed interior pitch center. "
                  "The OSM pitch is the displaced outdoor roll-out field and cannot supply arena center.",
    }
    write("presentation.json", {"presentation": {
        "renderer": "unity-spatial", "clubFmiId": 920, "clubId": club.pk,
        "stadium": stadium.name, "capacity": stadium.capacity_total,
        "sourceSha256": manifest["sourceSha256"],
        "calibration": manifest["calibration"], "designColors": {},
    }})
    build(study=OUT, out=OUT / "osm-fresh", pitch_id=ROLLOUT_PITCH,
          stadium_id=STADIUM_WAY, stadium_building_id=None, stadium_wikidata=None,
          fmi=920, opening=opening, north_axis=True, frame_reference=reference,
          represented_stadium_roofs=(147192583, 147192591))
    terrain = json.loads((OUT / "osm-fresh/terrain-check.json").read_text())
    assert terrain["ok"] and terrain["terrainDeclared"] and not terrain["findings"], terrain
    presentation = json.loads((OUT / "osm-fresh/presentation.json").read_text())["presentation"]
    write("editor-geometry.json", editor_geometry(stadium, manifest, binary, presentation))
    print(json.dumps({"club": club.name, "seats": len(seats), "roofs": len(roofs),
                      "matchedCrowdSections": len(scores[best]),
                      "verifiedLights": manifest["verifiedFixtureCount"]}))


if __name__ == "__main__":
    prepare()
