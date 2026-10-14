"""Apply only the approved Wolfsburg metadata/context correction, with backups."""
import json
import os
from copy import deepcopy
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

import django
django.setup()

from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from game.models import Club, Stadium, StadiumExpansion
from stadium_editor.models import StadiumDesign, StadiumGeometry
from stadium_editor.scene_service import current_live_scene

OUT = ROOT / "generated-artifacts/wolfsburg-korrektur"
REMOVED = [[-358.3, -223.3], [-375.7, -150.5]]


def snapshot(club, stadium, geometry):
    return {
        "club": Club.objects.filter(pk=club.pk).values().get(),
        "stadium": Stadium.objects.filter(pk=stadium.pk).values().get(),
        "geometry": StadiumGeometry.objects.filter(pk=geometry.pk).values().get(),
        "designs": list(StadiumDesign.objects.filter(stadium=stadium).order_by("pk").values()),
        "expansions": list(StadiumExpansion.objects.filter(stadium=stadium).order_by("pk").values()),
    }


def write(name, data):
    (OUT / name).write_text(json.dumps(data, cls=DjangoJSONEncoder, indent=2, ensure_ascii=False))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    # Never overwrite the original backup on a repeated invocation.
    if (OUT / "db-before.json").exists():
        raise ValueError("Backup besteht bereits; keine erneute Mutation.")
    with transaction.atomic():
        club = Club.objects.select_for_update().get(fm_inside_id=961)
        stadium = Stadium.objects.select_for_update().get(club=club)
        row = StadiumGeometry.objects.select_for_update().get(stadium=stadium)
        list(StadiumDesign.objects.select_for_update().filter(stadium=stadium))
        list(StadiumExpansion.objects.select_for_update().filter(stadium=stadium))
        assert club.name == "VfL Wolfsburg" and stadium.capacity_total == 30000
        before = snapshot(club, stadium, row)
        geometry = deepcopy(row.geometry)
        water = geometry["bg"]["water"]
        assert water[5] == REMOVED, "Unerwartete Quellfläche: Abbruch statt Raten."
        assert "mainStand" not in geometry and "farStand" not in geometry
        write("db-before.json", before)
        water.pop(5)
        geometry.setdefault("meta", {})["homeStand"] = "NORD"
        geometry.setdefault("scene_meta", {}).update(mainStand="WEST", farStand="OST")
        row.geometry = geometry
        row.save(update_fields=["geometry", "updated_at"])
        after = snapshot(club, stadium, row)
        expected = deepcopy(before)
        expected["geometry"]["geometry"] = geometry
        expected["geometry"]["updated_at"] = after["geometry"]["updated_at"]
        assert expected == after, "Nicht freigegebene Datenänderung."
        scene = current_live_scene(stadium)
        assert [scene[k] for k in ("homeStand", "mainStand", "farStand")] == ["NORD", "WEST", "OST"]
        write("db-after.json", after)
        write("preservation-check.json", {
            "status": "passed", "clubFmiId": 961, "capacity": stadium.capacity_total,
            "clubStadiumDesignsExpansionsUnchanged": True,
            "onlyGeometryChanges": ["meta.homeStand", "scene_meta.mainStand", "scene_meta.farStand", "bg.water[5]"],
            "removedInvalidPolygon": REMOVED, "waterBefore": len(water) + 1, "waterAfter": len(water),
            "reason": "Zwei Punkte bilden keine Wasserfläche. Keine erfundene Schließkante oder Fläche ergänzt.",
            "sceneOrientation": {k: scene[k] for k in ("homeStand", "mainStand", "farStand")},
            "registrationPerformed": False,
        })
    print("Wolfsburg korrigiert; Schutzvergleich bestanden, 30.000 Plätze unverändert.")


if __name__ == "__main__":
    main()
