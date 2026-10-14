"""Apply only the approved Augsburg orientation correction, never register assets."""
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

OUT = ROOT / "generated-artifacts/augsburg-korrektur"
TARGET = dict(homeStand="NORD", mainStand="WEST", farStand="OST")


def write(name, data):
    (OUT / name).write_text(
        json.dumps(data, cls=DjangoJSONEncoder, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def orientation(stadium):
    scene = current_live_scene(stadium)
    return {key: scene[key] for key in TARGET}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    if (OUT / "db-before.json").exists():
        raise ValueError("Originalbackup besteht bereits; keine erneute Mutation.")
    with transaction.atomic():
        club = Club.objects.select_for_update().get(fm_inside_id=2238)
        stadium = Stadium.objects.select_for_update().get(club=club)
        row = StadiumGeometry.objects.select_for_update().get(stadium=stadium)
        list(StadiumDesign.objects.select_for_update().filter(stadium=stadium))
        list(StadiumExpansion.objects.select_for_update().filter(stadium=stadium))
        if (club.name != "FC Augsburg" or stadium.capacity_total != 30660
                or [stadium.nord_standing, stadium.sued_standing,
                    stadium.ost_standing, stadium.west_standing] != [5366, 1150, 0, 0]):
            raise ValueError("Identität, Kapazität oder Stehplatzbestand weichen ab.")
        if orientation(stadium) != dict(homeStand="SUED", mainStand="SUED", farStand="NORD"):
            raise ValueError("Orientierung entspricht nicht dem geprüften Ausgangszustand.")
        before = snapshot(club, stadium, row)
        geometry = deepcopy(row.geometry)
        if any(key in geometry for key in ("mainStand", "farStand")):
            raise ValueError("Unerwartete vorrangige Orientierungsmetadaten.")
        write("db-before.json", before)
        geometry.setdefault("meta", {})["homeStand"] = TARGET["homeStand"]
        geometry.setdefault("scene_meta", {}).update(
            mainStand=TARGET["mainStand"], farStand=TARGET["farStand"],
        )
        row.geometry = geometry
        row.save(update_fields=["geometry", "updated_at"])
        after = snapshot(club, stadium, row)
        expected = deepcopy(before)
        expected["geometry"]["geometry"] = geometry
        expected["geometry"]["updated_at"] = after["geometry"]["updated_at"]
        if expected != after or orientation(stadium) != TARGET:
            raise ValueError("Schutzvergleich fehlgeschlagen; Transaktion abgebrochen.")
    # Read again after the commit: verify what subsequent requests actually see.
    club.refresh_from_db()
    stadium.refresh_from_db()
    row.refresh_from_db()
    persisted = snapshot(club, stadium, row)
    if persisted != after or orientation(stadium) != TARGET:
        raise ValueError("Nachprüfung des persistierten Zustands fehlgeschlagen.")
    write("db-after.json", persisted)
    write("preservation-check.json", {
        "status": "passed", "clubFmiId": 2238,
        "capacity": stadium.capacity_total, "sceneOrientation": TARGET,
        "standingAllocation": {"NORD": 5366, "SUED": 1150, "OST": 0, "WEST": 0},
        "clubStadiumDesignsExpansionsUnchanged": True,
        "blocksAndStandingAllocationUnchanged": True, "surroundingsUnchanged": True,
        "onlyGeometryChanges": [
            "meta.homeStand", "scene_meta.mainStand", "scene_meta.farStand",
        ],
        "registrationPerformed": False, "assetsChanged": False,
    })
    print("Augsburg korrigiert: NORD/WEST/OST; 30.660 Plätze und Schutzdaten unverändert.")


if __name__ == "__main__":
    main()
