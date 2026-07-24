"""Auth-Regressionstests für Creator-Sponsoring-Endpoints.

Prüft, dass die 3 Creator-POST-Endpoints ohne Staff-Rechte
einen Redirect (302) zur Login-Seite zurückgeben.
"""
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse

User = get_user_model()


class CreatorSponsoringAuthTests(TestCase):
    """Unautorisierte Requests müssen 302 → Login erhalten."""

    @classmethod
    def setUpTestData(cls):
        cls.staff_user = User.objects.create_user(
            username='teststaff', password='pass', is_staff=True,
        )
        cls.normal_user = User.objects.create_user(
            username='testnormal', password='pass', is_staff=False,
        )
        cls.club = None  # club_id Dummy

    def _post(self, url, data=None):
        return self.client.post(url, data or {})

    # ── Anonym ──────────────────────────────────────────────────────────────

    def test_deactivate_anonymous_redirects(self):
        url = reverse('creator_sponsoring_deactivate')
        resp = self._post(url, {'sponsor_id': '1'})
        self.assertIn(resp.status_code, (302, 403))
        if resp.status_code == 302:
            self.assertIn('/login', resp.url.lower())

    def test_slot_reset_anonymous_redirects(self):
        url = reverse('creator_sponsoring_slot_reset', kwargs={'club_id': 999999})
        resp = self._post(url, {'slot': 'haupt'})
        self.assertIn(resp.status_code, (302, 403))
        if resp.status_code == 302:
            self.assertIn('/login', resp.url.lower())

    def test_risk_mode_anonymous_redirects(self):
        url = reverse('creator_sponsoring_risk_mode')
        resp = self._post(url, {'risk_mode': 'Hardcore'})
        self.assertIn(resp.status_code, (302, 403))
        if resp.status_code == 302:
            self.assertIn('/login', resp.url.lower())

    # ── Eingeloggter Nicht-Staff ─────────────────────────────────────────────

    def test_deactivate_non_staff_redirects(self):
        self.client.force_login(self.normal_user)
        url = reverse('creator_sponsoring_deactivate')
        resp = self._post(url, {'sponsor_id': '1'})
        self.assertIn(resp.status_code, (302, 403))

    def test_slot_reset_non_staff_redirects(self):
        self.client.force_login(self.normal_user)
        url = reverse('creator_sponsoring_slot_reset', kwargs={'club_id': 999999})
        resp = self._post(url, {'slot': 'haupt'})
        self.assertIn(resp.status_code, (302, 403))

    def test_risk_mode_non_staff_redirects(self):
        self.client.force_login(self.normal_user)
        url = reverse('creator_sponsoring_risk_mode')
        resp = self._post(url, {'risk_mode': 'Hardcore'})
        self.assertIn(resp.status_code, (302, 403))
