"""Install the reviewed Mainz source assets and surroundings, retaining game state."""
from copy import deepcopy
import json
import os
from pathlib import Path
import shutil

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
import django
django.setup()

from django.db import transaction
from game.models import Club, Stadium
from stadium_editor.models import StadiumDesign, StadiumGeometry
from stadium_editor.model_registry import validate_model_manifest
from stadium_editor.package_preflight import inspect_package
from stadium_editor.scene_service import current_live_scene
from stadium_editor.seed import _key, load_blueprints, normalise_block_types
from scripts.register_stadium_model import register

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "generated-artifacts/mainz-study"
REVIEW = STUDY / "osm-fresh"


def install():
    club = Club.objects.get(fm_inside_id=918, transfermarkt_id=39)
    assert "mainz" in club.name.casefold()
    stadium = Stadium.objects.get(club=club)
    manifest = json.loads((REVIEW / "manifest.json").read_text())
    presentation = json.loads((REVIEW / "presentation.json").read_text())["presentation"]
    validate_model_manifest(manifest)
    assert manifest["clubFmiId"] == presentation["clubFmiId"] == 918
    original = StadiumGeometry.objects.filter(stadium=stadium).first()
    geometry = deepcopy(original.geometry if original else normalise_block_types(
        stadium, load_blueprints()[_key(club.name)]))
    before = {
        "stadium": Stadium.objects.filter(pk=stadium.pk).values().get(),
        "design": list(StadiumDesign.objects.filter(stadium=stadium).values()),
        "geometry": list(StadiumGeometry.objects.filter(stadium=stadium).values()),
    }
    # Legacy bg layers take precedence over surroundings in the shared renderer.
    # Retain block topology and all other geometry/design metadata.
    geometry["bg"] = deepcopy(presentation["surroundings"])
    geometry["bg"]["buildings"] = [
        {"poly": poly, "h": height, "id": identity}
        for poly, height, identity in zip(
            geometry["bg"]["buildings"], geometry["bg"]["buildingHeights"],
            geometry["bg"]["buildingIds"], strict=True)
    ]
    geometry["surroundings"] = deepcopy(presentation["surroundings"])
    geometry.setdefault("meta", {}).update(presentation["frame"])
    check = inspect_package(geometry, axes=manifest["calibration"]["surroundingsAxes"])
    assert check["ok"] and check["terrainDeclared"] and not check["findings"], check
    backup = REVIEW / "before-integration.json"
    if not backup.exists():
        backup.write_text(json.dumps(before, default=str, ensure_ascii=False, indent=2))
    package = STUDY / "install-package"
    target = package / "models" / "918.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    assets = package / "stadium-models" / "918" / manifest["assetVersion"]
    assets.mkdir(parents=True, exist_ok=True)
    for name in ("geometry.bin", *manifest["textures"]):
        shutil.copyfile(STUDY / "source-export" / name, assets / name)
    register(package, 918)
    with transaction.atomic():
        locked = Stadium.objects.select_for_update().get(pk=stadium.pk)
        row = StadiumGeometry.objects.select_for_update().filter(stadium=locked).first()
        assert list(StadiumGeometry.objects.filter(stadium=locked).values()) == before["geometry"]
        if row:
            row.geometry = geometry
            row.save(update_fields=["geometry", "updated_at"])
        else:
            StadiumGeometry.objects.create(
                stadium=locked, geometry=geometry, schema_version=2,
                source="Mainz Unity + frischer OSM-Auszug",
                attribution="© OpenStreetMap contributors (ODbL); Unity-Nutzerquelle")
        scene = current_live_scene(locked)
        actual = scene["presentation"]
        assert actual["renderer"] == "unity-spatial"
        assert actual["assetVersion"] == manifest["assetVersion"]
        for field in ("frame",):
            for key, value in presentation[field].items():
                assert actual[field][key] == value
        for layer in ("green", "water", "roads", "trees", "buildings",
                      "buildingHeights", "buildingIds", "groundCutout", "groundLevel"):
            assert actual["surroundings"][layer] == presentation["surroundings"][layer], layer
        assert Stadium.objects.filter(pk=locked.pk).values().get() == before["stadium"]
        assert list(StadiumDesign.objects.filter(stadium=locked).values()) == before["design"]
    result = {
        "registered": True, "integrated": True, "clubId": club.pk,
        "stadiumId": stadium.pk, "assetVersion": manifest["assetVersion"],
        "capacity": stadium.capacity_total, "stadiumAndDesignUnchanged": True,
        "terrain": check,
    }
    (REVIEW / "integration-check.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result))


if __name__ == "__main__":
    install()
