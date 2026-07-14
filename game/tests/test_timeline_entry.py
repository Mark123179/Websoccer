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
        self.assertTrue(
            ManagerTimelineEntry.objects.filter(
                manager=self.manager, title='Pokalsieg'
            ).exists()
        )

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
