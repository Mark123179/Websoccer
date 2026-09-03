from datetime import date, time
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from game.models import Club, GameSeasonState, League, SeasonFixture


class CalendarViewTests(TestCase):
    def setUp(self):
        GameSeasonState.objects.create(current_season=0, is_started=True)
        self.league = League.objects.create(
            name='1. Bundesliga',
            country='Deutschland',
        )
        self.club = Club.objects.create(
            name='FC Kalender',
            short_name='FCK',
            founded_year=1900,
            budget=Decimal('50000000.00'),
            league=self.league,
        )
        self.opponent = Club.objects.create(
            name='SV Termin',
            short_name='SVT',
            founded_year=1901,
            budget=Decimal('50000000.00'),
            league=self.league,
        )
        self.user = User.objects.create_user('kalendermanager', password='x')
        self.club.managed_by = self.user.manager_profile
        self.club.save(update_fields=['managed_by'])
        self.fixture = SeasonFixture.objects.create(
            league=self.league,
            season='0',
            matchday=4,
            home_club=self.club,
            away_club=self.opponent,
            scheduled_date=date(2026, 9, 5),
            scheduled_time=time(20, 30),
            home_lineup_set=True,
        )

    def test_calendar_requires_login(self):
        response = self.client.get(reverse('calendar'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/auth/login/', response.url)

    def test_topbar_calendar_action_sits_between_notifications_and_inbox(self):
        self.client.force_login(self.user)
        html = self.client.get(reverse('calendar')).content.decode()
        notification_pos = html.index(reverse('notifications_page'))
        calendar_pos = html.index(reverse('calendar'))
        inbox_pos = html.index('/inbox/')
        self.assertLess(notification_pos, calendar_pos)
        self.assertLess(calendar_pos, inbox_pos)
        self.assertIn('aria-label="Kalender öffnen"', html)

    def test_calendar_renders_real_fixture_and_all_views(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('calendar'), {
            'view': 'year',
            'calendar_date': '2026-09-05',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'SV Termin')
        self.assertContains(response, 'Aufstellung gespeichert')
        self.assertContains(response, 'data-calendar-panel="year"')
        self.assertContains(response, 'data-calendar-panel="month"')
        self.assertContains(response, 'data-calendar-panel="week"')
        self.assertContains(response, 'Saison #1 (Prognose)')

    def test_view_and_date_navigation_are_reflected_in_context(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('calendar'), {
            'view': 'week',
            'calendar_date': '2026-09-05',
        })
        self.assertEqual(response.context['calendar_active_view'], 'week')
        self.assertEqual(response.context['calendar_selected_date'], date(2026, 9, 5))
        self.assertEqual(response.context['calendar_week_days'][0]['date'], date(2026, 8, 31))

    def test_competition_filter_applies_to_calendar_data(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('calendar'), {
            'view': 'month',
            'calendar_date': '2026-09-05',
            'filters': 'pokal',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['calendar_month']['fixture_count'], 0)
        self.assertIsNone(response.context['calendar_detail_fixture'])