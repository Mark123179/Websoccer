"""View-Tests der Simulation-Diagnose (Staff-Gate + Abschnittsüberschriften)."""
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse


class SimulationDiagnosticsViewTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.staff = User.objects.create_user(
            'diag_staff', 'staff@example.de', 'pw12345', is_staff=True,
        )
        self.normal = User.objects.create_user(
            'diag_user', 'user@example.de', 'pw12345',
        )
        self.url = reverse('creator_simulation_diagnostics')

    def test_staff_gets_page(self):
        self.client.force_login(self.staff)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        for needle in [
            'Spieltag', 'Letzte Spiele', 'Balance', 'Feature-Ampel',
            'Positionsmatrix', 'Taktik-Wirkung', 'Liveticker', 'Regression',
        ]:
            self.assertContains(resp, needle)

    def test_non_staff_denied(self):
        self.client.force_login(self.normal)
        resp = self.client.get(self.url)
        self.assertNotEqual(resp.status_code, 200)

    def test_anonymous_denied(self):
        resp = self.client.get(self.url)
        self.assertNotEqual(resp.status_code, 200)
