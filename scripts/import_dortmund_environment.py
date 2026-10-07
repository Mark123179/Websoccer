"""Offline adapter for the supplied pitch-frame OSM package; never writes ORM."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from stadium_editor.natural_packages import validate_natural_package

SOURCES = ROOT / "stadium_editor/blueprints/natural/sources"


def prepare_package(environment, scene):
    """Preserve mapped objects; incoming coordinates are ALREADY pitch metres."""
    meta = environment["meta"]
    if meta["frame"]["origin"] != "pitch-center" or meta["frame"]["unit"] != "m":
        raise ValueError("Quellpaket ist nicht in Spielfeldmetern.")
    if scene.get("schema") != "websoccer.stadium-live-scene" or scene.get("units") != "m":
        raise ValueError("Ungültige ergänzende Ortsgeometrie.")
    base = scene["surroundings"]
    data = {
        "roads": deepcopy(base["roads"]),
        "buildings": [deepcopy(b["poly"]) for b in base["buildings"]],
        "buildingHeights": [b["h"] for b in base["buildings"]],
        "green": [deepcopy(g["poly"]) for g in environment["grass"]],
        "water": [deepcopy(w["poly"]) for w in environment["water"]],
        "trees": [deepcopy(t["p"]) for t in environment["trees"]],
        "treeMetadata": deepcopy(environment["trees"]),
        "shrubs": [],
        "sources": {
            "geography": meta["source"],
            "trees": f"OpenStreetMap natural=tree; {len(environment['trees'])} mapped nodes, not inferred representatives",
        },
        "sourceDetail": deepcopy(meta),
    }
    for key in ("parking", "forest", "scrub", "sports", "landuse", "buildingsTagged", "treeRows"):
        data[key] = deepcopy(environment[key])
    data["grassTagged"] = deepcopy(environment["grass"])
    package = {
        "schema": "websoccer.natural-surroundings", "version": 1, "visualVersion": 2,
        "units": "m", "id": "dortmund", "title": "Signal Iduna Park",
        "frame": {"fieldC": [0, 0], "axisTheta": 0, "sceneAxes": "pitch-west-camera"},
        "model": {"mirror": False, "mirrorAxis": "longitudinal", "verified": False},
        "data": data,
        "calibration": {
            "sceneMapping": "scene X=field Y, scene Z=field X, scene Y=height",
            "northVector": deepcopy(meta["frame"]["northVector"]),
            "southStand": "+field X", "cameraStand": "-field Y (WEST)",
        },
        "limitations": [
            "OSM snapshot, not real-time parking occupancy.",
            "Tree species, heights and car occupancy are graphical approximations.",
            "Additional representatives only inside mapped forest/scrub polygons.",
            "Unknown facade materials remain neutral; building heights are approximate.",
            "Model alignment must be checked against physical stand geometry before mirroring.",
        ],
    }
    return validate_natural_package(package)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "stadium_editor/blueprints/natural/dortmund.json")
    args = parser.parse_args()
    if args.archive:
        # Extract only known JSON entries, never arbitrary paths or bundled code.
        SOURCES.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(args.archive) as archive:
            for name, target in (
                ("dortmund_umfeld.json", "dortmund_umfeld.json"),
                ("scenes/bvb_v2.json", "dortmund_scene.json"),
            ):
                info = archive.getinfo(name)
                if info.file_size > 2_000_000:
                    raise ValueError("Quell-JSON ist zu groß.")
                raw = archive.read(name)
                json.loads(raw)
                (SOURCES / target).write_bytes(raw)
        (SOURCES / "source_archive.sha256").write_text(hashlib.sha256(args.archive.read_bytes()).hexdigest() + "\n")
    environment = json.loads((SOURCES / "dortmund_umfeld.json").read_text())
    scene = json.loads((SOURCES / "dortmund_scene.json").read_text())
    package = prepare_package(environment, scene)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(package, ensure_ascii=False, separators=(",", ":")))
    print("Prepared pitch-frame package:", {k: len(package["data"][k]) for k in
          ("parking", "trees", "forest", "scrub", "sports", "green")})


if __name__ == "__main__":
    main()
