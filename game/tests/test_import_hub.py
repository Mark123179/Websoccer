"""Smoke-Tests für den geführten Import-Hub im Creator-Mode.

Sichert die Verdrahtung der Hub-Seite und der „Weiter zu Schritt X"-Navigation
gegen künftige Routen-Regressionen ab.
"""
from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse


class ImportHubTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='hubuser', password='pw12345', is_staff=True,
        )
        self.client.force_login(self.user)

    def test_hub_requires_login(self):
        """Ohne Login leitet der Hub auf die Anmeldung um."""
        self.client.logout()
        resp = self.client.get(reverse('creator_import_hub'))
        self.assertEqual(resp.status_code, 302)

    def test_hub_lists_all_three_steps(self):
        """Die Hub-Seite verlinkt alle drei Import-Flows in der Reihenfolge."""
        resp = self.client.get(reverse('creator_import_hub'))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertIn(reverse('creator_import_index'), html)
        self.assertIn(reverse('creator_fmid_csv_import'), html)
        self.assertIn(reverse('creator_sofifa_import'), html)

    def test_all_routes_resolve(self):
        """Alle im Hub-Ablauf genutzten Routen lösen sauber auf."""
        self.assertEqual(reverse('creator_import_hub'), '/creator/import/hub/')
        self.assertEqual(reverse('creator_import_index'), '/creator/import/')
        self.assertEqual(reverse('creator_fmid_csv_import'), '/creator/import/fmids/')
        self.assertEqual(reverse('creator_sofifa_import'), '/creator/import/sofifa/')
