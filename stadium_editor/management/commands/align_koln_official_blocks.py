"""Explicit, backed-up replacement of the legacy Cologne editor envelopes."""
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from game.models import Stadium
from stadium_editor.capacity import distribute_capacities
from stadium_editor.contracts import geometry_blocks, spatial_project_design
from stadium_editor.image_validation import normalize_design_payload
from stadium_editor.koln_blocks import TOPOLOGY, fingerprint
from stadium_editor.live_scene import build_live_scene, standard_design_for_geometry
from stadium_editor.models import StadiumDesign, StadiumGeometry

RESOURCE = Path(__file__).resolve().parents[2] / "blueprints/v2/koln_official_blocks.json"


def colour_counts(design):
    counts = Counter()
    for block in design.get("blocks", []):
        for count, colour in block["rle"]:
            counts[colour] += count
    return dict(counts)


class Command(BaseCommand):
    help = "Kölner FC-Planblöcke prüfen; Schreiben nur mit --apply und vollständigem Backup."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--if-present", action="store_true")
        parser.add_argument("--backup-dir", default="generated-artifacts/koln-blocks/backups")

    @transaction.atomic
    def handle(self, *args, **options):
        if options["if_present"] and not StadiumGeometry.objects.filter(
                stadium__club__fm_inside_id=916, stadium__club__transfermarkt_id=3).exists():
            self.stdout.write("Keine Köln-Geometrie vorhanden; nichts zu übernehmen.")
            return
        try:
            self.align(options)
        except (ValueError, OSError, KeyError, Stadium.DoesNotExist,
                StadiumGeometry.DoesNotExist) as exc:
            raise CommandError(str(exc)) from exc

    def align(self, options):
        resource = json.loads(RESOURCE.read_text())
        stadium = Stadium.objects.select_for_update().select_related("club").get(
            club__fm_inside_id=916, club__transfermarkt_id=3)
        row = StadiumGeometry.objects.select_for_update().get(stadium=stadium)
        design = StadiumDesign.objects.select_for_update().filter(stadium=stadium).first()
        old = row.geometry
        if old.get("blockTopology") == TOPOLOGY:
            self.stdout.write("Kölner Planblöcke bereits vorhanden; keine Änderung.")
            return
        # Expanded/custom topology is NEVER silently replaced by the base bowl.
        if fingerprint(old["blocks"]) != resource["evidence"]["legacyBlocksSha256"]:
            raise CommandError("Abweichende/ausgebaute Köln-Geometrie: keine Änderung. "
                               "Individuelle räumliche Übernahme erforderlich.")
        for key in ("axisTheta", "fieldC"):
            if old["meta"].get(key) != resource["referenceFrame"].get(key):
                raise CommandError("Abweichender Koordinatenrahmen: keine Änderung.")
        before = {
            "stadium": Stadium.objects.filter(pk=stadium.pk).values().get(),
            "geometry": StadiumGeometry.objects.filter(pk=row.pk).values().get(),
            "design": list(StadiumDesign.objects.filter(stadium=stadium).values()),
        }
        new = deepcopy(old)
        for key in ("blocks", "blockTopology", "physical_grid", "officialPlan",
                    "homeStand", "mainStand"):
            new[key] = deepcopy(resource[key])
        new["meta"].update(homeStand="SUED", mainStand="WEST")
        old_effective = distribute_capacities(stadium, old)
        effective = distribute_capacities(stadium, new)
        if design:
            old_design = normalize_design_payload(
                design.design, geometry=old_effective, stadium_name=stadium.name,
                blickrichtung=design.blickrichtung)
            projected = spatial_project_design(
                old_design, old_effective, effective, stadium.name, design.blickrichtung)
            projected = normalize_design_payload(
                projected, geometry=effective, stadium_name=stadium.name)
            if set(colour_counts(old_design)) - set(colour_counts(projected)) - {0}:
                raise CommandError("Eine Entwurfsfarbe wäre nicht mehr sichtbar: keine Änderung.")
        else:
            projected = standard_design_for_geometry(stadium, effective)
            old_design = {}
        # Validate complete canonical runtime contract before touching persistence.
        trusted = {b["id"]: b for b in geometry_blocks(effective)}
        for block in effective["blocks"]:
            block.update(trusted[block["id"]])
        build_live_scene(stadium, new, projected)
        report = {
            "apply": options["apply"], "oldBlocks": len(old["blocks"]),
            "newBlocks": len(new["blocks"]), "capacity": stadium.capacity_total,
            "oldColours": colour_counts(old_design), "newColours": colour_counts(projected),
            "stadiumUnchanged": True, "designProjected": bool(design),
            "sourceSeatPoints": resource["evidence"]["sourceSeatPoints"],
        }
        if options["apply"]:
            backup_dir = Path(options["backup_dir"])
            backup_dir.mkdir(parents=True, exist_ok=True)
            backup = backup_dir / f"koln-{timezone.now():%Y%m%dT%H%M%S%f}.json"
            # Exclusive file creation: an earlier recovery copy is never overwritten.
            with backup.open("x") as out:
                json.dump({"before": before, "report": report}, out,
                          default=str, ensure_ascii=False, indent=2)
            row.geometry = new
            row.schema_version = 2
            row.source = "FC-Plan 2026/27 + Unity-Sitzgruppen (schematische Sektoren)"
            row.save(update_fields=["geometry", "schema_version", "source", "updated_at"])
            if design:
                design.design = projected
                design.save(update_fields=["design", "updated_at"])
            if Stadium.objects.filter(pk=stadium.pk).values().get() != before["stadium"]:
                raise CommandError("Stadionwerte verändert; vollständiger Datenbank-Rollback.")
            report["backup"] = str(backup)
        self.stdout.write(json.dumps(report, ensure_ascii=False, default=str))
