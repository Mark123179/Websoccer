from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.db import IntegrityError
from django.test import TestCase

from game.models import (
    Club,
    ClubRecord,
    ClubRecordBreak,
    CupFixture,
    CupRound,
    CupSeason,
    DataSource,
    League,
    ManagerCareerEntry,
    ManagerProfile,
    Player,
    PlayerMarketValueSnapshot,
    PlayerSeasonStat,
    PlayerTransferHistory,
    SeasonFixture,
    SimulatedMatch,
)
from game.records.engine import rebuild_for_club
from game.transfer_v2.models import TransferRecord, TransferRecordPlayer
from game.cup_service import simulate_cup_fixture
from game.season_service import simulate_matchday


def make_club(name, league):
    return Club.objects.create(
        name=name,
        short_name=name[:3].upper(),
        founded_year=1900,
        budget=Decimal('0'),
        league=league,
    )


def make_player(club, name, position='ST'):
    first_name, last_name = name.split(' ', 1)
    return Player.objects.create(
        club=club,
        first_name=first_name,
        last_name=last_name,
        position=position,
        age=25,
    )


class HallOfFameRecordEngineTests(TestCase):
    def setUp(self):
        self.league = League.objects.create(name='Ruhmesliga', country='DE')
        self.club = make_club('FC Ruhm', self.league)
        self.opponent = make_club('FC Gegner', self.league)

    def _league_fixture(self, fixture_date, home_goals, away_goals, *, friendly=False):
        simulated = None
        if friendly:
            simulated = SimulatedMatch.objects.create(
                home_club=self.club,
                away_club=self.opponent,
                home_goals=home_goals,
                away_goals=away_goals,
                match_type='freundschaft',
            )
        return SeasonFixture.objects.create(
            league=self.league,
            matchday=1,
            home_club=self.club,
            away_club=self.opponent,
            scheduled_date=fixture_date,
            season='0',
            home_goals=home_goals,
            away_goals=away_goals,
            is_played=True,
            simulated_match=simulated,
        )

    def test_seed_is_preserved_and_first_rebuild_writes_no_break(self):
        player = make_player(self.club, 'Erik Rekord')
        PlayerSeasonStat.objects.create(
            player=player, club=self.club, season='0', competition='Liga',
            matches=1, goals=4,
        )
        ClubRecord.objects.create(
            club=self.club,
            record_key='top_scorer',
            source=ClubRecord.SOURCE_SEED,
            value_numeric=Decimal('99'),
            value_display='99',
            holder_name='Historische Legende',
            source_note='Archiv',
        )

        result = rebuild_for_club(self.club)

        self.assertGreater(result['created'], 0)
        self.assertEqual(ClubRecordBreak.objects.count(), 0)
        seed = ClubRecord.objects.get(
            club=self.club,
            record_key='top_scorer',
            source=ClubRecord.SOURCE_SEED,
        )
        self.assertEqual(seed.value_numeric, Decimal('99'))
        sim = ClubRecord.objects.get(
            club=self.club,
            record_key='top_scorer',
            source=ClubRecord.SOURCE_SIM,
        )
        self.assertEqual(sim.holder_player, player)
        self.assertEqual(sim.value_numeric, Decimal('4'))

    def test_rebuild_is_idempotent_then_logs_actual_record_change(self):
        player = make_player(self.club, 'Erik Rekord')
        stat = PlayerSeasonStat.objects.create(
            player=player, club=self.club, season='0', competition='Liga',
            matches=3, goals=4,
        )

        rebuild_for_club(self.club)
        unchanged = rebuild_for_club(self.club)
        self.assertEqual(unchanged['changed'], 0)
        self.assertEqual(ClubRecordBreak.objects.count(), 0)

        stat.goals = 5
        stat.save(update_fields=['goals'])
        rebuild_for_club(self.club)

        record = ClubRecord.objects.get(
            club=self.club,
            record_key='top_scorer',
            source=ClubRecord.SOURCE_SIM,
        )
        break_event = ClubRecordBreak.objects.get(
            club=self.club, record_key='top_scorer',
        )
        self.assertEqual(record.value_numeric, Decimal('5'))
        self.assertEqual(break_event.old_value_numeric, Decimal('4'))
        self.assertEqual(break_event.new_value_numeric, Decimal('5'))

    def test_friendlies_are_strictly_excluded_and_source_date_is_kept(self):
        historic_date = date(2026, 8, 1)
        self._league_fixture(historic_date, 2, 0)
        self._league_fixture(historic_date + timedelta(days=1), 10, 0, friendly=True)

        rebuild_for_club(self.club)

        record = ClubRecord.objects.get(
            club=self.club,
            record_key='biggest_win',
            source=ClubRecord.SOURCE_SIM,
        )
        self.assertEqual(record.value_display, '2:0')
        self.assertEqual(record.record_date, historic_date)

    def test_best_ppg_requires_thirty_league_matches(self):
        manager = ManagerProfile.objects.create(name='Punktesammler')
        ManagerCareerEntry.objects.create(
            manager=manager,
            club=self.club,
            started_at=date(2026, 1, 1),
            ended_at=date(2026, 12, 31),
            active=False,
        )
        for matchday in range(1, 30):
            SeasonFixture.objects.create(
                league=self.league,
                matchday=matchday,
                home_club=self.club,
                away_club=self.opponent,
                scheduled_date=date(2026, 1, 1) + timedelta(days=matchday),
                season='0',
                home_goals=1,
                away_goals=0,
                is_played=True,
            )

        rebuild_for_club(self.club)

        self.assertFalse(ClubRecord.objects.filter(
            club=self.club,
            record_key='best_ppg_coach',
            source=ClubRecord.SOURCE_SIM,
        ).exists())

    def test_record_source_is_unique_per_club_and_key(self):
        ClubRecord.objects.create(
            club=self.club,
            record_key='record_sale',
            source=ClubRecord.SOURCE_SIM,
            value_numeric=Decimal('1'),
            value_display='1',
            holder_name='A',
        )
        with self.assertRaises(IntegrityError):
            ClubRecord.objects.create(
                club=self.club,
                record_key='record_sale',
                source=ClubRecord.SOURCE_SIM,
                value_numeric=Decimal('2'),
                value_display='2',
                holder_name='B',
            )

    def test_penalty_win_extends_a_competitive_win_streak(self):
        today = date(2026, 8, 1)
        self._league_fixture(today, 1, 0)
        cup = CupSeason.objects.create(
            competition=League.objects.create(
                name='Ruhmespokal',
                country='DE',
                competition_type=League.COMPETITION_TYPE_CUP,
            ),
            season='0',
        )
        round_obj = CupRound.objects.create(
            cup_season=cup,
            round_number=1,
            round_code='final',
            scheduled_date=today + timedelta(days=1),
            status=CupRound.STATUS_COMPLETED,
        )
        CupFixture.objects.create(
            cup_round=round_obj,
            bracket_position=1,
            home_club=self.club,
            away_club=self.opponent,
            winner_club=self.club,
            status=CupFixture.STATUS_PLAYED,
            home_goals_90=1,
            away_goals_90=1,
            home_goals_et=0,
            away_goals_et=0,
            home_penalties=5,
            away_penalties=4,
            decided_by=CupFixture.DECIDED_BY_PENALTIES,
        )

        rebuild_for_club(self.club)

        record = ClubRecord.objects.get(
            club=self.club,
            record_key='longest_win_streak',
            source=ClubRecord.SOURCE_SIM,
        )
        self.assertEqual(record.value_numeric, Decimal('2'))

    @patch('game.match_engine.simulate_ko_match')
    @patch('game.season_service.write_simulated_match_stats')
    @patch('game.season_service._decrement_suspensions_for_clubs')
    def test_cup_simulation_refreshes_both_clubs_immediately(
        self, mock_decrement, mock_stats, mock_simulate,
    ):
        cup = CupSeason.objects.create(
            competition=League.objects.create(
                name='Ruhmespokal Rebuild',
                country='DE',
                competition_type=League.COMPETITION_TYPE_CUP,
            ),
            season='0',
        )
        round_obj = CupRound.objects.create(
            cup_season=cup,
            round_number=1,
            round_code='quarter_final',
            scheduled_date=date(2026, 8, 3),
            status=CupRound.STATUS_SCHEDULED,
        )
        fixture = CupFixture.objects.create(
            cup_round=round_obj,
            bracket_position=1,
            home_club=self.club,
            away_club=self.opponent,
            status=CupFixture.STATUS_SCHEDULED,
        )
        mock_simulate.return_value = {
            'home_goals': 2,
            'away_goals': 0,
            'home_goals_90': 2,
            'away_goals_90': 0,
            'home_goals_et': None,
            'away_goals_et': None,
            'home_penalties': None,
            'away_penalties': None,
            'winner_club_id': self.club.pk,
            'decided_by': 'regular_time',
            'events': [],
            'ratings': {},
        }

        simulate_cup_fixture(fixture)

        self.assertTrue(
            ClubRecord.objects.filter(
                club=self.club,
                record_key='biggest_win',
                source=ClubRecord.SOURCE_SIM,
            ).exists(),
            list(ClubRecord.objects.filter(club=self.club).values_list('record_key', flat=True)),
        )
        win = ClubRecord.objects.get(
            club=self.club,
            record_key='biggest_win',
            source=ClubRecord.SOURCE_SIM,
        )
        defeat = ClubRecord.objects.get(
            club=self.opponent,
            record_key='biggest_defeat',
            source=ClubRecord.SOURCE_SIM,
        )
        self.assertEqual(win.value_display, '2:0')
        self.assertEqual(defeat.value_display, '0:2')

    @patch('game.match_engine.simulate_match')
    @patch('game.economy.matchday_run.run_matchday_finance')
    @patch('game.economy.ai_buyer.run_ai_buyer_matchday')
    def test_league_service_refreshes_both_clubs_immediately(
        self, mock_ai_buyer, mock_finance, mock_simulate,
    ):
        SeasonFixture.objects.create(
            league=self.league,
            matchday=1,
            home_club=self.club,
            away_club=self.opponent,
            scheduled_date=date(2026, 8, 4),
            season='0',
            is_played=False,
        )
        mock_simulate.return_value = {
            'home_goals': 3,
            'away_goals': 0,
            'events': [],
            'ratings': {},
        }
        mock_finance.return_value = {'errors': []}

        result = simulate_matchday(self.league, '0', 1)
        self.assertEqual(result['errors'], [])
        self.assertEqual(len(result['simulated']), 1)
        win = ClubRecord.objects.get(
            club=self.club,
            record_key='biggest_win',
            source=ClubRecord.SOURCE_SIM,
        )
        defeat = ClubRecord.objects.get(
            club=self.opponent,
            record_key='biggest_defeat',
            source=ClubRecord.SOURCE_SIM,
        )
        self.assertEqual(win.value_display, '3:0')
        self.assertEqual(defeat.value_display, '0:3')

    def test_score_tie_uses_winner_goals_before_the_date(self):
        older = date(2026, 8, 1)
        self._league_fixture(older, 4, 0)
        self._league_fixture(older + timedelta(days=1), 5, 1)

        rebuild_for_club(self.club)

        record = ClubRecord.objects.get(
            club=self.club,
            record_key='biggest_win',
            source=ClubRecord.SOURCE_SIM,
        )
        self.assertEqual(record.value_display, '5:1')

    def test_disappearing_materialized_record_is_audited_as_revocation(self):
        player = make_player(self.club, 'Erik Rekord')
        stat = PlayerSeasonStat.objects.create(
            player=player, club=self.club, season='0', competition='Liga',
            matches=1, goals=1,
        )
        rebuild_for_club(self.club)

        stat.delete()
        rebuild_for_club(self.club)

        self.assertFalse(ClubRecord.objects.filter(
            club=self.club,
            record_key='top_scorer',
            source=ClubRecord.SOURCE_SIM,
        ).exists())
        revocation = ClubRecordBreak.objects.get(
            club=self.club,
            record_key='top_scorer',
        )
        self.assertEqual(revocation.old_value_numeric, Decimal('1'))
        self.assertIsNone(revocation.new_value_numeric)
        self.assertEqual(revocation.new_value_display, '')

    def test_v2_transfer_history_materializes_signing_and_sale_for_both_clubs(self):
        player = make_player(self.club, 'Erik Rekord')
        transfer = TransferRecord.objects.create(
            date=date(2026, 8, 2),
            kind=TransferRecord.KIND_CASH,
            timing='SOFORT',
            club_a=self.club,
            club_b=self.opponent,
            cash_b=Decimal('1234567.00'),
        )
        TransferRecordPlayer.objects.create(
            record=transfer,
            player=player,
            side=TransferRecordPlayer.SIDE_A,
            market_value_at_transfer=Decimal('2000000'),
        )
        cancelled_transfer = TransferRecord.objects.create(
            date=date(2026, 8, 3),
            kind=TransferRecord.KIND_CASH,
            timing='SOFORT',
            club_a=self.club,
            club_b=self.opponent,
            cash_b=Decimal('9999999.00'),
            is_cancelled=True,
        )
        TransferRecordPlayer.objects.create(
            record=cancelled_transfer,
            player=player,
            side=TransferRecordPlayer.SIDE_A,
        )

        rebuild_for_club(self.club)
        rebuild_for_club(self.opponent)

        sale = ClubRecord.objects.get(
            club=self.club,
            record_key='record_sale',
            source=ClubRecord.SOURCE_SIM,
        )
        signing = ClubRecord.objects.get(
            club=self.opponent,
            record_key='record_signing',
            source=ClubRecord.SOURCE_SIM,
        )
        self.assertEqual(sale.value_numeric, Decimal('1234567.00'))
        self.assertEqual(signing.value_numeric, Decimal('1234567.00'))
        self.assertEqual(sale.record_date, date(2026, 8, 2))
        self.assertEqual(signing.holder_player, player)

    def test_market_value_before_a_documented_sale_stays_with_original_club(self):
        player = make_player(self.opponent, 'Erik Rekord')
        source, _ = DataSource.objects.get_or_create(
            code=DataSource.CODE_WEBSOCCER,
            defaults={'name': 'Testquelle'},
        )
        PlayerMarketValueSnapshot.objects.create(
            player=player,
            source=source,
            recorded_at=date(2026, 8, 1),
            value_eur=Decimal('7500000'),
            update_current=False,
        )
        PlayerTransferHistory.objects.create(
            player=player,
            transfer_date=date(2026, 8, 2),
            from_club=self.club,
            to_club=self.opponent,
            fee_eur=Decimal('1000000'),
        )

        rebuild_for_club(self.club)

        record = ClubRecord.objects.get(
            club=self.club,
            record_key='highest_market_value',
            source=ClubRecord.SOURCE_SIM,
        )
        self.assertEqual(record.holder_player, player)
        self.assertEqual(record.value_numeric, Decimal('7500000'))
        self.assertEqual(record.record_date, date(2026, 8, 1))

    def test_seed_break_marks_event_and_is_the_only_news_trigger(self):
        player = make_player(self.club, 'Erik Rekord')
        stat = PlayerSeasonStat.objects.create(
            player=player, club=self.club, season='0', competition='Liga',
            matches=4, goals=4,
        )
        ClubRecord.objects.create(
            club=self.club,
            record_key='top_scorer',
            source=ClubRecord.SOURCE_SEED,
            value_numeric=Decimal('5'),
            value_display='5',
            holder_name='Archivspieler',
        )
        rebuild_for_club(self.club)
        self.assertEqual(ClubRecordBreak.objects.count(), 0)

        stat.goals = 6
        stat.save(update_fields=['goals'])
        rebuild_for_club(self.club)

        event = ClubRecordBreak.objects.get(
            club=self.club, record_key='top_scorer',
        )
        self.assertTrue(event.broke_seed)
        self.assertEqual(self.club.public_news.filter(category='Ruhmeshalle').count(), 1)