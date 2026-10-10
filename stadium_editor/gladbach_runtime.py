"""Read-only source-model presentation; existing design and capacity are retained."""
import json
from pathlib import Path

from .dortmund_runtime import runtime_presentation

MODEL = Path(__file__).parent / "blueprints" / "v2" / "gladbach_model.json"


def gladbach_presentation(stadium, geometry, design):
    manifest = json.loads(MODEL.read_text())
    if manifest["clubFmiId"] != stadium.club.fm_inside_id:
        raise ValueError("Borussia-Park-Modell gehört nicht zu diesem Verein.")
    presentation = runtime_presentation(stadium, geometry, design)
    presentation.update({
        "renderer": "unity-spatial",
        "modelUrl": f"/stadion/model-assets/908/{manifest['assetVersion']}/manifest.json",
        "stadium": stadium.name,
        "clubId": stadium.club_id,
        "clubFmiId": stadium.club.fm_inside_id,
        "sourceSha256": manifest["sourceSha256"],
    })
    presentation["surroundings"]["source"] = "OpenStreetMap/BLUEPRINT-Bundle (ODbL)"
    presentation["surroundings"]["heightQuality"] = "schematic"
    return presentation
