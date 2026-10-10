"""Parity and read-only guarantees for Elversberg's integrated surroundings."""
from copy import deepcopy
import json
import math
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from game.models import Club, League, Stadium
from game.stadium_scene_context import ticker_scene_context
from stadium_editor.blueprints.v2.imports import scene_to_geometry
from stadium_editor.elversberg_environment import (
    ROOT, SCHEMATIC_HEIGHT, club_surroundings, load_surroundings,
    with_editor_surroundings,
)
from stadium_editor.models import StadiumDesign, StadiumGeometry
from stadium_editor.scene_service import current_live_scene


class ElversbergSourceTests(SimpleTestCase):
    def test_priority_buildings_have_exact_identities_and_honest_heights(self):
        surroundings = load_surroundings()
        buildings = {b["osmId"]: b for b in surroundings["buildings"]}
        self.assertEqual(buildings[30887518]["name"], "Wasgau")
        self.assertEqual(buildings[30887518]["h"], 9.379)
        self.assertEqual(buildings[53864244]["h"], 14.204)
        self.assertEqual(buildings[53864241]["name"], "Lidl")
        self.assertEqual(buildings[53864241]["h"], SCHEMATIC_HEIGHT)
        self.assertEqual(buildings[53864241]["heightStatus"], "schematic-not-measured")
        self.assertEqual(buildings[30887518]["heightStatus"], "conditional-lvgl-envelope")
        self.assertEqual(len({b["id"] for b in buildings.values()}), len(buildings))

    def test_source_is_reproducible_and_cached_copy_cannot_be_poisoned(self):
        source = load_surroundings()
        before = deepcopy(source)
        source["buildings"][0]["poly"][0][0] = 999999
        self.assertEqual(load_surroundings(), before)
        for key in ("buildings", "roads", "green", "vegetation"):
            self.assertTrue(before[key])

    def test_non_elversberg_club_is_strict_noop(self):
        club = SimpleNamespace(fm_inside_id=907)
        geometry = {"untouched": True}
        self.assertIsNone(club_surroundings(club))
        self.assertIs(with_editor_surroundings(geometry, club), geometry)

    def test_optional_source_failure_is_explicit_without_invented_city(self):
        with patch("stadium_editor.elversberg_environment.load_surroundings",
                   side_effect=ValueError("source mismatch")):
            source = club_surroundings(SimpleNamespace(fm_inside_id=121200))
        self.assertTrue(source["unavailable"])
        self.assertIn("Stadion bleibt sichtbar", source["warning"])
        self.assertEqual(source["buildings"], [])

    def test_editor_raw_frame_roundtrips_without_mutating_input(self):
        geometry = {"meta": {"axisTheta": .72, "fieldC": [35, -21]}, "bg": {"old": True}}
        before = deepcopy(geometry)
        prepared = with_editor_surroundings(
            geometry, SimpleNamespace(fm_inside_id=121200),
        )
        self.assertEqual(geometry, before)
        self.assertNotIn("bg", prepared)
        self.assertEqual(prepared["surroundings"]["frame"], "editor")
        raw = prepared["surroundings"]["buildings"][0]["poly"]
        pitch = load_surroundings()["buildings"][0]["poly"]
        ct, st = math.cos(.72), math.sin(.72)
        for point, target in zip(raw, pitch):
            x, y = point[0] - 35, point[1] + 21
            self.assertAlmostEqual(x * ct + y * st, target[0], places=8)
            self.assertAlmostEqual(-x * st + y * ct, target[1], places=8)


class ElversbergRuntimeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        league = League.objects.create(name="Elversberg-Parität", country="DE")
        cls.user = User.objects.create_user("elversberg-scene-check")
        cls.club = Club.objects.create(
            name="SV 07 Elversberg", short_name="SVE", fm_inside_id=121200,
            founded_year=1907, budget=0, league=league,
            managed_by=cls.user.manager_profile,
        )
        cls.stadium = Stadium.objects.create(
            club=cls.club, name="URSAPHARM-Arena", city="Elversberg",
            nord_seating=2500, sued_seating=5000, ost_standing=1500, west_seating=1000,
        )
        scene = json.loads((ROOT / "elversberg_v2.json").read_text())
        cls.geometry = StadiumGeometry.objects.create(
            stadium=cls.stadium, geometry=scene_to_geometry(scene),
        )

    def test_public_scene_and_editor_share_same_current_environment_without_writes(self):
        before = deepcopy(self.geometry.geometry)
        self.client.force_login(self.user)
        editor = self.client.get(reverse("stadium_editor_geometry")).json()
        response = self.client.get(reverse("stadium_live_scene", args=[self.club.pk]))
        self.assertEqual(response.status_code, 200)
        live = response.json()
        self.assertEqual(live["surroundings"]["buildings"], editor["surroundings"]["buildings"])
        self.assertEqual(live["surroundings"]["vegetation"], editor["surroundings"]["vegetation"])
        self.assertEqual(response["Cache-Control"], "no-store")
        self.geometry.refresh_from_db()
        self.assertEqual(self.geometry.geometry, before)
        self.assertFalse(StadiumDesign.objects.filter(stadium=self.stadium).exists())

    def test_saved_design_is_visible_on_next_scene_read(self):
        initial = current_live_scene(self.stadium)
        design = {
            "version": 2, "stadium": self.stadium.name, "blickrichtung": "NORD",
            "palette": ["#22e6ff", "#ffffff"],
            "blocks": [{
                **{key: block[key] for key in ("id", "stand", "tier", "order", "rows", "seats")},
                "rle": [[block["rows"] * block["seats"], 0]],
            } for block in initial["blocks"]],
        }
        row = StadiumDesign.objects.create(stadium=self.stadium, design=design)
        first = current_live_scene(self.stadium)
        row.design["palette"][0] = "#1d9e50"
        row.save(update_fields=["design"])
        second = current_live_scene(self.stadium)
        self.assertEqual(second["palette"][0], "#1d9e50")
        self.assertNotEqual(first["palette"], second["palette"])
        self.assertEqual(first["surroundings"], second["surroundings"])
        self.assertEqual(first["outline"], second["outline"])

    def test_ticker_configuration_is_club_specific_and_points_to_current_scene(self):
        context = ticker_scene_context(self.club)
        self.assertEqual(context["renderer"], "canonical")
        self.assertEqual(context["sceneUrl"], reverse("stadium_live_scene", args=[self.club.pk]))
        self.assertEqual(context["clubId"], self.club.pk)
        self.assertIsNone(ticker_scene_context(SimpleNamespace(fm_inside_id=907)))

    def test_admin_study_is_current_scene_not_static_stadium_copy(self):
        self.user.is_superuser = True
        self.user.save(update_fields=["is_superuser"])
        self.client.force_login(self.user)
        response = self.client.get(reverse("stadium_study"))
        self.assertEqual(response.status_code, 200)
        scene = response.context["study_config"]["elversberg"]
        self.assertEqual(scene["club"]["id"], self.club.pk)
        self.assertEqual(scene["surroundings"], current_live_scene(self.stadium)["surroundings"])
        self.assertContains(response, "Elversberg im Admin-Liveticker")

    def test_missing_geometry_does_not_offer_unrelated_stadium(self):
        self.geometry.delete()
        self.assertIsNone(ticker_scene_context(self.club))
