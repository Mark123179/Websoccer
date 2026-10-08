"""Isolated read-only comparison; no sandbox-match generation or game writes."""
import json
from pathlib import Path

from django.shortcuts import render
from django.templatetags.static import static

from .views_story_test import admin_only
from stadium_editor.image_backgrounds import load_image_background


ROOT = Path(__file__).resolve().parents[1]


@admin_only
def stadium_study(request):
    source = ROOT / "stadium_editor/blueprints/v2/elversberg_v2.json"
    scene = json.loads(source.read_text())
    # No synthetic lamps/masts or fictitious geographical surroundings.
    scene["steckbrief"] = {key: value for key, value in scene.get("steckbrief", {}).items()
                           if key not in ("floodlights", "pylons")}
    scene["surroundings"] = {}
    config = {
        "elversberg": scene,
        "images": load_image_background(907)["images"],
        "lightsUrl": static("stadium_editor/study_assets/dortmund_lights.json"),
        "sourceEvidence": {
            "dortmund": "Unity-Geometrie und gesondert geprüfte Unity-Lichtkomponenten.",
            "elversberg": "Eigene vermessene Blaupause; keine belegten Leuchtenkomponenten und kein Umfeldfoto.",
        },
    }
    response = render(request, "game/stadium_study.html", {"study_config": config})
    response["Cache-Control"] = "private, no-store"
    return response
