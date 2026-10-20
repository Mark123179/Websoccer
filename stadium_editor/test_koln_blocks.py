"""Cologne plan registration and loss-safe manager-design handover."""
from copy import deepcopy
import io
import json
import math
from pathlib import Path
import tempfile
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from game.models import Club, League, Stadium
from stadium_editor.capacity import distribute_capacities
from stadium_editor.contracts import geometry_blocks, spatial_project_design
from stadium_editor.image_validation import normalize_design_payload
from stadium_editor.koln_blocks import TOPOLOGY
from stadium_editor.live_scene import build_live_scene, standard_design_for_geometry
from stadium_editor.management.commands.align_koln_official_blocks import RESOURCE
from stadium_editor.models import StadiumDesign, StadiumGeometry


def resource():
    return json.loads(RESOURCE.read_text())


def legacy_geometry():
    data = resource()
    return {"version": 2, "physical_grid": "v2", "meta": data["referenceFrame"],
            "outline": [[-120, -120], [120, -120], [120, 120], [-120, 120]],
            "blocks": data["legacyBlocks"], "bg": {}, "roofs": [],
            "surroundings": {"sentinel": "retain"}}


def model_center(block):
    theta = resource()["referenceFrame"]["axisTheta"]
    wx = sum(p[0] for p in block["quad"])/4
    wy = sum(p[1] for p in block["quad"])/4
    return wx*math.sin(theta)-wy*math.cos(theta), wx*math.cos(theta)+wy*math.sin(theta)


class KolnPlanRegistrationTests(SimpleTestCase):
    def test_all_official_labels_and_every_source_point_are_accounted_for(self):
        data = resource()
        self.assertEqual(
            {b["officialBlock"] for b in data["blocks"]},
            {f"{prefix}{n}" for prefix, count in (("N", 6), ("S", 6), ("O", 8), ("W", 8))
             for n in [*range(1, count+1), *range(11, 11+count)]})
        self.assertEqual(len({b["id"] for b in data["blocks"]}), 56)
        self.assertTrue(all(b["id"] >= 1000 for b in data["blocks"]))
        self.assertEqual(sum(b["sourceSeatCount"] for b in data["blocks"]), 46424)
        for b in data["blocks"]:
            self.assertEqual(sum(b["sourceSections"].values()), b["sourceSeatCount"])
            self.assertGreater(b["sourceSeatCount"], 0)

    def test_south_terrace_and_northeast_away_corner(self):
        for b in resource()["blocks"]:
            x, z = model_center(b)
            if b["fanZone"] == "HEIM":
                self.assertLess(z, 0)
                self.assertEqual((b["stand"], b["tier"], b["type"]), ("SUED", "UNTER", "STEH"))
            if b["fanZone"] == "GAST":
                self.assertGreater(x, 0)
                self.assertGreater(z, 0)
            if b["type"] == "STEH":
                self.assertEqual(b["tier"], "UNTER")
        self.assertEqual({b["officialBlock"] for b in resource()["blocks"] if b["fanZone"] == "GAST"},
                         {"N6", "N15", "N16", "O11"})

    def test_numbering_follows_plan_not_unity_source_order(self):
        blocks = {b["officialBlock"]: b for b in resource()["blocks"]}
        self.assertLess(model_center(blocks["N1"])[0], model_center(blocks["N6"])[0])
        self.assertGreater(model_center(blocks["S1"])[0], model_center(blocks["S6"])[0])
        self.assertGreater(model_center(blocks["O1"])[1], model_center(blocks["O8"])[1])
        self.assertLess(model_center(blocks["W1"])[1], model_center(blocks["W8"])[1])

    def test_north_away_source_groups_are_exclusively_in_the_official_away_corner(self):
        for b in resource()["blocks"]:
            away = any("UltraAway" in section for section in b["sourceSections"])
            if b["officialBlock"] in ("N6", "N15", "N16"):
                self.assertTrue(away)
                self.assertTrue(all("UltraAway" in s for s in b["sourceSections"]))
            else:
                self.assertFalse(away)

    def test_overlapping_tiers_do_not_steal_each_others_colours(self):
        quad = [[0, 10], [10, 10], [10, 0], [0, 0]]
        old_blocks = [{"id": i, "stand": "NORD", "tier": tier,
                       "rows": 2, "seats": 2, "quad": quad}
                      for i, tier in enumerate(("OBER", "UNTER"))]
        old = {"blocks": old_blocks}
        new = {"blocks": [{**b, "id": b["id"]+10} for b in reversed(old_blocks)]}
        design = {"palette": ["#000000", "#ff0000", "#ffffff"],
                  "blocks": [{"id": 0, "rle": [[4, 1]]},
                             {"id": 1, "rle": [[1, 2], [1, 0], [1, 0], [1, 2]]}]}
        projected = spatial_project_design(design, old, new, "Köln", "SUED")
        self.assertEqual(projected["blocks"][0]["rle"], [[1, 2], [2, 0], [1, 2]])
        self.assertEqual(projected["blocks"][1]["rle"], [[4, 1]])
        self.assertEqual(projected["blickrichtung"], "SUED")

    def test_adjacent_split_retains_asymmetric_row_and_seat_positions(self):
        base = {"id": 0, "stand": "WEST", "tier": "UNTER", "rows": 2, "seats": 4,
                "quad": [[0, 2], [4, 2], [4, 0], [0, 0]]}
        new = {"blocks": [
            {**base, "id": 10, "seats": 2, "quad": [[0, 2], [2, 2], [2, 0], [0, 0]]},
            {**base, "id": 11, "seats": 2, "quad": [[2, 2], [4, 2], [4, 0], [2, 0]]}]}
        result = spatial_project_design(
            {"palette": ["#000000"]*8,
             "blocks": [{"id": 0, "rle": [[1, i] for i in range(8)]}]},
            {"blocks": [base]}, new, "Köln")
        self.assertEqual(result["blocks"][0]["rle"], [[1, i] for i in (0, 1, 4, 5)])
        self.assertEqual(result["blocks"][1]["rle"], [[1, i] for i in (2, 3, 6, 7)])


class KolnHandoverTests(TestCase):
    def setUp(self):
        league = League.objects.create(name="Köln-Test", country="DE")
        self.user = User.objects.create_user("koln-editor")
        club = Club.objects.create(name="1.FC Köln", fm_inside_id=916, transfermarkt_id=3,
                                   founded_year=1900, budget=0,
                                   league=league, managed_by=self.user.manager_profile)
        self.stadium = Stadium.objects.create(
            club=club, name="RheinEnergieSTADION", city="Köln",
            nord_standing=1635, nord_seating=11454, sued_standing=6540,
            sued_seating=4042, ost_seating=13479, west_seating=11050, west_vip=1800)
        self.row = StadiumGeometry.objects.create(stadium=self.stadium, geometry=legacy_geometry())
        self.out = io.StringIO()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

    def run_command(self, apply=False):
        call_command("align_koln_official_blocks", apply=apply,
                     backup_dir=self.temp.name, stdout=self.out)

    def test_dry_run_changes_nothing_and_apply_is_idempotent(self):
        before = Stadium.objects.filter(pk=self.stadium.pk).values().get()
        original = deepcopy(self.row.geometry)
        self.run_command()
        self.row.refresh_from_db()
        self.assertEqual(self.row.geometry, original)
        self.assertEqual(list(Path(self.temp.name).iterdir()), [])
        self.run_command(True)
        self.row.refresh_from_db()
        self.assertEqual(self.row.geometry["blockTopology"], TOPOLOGY)
        self.assertEqual(self.row.geometry["surroundings"], original["surroundings"])
        self.assertEqual(self.row.geometry["outline"], original["outline"])
        self.assertEqual(Stadium.objects.filter(pk=self.stadium.pk).values().get(), before)
        self.assertFalse(StadiumDesign.objects.filter(stadium=self.stadium).exists())
        effective = distribute_capacities(self.stadium, self.row.geometry)
        self.assertEqual(sum(b["capacity"] for b in effective["blocks"]), 50000)
        for stand in ("NORD", "SUED", "OST", "WEST"):
            for typ, suffix in (("STEH", "standing"), ("SITZ", "seating"), ("VIP", "vip")):
                self.assertEqual(sum(b["capacity"] for b in effective["blocks"]
                                     if b["stand"] == stand and b["type"] == typ),
                                 getattr(self.stadium, f"{stand.lower()}_{suffix}"))
        files = list(Path(self.temp.name).iterdir())
        self.assertEqual(len(files), 1)
        self.assertEqual(json.loads(files[0].read_text())["before"]["geometry"]["geometry"], original)
        self.run_command(True)
        self.assertEqual(list(Path(self.temp.name).iterdir()), files)

    def test_existing_manager_design_is_projected_with_palette_direction_and_backup(self):
        effective = distribute_capacities(self.stadium, self.row.geometry)
        saved = standard_design_for_geometry(self.stadium, effective)
        # Distinct lower/upper colours reveal accidental plan-view tier mixing.
        saved["palette"] = ["#111111", "#aa0000", "#ffffff"]
        meta = {b["id"]: b for b in geometry_blocks(effective)}
        for b in saved["blocks"]:
            b.update(meta[b["id"]])
            b["rle"] = [[b["rows"]*b["seats"], 1 if b["tier"] == "UNTER" else 2]]
        saved["blickrichtung"] = "WEST"
        design = StadiumDesign.objects.create(
            stadium=self.stadium, design=saved, blickrichtung="WEST")
        self.run_command(True)
        design.refresh_from_db()
        self.row.refresh_from_db()
        self.assertEqual(design.design["palette"], saved["palette"])
        self.assertEqual(design.blickrichtung, "WEST")
        for b in design.design["blocks"]:
            self.assertEqual(sum(n for n, _ in b["rle"]), b["rows"]*b["seats"])
            self.assertTrue({c for _, c in b["rle"]} <= {0, 1 if b["tier"] == "UNTER" else 2})
        backup = json.loads(next(Path(self.temp.name).iterdir()).read_text())
        self.assertEqual(backup["before"]["design"][0]["design"], saved)
        build_live_scene(self.stadium, self.row.geometry, design.design)
        self.assertEqual(normalize_design_payload(
            design.design, geometry=distribute_capacities(self.stadium, self.row.geometry),
            stadium_name=self.stadium.name), design.design)
        # A tab with old block IDs cannot overwrite the transferred design.
        self.client.force_login(self.user)
        response = self.client.post(reverse("stadium_editor_save_design"),
                                    json.dumps(saved), content_type="application/json")
        self.assertEqual(response.status_code, 400)
        design.refresh_from_db()
        self.assertNotEqual(design.design, saved)
        geometry_response = self.client.get(reverse("stadium_editor_geometry"))
        self.assertEqual(geometry_response.status_code, 200)
        self.assertEqual(len(geometry_response.json()["blocks"]), 56)
        self.assertContains(self.client.get(reverse("stadium_editor")), "officialBlockSelect")
        # The current draft roundtrips through the real save endpoint.
        response = self.client.post(reverse("stadium_editor_save_design"),
                                    json.dumps(design.design), content_type="application/json")
        self.assertEqual(response.status_code, 200)

    def test_expansion_or_other_custom_geometry_is_never_overwritten(self):
        self.row.geometry["blocks"][0]["rows"] += 1
        self.row.save()
        before = deepcopy(self.row.geometry)
        with self.assertRaisesMessage(CommandError, "Abweichende/ausgebaute"):
            self.run_command(True)
        self.row.refresh_from_db()
        self.assertEqual(self.row.geometry, before)
        self.assertEqual(list(Path(self.temp.name).iterdir()), [])

    def test_failed_write_rolls_back_geometry_and_keeps_original_backup(self):
        original = deepcopy(self.row.geometry)
        with patch.object(StadiumGeometry, "save", side_effect=ValueError("Test write error")):
            with self.assertRaisesMessage(CommandError, "Test write error"):
                self.run_command(True)
        self.row.refresh_from_db()
        self.assertEqual(self.row.geometry, original)
        self.assertEqual(len(list(Path(self.temp.name).iterdir())), 1)
