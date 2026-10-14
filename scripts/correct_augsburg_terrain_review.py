"""Apply the approved, source-bound Augsburg terrain declaration; never register."""
import argparse
from copy import deepcopy
import hashlib
import json
import os
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
from stadium_editor.dortmund_runtime import runtime_presentation
from stadium_editor.model_registry import validate_model_manifest
from stadium_editor.pitch_validation import validate_pitch_geometry
from stadium_editor.surroundings_ground import validated_ground_fields
from scripts.correct_wolfsburg_review import snapshot

OUT = ROOT / "generated-artifacts/augsburg-v2-korrektur"
VERSION = "7718595a38dc4253"
GEOMETRY_HASH = "6c9c6d7a39f8035834661655bdcab71d8368f05e827e09993929a70280b6e06c"


def write(name, value):
    (OUT / name).write_text(
        json.dumps(value, cls=DjangoJSONEncoder, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main(package):
    manifest = json.loads((package / "models/2238.json").read_text())
    validate_model_manifest(manifest)
    if (manifest["clubFmiId"] != 2238 or manifest["assetVersion"] != VERSION
            or manifest["geometrySha256"] != GEOMETRY_HASH):
        raise ValueError("Nicht das geprüfte Augsburg-V2-Paket.")
    assets = package / f"stadium-models/2238/{VERSION}"
    for name, digest in manifest["assetSha256"].items():
        if hashlib.sha256((assets / name).read_bytes()).hexdigest() != digest:
            raise ValueError(f"Asset-Prüfsumme stimmt nicht: {name}")
    pitch = validate_pitch_geometry(manifest, (assets / "geometry.bin").read_bytes())
    source_bytes = (package / "quellbelege/gelaende_umlaufplatte.json").read_bytes()
    if hashlib.sha256(source_bytes).hexdigest() != (
            "32884cbbe24ab93ffd5dd66346479ac749aebc2f07367fdd558651b28e336057"):
        raise ValueError("Geländebeleg entspricht nicht der geprüften Umlaufplatten-Hülle.")
    source = json.loads(source_bytes)
    fields = validated_ground_fields({"groundLevel": 7.7, "groundCutout": source["polygon"]})
    preview = json.loads((package / "werkzeuge/render/presentation_ab_v2.json").read_text())["presentation"]
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
            raise ValueError("Geprüfte Schutzdaten weichen ab.")
        scene = current_live_scene(stadium)
        if {k: scene[k] for k in ("homeStand", "mainStand", "farStand")} != {
                "homeStand": "NORD", "mainStand": "WEST", "farStand": "OST"}:
            raise ValueError("Orientierung entspricht nicht dem korrigierten Stand.")
        geometry = deepcopy(row.geometry)
        if any(k in (geometry.get("surroundings") or {}) for k in fields):
            raise ValueError("Unerwartete bestehende Geländedeklaration.")
        local = runtime_presentation(stadium, geometry, {})["surroundings"]
        for key in ("green", "water", "buildings", "roads"):
            if local[key] != preview["surroundings"][key]:
                raise ValueError(f"Lokaler Quellbestand weicht ab: {key}")
        before = snapshot(club, stadium, row)
        write("db-before.json", before)
        geometry.setdefault("surroundings", {}).update(fields)
        row.geometry = geometry
        row.save(update_fields=["geometry", "updated_at"])
        after = snapshot(club, stadium, row)
        expected = deepcopy(before)
        expected["geometry"]["geometry"] = geometry
        expected["geometry"]["updated_at"] = after["geometry"]["updated_at"]
        if expected != after:
            raise ValueError("Nicht freigegebene Datenänderung; Transaktion abgebrochen.")
    club.refresh_from_db()
    stadium.refresh_from_db()
    row.refresh_from_db()
    persisted = snapshot(club, stadium, row)
    if persisted != after:
        raise ValueError("Persistierter Nachherstand weicht ab.")
    design_row = StadiumDesign.objects.filter(stadium=stadium).first()
    presentation = runtime_presentation(
        stadium, row.geometry, design_row.design if design_row else {},
    )
    for key in ("groundLevel", "groundCutout"):
        if presentation["surroundings"][key] != fields[key]:
            raise ValueError("Geländedaten fehlen in der Laufzeitprojektion.")
    presentation.pop("capacity", None)
    presentation.update(
        renderer="unity-spatial", clubFmiId=2238, stadium=manifest["stadiumName"],
        modelUrl=f"/models/2238/{VERSION}/manifest.json",
        calibration=deepcopy(manifest["calibration"]),
        sourceSha256=manifest["sourceSha256"],
    )
    presentation["surroundings"].update(
        source="OpenStreetMap/BLUEPRINT-Bundle (ODbL)", heightQuality="schematic",
    )
    write("db-after.json", persisted)
    write("presentation_replit_korrigiert.json", {"presentation": presentation})
    write("preservation-check.json", {
        "status": "passed", "clubFmiId": 2238, "capacity": 30660,
        "standingAllocation": {"NORD": 5366, "SUED": 1150, "OST": 0, "WEST": 0},
        "onlyGeometryChanges": ["surroundings.groundLevel", "surroundings.groundCutout"],
        "clubStadiumBlocksDesignsExpansionsUnchanged": True,
        "allSourceSurroundingsPolygonsUnchanged": True,
        "terrain": fields, "pitch": pitch,
        "registrationPerformed": False, "assetsUploaded": False,
    })
    print("Augsburg-Gelände deklariert; alle Schutzdaten und Quellpolygone unverändert.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    main(parser.parse_args().package)
