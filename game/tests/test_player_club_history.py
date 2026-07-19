"""Tests für die Vereinsstationen-Historie (Phase 0 Finanzsystem)."""

from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from game.club_history import record_club_stint, snapshot_season
from game.models import (
    Club,
    GameSeasonState,
    League,
    Player,
    PlayerClubHistory,
)


def _league(name='Historie Liga'):
    return League.objects.create(name=name, country='Deutschland')


def _club(league, name):
    return Club.objects.create(
        name=name,
        short_name=name[:20],
        founded_year=1900,
        budget=1_000_000,
        fan_popularity=50,
        league=league,
    )


def _player(first_name, last_name, club=None, **kwargs):
    defaults = {
        'age': 20,
        'position': 'ZM',
        'primary_position': 'ZM',
        'main_position_1': 'ZM',
        'potential': 70,
        'salary_per_match': 1000,
        'club': club,
    }
    defaults.update(kwargs)
    return Player.objects.create(
        first_name=first_name,
        last_name=last_name,
        **defaults,
    )


class PlayerClubHistoryTrackingTest(TestCase):
    def setUp(self):
        self.league = _league()
        self.club_a = _club(self.league, 'FC Alpha')
        self.club_b = _club(self.league, 'FC Beta')
        GameSeasonState.objects.all().delete()
        GameSeasonState.objects.create(current_season=0, is_started=False)

    def test_create_player_with_club_records_stint(self):
        player = _player('Max', 'Muster', club=self.club_a)
        self.assertTrue(
            PlayerClubHistory.objects.filter(
                player=player, club=self.club_a, season=0
            ).exists()
        )

    def test_create_clubless_player_records_nothing(self):
        player = _player('Ohne', 'Verein', club=None)
        self.assertEqual(player.club_history.count(), 0)

    def test_club_change_records_new_stint(self):
        player = _player('Max', 'Wechsler', club=self.club_a)
        loaded = Player.objects.get(pk=player.pk)
        loaded.club = self.club_b
        loaded.save()
        seasons_clubs = set(
            loaded.club_history.values_list('club_id', 'season')
        )
        self.assertEqual(
            seasons_clubs,
            {(self.club_a.pk, 0), (self.club_b.pk, 0)},
        )

    def test_change_to_clubless_records_nothing_new(self):
        player = _player('Bald', 'Vereinslos', club=self.club_a)
        loaded = Player.objects.get(pk=player.pk)
        loaded.club = None
        loaded.save()
        self.assertEqual(loaded.club_history.count(), 1)

    def test_resave_without_change_is_idempotent(self):
        player = _player('Stabil', 'Bleibt', club=self.club_a)
        loaded = Player.objects.get(pk=player.pk)
        loaded.save()
        loaded.save()
        self.assertEqual(loaded.club_history.count(), 1)

    def test_return_to_same_club_same_season_no_duplicate(self):
        player = _player('Hin', 'Undzurueck', club=self.club_a)
        loaded = Player.objects.get(pk=player.pk)
        loaded.club = self.club_b
        loaded.save()
        loaded.club = self.club_a
        loaded.save()
        self.assertEqual(loaded.club_history.count(), 2)

    def test_suppress_flag_blocks_recording(self):
        player = _player('Kein', 'Eintrag', club=None)
        loaded = Player.objects.get(pk=player.pk)
        loaded.club = self.club_a
        loaded._suppress_club_history = True
        loaded.save()
        self.assertEqual(loaded.club_history.count(), 0)

    def test_karrierende_club_records_nothing(self):
        karrierende = _club(self.league, 'Karrierende')
        player = _player('Alte', 'Legende', club=self.club_a)
        loaded = Player.objects.get(pk=player.pk)
        loaded.club = karrierende
        loaded.save()
        self.assertEqual(loaded.club_history.count(), 1)
        self.assertEqual(loaded.club_history.first().club_id, self.club_a.pk)

    def test_record_club_stint_returns_created_flag(self):
        player = _player('Direkt', 'Aufruf', club=None)
        self.assertTrue(record_club_stint(player.pk, self.club_a.pk, season=3))
        self.assertFalse(record_club_stint(player.pk, self.club_a.pk, season=3))

    def test_only_load_without_club_triggers_no_extra_queries(self):
        for i in range(3):
            _player(f'Deferred{i}', 'Spieler', club=self.club_a)
        with self.assertNumQueries(1):
            list(
                Player.objects.only('pk', 'main_position_1')
                .filter(club=self.club_a)
            )

    def test_deferred_load_then_club_change_still_records(self):
        player = _player('Deferred', 'Wechsler', club=self.club_a)
        loaded = Player.objects.only('pk', 'first_name').get(pk=player.pk)
        loaded.club = self.club_b
        loaded.save()
        self.assertTrue(
            PlayerClubHistory.objects.filter(
                player=player, club=self.club_b, season=0
            ).exists()
        )


class SeasonSnapshotTest(TestCase):
    def setUp(self):
        self.league = _league()
        self.club_a = _club(self.league, 'FC Alpha')
        self.karrierende = _club(self.league, 'Karrierende')
        GameSeasonState.objects.all().delete()
        self.state = GameSeasonState.objects.create(
            current_season=0, is_started=True
        )

    def test_snapshot_season_creates_rows_for_players_with_club(self):
        p1 = _player('Eins', 'Spieler', club=self.club_a)
        p2 = _player('Zwei', 'Vereinslos', club=None)
        p3 = _player('Drei', 'Rentner', club=self.karrierende)
        PlayerClubHistory.objects.all().delete()

        created = snapshot_season(5)
        self.assertEqual(created, 1)
        self.assertTrue(
            PlayerClubHistory.objects.filter(
                player=p1, club=self.club_a, season=5
            ).exists()
        )
        self.assertFalse(
            PlayerClubHistory.objects.filter(player=p2).exists()
        )
        self.assertFalse(
            PlayerClubHistory.objects.filter(player=p3).exists()
        )

    def test_snapshot_is_idempotent(self):
        _player('Eins', 'Spieler', club=self.club_a)
        self.assertEqual(snapshot_season(7), 1)
        self.assertEqual(snapshot_season(7), 0)

    def test_season_advance_triggers_snapshot(self):
        player = _player('Saison', 'Springer', club=self.club_a)
        PlayerClubHistory.objects.all().delete()

        self.state.current_season = 1
        self.state.save()

        self.assertTrue(
            PlayerClubHistory.objects.filter(
                player=player, club=self.club_a, season=1
            ).exists()
        )

    def test_is_started_toggle_does_not_snapshot(self):
        _player('Nur', 'Start', club=self.club_a)
        PlayerClubHistory.objects.all().delete()

        self.state.is_started = False
        self.state.save()
        self.state.is_started = True
        self.state.save()

        self.assertEqual(PlayerClubHistory.objects.count(), 0)


class SeedCommandTest(TestCase):
    def setUp(self):
        self.league = _league()
        self.club_a = _club(self.league, 'FC Alpha')
        GameSeasonState.objects.all().delete()
        GameSeasonState.objects.create(current_season=0, is_started=False)

    def test_seed_command_is_idempotent(self):
        _player('Genesis', 'Spieler', club=self.club_a)
        PlayerClubHistory.objects.all().delete()

        out = StringIO()
        call_command('seed_player_club_history', stdout=out)
        self.assertIn('1 neue Vereinsstationen', out.getvalue())
        self.assertEqual(PlayerClubHistory.objects.count(), 1)

        out2 = StringIO()
        call_command('seed_player_club_history', stdout=out2)
        self.assertIn('0 neue Vereinsstationen', out2.getvalue())
        self.assertEqual(PlayerClubHistory.objects.count(), 1)

    def test_seed_command_with_explicit_season(self):
        _player('Explizit', 'Saison', club=self.club_a)
        PlayerClubHistory.objects.all().delete()

        call_command('seed_player_club_history', '--season', '4', stdout=StringIO())
        self.assertTrue(
            PlayerClubHistory.objects.filter(season=4).exists()
        )
