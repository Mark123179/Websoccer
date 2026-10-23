"""The pilot is isolated, read-only and never exposes private storage to guests."""
from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse


class GrassPilotTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create(username="grass-pilot-admin", is_superuser=True)
        cls.regular = User.objects.create(username="grass-pilot-user")

    def test_guest_and_regular_user_cannot_access_page_or_assets(self):
        urls = [reverse("grass_pilot"), reverse("grass_pilot_asset", args=["basis"])]
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.regular)
        with patch("game.views_grass_pilot.get_client") as client:
            for url in urls:
                self.assertEqual(self.client.get(url).status_code, 403)
            client.assert_not_called()

    def test_admin_get_is_read_only_and_defaults_to_existing_pitch(self):
        from django.apps import apps
        self.client.force_login(self.admin)
        models = [model for model in apps.get_models()
                  if model._meta.app_label in ("game", "stadium_editor")]
        before = {model: list(model.objects.values().order_by("pk")) for model in models}
        response = self.client.get(reverse("grass_pilot"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertContains(response, 'id="grass-pilot-config"')
        self.assertContains(response, 'value="bestand"')
        for name in ("A1", "A2", "A3", "A4", "B1", "B2", "B3",
                     "C1", "C2", "D1", "D2", "D3"):
            self.assertContains(response, f'value="{name}"')
        after = {model: list(model.objects.values().order_by("pk")) for model in models}
        self.assertEqual(before, after)
        self.assertEqual(self.client.post(reverse("grass_pilot")).status_code, 405)

    def test_asset_whitelist_mime_and_storage_errors(self):
        self.client.force_login(self.admin)
        client = Mock()
        client.download_as_bytes.return_value = b"fixture-image"
        with patch("game.views_grass_pilot.get_client", return_value=client):
            response = self.client.get(reverse("grass_pilot_asset", args=["basis"]))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response["Content-Type"], "image/webp")
            self.assertEqual(response["X-Content-Type-Options"], "nosniff")
            client.download_as_bytes.assert_called_once_with(
                "studies/grass-pilot/v1/rasen_basis.webp")
            self.assertEqual(self.client.get(
                reverse("grass_pilot_asset", args=["private"])).status_code, 404)
            self.assertEqual(client.download_as_bytes.call_count, 1)
            client.download_as_bytes.side_effect = RuntimeError("private storage detail")
            response = self.client.get(reverse("grass_pilot_asset", args=["abnutzung"]))
            self.assertEqual(response.status_code, 503)
            self.assertNotContains(response, "private storage detail", status_code=503)
