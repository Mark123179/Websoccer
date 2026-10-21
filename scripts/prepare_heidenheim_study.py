"""Read-only preparation of the reviewed Voith-Arena source package."""
import hashlib
import json
import math
import os
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.spatial import cKDTree

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
import django
django.setup()

from game.models import Club
from scripts.build_mainz_osm_review import bowl_opening, build
from scripts.prepare_veltins_study import editor_geometry
from stadium_editor.model_registry import validate_model_manifest
from stadium_editor.package_preflight import inspect_package
from stadium_editor.pitch_validation import validate_pitch_geometry

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "generated-artifacts/heidenheim-study"
SOURCE = OUT / "source-export"
SEATS = ROOT / "attached_assets/heidenheim_1792607899714.json"
ROOFS = {
    "center2_3", "center2_4", "center2_5", "center2_7", "center2_8",
    "front3_7", "front3_8", "front3_9", "front3_11", "left1_19",
}


def write(name, document):
    (OUT / name).write_text(json.dumps(document, ensure_ascii=False, indent=2))


def prepare():
    club = Club.objects.get(fm_inside_id=880295, transfermarkt_id=2036)
    stadium = club.stadium
    assert "heidenheim" in club.name.casefold() and "voith" in stadium.name.casefold()
    manifest = json.loads((SOURCE / "manifest.json").read_text())
    binary = (SOURCE / "geometry.bin").read_bytes()
    assert hashlib.sha256(binary).hexdigest() == manifest["geometrySha256"]
    actual_roofs = []
    for mesh in manifest["meshes"]:
        if mesh["name"] in ROOFS:
            actual_roofs.append(mesh["name"])
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
    assert set(actual_roofs) == ROOFS
    manifest["calibration"].update({
        "standAxes": {"+x": "SUED", "-x": "NORD", "+z": "OST", "-z": "WEST"},
        "surroundingsAxes": {"NORD": "-x", "WEST": "-z"},
    })
    # Browser photometry, not a claim about Unity's point-light settings.
    # Four corner towers need wider coverage than an overhead roof-light bank.
    for fixture in manifest["fixtures"]:
        fixture.update(range=250., angle=100., intensity=320.)
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
    assert all(scores.values()), "No source seat-to-crowd section matches"
    best = min(scores, key=lambda k: np.mean(list(scores[k].values())))
    angle = math.radians(int(best))
    matrix = np.array([[math.cos(angle), 0, math.sin(angle)], [0, 1, 0],
                       [-math.sin(angle), 0, math.cos(angle)]])
    points = np.asarray([s["pos"] for s in seats]) @ matrix.T
    crowd_points = np.vstack([
        np.frombuffer(binary, "<f4", count=m["vertexCount"] * 3,
                      offset=m["positionOffset"]).reshape(-1, 3) for m in crowd.values()])
    distances = cKDTree(crowd_points).query(points)[0]
    candidates = [i for i, s in enumerate(seats) if s["section"] in crowd and distances[i] < 1]
    assert candidates
    index = min(candidates, key=lambda i: abs(points[i, 2] - 65) +
                3 * abs(points[i, 0]) + abs(points[i, 1] - 7))
    manifest["seatView"] = {"position": points[index].tolist(), "sourceIndex": index,
                            "sourceFrameRotationY": int(best)}
    manifest["limits"].extend([
        "Four original tower panels: 144 photo-texture UV emitter samples, 12 runtime fixtures.",
        "Unity point-light components are not adopted: their type/range/directions do not define pitch floodlights.",
        "Emitter locations/normals follow original textured triangles; runtime range/angle/intensity are schematic.",
        "Original far-context mesh center2_2 replaced by fresh mapped OSM surroundings; source assets unchanged.",
        "Schematic crowd envelopes, not official numbered block boundaries or an individual seat survey.",
        "North main stand is source -x, home east end +z, guest west end -z.",
        "Terrain is explicitly flat schematic y=0; no measured Schlossberg terrain surface.",
    ])
    manifest["assetVersion"] = hashlib.sha256(
        json.dumps({k: v for k, v in manifest.items() if k != "assetVersion"},
                   sort_keys=True).encode()).hexdigest()[:16]
    validate_model_manifest(manifest)
    write("manifest.json", manifest)
    write("pitch-check.json", validate_pitch_geometry(manifest, binary))
    write("seat-alignment.json", {
        "sourceSeatPoints": len(seats), "errorsByRotation": scores, "selectedRotation": int(best),
        "unmatchedSeatSections": sorted(set(groups) - set(crowd)),
        "unmatchedCrowdSections": sorted(set(crowd) - set(groups)),
        "distanceQuantilesMeters": np.quantile(distances, [0, .5, .9, .99, 1]).tolist(),
        "economicCapacityNotDerivedFromSeats": True,
    })
    write("roof-evidence.json", {"roofMeshes": sorted(actual_roofs),
                                "includedExtraRoot": True, "towerMeshRetained": "center2_9"})
    opening = bowl_opening(manifest, binary, level=1.3)
    opening["groundLevel"] = 0
    write("presentation.json", {"presentation": {
        "renderer": "unity-spatial", "clubFmiId": 880295, "clubId": club.pk,
        "stadium": stadium.name, "capacity": stadium.capacity_total,
        "sourceSha256": manifest["sourceSha256"], "calibration": manifest["calibration"],
        "designColors": {},
    }})
    raw = json.loads((OUT / "osm-fresh/raw.json").read_text())
    (OUT / "osm-fresh/fetch.json").write_text(json.dumps({
        "url": raw["source"], "method": "GET", "format": "OSM XML converted without tag changes",
        "originalXmlSha256": hashlib.sha256((OUT / "osm-fresh/map-source.osm").read_bytes()).hexdigest(),
        "overpassUnavailable": "HTTP 406; official OSM map API used instead",
    }, indent=2))
    build(study=OUT, out=OUT / "osm-fresh", pitch_id=33882045,
          stadium_id=681162690, stadium_building_id=-1,
          stadium_wikidata="Q548138", fmi=880295, opening=opening,
          represented_stadium_buildings=(68102802, 68102804))
    presentation = json.loads((OUT / "osm-fresh/presentation.json").read_text())["presentation"]
    geometry = editor_geometry(
        stadium, manifest, binary, presentation, out=OUT,
        model_stands={"NORD": "OST", "SUED": "WEST", "OST": "SUED", "WEST": "NORD"},
        home_stand="OST", main_stand="NORD")
    check = inspect_package(geometry, axes=manifest["calibration"]["surroundingsAxes"])
    assert check["ok"] and check["terrainDeclared"] and not check["findings"], check
    write("editor-geometry.json", geometry)
    write("terrain-preflight.json", check)
    print(json.dumps({"club": club.name, "seats": len(seats), "roofs": len(actual_roofs),
                      "seatRotation": int(best), "sourceEmitters": manifest["verifiedFixtureCount"],
                      "runtimeLights": len(manifest["fixtures"]), "capacity": stadium.capacity_total}))


if __name__ == "__main__":
    prepare()
