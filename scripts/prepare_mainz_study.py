"""Build a read-only Mainz source review. No registration, storage or ORM writes."""
import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import sys

import numpy as np
from PIL import Image
from shapely.geometry import Polygon
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
import django
django.setup()

from game.models import Club, Stadium
from stadium_editor.model_registry import validate_model_manifest
from stadium_editor.package_preflight import inspect_package
from stadium_editor.pitch_validation import validate_pitch_geometry


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2))


def main(out):
    source = out / "source-export"
    manifest = json.loads((source / "manifest.json").read_text())
    geometry = (source / "geometry.bin").read_bytes()
    club = Club.objects.get(fm_inside_id=918, transfermarkt_id=39)
    stadium = Stadium.objects.get(club=club)
    assert "mainz" in club.name.casefold()
    original = deepcopy(manifest)

    # Separate the source roof skins/trusses by actual mesh identity, not height.
    roof_names = {f"front3_{i}" for i in range(33)} | {"front3_df_0"}
    assert roof_names <= {mesh["name"] for mesh in manifest["meshes"]}
    roof_triangles = 0
    for mesh in manifest["meshes"]:
        if mesh["name"] in roof_names:
            mesh["sourceMeshName"] = mesh["name"]
            mesh["name"] = "DACH_" + mesh["name"]
            roof_triangles += sum(p["indexCount"] // 3 for p in mesh["parts"])
        for part in mesh["parts"]:
            if mesh["name"] == "st081_pitch_1" and part["material"] == "000STADIUMLINE":
                # Retain the actual 105x68m source line triangles. Unity's
                # feathering shader is not reproduced by a plain alpha map.
                part["texture"] = None
                part["transparent"] = False
                part.pop("alphaTest", None)
                continue
            if part["texture"]:
                image = Image.open(source / part["texture"])
                if "A" in image.getbands() and image.getchannel("A").getextrema()[0] < 255:
                    part["transparent"] = True
                    part["alphaTest"] = 0.02
    manifest["calibration"]["roofMeshPrefixes"] = ["DACH_"]
    # Source-exported generic background is not geographically mapped context.
    manifest["calibration"]["skipMeshPrefixes"] = ["center2_"]

    # The source apron is at +5.85m. Its actual inner boundary supplies the hole
    # for the shared terrain plane; never approximate the bowl with a rectangle.
    apron = next(mesh for mesh in original["meshes"] if mesh["name"] == "center2_1")
    positions = np.frombuffer(geometry, dtype="<f4", count=apron["vertexCount"] * 3,
                              offset=apron["positionOffset"]).reshape(-1, 3)
    polygons = []
    for part in apron["parts"]:
        indices = np.frombuffer(geometry, dtype="<u4", count=part["indexCount"],
                                offset=part["indexOffset"]).reshape(-1, 3)
        for ids in indices:
            polygon = Polygon(positions[ids][:, [0, 2]])
            if polygon.area > 1e-8:
                polygons.append(polygon)
    surface = unary_union(polygons)
    assert surface.geom_type == "Polygon" and len(surface.interiors) == 1
    cutout = [list(point) for point in list(surface.interiors[0].coords)[:-1]]
    ground_level = float(np.median(positions[:, 1]))

    seats_path = ROOT / "attached_assets/mainz_1792480841090.json"
    seats_data = json.loads(seats_path.read_text())
    rotation_scores = {}
    for degrees in (0, 90, 180, 270):
        theta = np.deg2rad(degrees)
        rotation = np.array([[np.cos(theta), 0, np.sin(theta)], [0, 1, 0],
                             [-np.sin(theta), 0, np.cos(theta)]])
        errors = {}
        for name in seats_data["sections"]:
            seats = np.array([s["pos"] for s in seats_data["seats"] if s["section"] == name])
            transformed = seats @ rotation.T
            crowd = next(mesh for mesh in original["meshes"] if mesh["name"] == name)
            errors[name] = float(np.abs(np.array([transformed.min(0), transformed.max(0)])
                                       - np.array(crowd["bounds"])).mean())
        rotation_scores[str(degrees)] = errors
    assert min(rotation_scores, key=lambda angle: np.mean(list(rotation_scores[angle].values()))) == "90"
    assert max(rotation_scores["90"].values()) < 1.0
    manifest["seatView"]["sourceFrameRotationY"] = 90
    manifest["limits"].extend([
        "Review only: original source materials use historical Opel branding.",
        "Roof skins/trusses are separated; fixed facade columns remain body.",
        "No new manager design exists for this stadium; source seating colors remain visible.",
        "Flat surroundings at the source apron elevation, not an official terrain survey.",
        "OSM bundle heights are schematic, not measured building elevations.",
        "Pitch markings use the original line triangles and source white color without Unity alpha feathering.",
        "World orientation and economic stand labels require separate acceptance.",
    ])
    manifest["assetVersion"] = hashlib.sha256(
        json.dumps(manifest, sort_keys=True).encode()).hexdigest()[:16]
    validate_model_manifest(manifest)
    pitch = validate_pitch_geometry(manifest, geometry)

    raw = json.loads((out / "osm-source.json").read_text())
    bg = raw["bg"]
    surroundings = {
        "source": "OpenStreetMap/BLUEPRINT-Bundle (ODbL)",
        "treeSource": "", "green": bg["green"], "water": bg["water"], "roads": bg["roads"],
        "buildings": [b if isinstance(b, list) else b["poly"] for b in bg["buildings"]],
        "buildingHeights": [None if isinstance(b, list) else b.get("h") for b in bg["buildings"]],
        "buildingIds": [None if isinstance(b, list) else b.get("id") for b in bg["buildings"]],
        "trees": bg.get("trees", []), "heightQuality": "schematic",
        "groundLevel": ground_level, "groundCutout": cutout,
    }
    presentation = {
        "renderer": "unity-spatial", "clubFmiId": 918, "stadium": stadium.name,
        "sourceSha256": manifest["sourceSha256"],
        "modelUrl": f"/models/918/{manifest['assetVersion']}/manifest.json",
        "frame": {k: raw["meta"][k] for k in ("fieldC", "axisTheta", "maxR")},
        "surroundings": surroundings, "calibration": manifest["calibration"],
        "designColors": {},
    }
    terrain = inspect_package(presentation,
                              axes=manifest["calibration"]["surroundingsAxes"])
    write(out / "terrain-check.json", terrain)
    # A source conflict is a review finding, not permission to delete OSM data.
    if not terrain["ok"]:
        write(out / "presentation-with-legacy-osm-blocked.json", {"presentation": presentation})
        manifest["calibration"]["skipMeshPrefixes"] = ["center2_2", "center2_3",
                                                        "center2_4", "center2_5",
                                                        "center2_6", "center2_7",
                                                        "center2_8", "center2_9",
                                                        "center2_10"]
        presentation["calibration"] = manifest["calibration"]
        presentation["surroundings"] = {
            "source": "Isolierte Originalmodell-Prüfung; geografisches Umfeld wegen Quellkonflikt nicht geladen",
            "heightQuality": "not-loaded", "green": [], "water": [], "roads": [],
            "buildings": [], "trees": [],
        }
        manifest["limits"].append(
            "Geographic surroundings blocked by a conflicting legacy polygon. "
            "Source pavement and grass retained for isolated review; no OSM features deleted."
        )
    manifest.pop("assetVersion")
    manifest["assetVersion"] = hashlib.sha256(
        json.dumps(manifest, sort_keys=True).encode()).hexdigest()[:16]
    presentation["modelUrl"] = f"/models/918/{manifest['assetVersion']}/manifest.json"
    validate_model_manifest(manifest)
    write(out / "manifest.json", manifest)
    write(out / "presentation.json", {"presentation": presentation})
    write(out / "review.json", {
        "clubFmiId": 918, "localClubId": club.pk, "localStadiumId": stadium.pk,
        "capacityFromDatabase": stadium.capacity_total,
        "sourceSeatCount": seats_data["total_seats"], "pitch": pitch,
        "roofMeshCount": len(roof_names), "roofTriangles": roof_triangles,
        "extraRootIncluded": "EXTRA", "sourceGeometryUnchanged": original["geometrySha256"] == manifest["geometrySha256"],
        "seatFrameErrorsMeters": rotation_scores,
        "terrainSourceMesh": "center2_1", "sourceApronElevation": ground_level,
        "cutoutVertices": len(cutout), "terrainOk": terrain["ok"],
        "databaseWrites": False, "registrationPerformed": False, "assetsUploaded": False,
        "limits": manifest["limits"],
    })
    print(json.dumps({"capacity": stadium.capacity_total, "sourceSeats": seats_data["total_seats"],
                      "roofMeshes": len(roof_names), "terrainOk": terrain["ok"],
                      "fixtures": manifest["verifiedFixtureCount"]}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "generated-artifacts/mainz-study")
    main(parser.parse_args().out)
