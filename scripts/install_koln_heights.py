"""Install only the verified Cologne environment, preserving all game state."""
from copy import deepcopy
import hashlib
import json
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
import django
django.setup()

from django.db import transaction
from game.models import Stadium
from stadium_editor.models import StadiumGeometry, StadiumDesign
from stadium_editor.model_registry import model_manifest
from stadium_editor.scene_service import current_live_scene
from stadium_editor.package_preflight import inspect_package
from scripts.refine_koln_heights import REVIEW, HEIGHTS, STUDY, write


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def install():
    raw = (REVIEW / "presentation.json").read_bytes()
    presentation = json.loads(raw)["presentation"]
    manifest = json.loads((REVIEW / "manifest.json").read_text())
    assert model_manifest(916) == manifest, "Model assets/registration must remain unchanged"
    assert presentation["surroundings"]["groundElevation"]["source"]
    rendered = json.loads((REVIEW / "ansichten/render-evidence.json").read_text())
    assert {"editor-dach-an","editor-dach-aus","draufsicht","ticker-tag",
            "ticker-nacht-flutlicht"} <= {r["name"] for r in rendered}
    assert all(not r["errors"] and r["presentationSha256"] == hashlib.sha256(raw).hexdigest()
               for r in rendered), "Render evidence must belong to these exact environment data"
    with transaction.atomic():
        stadium = Stadium.objects.select_for_update().get(club__fm_inside_id=916, club__transfermarkt_id=3)
        row = StadiumGeometry.objects.select_for_update().get(stadium=stadium)
        designs = list(StadiumDesign.objects.select_for_update().filter(stadium=stadium).values())
        before = {"stadium": Stadium.objects.filter(pk=stadium.pk).values().get(),
                  "designs": designs, "geometry": deepcopy(row.geometry)}
        write(HEIGHTS / "before-height-integration.json", json.loads(json.dumps(before, default=str)))
        data = presentation["surroundings"]
        geometry = deepcopy(row.geometry)
        geometry["surroundings"] = deepcopy(data)
        geometry["bg"] = deepcopy(data)
        geometry["bg"]["buildings"] = [
            {"poly":p,"h":h,"id":identity}
            for p,h,identity in zip(data["buildings"],data["buildingHeights"],data["buildingIds"],strict=True)]
        # No block, expansion, frame or stored design replacement.
        assert {k:v for k,v in geometry.items() if k not in ("bg","surroundings")} == {
            k:v for k,v in before["geometry"].items() if k not in ("bg","surroundings")}
        check = inspect_package(geometry, axes=manifest["calibration"]["surroundingsAxes"])
        assert check["ok"] and check["terrainDeclared"] and not check["findings"], check
        row.geometry = geometry
        row.save(update_fields=["geometry","updated_at"])
        actual = current_live_scene(stadium)["presentation"]
        assert actual["renderer"] == "unity-spatial"
        for layer in ("roads","green","water","trees","buildings","buildingIds","buildingHeights",
                      "groundLevel","groundCutout","groundElevation","heightQuality","heightEvidence","buildingParts"):
            assert actual["surroundings"][layer] == data[layer], layer
        assert Stadium.objects.filter(pk=stadium.pk).values().get() == before["stadium"]
        assert list(StadiumDesign.objects.filter(stadium=stadium).values()) == designs
        assert actual["assetVersion"] == manifest["assetVersion"]
    write(REVIEW / "installed-presentation.json", {"presentation":actual})
    result = {"environmentOnly":True, "capacity":stadium.capacity_total,
              "stadiumAndDesignUnchanged":True, "geometryOutsideEnvironmentUnchanged":True,
              "stadiumBeforeAfterSha256":digest(before["stadium"]),
              "designsBeforeAfterSha256":digest(designs),
              "blocksBeforeAfterSha256":digest(geometry["blocks"]),
              "modelManifestSha256":digest(manifest), "terrain":check}
    write(HEIGHTS / "integration-check.json",result)
    print(json.dumps(result))


if __name__ == "__main__":
    install()
