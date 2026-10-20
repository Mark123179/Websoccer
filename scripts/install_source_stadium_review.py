"""Register a rendered source package without changing stadium economics/designs."""
import argparse
from copy import deepcopy
import hashlib
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
from stadium_editor.capacity import distribute_capacities
from stadium_editor.contracts import geometry_blocks
from stadium_editor.live_scene import build_live_scene, standard_design_for_geometry
from stadium_editor.model_registry import validate_model_manifest
from stadium_editor.package_preflight import inspect_package
from stadium_editor.scene_service import current_live_scene
from scripts.register_stadium_model import register


def install(study, fmi, tm_id):
    review = study / "osm-fresh"
    club = Club.objects.get(fm_inside_id=fmi, transfermarkt_id=tm_id)
    stadium = Stadium.objects.get(club=club)
    manifest = json.loads((review / "manifest.json").read_text())
    presentation_bytes = (review / "presentation.json").read_bytes()
    presentation = json.loads(presentation_bytes)["presentation"]
    validate_model_manifest(manifest)
    assert manifest["clubFmiId"] == presentation["clubFmiId"] == fmi
    renders = json.loads((review / "ansichten/render-evidence.json").read_text())
    assert {r["name"] for r in renders} == {
        "editor-dach-an", "editor-dach-aus", "draufsicht", "ticker-tag",
        "ticker-ohne-dach", "ticker-nacht-flutlicht", "sitzkamera"}
    assert all(r["assetVersion"] == manifest["assetVersion"] and not r["errors"]
               and not r["installed"]
               and r["presentationSha256"] == hashlib.sha256(presentation_bytes).hexdigest()
               for r in renders)
    before = {
        "stadium": Stadium.objects.filter(pk=stadium.pk).values().get(),
        "design": list(StadiumDesign.objects.filter(stadium=stadium).values()),
        "geometry": list(StadiumGeometry.objects.filter(stadium=stadium).values()),
    }
    source = json.loads((study / "editor-geometry.json").read_text())
    geometry = deepcopy(before["geometry"][0]["geometry"] if before["geometry"] else source)
    for field in ("bg", "surroundings"):
        geometry[field] = deepcopy(source[field])
    geometry.setdefault("meta", {}).update(presentation["frame"])
    check = inspect_package(geometry, axes=manifest["calibration"]["surroundingsAxes"])
    assert check["ok"] and check["terrainDeclared"] and not check["findings"], check
    effective = distribute_capacities(stadium, geometry)
    trusted = {b["id"]: b for b in geometry_blocks(effective)}
    for block in effective["blocks"]:
        block.update(trusted[block["id"]])
    design = (before["design"][0]["design"] if before["design"] else
              standard_design_for_geometry(stadium, effective))
    build_live_scene(stadium, geometry, design)
    backup = review / "before-integration.json"
    if not backup.exists():
        backup.write_text(json.dumps(before, default=str, ensure_ascii=False, indent=2))
    package = study / "install-package"
    target = package / "models" / f"{fmi}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    assets = package / "stadium-models" / str(fmi) / manifest["assetVersion"]
    assets.mkdir(parents=True, exist_ok=True)
    for name in ("geometry.bin", *manifest["textures"]):
        shutil.copyfile(study / "source-export" / name, assets / name)
    register(package, fmi)
    with transaction.atomic():
        locked = Stadium.objects.select_for_update().get(pk=stadium.pk)
        row = StadiumGeometry.objects.select_for_update().filter(stadium=locked).first()
        assert list(StadiumGeometry.objects.filter(stadium=locked).values()) == before["geometry"]
        assert Stadium.objects.filter(pk=locked.pk).values().get() == before["stadium"]
        assert list(StadiumDesign.objects.filter(stadium=locked).values()) == before["design"]
        if row:
            row.geometry = geometry
            row.save(update_fields=["geometry", "updated_at"])
        else:
            StadiumGeometry.objects.create(
                stadium=locked, geometry=geometry, schema_version=2,
                source="Unity-Quellmesh-Hüllen + frischer OSM-Auszug",
                attribution="© OpenStreetMap contributors (ODbL); Unity-Nutzerquelle")
        actual = current_live_scene(locked)["presentation"]
        assert actual["renderer"] == "unity-spatial"
        assert actual["assetVersion"] == manifest["assetVersion"]
        for layer in ("green", "water", "roads", "trees", "buildings", "buildingHeights",
                      "buildingIds", "groundLevel", "groundCutout"):
            assert actual["surroundings"][layer] == presentation["surroundings"][layer], layer
        for key, value in presentation["frame"].items():
            assert actual["frame"][key] == value
        assert Stadium.objects.filter(pk=locked.pk).values().get() == before["stadium"]
        assert list(StadiumDesign.objects.filter(stadium=locked).values()) == before["design"]
    (review / "installed-presentation.json").write_text(json.dumps({"presentation": actual}))
    result = {
        "registered": True, "integrated": True, "clubId": club.pk, "stadiumId": stadium.pk,
        "assetVersion": manifest["assetVersion"], "capacity": stadium.capacity_total,
        "stadiumAndDesignUnchanged": True, "terrain": check,
    }
    (review / "integration-check.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", type=Path, required=True)
    parser.add_argument("--fmi", type=int, required=True)
    parser.add_argument("--tm", type=int, required=True)
    args = parser.parse_args()
    install(args.study, args.fmi, args.tm)
