"""Prepare the source-faithful Cologne package without touching game state."""
import argparse
from collections import defaultdict
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image
from shapely.geometry import MultiPoint

from stadium_editor.model_registry import validate_model_manifest
from stadium_editor.pitch_validation import validate_pitch_geometry

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "generated-artifacts/koln-study"
SOURCE = OUT / "source-export"

CALIBRATION = {
    "roofMinHeight": -1, "roofMeshPrefixes": ["DACH_"],
    "skipMeshPrefixes": ["center2_26", "center2_28", "center2_29", "center2_37", "center2_38"],
    "crowdPrefix": "C_", "pitchPrefix": "st081_pitch_",
    "tickerRotationY": -90, "tickerFrontCut": {"normal": [1, 0, 0], "constant": 32},
    # Official FC plan: away corner is north/east, matching source +z/+x.
    "standAxes": {"+x": "OST", "-x": "WEST", "+z": "NORD", "-z": "SUED"},
    "surroundingsAxes": {"NORD": "+z", "WEST": "-x"},
    "orbitDefault": {"azimuth": .95, "elevation": .65, "distance": 360},
}


def write(name, data):
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2))


def prepare():
    manifest = json.loads((SOURCE / "manifest.json").read_text())
    binary = (SOURCE / "geometry.bin").read_bytes()
    assert hashlib.sha256(binary).hexdigest() == manifest["geometrySha256"]
    roof_names = {f"front3_{i}" for i in range(52)} - {"front3_20"}
    assert roof_names <= {m["name"] for m in manifest["meshes"]}
    for mesh in manifest["meshes"]:
        if mesh["name"] in roof_names:
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
    seat_data = json.loads((ROOT / "attached_assets/koln_1792488328917.json").read_text())
    seats = seat_data["seats"]
    grouped = defaultdict(list)
    for seat in seats:
        grouped[seat["section"]].append(seat["pos"])
    rotations = {}
    for degrees in (0, 90, 180, 270):
        theta = math.radians(degrees)
        rotation = np.array([[math.cos(theta), 0, math.sin(theta)], [0, 1, 0],
                             [-math.sin(theta), 0, math.cos(theta)]])
        rotations[str(degrees)] = {}
        for section, positions in grouped.items():
            points = np.asarray(positions) @ rotation.T
            mesh = next(m for m in manifest["meshes"] if m["name"] == section)
            rotations[str(degrees)][section] = float(np.abs(
                np.asarray([points.min(0), points.max(0)]) - mesh["bounds"]).mean())
    best = min(rotations, key=lambda k: np.mean(list(rotations[k].values())))
    assert best == "90", rotations
    assert max(rotations[best].values()) < 1, rotations[best]
    write("seat-alignment.json", {"errorsByRotation": rotations, "selectedRotation": 90,
                                  "seatPoints": len(seats),
                                  "economicCapacityNotDerivedFromSeats": True})
    # The source seat choice must be made in the transformed frame.
    transformed = [[s["pos"][2], s["pos"][1], -s["pos"][0]] for s in seats]
    index = min(range(len(seats)), key=lambda i:
                abs(transformed[i][2] + 75) + 3 * abs(transformed[i][0]) +
                abs(transformed[i][1] - 12))
    manifest["seatView"] = {"position": transformed[index], "sourceIndex": index,
                            "sourceFrameRotationY": 90}
    manifest["limits"] += [
        "51 individually identified front3 roof meshes; facade railings and permanent pylons retained.",
        "Source seat points are visual evidence, not the economic capacity.",
        "Background terrain, trees and duplicate Abel buildings replaced by georeferenced OSM.",
    ]
    manifest.pop("assetVersion", None)
    manifest["assetVersion"] = hashlib.sha256(
        json.dumps(manifest, sort_keys=True).encode()).hexdigest()[:16]
    validate_model_manifest(manifest)
    write("manifest.json", manifest)
    write("pitch-check.json", validate_pitch_geometry(manifest, binary))
    # Cross-section protects the below-grade bowl, not buried foundations.
    level = 2.1
    points = []
    for mesh in manifest["meshes"]:
        if not mesh["name"].startswith(("C_", "st081_pitch_", "field_")):
            continue
        vertices = np.frombuffer(binary, "<f4", count=mesh["vertexCount"] * 3,
                                 offset=mesh["positionOffset"]).reshape(-1, 3)
        for part in mesh["parts"]:
            triangles = np.frombuffer(binary, "<u4", count=part["indexCount"],
                                      offset=part["indexOffset"]).reshape(-1, 3)
            for triangle in vertices[triangles]:
                for a, b in zip(triangle, np.roll(triangle, -1, axis=0)):
                    if a[1] <= level:
                        points.append(a[[0, 2]].tolist())
                    if min(a[1], b[1]) < level < max(a[1], b[1]):
                        p = a + (b-a) * (level-a[1]) / (b[1]-a[1])
                        points.append(p[[0, 2]].tolist())
    opening = MultiPoint(points).convex_hull
    write("bowl-opening.json", {"groundLevel": level,
                              "groundCutout": list(map(list, opening.exterior.coords[:-1])),
                              "method": "Source lower-crowd and field cross-section at source terrain level.",
                              "areaSquareMeters": opening.area,
                              "geometrySha256": manifest["geometrySha256"]})
    print(json.dumps({"meshes": len(manifest["meshes"]), "roofMeshes": len(roof_names),
                      "seats": len(seats), "seatAlignmentWorstError": max(rotations[best].values()),
                      "openingArea": opening.area}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--calibration-only", action="store_true")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    write("calibration.json", CALIBRATION)
    if not args.calibration_only:
        prepare()
