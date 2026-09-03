from datetime import date, time
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from game.models import Club, ClubPublicProfile, GameSeasonState, League, SeasonFixture
from game.models import (


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
        self.club.fm_inside_id = 915
        self.club.save(update_fields=['fm_inside_id'])
        ClubPublicProfile.objects.create(
            club=self.club,
            stadium_image_static_path='game/images/stadiums/germany/fc-bayern.jpg',
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

    def test_fixture_uses_home_profile_stadium_as_calendar_background(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('calendar'), {
            'view': 'month',
            'calendar_date': '2026-09-05',
        })
        payload = response.context['calendar_detail_fixture']
        self.assertEqual(
            payload['stadium'],
            '/static/game/images/stadiums/germany/fc-bayern.jpg',
        )
        self.assertContains(response, 'has-stadium')
        self.assertContains(response, '--calendar-stadium-image:')

    def test_calendar_header_has_no_chevron_step_buttons(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('calendar'))
        self.assertNotContains(response, 'calendar-step')
        self.assertNotContains(response, 'Einen Monat zurück')
        self.assertNotContains(response, 'Einen Monat weiter')

    def test_global_calendar_card_uses_static_home_stadium_url(self):
        self.fixture.scheduled_date = date.today()
        self.fixture.save(update_fields=['scheduled_date'])
        self.client.force_login(self.user)
        response = self.client.get(reverse('calendar'))
        self.assertContains(
            response,
            "--fixture-stadium: url('/static/game/images/stadiums/germany/fc-bayern.jpg')",
        )

    @override_settings(ASSETS_BASE_URL='/custom-assets/')
    def test_uploaded_stadium_url_is_used_in_detail_and_global_header(self):
        profile = self.club.public_profile
        profile.stadium_image_static_path = 'clubs/stadiums/915_stadium.jpg'
        profile.save(update_fields=['stadium_image_static_path'])
        self.fixture.scheduled_date = date.today()
        self.fixture.save(update_fields=['scheduled_date'])
        self.client.force_login(self.user)

        response = self.client.get(reverse('calendar'), {
            'view': 'month',
            'calendar_date': date.today().isoformat(),
        })

        expected_url = '/custom-assets/clubs/stadiums/915_stadium.jpg'
        self.assertEqual(
            response.context['calendar_detail_fixture']['stadium'],
            expected_url,
        )
        self.assertContains(
            response,
            f"--calendar-stadium-image: url('{expected_url}')",
        )
        self.assertContains(
            response,
            f"--fixture-stadium: url('{expected_url}')",
        )
        self.assertNotContains(
            response,
            '/static/clubs/stadiums/915_stadium.jpg',
        )

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

    def test_calendar_links_future_league_fixture_to_its_specific_preview(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('calendar'), {
            'view': 'month',
            'calendar_date': '2026-09-05',
        })
        fixture = response.context['calendar_detail_fixture']
        expected_url = reverse(
            'club_match_fixture_preview',
            args=[self.club.pk, self.fixture.pk],
        )
        self.assertEqual(fixture['detail_url'], expected_url)
        self.assertEqual(fixture['detail_label'], 'Spielvorschau')
        self.assertContains(response, f'href="{expected_url}"')

        preview_response = self.client.get(expected_url)
        self.assertEqual(preview_response.status_code, 200)
        self.assertContains(preview_response, 'SV Termin')
        self.assertContains(preview_response, '05.09.2026')

    def test_calendar_links_played_league_fixture_to_its_report(self):
        simulated = SimulatedMatch.objects.create(
            home_club=self.club,
            away_club=self.opponent,
            home_goals=2,
            away_goals=1,
            report_data={'match_stats': {}},
        )
        self.fixture.is_played = True
        self.fixture.home_goals = 2
        self.fixture.away_goals = 1
        self.fixture.simulated_match = simulated
        self.fixture.save()

        self.client.force_login(self.user)
        response = self.client.get(reverse('calendar'), {
            'view': 'week',
            'calendar_date': '2026-09-05',
        })
        fixture = response.context['calendar_detail_fixture']
        expected_url = reverse('match_report_by_id', args=[simulated.pk])
        self.assertEqual(fixture['detail_url'], expected_url)
        self.assertEqual(fixture['detail_label'], 'Spielbericht')
        self.assertContains(response, f'href="{expected_url}"')

    def test_calendar_uses_cup_tree_and_forecasts_have_no_detail_url(self):
        cup = League.objects.create(
            name='Kalenderpokal',
            country='Deutschland',
            competition_type=League.COMPETITION_TYPE_CUP,
        )
        cup_season = CupSeason.objects.create(
            competition=cup,
            season='0',
        )
        cup_round = CupRound.objects.create(
            cup_season=cup_season,
            round_number=1,
            round_code='round_of_32',
            scheduled_date=date(2026, 9, 12),
        )
        CupFixture.objects.create(
            cup_round=cup_round,
            bracket_position=1,
            home_club=self.club,
            away_club=self.opponent,
            status=CupFixture.STATUS_SCHEDULED,
        )

        self.client.force_login(self.user)
        response = self.client.get(reverse('calendar'), {
            'view': 'month',
            'calendar_date': '2026-09-12',
        })
        cup_fixture = response.context['calendar_detail_fixture']
        expected_url = reverse('cup_tree', args=[cup.pk, cup_season.season])
        self.assertEqual(cup_fixture['detail_url'], expected_url)
        self.assertEqual(cup_fixture['detail_label'], 'Pokalansicht')

        forecast = next(
            fixture for fixture in response.context['calendar_upcoming']
            if fixture['forecast']
        )
        self.assertIsNone(forecast['detail_url'])

    def test_calendar_links_played_cup_fixture_to_its_report(self):
        cup = League.objects.create(
            name='Berichtspokal',
            country='Deutschland',
            competition_type=League.COMPETITION_TYPE_CUP,
        )
        cup_season = CupSeason.objects.create(
            competition=cup,
            season='0',
        )
        cup_round = CupRound.objects.create(
            cup_season=cup_season,
            round_number=1,
            round_code='round_of_32',
            scheduled_date=date(2026, 9, 12),
        )
        simulated = SimulatedMatch.objects.create(
            home_club=self.club,
            away_club=self.opponent,
            home_goals=1,
            away_goals=0,
            report_data={'match_stats': {}},
            match_type='pokal',
        )
        CupFixture.objects.create(
            cup_round=cup_round,
            bracket_position=1,
            home_club=self.club,
            away_club=self.opponent,
            simulated_match=simulated,
            status=CupFixture.STATUS_PLAYED,
            home_goals_90=1,
            away_goals_90=0,
        )

        self.client.force_login(self.user)
        response = self.client.get(reverse('calendar'), {
            'view': 'week',
            'calendar_date': '2026-09-12',
        })
        fixture = response.context['calendar_detail_fixture']
        expected_url = reverse('match_report_by_id', args=[simulated.pk])
        self.assertEqual(fixture['detail_url'], expected_url)
        self.assertEqual(fixture['detail_label'], 'Spielbericht')
        self.assertContains(response, f'href="{expected_url}"')
