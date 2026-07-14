"""Tests für 'Eintrag einreichen' im Managerprofil (ManagerTimelineEntry)."""
import json

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from game.models import (
    Club,
    League,
    ManagerCareerStation,
    ManagerProfile,
    ManagerTimelineEntry,
)

XSS = '</script><script>alert(1)</script>'


class TimelineEntrySubmitTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.user = User.objects.create_user(username='tle_user', password='x')
        cls.manager, _ = ManagerProfile.objects.get_or_create(
            user=cls.user, defaults={'name': 'TLE Manager'}
        )
        cls.league = League.objects.create(
            name='TLE Testliga', country='Deutschland',
            competition_type='league', max_teams=32,
        )
        cls.club = Club.objects.create(
            name='TLE FC', short_name='TLE', founded_year=1900,
            budget=1_000_000, fan_popularity=50, league=cls.league,
        )
        cls.station = ManagerCareerStation.objects.create(
            manager=cls.manager, club=cls.club,
            custom_club_name='TLE FC', city_name='Teststadt',
        )

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.user)

    def _payload(self, **overrides):
        payload = {
            'station_id': self.station.id,
            'club_id': '',
            'event_date': '2026-05-17',
            'category': 'titel',
            'title': 'Pokalsieg',
            'body': 'Ein großartiger Abend.',
            'result_text': '3:1',
            'show_trophy': True,
            'player_id': '',
        }
        payload.update(overrides)
        return payload

    def _post(self, payload):
        return self.client.post(
            '/manager/timeline-entry/save/',
            json.dumps(payload),
            content_type='application/json',
        )

    def test_submit_ok(self):
        resp = self._post(self._payload())
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['ok'])
        self.assertEqual(data['event']['type'], 'titel')
        self.assertEqual(data['event']['tone'], 'gold')
        self.assertEqual(data['event']['status'], 'pending')
        self.assertIn('Pr\u00fcfung', data.get('message', ''))
        entry = ManagerTimelineEntry.objects.get(manager=self.manager, title='Pokalsieg')
        self.assertEqual(entry.status, ManagerTimelineEntry.STATUS_PENDING)

    def test_pending_not_visible_on_profile(self):
        """Nur genehmigte Eintr\u00e4ge erscheinen im \u00f6ffentlichen Profil."""
        self._post(self._payload(title='Sichtbar'))
        entry = ManagerTimelineEntry.objects.get(manager=self.manager, title='Sichtbar')
        entry.status = ManagerTimelineEntry.STATUS_APPROVED
        entry.save(update_fields=['status'])
        # Ein pending-Eintrag
        self._post(self._payload(title='Unsichtbar'))

        page = self.client.get('/manager/profil/')
        self.assertEqual(page.status_code, 200)
        html = page.content.decode()
        self.assertIn('Sichtbar', html)
        self.assertNotIn('Unsichtbar', html)

    def test_invalid_category_rejected(self):
        resp = self._post(self._payload(category='xxx'))
        self.assertEqual(resp.status_code, 400)

    def test_unauthenticated_rejected(self):
        resp = Client().post(
            '/manager/timeline-entry/save/',
            json.dumps(self._payload()),
            content_type='application/json',
        )
        self.assertIn(resp.status_code, (401, 302))

    def test_foreign_station_rejected(self):
        User = get_user_model()
        other_user = User.objects.create_user(username='tle_other', password='x')
        other_mgr, _ = ManagerProfile.objects.get_or_create(
            user=other_user, defaults={'name': 'Other'}
        )
        other_station = ManagerCareerStation.objects.create(
            manager=other_mgr, club=self.club,
            custom_club_name='TLE FC', city_name='Teststadt',
        )
        resp = self._post(self._payload(station_id=other_station.id))
        self.assertEqual(resp.status_code, 400)

    def test_stored_xss_stays_inert_on_profile_page(self):
        resp = self._post(self._payload(
            title='XSSTEST ' + XSS, body='Body ' + XSS,
        ))
        self.assertEqual(resp.status_code, 200)

        page = self.client.get('/manager/profil/')
        self.assertEqual(page.status_code, 200)
        html = page.content.decode()
        # Der rohe Script-Breakout darf nirgends im Quelltext auftauchen.
        self.assertNotIn(XSS, html)
        # json_script muss die Payload entschärft einbetten.
        self.assertIn('mp-tl-events-data', html)


class TimelineEntryModerationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.user = User.objects.create_user(username='tle_user2', password='x')
        cls.manager, _ = ManagerProfile.objects.get_or_create(
            user=cls.user, defaults={'name': 'TLE Manager 2'}
        )
        cls.league = League.objects.create(
            name='TLE Testliga 2', country='Deutschland',
            competition_type='league', max_teams=32,
        )
        cls.club = Club.objects.create(
            name='TLE FC 2', short_name='TLE2', founded_year=1900,
            budget=1_000_000, fan_popularity=50, league=cls.league,
        )
        cls.station = ManagerCareerStation.objects.create(
            manager=cls.manager, club=cls.club,
            custom_club_name='TLE FC 2', city_name='Teststadt',
        )
        cls.admin = User.objects.create_user(
            username='tle_admin', password='x', is_staff=True)
        cls.entry = ManagerTimelineEntry.objects.create(
            manager=cls.manager,
            club=cls.club,
            club_name='TLE FC 2',
            event_date='2026-05-17',
            category='titel',
            title='Pokalsieg',
            body='Ein großartiger Abend.',
            status=ManagerTimelineEntry.STATUS_PENDING,
        )

    def test_non_staff_forbidden_on_overview(self):
        """Nicht-Staff darf Anträge-Liste nicht sehen."""
        client = Client()
        client.force_login(self.user)
        resp = client.get('/creator/antraege/')
        self.assertEqual(resp.status_code, 403)

    def test_non_staff_forbidden_on_moderate(self):
        """Nicht-Staff darf keine Einträge moderieren."""
        client = Client()
        client.force_login(self.user)
        resp = client.post(
            f'/creator/antraege/{self.entry.id}/moderieren/',
            {'action': 'approve'},
        )
        self.assertEqual(resp.status_code, 403)
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.status, ManagerTimelineEntry.STATUS_PENDING)

    def test_staff_approve_updates_status(self):
        """Staff kann Eintrag genehmigen."""
        client = Client()
        client.force_login(self.admin)
        resp = client.post(
            f'/creator/antraege/{self.entry.id}/moderieren/',
            {'action': 'approve'},
        )
        self.assertEqual(resp.status_code, 302)
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.status, ManagerTimelineEntry.STATUS_APPROVED)
        self.assertIsNotNone(self.entry.reviewed_at)

    def test_staff_reject_updates_status(self):
        """Staff kann Eintrag ablehnen."""
        client = Client()
        client.force_login(self.admin)
        resp = client.post(
            f'/creator/antraege/{self.entry.id}/moderieren/',
            {'action': 'reject'},
        )
        self.assertEqual(resp.status_code, 302)
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.status, ManagerTimelineEntry.STATUS_REJECTED)
        self.assertIsNotNone(self.entry.reviewed_at)

    def test_invalid_action_is_error(self):
        """Ungültige Aktion wird abgewiesen."""
        client = Client()
        client.force_login(self.admin)
        resp = client.post(
            f'/creator/antraege/{self.entry.id}/moderieren/',
            {'action': 'banana'},
        )
        self.assertEqual(resp.status_code, 302)
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.status, ManagerTimelineEntry.STATUS_PENDING)
