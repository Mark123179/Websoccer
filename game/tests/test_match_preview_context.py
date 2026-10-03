"""Briefing data must describe the real opponent without changing the game."""
from datetime import date, time
from decimal import Decimal
from types import SimpleNamespace as NS
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings

from game import match_preview as briefing
from game.models import Player


def player(pk, name='Spieler', value=Decimal('1000000'), **kwargs):
    return Player(
        pk=pk, first_name=name, last_name='Test', position='ST',
        market_value=value, fm_inside_id=123000 + pk, **kwargs,
    )


def club(pk, name, fm_id):
    news = MagicMock()
    news.filter.return_value.order_by.return_value.__getitem__.return_value = []
    return NS(
        pk=pk, name=name, short_name=name, fm_inside_id=fm_id,
        crest_static_path=f'/assets/{fm_id}.png', managed_by=None,
        kit_static_paths=[
            {'label': 'Heim', 'path': f'/{fm_id}-home.png'},
            {'label': 'Auswärts', 'path': f'/{fm_id}-away.png'},
        ],
        public_profile=NS(city_name=name + '-Stadt', stadium_name=name + '-Arena',
                          stadium_image_static_path=''),
        stadium=None, public_news=news,
    )


@override_settings(ASSETS_BASE_URL='/assets/')
class MatchPreviewImageTests(SimpleTestCase):
    def test_missing_pack_uses_existing_same_identity_photo(self):
        with patch('game.match_preview.Path.is_file', return_value=False), \
                patch('game.match_preview.finders.find', return_value='/known/photo.png') as finder:
            self.assertEqual(
                briefing._report_portrait('/static/assets/players/face_987.png'),
                '/static/game/images/players/987.png',
            )
            finder.assert_called_once_with('game/images/players/987.png')

    def test_existing_canonical_image_has_priority(self):
        with patch('game.match_preview.Path.is_file', return_value=True), \
                patch('game.match_preview.finders.find') as finder:
            self.assertEqual(
                briefing._report_portrait('/assets/players/face_987.png'),
                '/assets/players/face_987.png',
            )
            finder.assert_not_called()

    def test_external_photo_is_not_replaced(self):
        with patch('game.match_preview.finders.find') as finder:
            url = 'https://example.test/players/face_987.png'
            self.assertEqual(briefing._report_portrait(url), url)
            finder.assert_not_called()

    def test_missing_pack_without_legacy_photo_keeps_canonical_identity(self):
        with patch('game.match_preview.Path.is_file', return_value=False), \
                patch('game.match_preview.finders.find', return_value=None):
            self.assertEqual(
                briefing._report_portrait('/assets/players/face_987.png'),
                '/assets/players/face_987.png',
            )

    def test_formation_display_keeps_each_populated_snapshot_line(self):
        self.assertEqual(briefing._formation_label('4n-2-0-1-3'), '4-2-1-3')
        self.assertEqual(briefing._formation_label('3n-3-2-0-2'), '3-3-2-2')
        self.assertEqual(briefing._formation_label('unknown'), '')
        self.assertEqual(briefing._formation_label('4n-3-5-0-2'), '')


class MatchPreviewContextTests(SimpleTestCase):
    def setUp(self):
        self.home = club(2, 'Heim', 915)
        self.away = club(3, 'Gast', 907)
        self.fixture = NS(
            home_club=self.home, away_club=self.away, matchday=9,
            scheduled_date=date(2026, 10, 3), scheduled_time=time(18, 30),
            simulated_match_id=None,
        )

    def context(self, viewed=None, players=(), last=None, day_weather=None):
        with (
            patch.object(briefing.Player.objects, 'filter') as squad,
            patch.object(briefing, '_season_leaders', return_value=[]),
            patch.object(briefing, 'get_form_rows', return_value=[]),
            patch.object(briefing, '_last_report', return_value=last or (None, {}, '')),
            patch.object(briefing.DayWeather.objects, 'filter') as weather,
            patch.object(briefing.Player.objects, 'in_bulk', return_value={}),
        ):
            squad.return_value.order_by.return_value = list(players)
            weather.return_value.first.return_value = day_weather
            result = briefing.build_match_preview_context(viewed or self.home, self.fixture)
            if self.fixture:
                expected = self.away if (viewed or self.home).pk == self.home.pk else self.home
                squad.assert_called_once_with(club=expected)
            else:
                squad.assert_not_called()
            return result

    def test_home_role_uses_away_opponent_and_actual_home_venue(self):
        result = self.context()
        self.assertEqual(result['opponent']['id'], 3)
        self.assertEqual(result['stadium']['name'], 'Heim-Arena')
        self.assertEqual(result['home']['kit_url'], '/915-home.png')
        self.assertEqual(result['away']['kit_url'], '/907-away.png')
        self.assertTrue(result['stadium']['model_available'])
        self.assertTrue(result['stadium']['model_is_demo'])
        self.assertEqual(result['time_label'], '18:30 Uhr')

    def test_away_role_still_uses_home_stadium_and_reverses_opponent(self):
        result = self.context(self.away)
        self.assertEqual(result['opponent']['id'], 2)
        self.assertEqual(result['stadium']['location'], 'Heim-Stadt')

    def test_home_dortmund_model_is_not_misattributed_as_other_venue(self):
        self.fixture.home_club, self.fixture.away_club = self.away, self.home
        result = self.context(self.home)
        self.assertTrue(result['stadium']['model_available'])
        self.assertFalse(result['stadium']['model_is_demo'])
        self.assertIn('dortmund_editor_scene.js', result['stadium']['model_scene_url'])

    def test_no_fixture_never_invents_opponent_or_runs_squad_queries(self):
        self.fixture = None
        result = self.context()
        self.assertFalse(result['has_fixture'])
        self.assertIsNone(result['opponent'])
        self.assertIsNone(result['home'])
        self.assertEqual(result['lineup'], [])
        self.assertEqual(result['absences'], [])
        self.assertIsNone(result['trainer'])
        self.assertIsNone(result['referee'])
        self.assertIsNone(result['weather'])
        self.assertFalse(result['stadium']['model_available'])

    def test_saved_weather_has_priority_over_display_only_demo(self):
        real_weather = {'type': 'rain', 'label': 'Regen', 'temperature': 0}
        with patch.object(briefing, 'weather_context', return_value=real_weather.copy()):
            result = self.context(day_weather=NS(pk=1))
        self.assertEqual(result['weather']['label'], 'Regen')
        self.assertEqual(result['weather']['temperature'], 0)
        self.assertNotIn('is_demo', result['weather'])

    def test_injuries_suspensions_and_unknown_values_are_honest(self):
        hurt = player(1, ws_injury_type='Muskelverletzung', ws_injury_days_remaining=4)
        banned = player(2, ws_suspension_reason='Rot', ws_suspension_matches_remaining=2)
        expired = player(3, value=None, ws_injury_type='Alt', ws_injury_days_remaining=0)
        result = self.context(players=[hurt, banned, expired])
        self.assertEqual([row['kind'] for row in result['absences']], ['injury', 'suspension'])
        self.assertEqual(result['absences'][0]['duration'], '4 Tage')
        self.assertEqual(result['absences'][1]['player']['id'], 2)
        self.assertEqual(result['spotlights'][-1]['player']['id'], 1)
        self.assertTrue(result['referee']['is_demo'])
        self.assertTrue(result['weather']['is_demo'])
        self.assertTrue(result['trainer']['is_demo'])
        self.assertEqual(result['weather']['temperature'], 18)

    def test_future_referee_is_not_borrowed_from_last_match(self):
        result = self.context()
        self.assertTrue(result['referee']['is_demo'])
        self.fixture.simulated_match_id = 9
        referee = NS(name='Angesetzter Referee', face_url=lambda: '/real-ref.png')
        self.fixture.simulated_match = NS(referee=referee)
        result = self.context()
        self.assertEqual(result['referee']['name'], referee.name)
        self.assertEqual(result['referee']['portrait_url'], '/real-ref.png')
        self.assertNotIn('is_demo', result['referee'])

    def test_news_query_is_latest_published_news_not_pinned_sort_order(self):
        self.context()
        self.home.public_news.filter.assert_called_once()
        self.home.public_news.filter.return_value.order_by.assert_called_once_with(
            '-published_at', '-pk',
        )

    @override_settings(MEDIA_URL='/media/')
    def test_trainer_is_responsible_manager_with_real_uploaded_portrait(self):
        self.away.managed_by = NS(
            name='Trainer Test', profile_image='managers/test.png', user=NS(username='coach'),
            trainer_type_label='Laptoptrainer',
        )
        result = self.context()
        self.assertEqual(result['trainer']['portrait_url'], '/media/managers/test.png')
        self.assertEqual(result['trainer']['name'], 'Trainer Test')
        self.assertIn('/manager/coach/', result['trainer']['url'])

    def test_best_last_player_is_opponents_best_grade_even_if_motm_is_other_side(self):
        report = {
            'home_ratings': [{'id': 3, 'name': 'Fremder MOTM', 'rating': 1.0}],
            'away_ratings': [
                {'id': 1, 'name': 'Gegner A', 'rating': 4.2},
                {'id': 2, 'name': 'Gegner B', 'rating': 1.5},
                {'id': 9, 'name': 'Unbewertet', 'rating': None},
            ],
        }
        with patch.object(briefing.Player.objects, 'in_bulk', return_value={}):
            lineup, best = briefing._report_players(report, 'away')
        self.assertEqual(lineup, [])
        self.assertEqual(best['player']['name'], 'Gegner B')
        self.assertEqual(best['value'], 'Note 1,5')

    def test_last_xi_uses_snapshot_formation_and_names_not_current_squad(self):
        report = {
            'away_players': [{'id': p, 'name': f'Snapshot {p}', 'position': 'ST'}
                             for p in range(1, 12)],
            'away_formation': '4n-0-4-0-2',
            'away_ratings': [],
        }
        with patch.object(briefing.Player.objects, 'in_bulk', return_value={1: player(1, 'Heute')}):
            lineup, _ = briefing._report_players(report, 'away')
        self.assertEqual(len(lineup), 11)
        self.assertEqual(lineup[0]['name'], 'Snapshot 1')
        self.assertEqual(lineup[0]['x'], 50)
        self.assertGreater(lineup[0]['y'], lineup[-1]['y'])
        report['away_formation'] = 'unbekannt'
        with patch.object(briefing.Player.objects, 'in_bulk', return_value={}):
            self.assertEqual(briefing._report_players(report, 'away')[0], [])

    def test_season_leaders_are_club_scoped_weighted_and_lower_grade_wins(self):
        rows = [
            NS(player_id=1, goals=2, matches=2, average_grade=Decimal('2.0')),
            NS(player_id=1, goals=1, matches=1, average_grade=Decimal('5.0')),
            NS(player_id=2, goals=2, matches=4, average_grade=Decimal('2.5')),
            NS(player_id=9, goals=100, matches=0, average_grade=None),
        ]
        with (
            patch.object(briefing.GameSeasonState.objects, 'values_list') as season,
            patch.object(briefing.PlayerSeasonStat.objects, 'filter', return_value=rows) as stats,
        ):
            season.return_value.first.return_value = 7
            result = briefing._season_leaders(self.away, [player(1), player(2)])
        stats.assert_called_once_with(club=self.away, player__club=self.away, season_number=7)
        self.assertEqual(result[0]['player']['id'], 1)
        self.assertEqual(result[0]['value'], '3 Tore')
        self.assertEqual(result[1]['player']['id'], 2)
        self.assertEqual(result[1]['value'], 'Ø 2,50')

    def test_grade_and_price_formatting_do_not_treat_missing_as_zero(self):
        for invalid in (None, '', 'NaN', 0, 10):
            self.assertIsNone(briefing._grade(invalid))
        self.assertEqual(briefing._grade('1.2'), 1.2)
        self.assertEqual(briefing._money(Decimal('20000000')), '20,0 Mio. €')
        self.assertEqual(briefing._money(Decimal('125000')), '125.000 €')