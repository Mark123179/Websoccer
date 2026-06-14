"""
game/tests/test_cup_service.py

≥ 20 Unit-Tests für cup_service.py:
  - calculate_opening_round()
  - generate_dummy_clubs()
  - build_cup_participants()
  - draw_cup_round()
  - simulate_cup_fixture()  (gemockt)
  - advance_cup_round()
  - schedule_cup_round()
  - Fehlerklassen
"""

from unittest.mock import MagicMock, patch

from django.test import TestCase

from game.cup_service import (
    CupInvalidParticipantsError,
    CupRoundAlreadyDrawnError,
    CupRoundAlreadyExistsError,
    CupRoundNotCompleteError,
    CupServiceError,
    ROUND_CODES,
    _round_display_name,
    advance_cup_round,
    build_cup_participants,
    calculate_opening_round,
    draw_cup_round,
    generate_dummy_clubs,
    schedule_cup_round,
    simulate_cup_fixture,
)
from game.models import Club, CupFixture, CupRound, CupSeason, League, Player


def _make_league(name='Testliga', competition_type='league', country='Deutschland'):
    return League.objects.create(
        name=name,
        country=country,
        competition_type=competition_type,
        max_teams=32,
    )


def _make_club(league, name='FC Test'):
    return Club.objects.create(
        name=name,
        short_name=name[:8],
        founded_year=2000,
        budget=1_000_000,
        league=league,
        fan_popularity=50,
    )


def _make_cup_season(competition, season='2025/26'):
    return CupSeason.objects.create(
        competition=competition,
        season=season,
        status=CupSeason.STATUS_SETUP,
    )


def _make_cup_round(cup_season, round_number=1, round_code='round_of_32'):
    return CupRound.objects.create(
        cup_season=cup_season,
        round_number=round_number,
        round_code=round_code,
        status=CupRound.STATUS_PENDING,
    )


# ── 1. calculate_opening_round ────────────────────────────────────────────────

class CalculateOpeningRoundTests(TestCase):

    def test_power_of_two_no_byes(self):
        result = calculate_opening_round(32)
        self.assertEqual(result['matches'], 16)
        self.assertEqual(result['byes'], 0)

    def test_power_of_two_16(self):
        result = calculate_opening_round(16)
        self.assertEqual(result['matches'], 8)
        self.assertEqual(result['byes'], 0)

    def test_36_teams_4_matches_28_byes(self):
        result = calculate_opening_round(36)
        self.assertEqual(result['matches'], 4)
        self.assertEqual(result['byes'], 28)

    def test_two_teams(self):
        result = calculate_opening_round(2)
        self.assertEqual(result['matches'], 1)
        self.assertEqual(result['byes'], 0)

    def test_raises_for_less_than_two(self):
        with self.assertRaises(ValueError):
            calculate_opening_round(1)

    def test_32_teams_total_correct(self):
        result = calculate_opening_round(32)
        self.assertEqual(result['matches'] * 2 + result['byes'], 32)

    def test_36_teams_total_correct(self):
        result = calculate_opening_round(36)
        self.assertEqual(result['matches'] * 2 + result['byes'], 36)


# ── 2. ROUND_CODES dict ───────────────────────────────────────────────────────

class RoundCodesTests(TestCase):

    def test_round_codes_keys(self):
        self.assertIn(32, ROUND_CODES)
        self.assertIn(16, ROUND_CODES)
        self.assertIn(8,  ROUND_CODES)
        self.assertIn(4,  ROUND_CODES)
        self.assertIn(2,  ROUND_CODES)

    def test_final_code(self):
        self.assertEqual(ROUND_CODES[2], 'final')

    def test_semi_final_code(self):
        self.assertEqual(ROUND_CODES[4], 'semi_final')


# ── 3. build_cup_participants ─────────────────────────────────────────────────

class BuildCupParticipantsTests(TestCase):

    def setUp(self):
        self.bundesliga = _make_league('Bundesliga', competition_type='league')
        self.zweitliga  = _make_league('2. Bundesliga', competition_type='league')
        self.pokal      = _make_league('DFB-Pokal', competition_type='cup')
        self.cup_season = _make_cup_season(self.pokal)

        for i in range(18):
            _make_club(self.bundesliga, f'BL-Verein {i+1:02d}')
        for i in range(18):
            _make_club(self.zweitliga, f'ZWB-Verein {i+1:02d}')

    def test_builds_correct_participant_count(self):
        participants = build_cup_participants(
            self.cup_season, self.bundesliga, self.zweitliga,
            bl_count=18, zweite_bl_count=14,
        )
        self.assertEqual(len(participants), 32)

    def test_participants_saved_to_cup_season(self):
        build_cup_participants(
            self.cup_season, self.bundesliga, self.zweitliga,
            bl_count=18, zweite_bl_count=14,
        )
        self.assertEqual(self.cup_season.participants.count(), 32)

    def test_status_set_to_running(self):
        build_cup_participants(
            self.cup_season, self.bundesliga, self.zweitliga,
            bl_count=18, zweite_bl_count=14,
        )
        self.cup_season.refresh_from_db()
        self.assertEqual(self.cup_season.status, CupSeason.STATUS_RUNNING)

    def test_raises_if_too_few_participants(self):
        empty_league = _make_league('Leer')
        with self.assertRaises(CupInvalidParticipantsError):
            build_cup_participants(
                self.cup_season, empty_league, empty_league,
                bl_count=0, zweite_bl_count=0,
            )


# ── 3b. generate_dummy_clubs ─────────────────────────────────────────────────

class GenerateDummyClubsTests(TestCase):

    def setUp(self):
        self.liga = _make_league('2. Bundesliga Test', competition_type='league')

    def test_creates_requested_count(self):
        clubs = generate_dummy_clubs(self.liga, count=4)
        self.assertEqual(len(clubs), 4)
        self.assertEqual(Club.objects.filter(league=self.liga).count(), 4)

    def test_each_club_has_18_players(self):
        generate_dummy_clubs(self.liga, count=2)
        for club in Club.objects.filter(league=self.liga):
            self.assertEqual(
                Player.objects.filter(club=club).count(),
                18,
                msg=f'{club.name} hat nicht 18 Spieler',
            )

    def test_players_have_valid_age(self):
        generate_dummy_clubs(self.liga, count=1)
        for p in Player.objects.filter(club__league=self.liga):
            self.assertGreater(p.age, 0)
            self.assertLess(p.age, 60)

    def test_idempotent_on_second_call(self):
        generate_dummy_clubs(self.liga, count=3)
        generate_dummy_clubs(self.liga, count=3)
        self.assertEqual(Club.objects.filter(league=self.liga).count(), 3)

    def test_position_distribution_includes_goalkeeper(self):
        generate_dummy_clubs(self.liga, count=1)
        club = Club.objects.filter(league=self.liga).first()
        gk_count = Player.objects.filter(club=club, position='TW').count()
        self.assertGreaterEqual(gk_count, 1)

    def test_default_count_is_18(self):
        clubs = generate_dummy_clubs(self.liga)
        self.assertEqual(len(clubs), 18)


# ── 4. draw_cup_round ────────────────────────────────────────────────────────

class DrawCupRoundTests(TestCase):

    def setUp(self):
        self.pokal      = _make_league('DFB-Pokal', competition_type='cup')
        self.cup_season = _make_cup_season(self.pokal)
        self.cup_round  = _make_cup_round(self.cup_season)

        self.bl = _make_league('BL')
        self.clubs = [_make_club(self.bl, f'Verein {i:02d}') for i in range(32)]

    def test_creates_correct_fixture_count_power_of_2(self):
        fixtures = draw_cup_round(self.cup_round, self.clubs)
        self.assertEqual(len(fixtures), 16)

    def test_idempotent_second_call_returns_same_fixtures(self):
        first  = draw_cup_round(self.cup_round, self.clubs)
        second = draw_cup_round(self.cup_round, self.clubs)
        self.assertEqual(
            [f.pk for f in first],
            [f.pk for f in second],
        )

    def test_raises_on_different_participants_second_call(self):
        draw_cup_round(self.cup_round, self.clubs)
        other_clubs = [_make_club(self.bl, f'Ander {i:02d}') for i in range(32)]
        with self.assertRaises(CupRoundAlreadyDrawnError):
            draw_cup_round(self.cup_round, other_clubs)

    def test_raises_on_less_than_two_participants(self):
        with self.assertRaises(CupInvalidParticipantsError):
            draw_cup_round(self.cup_round, [self.clubs[0]])

    def test_raises_on_duplicate_participants(self):
        with self.assertRaises(CupInvalidParticipantsError):
            draw_cup_round(self.cup_round, [self.clubs[0], self.clubs[0]])

    def test_bracket_positions_assigned(self):
        fixtures = draw_cup_round(self.cup_round, self.clubs)
        positions = [f.bracket_position for f in fixtures]
        self.assertEqual(sorted(positions), list(range(1, len(fixtures) + 1)))

    def test_non_power_of_two_creates_byes(self):
        cup_season2 = _make_cup_season(self.pokal, season='2026/27')
        cup_round2  = _make_cup_round(cup_season2, round_code='round_of_36')
        clubs36     = [_make_club(self.bl, f'C36-{i:02d}') for i in range(36)]
        fixtures    = draw_cup_round(cup_round2, clubs36)
        bye_count   = sum(1 for f in fixtures if f.is_bye)
        match_count = sum(1 for f in fixtures if not f.is_bye)
        self.assertEqual(bye_count, 28)
        self.assertEqual(match_count, 4)

    def test_seed_determinism_via_stable_seed(self):
        """stable_seed gibt für gleiche Argumente immer denselben int zurück."""
        from game.random_utils import stable_seed
        s1 = stable_seed('cup-draw', 99, '2025/26', 1)
        s2 = stable_seed('cup-draw', 99, '2025/26', 1)
        self.assertEqual(s1, s2)
        s3 = stable_seed('cup-draw', 99, '2025/26', 2)
        self.assertNotEqual(s1, s3)


# ── 5. simulate_cup_fixture (gemockt) ────────────────────────────────────────

class SimulateCupFixtureTests(TestCase):

    def _setup(self):
        pokal      = _make_league('DFB-Pokal', competition_type='cup')
        cup_season = _make_cup_season(pokal)
        cup_round  = _make_cup_round(cup_season)
        bl         = _make_league('BL')
        home       = _make_club(bl, 'FC Heim')
        away       = _make_club(bl, 'FC Auswärts')
        fixture = CupFixture.objects.create(
            cup_round=cup_round,
            bracket_position=1,
            home_club=home,
            away_club=away,
            is_bye=False,
            status=CupFixture.STATUS_SCHEDULED,
        )
        return fixture, home, away

    def _mock_result(self, winner_id, decided_by='regular_time', home_goals=2, away_goals=1):
        return {
            'home_goals': home_goals,
            'away_goals': away_goals,
            'home_goals_90': home_goals,
            'away_goals_90': away_goals,
            'home_goals_et': None,
            'away_goals_et': None,
            'home_penalties': None,
            'away_penalties': None,
            'winner_club_id': winner_id,
            'decided_by': decided_by,
            'events': [],
            'ratings': {},
        }

    def test_raises_on_bye_fixture(self):
        pokal      = _make_league('DFB-Pokal', competition_type='cup')
        cup_season = _make_cup_season(pokal)
        cup_round  = _make_cup_round(cup_season)
        bl         = _make_league('BL2')
        home       = _make_club(bl, 'FC Bye')
        bye = CupFixture.objects.create(
            cup_round=cup_round,
            bracket_position=1,
            home_club=home,
            is_bye=True,
            status=CupFixture.STATUS_BYE,
        )
        with self.assertRaises(CupServiceError):
            simulate_cup_fixture(bye)

    def test_raises_if_already_played(self):
        fixture, home, _ = self._setup()
        fixture.status = CupFixture.STATUS_PLAYED
        fixture.save()
        with self.assertRaises(CupServiceError):
            simulate_cup_fixture(fixture)

    @patch('game.match_engine.simulate_ko_match')
    @patch('game.season_service.write_simulated_match_stats')
    @patch('game.season_service._decrement_suspensions_for_clubs')
    def test_winner_set_correctly(self, mock_dec, mock_stats, mock_sim):
        fixture, home, away = self._setup()
        mock_sim.return_value = self._mock_result(home.pk)
        result = simulate_cup_fixture(fixture)
        self.assertEqual(result.winner_club_id, home.pk)

    @patch('game.match_engine.simulate_ko_match')
    @patch('game.season_service.write_simulated_match_stats')
    @patch('game.season_service._decrement_suspensions_for_clubs')
    def test_status_set_to_played(self, mock_dec, mock_stats, mock_sim):
        fixture, home, _ = self._setup()
        mock_sim.return_value = self._mock_result(home.pk)
        result = simulate_cup_fixture(fixture)
        self.assertEqual(result.status, CupFixture.STATUS_PLAYED)

    @patch('game.match_engine.simulate_ko_match')
    @patch('game.season_service.write_simulated_match_stats')
    @patch('game.season_service._decrement_suspensions_for_clubs')
    def test_decided_by_penalties_stored(self, mock_dec, mock_stats, mock_sim):
        fixture, home, away = self._setup()
        mock_sim.return_value = {
            **self._mock_result(home.pk, decided_by='penalties'),
            'home_penalties': 5,
            'away_penalties': 4,
            'home_goals_et': 1,
            'away_goals_et': 1,
        }
        result = simulate_cup_fixture(fixture)
        self.assertEqual(result.decided_by, 'penalties')
        self.assertEqual(result.home_penalties, 5)


# ── 6. advance_cup_round ─────────────────────────────────────────────────────

class AdvanceCupRoundTests(TestCase):

    def _setup_played_round(self, n=4):
        pokal      = _make_league('Pokal Advance', competition_type='cup')
        cup_season = _make_cup_season(pokal)
        cup_round  = _make_cup_round(cup_season, round_number=1, round_code='quarter_final')
        bl         = _make_league('BL Adv')
        clubs      = [_make_club(bl, f'Team-A-{i:02d}') for i in range(n)]
        for i in range(0, n, 2):
            home, away = clubs[i], clubs[i+1]
            CupFixture.objects.create(
                cup_round=cup_round,
                bracket_position=i//2 + 1,
                home_club=home,
                away_club=away,
                winner_club=home,
                is_bye=False,
                status=CupFixture.STATUS_PLAYED,
                decided_by='regular_time',
            )
        return cup_round, clubs

    def test_creates_next_round(self):
        cup_round, _ = self._setup_played_round(4)
        next_round = advance_cup_round(cup_round)
        self.assertIsNotNone(next_round)
        self.assertEqual(next_round.round_number, 2)

    def test_current_round_marked_completed(self):
        cup_round, _ = self._setup_played_round(4)
        advance_cup_round(cup_round)
        cup_round.refresh_from_db()
        self.assertEqual(cup_round.status, CupRound.STATUS_COMPLETED)

    def test_raises_if_incomplete_fixtures(self):
        pokal      = _make_league('Pokal Inc', competition_type='cup')
        cup_season = _make_cup_season(pokal)
        cup_round  = _make_cup_round(cup_season)
        bl         = _make_league('BL Inc')
        home       = _make_club(bl, 'TeamI H')
        away       = _make_club(bl, 'TeamI A')
        CupFixture.objects.create(
            cup_round=cup_round,
            bracket_position=1,
            home_club=home,
            away_club=away,
            is_bye=False,
            status=CupFixture.STATUS_SCHEDULED,
        )
        with self.assertRaises(CupRoundNotCompleteError):
            advance_cup_round(cup_round)

    def test_final_returns_none_and_sets_winner(self):
        """Wenn nur 1 Sieger übrig bleibt, ist der Pokal abgeschlossen."""
        pokal      = _make_league('Pokal Final', competition_type='cup')
        cup_season = _make_cup_season(pokal)
        cup_round  = _make_cup_round(cup_season, round_number=5, round_code='final')
        bl         = _make_league('BL Final')
        home       = _make_club(bl, 'Finalist H')
        away       = _make_club(bl, 'Finalist A')
        CupFixture.objects.create(
            cup_round=cup_round,
            bracket_position=1,
            home_club=home,
            away_club=away,
            winner_club=home,
            is_bye=False,
            status=CupFixture.STATUS_PLAYED,
        )
        result = advance_cup_round(cup_round)
        self.assertIsNone(result)
        cup_season.refresh_from_db()
        self.assertEqual(cup_season.winner_club_id, home.pk)
        self.assertEqual(cup_season.status, CupSeason.STATUS_COMPLETED)


# ── 7. schedule_cup_round ────────────────────────────────────────────────────

class ScheduleCupRoundTests(TestCase):

    def _setup(self, season='2025/26'):
        pokal      = _make_league(f'Pokal Sched {season}', competition_type='cup')
        cup_season = _make_cup_season(pokal, season=season)
        cup_round  = _make_cup_round(cup_season)
        return cup_round

    def test_sets_scheduled_date(self):
        cup_round = self._setup()
        schedule_cup_round(cup_round)
        cup_round.refresh_from_db()
        self.assertIsNotNone(cup_round.scheduled_date)

    def test_scheduled_date_is_tuesday_or_wednesday(self):
        cup_round = self._setup(season='2024/25')
        schedule_cup_round(cup_round)
        cup_round.refresh_from_db()
        self.assertIn(cup_round.scheduled_date.weekday(), (1, 2))

    def test_status_set_to_scheduled(self):
        cup_round = self._setup(season='2023/24')
        schedule_cup_round(cup_round)
        cup_round.refresh_from_db()
        self.assertEqual(cup_round.status, CupRound.STATUS_SCHEDULED)

    def test_season_start_date_parser(self):
        """_season_start_date gibt saisonalen August-Startpunkt zurück."""
        from game.cup_service import _season_start_date
        from datetime import date as d
        self.assertEqual(_season_start_date('2025/26'), d(2025, 8, 1))
        self.assertEqual(_season_start_date('2023/24'), d(2023, 8, 1))
        self.assertEqual(_season_start_date('2030'), d(2030, 8, 1))


# ── 8. Fehlerklassen-Hierarchie ───────────────────────────────────────────────

class ErrorHierarchyTests(TestCase):

    def test_cup_service_error_is_base(self):
        self.assertTrue(issubclass(CupRoundAlreadyDrawnError, CupServiceError))
        self.assertTrue(issubclass(CupRoundAlreadyExistsError, CupServiceError))
        self.assertTrue(issubclass(CupRoundNotCompleteError, CupServiceError))
        self.assertTrue(issubclass(CupInvalidParticipantsError, CupServiceError))

    def test_cup_service_error_catchable_as_exception(self):
        with self.assertRaises(Exception):
            raise CupServiceError('test')
