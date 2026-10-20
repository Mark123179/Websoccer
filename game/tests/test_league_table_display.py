from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from game.league_table import display_standings
from game.models import Club, League


class PreparationTableTests(SimpleTestCase):
    def setUp(self):
        self.league = League(pk=19, name="1. Bundesliga")

    def test_real_standings_always_take_precedence(self):
        row = SimpleNamespace(points=12, played=4)
        self.assertEqual(display_standings(self.league, "0", [row]), [row])

    def test_later_missing_season_is_not_fabricated(self):
        self.assertEqual(display_standings(self.league, "1", []), [])

    @patch("game.league_table.GameSeasonState.objects")
    def test_started_game_does_not_get_a_zero_table(self, states):
        states.only.return_value.first.return_value = SimpleNamespace(is_started=True)
        self.assertEqual(display_standings(self.league, "0", []), [])

    @patch("game.league_table.SeasonFixture.objects")
    @patch("game.league_table.GameSeasonState.objects")
    def test_played_fixtures_do_not_get_a_zero_table(self, states, fixtures):
        states.only.return_value.first.return_value = SimpleNamespace(is_started=False)
        fixtures.filter.return_value.exists.return_value = True
        self.assertEqual(display_standings(self.league, "0", []), [])

    @patch("game.club_import.runtime.visible_clubs")
    @patch("game.league_table.SeasonFixture.objects")
    @patch("game.league_table.GameSeasonState.objects")
    def test_preparation_shows_all_clubs_without_persisting(self, states, fixtures, clubs):
        states.only.return_value.first.return_value = SimpleNamespace(is_started=False)
        fixtures.filter.return_value.exists.return_value = False
        expected = [Club(pk=n + 1, name=f"Club {n:02}", league=self.league) for n in range(18)]
        clubs.return_value.filter.return_value.order_by.return_value = expected
        rows = display_standings(self.league, "0", [])
        self.assertEqual([row.club for row in rows], expected)
        self.assertEqual([row.position for row in rows], list(range(1, 19)))
        for row in rows:
            self.assertIsNone(row.pk)
            self.assertEqual((row.played, row.points, row.goals_for, row.goals_against), (0, 0, 0, 0))
        clubs.return_value.filter.assert_called_once_with(league=self.league)
        clubs.return_value.filter.return_value.order_by.assert_called_once_with("name", "pk")
