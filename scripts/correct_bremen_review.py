"""Apply the approved Bremen context/metadata fix; never alter seats or register."""
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
from scripts.correct_wolfsburg_review import snapshot

OUT = ROOT / "generated-artifacts/bremen-korrektur"
REMOVED = [[-159.1, -491.1], [-137.3, -447.5]]


def write(name, data):
    (OUT / name).write_text(json.dumps(data, cls=DjangoJSONEncoder, indent=2, ensure_ascii=False))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    if (OUT / "db-before.json").exists():
        raise ValueError("Backup besteht bereits; keine erneute Mutation.")
    with transaction.atomic():
        club = Club.objects.select_for_update().get(fm_inside_id=948)
        stadium = Stadium.objects.select_for_update().get(club=club)
        row = StadiumGeometry.objects.select_for_update().get(stadium=stadium)
        list(StadiumDesign.objects.select_for_update().filter(stadium=stadium))
        list(StadiumExpansion.objects.select_for_update().filter(stadium=stadium))
        if club.name != "SV Werder Bremen" or stadium.capacity_total != 42100:
            raise ValueError("Unerwartete Identität oder Kapazität.")
        before = snapshot(club, stadium, row)
        geometry = deepcopy(row.geometry)
        if geometry["bg"]["water"][2] != REMOVED:
            raise ValueError("Unerwartete Quellfläche; keine automatische Bereinigung.")
        if "mainStand" in geometry or "farStand" in geometry:
            raise ValueError("Unerwartete vorrangige Orientierungsmetadaten.")
        if current_live_scene(stadium)["homeStand"] != "SUED":
            raise ValueError("Heimkurve weicht vom freigegebenen Stand ab.")
        write("db-before.json", before)
        geometry["bg"]["water"].pop(2)
        geometry.setdefault("scene_meta", {}).update(mainStand="WEST", farStand="OST")
        row.geometry = geometry
        row.save(update_fields=["geometry", "updated_at"])
        after = snapshot(club, stadium, row)
        expected = deepcopy(before)
        expected["geometry"]["geometry"] = geometry
        expected["geometry"]["updated_at"] = after["geometry"]["updated_at"]
        if expected != after:
            raise ValueError("Nicht freigegebene Datenänderung; Transaktion abgebrochen.")
        scene = current_live_scene(stadium)
        orientation = {k: scene[k] for k in ("homeStand", "mainStand", "farStand")}
        if orientation != dict(homeStand="SUED", mainStand="WEST", farStand="OST"):
            raise ValueError("Laufzeitorientierung stimmt nicht.")
        write("db-after.json", after)
        write("preservation-check.json", {
            "status": "passed", "clubFmiId": 948, "capacity": stadium.capacity_total,
            "clubStadiumDesignsExpansionsUnchanged": True,
            "blocksAndStandingAllocationUnchanged": True, "homeStandMetadataUnchanged": True,
            "onlyGeometryChanges": ["scene_meta.mainStand", "scene_meta.farStand", "bg.water[2]"],
            "removedInvalidPolygon": REMOVED, "sceneOrientation": orientation,
            "registrationPerformed": False,
        })
    print("Bremen korrigiert; 42.100 Plätze und gesamte Stehplatzverteilung unverändert.")


if __name__ == "__main__":
    main()
