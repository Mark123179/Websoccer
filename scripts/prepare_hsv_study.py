"""Prepare the uploaded HSV source model without changing game data."""
import argparse
from collections import defaultdict
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.spatial import cKDTree

from stadium_editor.model_registry import validate_model_manifest
from stadium_editor.pitch_validation import validate_pitch_geometry
from scripts.build_mainz_osm_review import bowl_opening

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "generated-artifacts/hsv-study"
SOURCE = OUT / "source-export"
SEATS = ROOT / "attached_assets/volksparkstadion_1792496395203.json"
CALIBRATION = {
    "roofMinHeight": -1, "roofMeshPrefixes": ["DACH_"],
    "skipMeshPrefixes": ["center2_0"],
    "crowdPrefix": "C_", "pitchPrefix": "st081_pitch_",
    "tickerRotationY": 90,
    "tickerFrontCut": {"normal": [-1, 0, 0], "constant": 32},
    "standAxes": {"+x": "WEST", "-x": "OST", "+z": "SUED", "-z": "NORD"},
    "surroundingsAxes": {"NORD": "-z", "WEST": "+x"},
    "orbitDefault": {"azimuth": .95, "elevation": .65, "distance": 390},
}


def write(name, data):
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2))


def prepare():
    manifest = json.loads((SOURCE / "manifest.json").read_text())
    binary = (SOURCE / "geometry.bin").read_bytes()
    assert hashlib.sha256(binary).hexdigest() == manifest["geometrySha256"]
    # The hanging source scoreboards follow the user's roof-state convention.
    # Permanent support masts in center3_17 remain visible.
    roofs = {f"center3_{i}" for i in range(17)}
    assert roofs <= {m["name"] for m in manifest["meshes"]}
    for mesh in manifest["meshes"]:
        if mesh["name"] in roofs:
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
    manifest["calibration"] = deepcopy(CALIBRATION)
    seats = json.loads(SEATS.read_text())["seats"]
    groups = defaultdict(list)
    for seat in seats:
        groups[seat["section"]].append(seat["pos"])
    crowd = {m["name"]: m for m in manifest["meshes"] if m["name"].startswith("C_")}
    rotations = {}
    for degrees in (0, 90, 180, 270):
        theta = math.radians(degrees)
        rotation = np.array([[math.cos(theta), 0, math.sin(theta)],
                             [0, 1, 0], [-math.sin(theta), 0, math.cos(theta)]])
        errors = {}
        for name, rows in groups.items():
            if name not in crowd:
                continue
            points = np.asarray(rows) @ rotation.T
            errors[name] = float(np.abs(np.array([points.min(0), points.max(0)])
                                       - crowd[name]["bounds"]).mean())
        rotations[str(degrees)] = errors
    best = min(rotations, key=lambda key: np.mean(list(rotations[key].values())))
    assert best == "90", rotations
    transformed = np.asarray([[s["pos"][2], s["pos"][1], -s["pos"][0]] for s in seats])
    crowd_vertices = np.vstack([
        np.frombuffer(binary, "<f4", count=m["vertexCount"]*3,
                      offset=m["positionOffset"]).reshape(-1, 3)
        for m in crowd.values()
    ])
    distances = cKDTree(crowd_vertices).query(transformed)[0]
    write("seat-alignment.json", {
        "sourceSeatPoints": len(seats), "errorsByRotation": rotations,
        "selectedRotation": 90,
        "seatSectionsWithoutNamedCrowd": sorted(set(groups) - set(crowd)),
        "crowdSectionsWithoutNamedSeats": sorted(set(crowd) - set(groups)),
        "nearestCrowdVertexDistanceQuantilesMeters": np.quantile(
            distances, [0, .5, .9, .99, 1]).tolist(),
        "limits": "Fan-section names and bounds are not identical between seat JSON and crowd meshes. "
                  "The model and editor envelopes use actual source meshes; the seat camera "
                  "additionally requires proximity to crowd geometry.",
        "economicCapacityNotDerivedFromSeats": True,
    })
    # Use a source seat from a section whose crowd mesh is actually present.
    candidates = [(i, [s["pos"][2], s["pos"][1], -s["pos"][0]])
                  for i, s in enumerate(seats) if s["section"] in crowd and distances[i] < .8]
    assert candidates, "No source seat camera close to actual source crowd geometry"
    index, position = min(candidates, key=lambda row:
                          abs(row[1][2] + 75) + 3 * abs(row[1][0]) + abs(row[1][1] - 12))
    manifest["seatView"] = {"position": position, "sourceIndex": index,
                            "sourceFrameRotationY": 90}
    manifest["limits"] += [
        "17 reviewed roof meshes including hanging scoreboards; permanent masts retained.",
        "Source seat points and fan section labels do not define economic capacity or official blocks.",
        "Source billboard trees center2_0 replaced by actual OSM context.",
    ]
    manifest.pop("assetVersion", None)
    manifest["assetVersion"] = hashlib.sha256(
        json.dumps(manifest, sort_keys=True).encode()).hexdigest()[:16]
    validate_model_manifest(manifest)
    write("manifest.json", manifest)
    write("pitch-check.json", validate_pitch_geometry(manifest, binary))
    opening = bowl_opening(manifest, binary, 1.7)
    write("bowl-opening.json", opening)
    print(json.dumps({"meshes": len(manifest["meshes"]), "roofMeshes": len(roofs),
                      "seatPoints": len(seats), "matchedCrowdSections": len(rotations[best]),
                      "seatBoundsWorstMeanError": max(rotations[best].values()),
                      "openingArea": opening["areaSquareMeters"]}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--calibration-only", action="store_true")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    write("calibration.json", CALIBRATION)
    if not args.calibration_only:
        prepare()
