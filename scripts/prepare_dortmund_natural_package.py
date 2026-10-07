"""One-time adapter: existing measured review geometry + mapped-tree catalogue."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from stadium_editor.blueprints.v2.dortmund_preview import load_preview
from stadium_editor.surroundings import with_dortmund_mapped_trees
from stadium_editor.natural_packages import validate_natural_package

if (ROOT / "stadium_editor/blueprints/natural/sources/dortmund_umfeld.json").exists():
    from scripts.import_dortmund_environment import main
    main()
    raise SystemExit(0)

geometry = with_dortmund_mapped_trees(load_preview(), club_id=3)
source = geometry.get("surroundings") or geometry.get("bg")
data = deepcopy(source)
data["buildings"] = [b["poly"] for b in source["buildings"]]
data["buildingHeights"] = [b["h"] for b in source["buildings"]]
data["water"] = []
data["shrubs"] = []
data["sources"] = {"geography": source["source"], "trees": source["treeSource"]}
package = {
    "schema": "websoccer.natural-surroundings", "version": 1, "units": "m",
    "id": "dortmund", "title": "Signal Iduna Park",
    "frame": geometry.get("meta") or {"fieldC": [0, 0], "axisTheta": 0},
    "data": data,
    "calibration": {
        "coordinateSystem": "editor X goal-to-goal, Y touchline-to-touchline",
        "sceneMapping": "subtract fieldC, rotate -axisTheta, scene X=-v, Z=u",
        "roadHalfWidthScale": 1.25,
        "geometrySourceSha256": hashlib.sha256(json.dumps(load_preview(), sort_keys=True).encode()).hexdigest(),
    },
    "limitations": [
        "Lokaler OSM-Auszug; keine vollständige Einzelbaumvermessung.",
        "Ein Baumrepräsentant je ungefähr 16-m-Zelle.",
        "Baumformen, Arten und Größen sind grafische Annäherungen.",
        "Gebäudehöhen/-fassaden aus vereinfachtem Ausgangsmaterial; nicht vermessen.",
        "Keine neue Geländehöhe oder unbelegten Strauchpositionen.",
        "Straßenbreiten behalten die bestehende grafische Kalibrierung.",
    ],
}
validate_natural_package(package)
target = ROOT / "stadium_editor/blueprints/natural/dortmund.json"
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(json.dumps(package, ensure_ascii=False, separators=(",", ":")))
print("Prepared", package["id"], {key: len(data[key]) for key in ("roads", "buildings", "green", "trees", "shrubs")})
