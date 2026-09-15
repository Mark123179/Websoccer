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
            'opponent_name': 'TLE Gegner',
            'competition_name': 'TLE Testliga',
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
        self.assertEqual(entry.opponent_name, 'TLE Gegner')
        self.assertEqual(entry.competition_name, 'TLE Testliga')

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

    def test_superuser_gets_one_transient_compact_panorama_ticket(self):
        self.user.is_superuser = True
        self.user.save(update_fields=['is_superuser'])
        before_count = ManagerTimelineEntry.objects.count()

        response = self.client.get('/manager/profil/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'mp-tlticket-card')
        self.assertContains(response, 'mp-tlticket-stub-label')
        self.assertContains(response, 'mp-tlticket-stub-competition')
        self.assertContains(response, "esc(ev.title || 'SPIELERGEBNIS')")
        self.assertNotContains(response, 'mp-tlticket-stub-competition--fallback')
        self.assertNotContains(response, 'FINAL PASS')
        self.assertNotContains(response, 'SAMMLER-EDITION')
        tickets = [
            event for event in response.context['timeline_events_json']
            if event.get('ticket')
        ]
        self.assertEqual(len(tickets), 1)
        ticket = tickets[0]['ticket']
        self.assertEqual(tickets[0]['date_iso'], '2026-05-30')
        self.assertEqual(tickets[0]['type'], 'finale')
        self.assertEqual(ticket['home']['name'], 'Bayer 04 Leverkusen')
        self.assertEqual(ticket['home']['short'], 'Bayer 04')
        self.assertEqual(ticket['home']['mark'], 'B04')
        self.assertEqual(ticket['away']['name'], 'RB Leipzig')
        self.assertEqual(ticket['score'], '1:0')
        self.assertEqual(ticket['status'], 'FT')
        self.assertEqual(ticket['competition'], 'UEFA Champions League')
        self.assertNotIn('serial', ticket)
        self.assertNotIn('number', ticket)
        self.assertTrue(ticket['stadium_url'].endswith(
            '/game/images/stadiums/germany/b-leverkusen.jpg'
        ))
        self.assertEqual(ManagerTimelineEntry.objects.count(), before_count)

    def test_normal_manager_result_is_compact_ticket(self):
        self._post(self._payload(title='Normales Ergebnis'))
        entry = ManagerTimelineEntry.objects.get(
            manager=self.manager, title='Normales Ergebnis'
        )
        entry.status = ManagerTimelineEntry.STATUS_APPROVED
        entry.save(update_fields=['status'])

        response = self.client.get('/manager/profil/')

        self.assertEqual(response.status_code, 200)
        events = response.context['timeline_events_json']
        result_event = next(
            event for event in events if event['title'] == 'Normales Ergebnis'
        )
        self.assertEqual(result_event['result'], '3:1')
        self.assertEqual(result_event['ticket']['score'], '3:1')
        self.assertEqual(result_event['ticket']['home']['name'], 'TLE FC')
        self.assertEqual(result_event['ticket']['away']['name'], 'TLE Gegner')
        self.assertEqual(result_event['ticket']['competition'], 'TLE Testliga')
        self.assertTrue(result_event['ticket']['competition_logo_url'].endswith(
            f'/competitions/{self.league.id}_comp.png'
        ))
        self.assertContains(response, 'var isTicket = !!ev.ticket;')
        self.assertContains(response, 'var resultHtml = !isTicket && ev.result')
        self.assertContains(response, 'requestAnimationFrame(scrollToToday)')

    def test_legacy_result_without_ticket_details_still_becomes_ticket(self):
        entry = ManagerTimelineEntry.objects.create(
            manager=self.manager,
            club=self.club,
            club_name='TLE FC',
            event_date='2026-09-15',
            category='finale',
            title='Finale Dahoam',
            result_text='5:0',
            status=ManagerTimelineEntry.STATUS_APPROVED,
        )

        response = self.client.get('/manager/profil/')

        event = next(
            item for item in response.context['timeline_events_json']
            if item.get('entry_id') == entry.id
        )
        self.assertEqual(event['ticket']['score'], '5:0')
        self.assertEqual(event['ticket']['away']['name'], 'Gegner')
        self.assertEqual(event['ticket']['competition'], 'Finale')

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

    def test_staff_can_update_only_existing_ticket_details(self):
        opponent = Club.objects.create(
            name='TLE Gegner 2', short_name='G2', founded_year=1901,
            budget=1_000_000, fan_popularity=40, league=self.league,
        )
        original = {
            'status': self.entry.status,
            'result_text': self.entry.result_text,
            'title': self.entry.title,
            'body': self.entry.body,
            'reviewed_at': self.entry.reviewed_at,
        }
        client = Client()
        client.force_login(self.admin)

        response = client.post(
            f'/creator/antraege/{self.entry.id}/ticketdaten/',
            {'opponent_id': opponent.id, 'competition_id': self.league.id},
        )

        self.assertEqual(response.status_code, 302)
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.opponent_name, opponent.name)
        self.assertEqual(self.entry.competition_name, self.league.name)
        for field, value in original.items():
            self.assertEqual(getattr(self.entry, field), value)

    def test_non_staff_cannot_update_ticket_details(self):
        client = Client()
        client.force_login(self.user)

        response = client.post(
            f'/creator/antraege/{self.entry.id}/ticketdaten/',
            {'opponent_id': self.club.id, 'competition_id': self.league.id},
        )

        self.assertEqual(response.status_code, 403)
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.opponent_name, '')
        self.assertEqual(self.entry.competition_name, '')

    def test_overview_lists_approved_legacy_result_for_ticket_editing(self):
        self.entry.status = ManagerTimelineEntry.STATUS_APPROVED
        self.entry.result_text = '2:1'
        self.entry.save(update_fields=['status', 'result_text'])
        client = Client()
        client.force_login(self.admin)

        response = client.get('/creator/antraege/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'TICKETDATEN BEARBEITEN')
        self.assertContains(
            response,
            f'/creator/antraege/{self.entry.id}/ticketdaten/',
        )
