import json
from copy import deepcopy

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from game.models import Club, League, Stadium, StadiumExpansion
from stadium_editor.models import StadiumDesign, StadiumGeometry
from stadium_editor.scene_service import current_live_scene
from stadium_editor.tests import _block, _geometry


class ManagerSeatModeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("seat-mode-manager", password="test-only-password")
        league = League.objects.create(name="Seat mode test", country="DE")
        self.club = Club.objects.create(
            name="Mode Test Club", short_name="MTC", founded_year=1900,
            league=league, budget=12345, managed_by=self.user.manager_profile,
        )
        self.stadium = Stadium.objects.create(
            club=self.club, name="Mode Arena", city="Test", nord_seating=100,
        )
        geometry = _geometry([_block(5, rows=2, seats=3)])
        geometry["meta"].update(axisTheta=0, fieldC=[0, 0])
        self.geometry = StadiumGeometry.objects.create(stadium=self.stadium, geometry=geometry)
        self.client.force_login(self.user)
        self.draft = {
            "version": 1, "palette": ["#666666", "#ffff00"],
            "blocks": [{"id": 5, "rle": [[3, 0], [3, 1]]}],
        }

    def save_mode(self, mode):
        payload = {**deepcopy(self.draft), "seat_mode": mode}
        response = self.client.post(
            reverse("stadium_editor_save_design"),
            json.dumps(payload), content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        return StadiumDesign.objects.get(stadium=self.stadium).design

    def test_non_admin_sees_mode_selector_but_not_expansion_simulator(self):
        response = self.client.get(reverse("stadium_editor"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="seatDesignMode"')
        self.assertContains(response, "Stadionoriginal")
        self.assertContains(response, "Eigener Entwurf")
        self.assertNotContains(response, 'id="btnExpand"')
        self.assertNotContains(response, 'id="expStand"')
        self.assertContains(response, "isAdmin: false")

    def test_admin_retains_expansion_simulator_and_mode_selector(self):
        self.user.is_staff = True
        self.user.save(update_fields=["is_staff"])
        response = self.client.get(reverse("stadium_editor"))
        self.assertContains(response, 'id="seatDesignMode"')
        self.assertContains(response, 'id="btnExpand"')
        self.assertContains(response, "isAdmin: true")
        self.assertContains(response, '<option value="NORD">Nord</option>')
        self.assertNotContains(response, '<option value="OST">Nord</option>')

    def test_mode_survives_reload_without_losing_custom_paint(self):
        custom = self.save_mode("custom")
        original = self.save_mode("original")
        self.assertEqual(custom["blocks"], original["blocks"])
        self.assertEqual(original["seat_mode"], "original")
        response = self.client.get(reverse("stadium_editor_design"))
        self.assertEqual(response.json()["seat_mode"], "original")
        self.assertEqual(response.json()["blocks"], custom["blocks"])
        restored = self.save_mode("custom")
        self.assertEqual(restored["blocks"], custom["blocks"])

    def test_original_scene_uses_canonical_default_but_retains_saved_draft(self):
        saved = self.save_mode("original")
        scene = current_live_scene(self.stadium)
        self.assertEqual(scene["seatMode"], "original")
        self.assertEqual(
            StadiumDesign.objects.get(stadium=self.stadium).design, saved,
        )
        self.assertNotEqual(scene["originalDesign"]["palette"], saved["palette"])
        self.assertEqual(current_live_scene(self.stadium), scene)

    def test_legacy_draft_remains_custom_and_missing_draft_starts_original(self):
        self.assertEqual(current_live_scene(self.stadium)["seatMode"], "original")
        self.save_mode("custom")
        row = StadiumDesign.objects.get(stadium=self.stadium)
        row.design.pop("seat_mode")
        row.save(update_fields=["design"])
        self.assertEqual(current_live_scene(self.stadium)["seatMode"], "custom")

    def test_non_admin_cannot_submit_simulated_expansion_blocks(self):
        before_geometry = deepcopy(self.geometry.geometry)
        before_stadium = Stadium.objects.values().get(pk=self.stadium.pk)
        payload = deepcopy(self.draft)
        payload["blocks"].append({"id": 999999, "rle": [[60000, 1]]})
        response = self.client.post(
            reverse("stadium_editor_save_design"),
            json.dumps(payload), content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(StadiumDesign.objects.filter(stadium=self.stadium).exists())
        self.geometry.refresh_from_db()
        self.club.refresh_from_db()
        self.assertEqual(self.geometry.geometry, before_geometry)
        self.assertEqual(Stadium.objects.values().get(pk=self.stadium.pk), before_stadium)
        self.assertEqual(self.club.budget, 12345)
        self.assertFalse(StadiumExpansion.objects.filter(stadium=self.stadium).exists())

    def test_explicit_mode_is_preserved_for_old_clients_and_invalid_mode_is_rejected(self):
        self.save_mode("original")
        response = self.client.post(
            reverse("stadium_editor_save_design"),
            json.dumps(self.draft), content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            StadiumDesign.objects.get(stadium=self.stadium).design["seat_mode"], "original",
        )
        payload = {**self.draft, "seat_mode": "unexpected"}
        response = self.client.post(
            reverse("stadium_editor_save_design"),
            json.dumps(payload), content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
