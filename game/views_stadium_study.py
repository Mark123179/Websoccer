"""Isolated read-only comparison; no sandbox-match generation or game writes."""
import json
from pathlib import Path

from django.shortcuts import render
from django.templatetags.static import static

from .views_story_test import admin_only
from stadium_editor.image_backgrounds import load_image_background
from stadium_editor.scene_service import current_live_scene
from stadium_editor.elversberg_environment import ELVERSBERG_FMI_ID
from .models import Stadium


ROOT = Path(__file__).resolve().parents[1]


@admin_only
def stadium_study(request):
    stadium = Stadium.objects.select_related("club").get(
        club__fm_inside_id=ELVERSBERG_FMI_ID,
    )
    scene = current_live_scene(stadium)
    # No synthetic lamps/masts or fictitious geographical surroundings.
    scene["steckbrief"] = {key: value for key, value in scene.get("steckbrief", {}).items()
                           if key not in ("floodlights", "pylons")}
    config = {
        "elversberg": scene,
        "images": load_image_background(907)["images"],
        "lightsUrl": static("stadium_editor/study_assets/dortmund_lights.json"),
        "sourceEvidence": {
            "dortmund": "Unity-Geometrie und gesondert geprüfte Unity-Lichtkomponenten.",
            "elversberg": "Aktueller Editorbestand; OSM-Grundrisse, bedingte LVGL-Höhen und gekennzeichnete schematische Umgebung. Keine belegten Leuchtenkomponenten.",
        },
    }
    response = render(request, "game/stadium_study.html", {"study_config": config})
    response["Cache-Control"] = "private, no-store"
    return response
