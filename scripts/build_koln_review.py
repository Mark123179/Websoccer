"""Build Cologne OSM surroundings and source-seat editor envelopes."""
from collections import defaultdict
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
from scripts.prepare_koln_study import OUT, ROOT, prepare, write


def source_envelope_geometry(stadium, presentation):
    """Source-section envelopes, not invented official block numbers."""
    theta = presentation["frame"]["axisTheta"]
    def project(x, z):
        return [z * math.cos(theta) + x * math.sin(theta),
                z * math.sin(theta) - x * math.cos(theta)]

    seats = json.loads((ROOT / "attached_assets/koln_1792488328917.json").read_text())["seats"]
    groups = defaultdict(list)
    for seat in seats:
        a, y, b = seat["pos"]
        x, z = b, -a
        section = seat["section"]
        stand = ("NORD" if "left1" in section or "UltraAway" in section else
                 "SUED" if "right1" in section else
                 "WEST" if "front" in section else "OST")
        tier = "UNTER" if y < 12 else "OBER"
        groups[(stand, tier, section)].append([x, y, z])
    blocks, evidence = [], []
    for (stand, tier, section), rows in sorted(groups.items()):
        pts = np.asarray(rows)
        end = stand in ("NORD", "SUED")
        tangent = pts[:, 0 if end else 2]
        # Shared tangent boundaries prevent overlap between this section's strips.
        boundaries = np.linspace(tangent.min() - .25, tangent.max() + .25, 4)
        for i in range(3):
            selected = pts[(tangent >= boundaries[i]) & (tangent < boundaries[i+1])]
            if len(selected) < 4:
                continue
            t0, t1 = float(selected[:, 0 if end else 2].min() - .25), float(
                selected[:, 0 if end else 2].max() + .25)
            r = np.abs(selected[:, 2 if end else 0])
            r0, r1 = float(r.min() - .4), float(r.max() + .4)
            sign = 1 if stand in ("NORD", "OST") else -1
            def point(t, radius):
                return project(t, sign * radius) if end else project(sign * radius, t)
            block = {
                "id": len(blocks), "stand": stand, "tier": tier, "type": "SITZ",
                "quad": [point(t0, r1), point(t1, r1), point(t1, r0), point(t0, r0)],
                "rows": max(1, math.ceil((r1-r0) / .8)),
                "seats": max(1, math.ceil((t1-t0) / .5)),
                "z0": float(selected[:, 1].min()), "z1": float(selected[:, 1].max()),
                "sourceSection": section, "sourceSeatCount": len(selected),
            }
            blocks.append(block)
            evidence.append({"blockId": block["id"], "sourceSection": section,
                             "tier": tier, "stand": stand, "sourceSeatPoints": len(selected)})
    assert sum(b["sourceSeatCount"] for b in blocks) == len(seats)
    geometry = {
        "version": 2, "physical_grid": "v2",
        "meta": {"name": stadium.name, "club": stadium.club.name,
                 **deepcopy(presentation["frame"])},
        "blocks": blocks, "homeStand": "SUED", "mainStand": "WEST",
        "outline": [project(x, z) for x, z in json.loads(
            (OUT / "osm-fresh/evidence.json").read_text())["mappedStadiumModelCoordinates"]],
        "roofs": [], "surroundings": deepcopy(presentation["surroundings"]),
        "source": "Unity source-seat section envelopes + fresh OpenStreetMap",
    }
    geometry["bg"] = deepcopy(presentation["surroundings"])
    data = geometry["bg"]
    data["buildings"] = [
        {"poly": p, "h": h, "id": identity}
        for p, h, identity in zip(data["buildings"], data["buildingHeights"],
                                  data["buildingIds"], strict=True)
    ]
    geometry = normalise_block_types(stadium, geometry)
    effective = distribute_capacities(stadium, geometry)
    trusted = {b["id"]: b for b in geometry_blocks(effective)}
    for block in effective["blocks"]:
        block.update(trusted[block["id"]])
    build_live_scene(stadium, geometry, standard_design_for_geometry(stadium, effective))
    assert sum(b["capacity"] for b in effective["blocks"]) == stadium.capacity_total
    write("editor-envelope-evidence.json", {
        "method": "Three tangent strips per source seat section and tier; projected seat envelopes.",
        "limits": "Source-section envelopes, not official numbered block topology. "
                  "Physical grids are independent of economic capacity.",
        "sourceSeatPoints": len(seats), "blocks": evidence})
    return geometry


def editor_geometry(stadium, presentation):
    """Offer reviewed FC labels, retaining source envelopes as legacy evidence."""
    from stadium_editor.koln_blocks import build_official_geometry
    legacy = source_envelope_geometry(stadium, presentation)
    seats = json.loads((ROOT / "attached_assets/koln_1792488328917.json").read_text())["seats"]
    geometry, evidence = build_official_geometry(legacy, seats)
    write("editor-official-block-evidence.json", evidence)
    effective = distribute_capacities(stadium, geometry)
    build_live_scene(stadium, geometry, standard_design_for_geometry(stadium, effective))
    return geometry


def main():
    prepare()
    club = Club.objects.get(fm_inside_id=916, transfermarkt_id=3)
    stadium = Stadium.objects.get(club=club)
    manifest = json.loads((OUT / "manifest.json").read_text())
    presentation = {
        "renderer": "unity-spatial", "clubFmiId": 916, "clubId": club.pk,
        "stadium": stadium.name, "capacity": stadium.capacity_total,
        "sourceSha256": manifest["sourceSha256"],
        "calibration": manifest["calibration"], "designColors": {},
    }
    write("presentation.json", {"presentation": presentation})
    build(study=OUT, out=OUT / "osm-fresh", pitch_id=123127315,
          stadium_id=145246719, stadium_building_id=271681, stadium_wikidata=None,
          fmi=916, opening=json.loads((OUT / "bowl-opening.json").read_text()),
          north_axis=True)
    presentation = json.loads((OUT / "osm-fresh/presentation.json").read_text())["presentation"]
    geometry = editor_geometry(stadium, presentation)
    write("editor-geometry.json", geometry)
    print(json.dumps({"clubId": club.pk, "stadiumId": stadium.pk,
                      "capacity": stadium.capacity_total, "editorBlocks": len(geometry["blocks"])}))


if __name__ == "__main__":
    main()
