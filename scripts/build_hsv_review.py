"""Build HSV source-crowd editor envelopes and geographically mapped context."""
from copy import deepcopy
import json
import math
import os

import numpy as np

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
import django
django.setup()

from game.models import Club, Stadium
from stadium_editor.capacity import distribute_capacities
from stadium_editor.contracts import geometry_blocks
from stadium_editor.live_scene import build_live_scene, standard_design_for_geometry
from stadium_editor.seed import normalise_block_types
from scripts.build_mainz_osm_review import build
from scripts.prepare_hsv_study import OUT, SOURCE, write


def editor_geometry(stadium, presentation):
    manifest = json.loads((OUT / "manifest.json").read_text())
    binary = (SOURCE / "geometry.bin").read_bytes()
    groups = []
    for mesh in manifest["meshes"]:
        if mesh["name"].startswith("C_"):
            groups.append(np.frombuffer(
                binary, "<f4", count=mesh["vertexCount"]*3,
                offset=mesh["positionOffset"]).reshape(-1, 3))
    points = np.unique(np.vstack(groups), axis=0)
    theta = presentation["frame"]["axisTheta"]

    def project(x, z):
        # HSV +z is south and +x west, unlike the north-facing OSM pitch axis.
        return [-z*math.cos(theta)-x*math.sin(theta),
                -z*math.sin(theta)+x*math.cos(theta)]

    blocks, evidence = [], []
    for stand in ("NORD", "SUED", "OST", "WEST"):
        end = stand in ("NORD", "SUED")
        radial, tangent = (2, 0) if end else (0, 2)
        sign = 1 if stand in ("SUED", "WEST") else -1
        dominant = (np.abs(points[:, radial]) >= np.abs(points[:, tangent]) if end else
                    np.abs(points[:, radial]) > np.abs(points[:, tangent]))
        mask = (points[:, radial]*sign > 0) & dominant
        for rank, low, high in (("UNTEN", -100, 11.2), ("MITTE", 11.2, 20), ("OBEN", 20, 100)):
            selected = points[mask & (points[:, 1] >= low) & (points[:, 1] < high)]
            if len(selected) < 4:
                continue
            boundaries = np.linspace(selected[:, tangent].min()-.01,
                                     selected[:, tangent].max()+.01, 4)
            for i in range(3):
                strip = selected[(selected[:, tangent] >= boundaries[i]) &
                                 (selected[:, tangent] < boundaries[i+1])]
                if len(strip) < 4:
                    continue
                t0, t1 = float(strip[:, tangent].min()-.2), float(strip[:, tangent].max()+.2)
                r0, r1 = float(np.abs(strip[:, radial]).min()-.2), float(np.abs(strip[:, radial]).max()+.2)
                def point(t, r):
                    return project(t, sign*r) if end else project(sign*r, t)
                block = {
                    "id": len(blocks), "stand": stand,
                    "tier": "UNTER" if rank == "UNTEN" else "OBER",
                    "sourceRank": rank, "type": "SITZ",
                    "quad": [point(t0, r1), point(t1, r1), point(t1, r0), point(t0, r0)],
                    "rows": max(1, math.ceil((r1-r0)/.8)),
                    "seats": max(1, math.ceil((t1-t0)/.5)),
                    "z0": float(strip[:, 1].min()), "z1": float(strip[:, 1].max()),
                }
                assert block["z1"] > block["z0"]
                blocks.append(block)
                evidence.append({"blockId": block["id"], "sourceRank": rank,
                                 "stand": stand, "sourceVertices": len(strip)})
    assert sum(e["sourceVertices"] for e in evidence) == len(points)
    osm = json.loads((OUT / "osm-fresh/evidence.json").read_text())
    geometry = {
        "version": 2, "physical_grid": "v2",
        "meta": {"name": stadium.name, "club": stadium.club.name,
                 **deepcopy(presentation["frame"])},
        "blocks": blocks, "homeStand": "NORD", "mainStand": "WEST",
        "outline": [project(-x, -z) for x, z in osm["mappedStadiumModelCoordinates"]],
        "roofs": [], "surroundings": deepcopy(presentation["surroundings"]),
        "source": "HSV original crowd mesh envelopes + fresh OpenStreetMap",
    }
    geometry["bg"] = deepcopy(presentation["surroundings"])
    bg = geometry["bg"]
    bg["buildings"] = [{"poly": p, "h": h, "id": identity}
                       for p, h, identity in zip(bg["buildings"], bg["buildingHeights"],
                                                bg["buildingIds"], strict=True)]
    geometry = normalise_block_types(stadium, geometry)
    effective = distribute_capacities(stadium, geometry)
    trusted = {b["id"]: b for b in geometry_blocks(effective)}
    for block in effective["blocks"]:
        block.update(trusted[block["id"]])
    build_live_scene(stadium, geometry, standard_design_for_geometry(stadium, effective))
    assert sum(b["capacity"] for b in effective["blocks"]) == stadium.capacity_total
    write("editor-envelope-evidence.json", {
        "method": "Actual crowd vertices classified by side, source height band and three tangent strips.",
        "sourceCrowdVertices": len(points), "blocks": evidence,
        "limits": "Schematic source-mesh envelopes, not official numbered block boundaries. "
                  "Source middle and upper ranks share the existing OBER editor contract; "
                  "all three original ranks remain unchanged in the 3D source model.",
    })
    return geometry


def main():
    club = Club.objects.get(fm_inside_id=947, transfermarkt_id=41)
    stadium = Stadium.objects.get(club=club)
    manifest = json.loads((OUT / "manifest.json").read_text())
    presentation = {
        "renderer": "unity-spatial", "clubFmiId": 947, "clubId": club.pk,
        "stadium": stadium.name, "capacity": stadium.capacity_total,
        "sourceSha256": manifest["sourceSha256"],
        "calibration": manifest["calibration"], "designColors": {},
    }
    write("presentation.json", {"presentation": presentation})
    build(study=OUT, out=OUT / "osm-fresh", pitch_id=123124326,
          stadium_id=19617443, stadium_building_id=1686446,
          stadium_wikidata=None, fmi=947, north_axis=True,
          opening=json.loads((OUT / "bowl-opening.json").read_text()))
    presentation = json.loads((OUT / "osm-fresh/presentation.json").read_text())["presentation"]
    write("editor-geometry.json", editor_geometry(stadium, presentation))


if __name__ == "__main__":
    main()
