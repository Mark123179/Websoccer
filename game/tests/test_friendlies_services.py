from datetime import timedelta
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from game.friendlies.services import (
    accept_marketplace_offer,
    accept_request,
    cleanup_season,
    create_directed_request,
    create_marketplace_offer,
    get_squad,
    _attendance_preview,
    simulate_fixture,
)
from game.models import (
    Club,
    FriendlyFixture,
    NeutralVenue,
    League,
    GameSeasonState,
    MatchdayRevenue,
    PlayerFormSnapshot,
    PlayerInjuryRecord,
    PlayerSeasonStat,
    SimulatedMatch,
    SeasonFixture,
    Stadium,
)


class FriendlyServiceTests(TestCase):
    def setUp(self):
        self.league = League.objects.create(name='Freundschaft-Testliga')
        self.home = Club.objects.create(
            name='Freundschaft Heim',
            short_name='FSH',
            league=self.league,
            founded_year=2000,
            budget=0,
        )
        self.away = Club.objects.create(
            name='Freundschaft Gast',
            short_name='FSG',
            league=self.league,
            founded_year=2001,
            budget=0,
        )
        user = get_user_model().objects.create_user(
            username='friendly-away-manager',
            password='test-password',
        )
        self.away.managed_by = user.manager_profile
        self.away.save(update_fields=['managed_by'])
        self.kickoff = timezone.now() + timedelta(days=2)

    def test_u21_extension_point_is_empty(self):
        self.assertEqual(get_squad(self.home, FriendlyFixture.SQUAD_U21).count(), 0)

    def test_directed_request_waits_for_manager_but_ai_accepts_immediately(self):
        manager_request = create_directed_request(
            sender_club=self.home,
            target_club=self.away,
            kickoff_at=self.kickoff,
        )
        self.assertEqual(manager_request.status, FriendlyFixture.STATUS_REQUESTED)

        self.away.managed_by = None
        self.away.save(update_fields=['managed_by'])
        enough = Mock()
        enough.count.return_value = 11
        with patch('game.friendlies.services.get_squad', return_value=enough):
            ai_request = create_directed_request(
                sender_club=self.home,
                target_club=self.away,
                kickoff_at=self.kickoff + timedelta(hours=1),
            )
        self.assertEqual(ai_request.status, FriendlyFixture.STATUS_PLANNED)

    def test_acceptance_reports_concrete_squad_size(self):
        request = FriendlyFixture.objects.create(
            sender_club=self.home,
            target_club=self.away,
            kickoff_at=self.kickoff,
            status=FriendlyFixture.STATUS_REQUESTED,
        )
        full = Mock()
        full.count.return_value = 11
        short = Mock()
        short.count.return_value = 8
        with patch(
            'game.friendlies.services.get_squad',
            side_effect=[full, short],
        ):
            with self.assertRaisesMessage(
                ValidationError,
                'Freundschaft Gast: nur 8 von 11 benötigten einsatzfähigen Spielern',
            ):
                accept_request(request.pk, self.away)

    def test_marketplace_offer_can_only_be_awarded_once(self):
        offer = create_marketplace_offer(
            sender_club=self.home,
            kickoff_at=self.kickoff,
            squad_scope=FriendlyFixture.SQUAD_PRO,
            venue_type=FriendlyFixture.VENUE_HOME,
            offered_role=FriendlyFixture.VENUE_HOME,
        )
        enough = Mock()
        enough.count.return_value = 11
        with patch('game.friendlies.services.get_squad', return_value=enough):
            accepted = accept_marketplace_offer(offer.pk, self.away)
            self.assertEqual(accepted.status, FriendlyFixture.STATUS_PLANNED)
            with self.assertRaisesMessage(
                ValidationError,
                'Diese Partie wurde bereits vergeben.',
            ):
                accept_marketplace_offer(offer.pk, self.away)

    def test_simulation_is_idempotent_and_has_no_persistent_side_effects(self):
        fixture = FriendlyFixture.objects.create(
            sender_club=self.home,
            target_club=self.away,
            kickoff_at=self.kickoff,
            season='7',
            status=FriendlyFixture.STATUS_PLANNED,
        )
        enough = Mock()
        enough.count.return_value = 11
        report = {'home_goals': 2, 'away_goals': 1, 'goal_events': []}
        before = {
            'form': PlayerFormSnapshot.objects.count(),
            'stats': PlayerSeasonStat.objects.count(),
            'injuries': PlayerInjuryRecord.objects.count(),
            'revenue': MatchdayRevenue.objects.count(),
        }
        with (
            patch('game.friendlies.services.get_squad', return_value=enough),
            patch('game.match_engine.simulate_match', return_value=report) as engine,
            patch('game.friendlies.services._attendance_preview', return_value={}),
        ):
            first = simulate_fixture(fixture.pk)
            second = simulate_fixture(fixture.pk)

        self.assertEqual(first.status, FriendlyFixture.STATUS_PLAYED)
        self.assertEqual(second.simulated_match_id, first.simulated_match_id)
        self.assertEqual(SimulatedMatch.objects.filter(match_type='freundschaft').count(), 1)
        engine.assert_called_once()
        self.assertEqual(
            engine.call_args.kwargs['tactic_context'],
            'freundschaft',
        )
        self.assertEqual(before['form'], PlayerFormSnapshot.objects.count())
        self.assertEqual(before['stats'], PlayerSeasonStat.objects.count())
        self.assertEqual(before['injuries'], PlayerInjuryRecord.objects.count())
        self.assertEqual(before['revenue'], MatchdayRevenue.objects.count())

    def test_failed_simulation_returns_to_planned(self):
        fixture = FriendlyFixture.objects.create(
            sender_club=self.home,
            target_club=self.away,
            kickoff_at=self.kickoff,
            season='7',
            status=FriendlyFixture.STATUS_PLANNED,
        )
        enough = Mock()
        enough.count.return_value = 11
        with (
            patch('game.friendlies.services.get_squad', return_value=enough),
            patch('game.weather_service.roll_weather', side_effect=RuntimeError('weather down')),
        ):
            with self.assertRaisesMessage(RuntimeError, 'weather down'):
                simulate_fixture(fixture.pk)
        fixture.refresh_from_db()
        self.assertEqual(fixture.status, FriendlyFixture.STATUS_PLANNED)
        self.assertIsNone(fixture.simulated_match_id)
        self.assertEqual(fixture.simulation_attempts, 1)
        self.assertIsNotNone(fixture.next_simulation_attempt_at)

    def test_tick_continues_after_poison_fixture(self):
        from game.friendlies.services import run_tick
        first = FriendlyFixture.objects.create(
            sender_club=self.home,
            target_club=self.away,
            kickoff_at=timezone.now() - timedelta(minutes=2),
            season='7',
            status=FriendlyFixture.STATUS_PLANNED,
        )
        second = FriendlyFixture.objects.create(
            sender_club=self.home,
            target_club=self.away,
            kickoff_at=timezone.now() - timedelta(minutes=1),
            season='7',
            status=FriendlyFixture.STATUS_PLANNED,
        )
        enough = Mock()
        enough.count.return_value = 11
        with (
            patch('game.friendlies.services.get_squad', return_value=enough),
            patch('game.weather_service.roll_weather', return_value=('normal', 15)),
            patch(
                'game.match_engine.simulate_match',
                side_effect=[
                    RuntimeError('poison fixture'),
                    {'home_goals': 1, 'away_goals': 0},
                ],
            ),
            patch('game.friendlies.services._attendance_preview', return_value={}),
        ):
            result = run_tick()
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(result['processed'], 1)
        self.assertEqual(first.status, FriendlyFixture.STATUS_PLANNED)
        self.assertEqual(first.simulation_attempts, 1)
        self.assertEqual(second.status, FriendlyFixture.STATUS_PLAYED)

    def test_third_simulation_failure_becomes_terminal(self):
        fixture = FriendlyFixture.objects.create(
            sender_club=self.home,
            target_club=self.away,
            kickoff_at=self.kickoff,
            season='7',
            status=FriendlyFixture.STATUS_PLANNED,
        )
        enough = Mock()
        enough.count.return_value = 11
        with (
            patch('game.friendlies.services.get_squad', return_value=enough),
            patch('game.weather_service.roll_weather', side_effect=RuntimeError('always broken')),
        ):
            for _ in range(3):
                with self.assertRaisesMessage(RuntimeError, 'always broken'):
                    simulate_fixture(fixture.pk)
        fixture.refresh_from_db()
        self.assertEqual(fixture.status, FriendlyFixture.STATUS_NOT_PLAYED)
        self.assertEqual(fixture.simulation_attempts, 3)
        self.assertIsNone(fixture.next_simulation_attempt_at)
        self.assertEqual(fixture.simulation_last_error, 'always broken')

    def test_marketplace_guest_role_controls_engine_sides(self):
        fixture = FriendlyFixture.objects.create(
            sender_club=self.home,
            target_club=self.away,
            kickoff_at=self.kickoff,
            season='7',
            status=FriendlyFixture.STATUS_PLANNED,
            offered_role=FriendlyFixture.VENUE_AWAY,
        )
        enough = Mock()
        enough.count.return_value = 11
        with (
            patch('game.friendlies.services.get_squad', return_value=enough),
            patch(
                'game.match_engine.simulate_match',
                return_value={'home_goals': 0, 'away_goals': 0},
            ) as engine,
            patch('game.friendlies.services._attendance_preview', return_value={}),
        ):
            simulate_fixture(fixture.pk)
        self.assertEqual(engine.call_args.args[:2], (self.away, self.home))

    def test_neutral_fixture_disables_engine_home_advantage(self):
        from game.models import NeutralVenue
        venue = NeutralVenue.objects.create(
            name='Test-Neutralstadion',
            city='Teststadt',
            capacity=20000,
        )
        fixture = FriendlyFixture.objects.create(
            sender_club=self.home,
            target_club=self.away,
            kickoff_at=self.kickoff,
            season='7',
            status=FriendlyFixture.STATUS_PLANNED,
            venue_type=FriendlyFixture.VENUE_NEUTRAL,
            neutral_stadium=venue,
        )
        enough = Mock()
        enough.count.return_value = 11
        with (
            patch('game.friendlies.services.get_squad', return_value=enough),
            patch(
                'game.match_engine.simulate_match',
                return_value={'home_goals': 0, 'away_goals': 0},
            ) as engine,
        ):
            simulate_fixture(fixture.pk)
        self.assertIs(engine.call_args.kwargs['neutral_venue'], True)

    def test_tick_reclaims_stale_simulation_claim(self):
        from game.friendlies.services import run_tick
        fixture = FriendlyFixture.objects.create(
            sender_club=self.home,
            target_club=self.away,
            kickoff_at=timezone.now() + timedelta(days=1),
            season='7',
            status=FriendlyFixture.STATUS_RUNNING,
            simulation_claimed_at=timezone.now() - timedelta(minutes=20),
        )
        run_tick()
        fixture.refresh_from_db()
        self.assertEqual(fixture.status, FriendlyFixture.STATUS_PLANNED)
        self.assertIsNone(fixture.simulation_claim)
        self.assertIsNone(fixture.simulation_claimed_at)

    def test_undated_kickoff_time_reserves_complete_league_match_day(self):
        SeasonFixture.objects.create(
            league=self.league,
            matchday=1,
            home_club=self.home,
            away_club=self.away,
            scheduled_date=self.kickoff.date(),
            scheduled_time=None,
            season='7',
        )
        request = FriendlyFixture.objects.create(
            sender_club=self.home,
            target_club=self.away,
            kickoff_at=self.kickoff,
            status=FriendlyFixture.STATUS_REQUESTED,
        )
        enough = Mock()
        enough.count.return_value = 11
        with patch('game.friendlies.services.get_squad', return_value=enough):
            with self.assertRaisesMessage(
                ValidationError,
                'Zu diesem Zeitpunkt findet bereits eine Spielsimulation statt.',
            ):
                accept_request(request.pk, self.away)

    def test_season_change_rolls_back_when_friendly_cleanup_fails(self):
        state = GameSeasonState.objects.create(current_season=3)
        state.current_season = 4
        with patch(
            'game.friendlies.services.cleanup_season',
            side_effect=RuntimeError('cleanup failed'),
        ):
            with self.assertRaisesMessage(RuntimeError, 'cleanup failed'):
                state.save()
        state.refresh_from_db()
        self.assertEqual(state.current_season, 3)

    def test_http_u21_action_is_blocked_with_exact_message(self):
        user = self.away.managed_by.user
        self.client.force_login(user)
        response = self.client.post(
            '/management/freundschaften/action/',
            {
                'action': 'offer',
                'squad_scope': FriendlyFixture.SQUAD_U21,
                'kickoff_at': self.kickoff.isoformat(),
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()['error'],
            'Die U21 hat noch keinen Kader — der Jugendspielbetrieb ist in Arbeit.',
        )

    def test_http_marketplace_offer_is_created_for_manager_club(self):
        user = self.away.managed_by.user
        self.client.force_login(user)
        response = self.client.post(
            '/management/freundschaften/action/',
            {
                'action': 'offer',
                'squad_scope': FriendlyFixture.SQUAD_PRO,
                'kickoff_at': self.kickoff.isoformat(),
                'venue_type': FriendlyFixture.VENUE_HOME,
                'role': FriendlyFixture.VENUE_HOME,
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(response.status_code, 200)
        fixture = FriendlyFixture.objects.get(pk=response.json()['fixture_id'])
        self.assertEqual(fixture.sender_club, self.away)
        self.assertEqual(fixture.status, FriendlyFixture.STATUS_REQUESTED)

    def test_http_marketplace_offer_accepts_selected_neutral_stadium(self):
        venue = NeutralVenue.objects.create(
            name='Neutral-Arena', city='Teststadt', capacity=18000,
        )
        user = self.away.managed_by.user
        self.client.force_login(user)
        response = self.client.post(
            '/management/freundschaften/action/',
            {
                'action': 'offer',
                'squad_scope': FriendlyFixture.SQUAD_PRO,
                'kickoff_at': self.kickoff.isoformat(),
                'venue_type': FriendlyFixture.VENUE_NEUTRAL,
                'neutral_stadium': venue.pk,
                'role': FriendlyFixture.VENUE_AWAY,
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(response.status_code, 200)
        fixture = FriendlyFixture.objects.get(pk=response.json()['fixture_id'])
        self.assertEqual(fixture.neutral_stadium, venue)

    def test_marketplace_home_venue_belongs_to_offerer_even_as_away_team(self):
        Stadium.objects.create(
            club=self.home, name='Inserentenstadion', city='Heimstadt',
        )
        Stadium.objects.create(
            club=self.away, name='Annehmerstadion', city='Gaststadt',
        )
        fixture = FriendlyFixture.objects.create(
            sender_club=self.home,
            target_club=self.away,
            kickoff_at=self.kickoff,
            venue_type=FriendlyFixture.VENUE_HOME,
            offered_role=FriendlyFixture.VENUE_AWAY,
            status=FriendlyFixture.STATUS_PLANNED,
        )
        demand = {
            'zuschauer_gesamt': 0,
            'auslastung_pct': 0,
            'kategorien': {},
        }
        with patch(
            'game.economy.stadium.compute_demand',
            return_value=demand,
        ) as compute:
            preview = _attendance_preview(fixture, self.away, self.home)
        self.assertEqual(compute.call_args.args[0], self.home)
        self.assertEqual(preview['venue'], 'Inserentenstadion')

    def test_friendlies_script_uses_literal_form_action_attribute(self):
        user = self.away.managed_by.user
        self.client.force_login(user)
        response = self.client.get('/management/freundschaften/?tab=market&squad=pro')
        self.assertContains(response, "fetch(form.getAttribute('action')")
        self.assertNotContains(response, 'fetch(form.action')
        self.assertContains(response, 'name="neutral_stadium"', count=1)

    def test_cleanup_removes_fixture_and_linked_report(self):
        match = SimulatedMatch.create_numbered(
            season='4',
            home_club=self.home,
            away_club=self.away,
            home_goals=0,
            away_goals=0,
            match_type='freundschaft',
        )
        FriendlyFixture.objects.create(
            sender_club=self.home,
            target_club=self.away,
            kickoff_at=self.kickoff,
            season='4',
            status=FriendlyFixture.STATUS_PLAYED,
            simulated_match=match,
        )

        cleanup_season('4')

        self.assertFalse(FriendlyFixture.objects.filter(season='4').exists())
        self.assertFalse(SimulatedMatch.objects.filter(pk=match.pk).exists())