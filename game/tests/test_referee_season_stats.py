from django.test import TestCase
from django.template.loader import render_to_string

from game.models import Club, GameSeasonState, League, Referee, SimulatedMatch
from game.referee_season_stats import current_referee_stats


class RefereeSeasonStatsTests(TestCase):
    def setUp(self):
        GameSeasonState.objects.all().delete()
        self.state = GameSeasonState.objects.create(current_season=7)
        league = League.objects.create(name='Statistikliga', country='Deutschland')
        self.home = Club.objects.create(name='Statistikheim', short_name='Heim', league=league, founded_year=1900, budget=0)
        self.away = Club.objects.create(name='Statistikgast', short_name='Gast', league=league, founded_year=1900, budget=0)
        self.ref = Referee.objects.create(name='Statistikref', vorsaison_spiele=99, vorsaison_rot=99)
        self.peer = Referee.objects.create(name='Vergleich', nationality='Frankreich')

    def match(self, ref=None, yellow=4, red=0, goals=None, **kwargs):
        report = kwargs.pop('report_data', {
            'match_stats': {'home_yellow': yellow, 'away_yellow': 0, 'home_red': red, 'away_red': 0},
            'goal_events': [] if goals is None else goals,
        })
        return SimulatedMatch.objects.create(
            referee=ref or self.ref, home_club=self.home, away_club=self.away,
            season=kwargs.pop('season', '7'), report_data=report, **kwargs,
        )

    def metrics(self):
        return {metric['label']: metric for metric in current_referee_stats(self.ref.pk)['metrics']}

    def test_only_current_season_no_historical_profile_fallback(self):
        self.match(season='6', yellow=99, red=99)
        self.match(report_data={})  # a placeholder is not a played report
        result = current_referee_stats(self.ref.pk)
        self.assertEqual(result['games'], 0)
        self.assertEqual(result['metrics'], [])
        self.assertIn('Noch keine Einsätze', result['message'])

    def test_all_competitions_and_all_referees_contribute(self):
        for _ in range(5):
            self.match(yellow=10, red=2, match_type='liga')
        for _ in range(20):
            self.match(self.peer, yellow=2, red=0, match_type='pokal')
        rows = self.metrics()
        self.assertEqual(rows['Spiele']['value'], '5')
        self.assertEqual(rows['Ø Gelb']['value'], '10,0')
        self.assertEqual(rows['Rot']['value'], '10')
        self.assertEqual(rows['Ø Gelb']['class_name'], 'is-high')
        self.assertIn('gesamte Sim: 3.60', rows['Ø Gelb']['detail'])
        self.assertEqual(rows['Rot']['class_name'], 'is-high')

    def test_color_compares_rates_not_raw_totals(self):
        for _ in range(5):
            self.match(red=1)
        for _ in range(15):
            self.match(self.peer, red=1)
        self.assertEqual(self.metrics()['Rot']['class_name'], '')

    def test_few_appearances_and_self_only_stay_neutral(self):
        self.match(yellow=40)
        for _ in range(10):
            self.match(self.peer, yellow=2)
        self.assertEqual(self.metrics()['Ø Gelb']['class_name'], '')
        SimulatedMatch.objects.filter(referee=self.peer).delete()
        for _ in range(5):
            self.match(yellow=40)
        self.assertEqual(self.metrics()['Ø Gelb']['class_name'], '')

    def test_low_and_moderately_high_values(self):
        for _ in range(5):
            self.match(yellow=2)
            self.match(self.peer, yellow=6)
        self.assertEqual(self.metrics()['Ø Gelb']['class_name'], 'is-low')
        SimulatedMatch.objects.filter(referee=self.ref).update(
            report_data={'match_stats': {'home_yellow': 12, 'away_yellow': 0, 'home_red': 0, 'away_red': 0},
                         'goal_events': []},
        )
        self.assertEqual(self.metrics()['Ø Gelb']['class_name'], 'is-elevated')

    def test_missing_or_invalid_cards_do_not_become_zero(self):
        self.match()
        self.match(report_data={'match_stats': {'home_yellow': -1}, 'goal_events': []})
        rows = self.metrics()
        self.assertEqual(rows['Ø Gelb']['value'], '—')
        self.assertEqual(rows['Rot']['value'], '—')
        self.assertEqual(rows['Ø Gelb']['class_name'], '')

    def test_penalty_goals_not_shootout_and_disputes_not_invented(self):
        self.match(report_data={
            'match_stats': {'home_yellow': 0, 'away_yellow': 0, 'home_red': 0, 'away_red': 0},
            'goal_events': [{'goal_type': 'penalty_sp'}, {'goal_type': 'goal'},
                            {'goal_type': 'penalty_sp', 'minute': 112}],
            'penalty_events': [{'type': 'penalty_scored'}, {'type': 'penalty_missed'}],
        })
        rows = self.metrics()
        self.assertEqual(rows['Elfmeter-Tore']['value'], '2')
        self.assertEqual(rows['Umstritten']['value'], '—')
        self.assertIn('nicht erfasst', rows['Umstritten']['detail'])

    def test_old_goals_without_goal_types_are_not_assumed_non_penalties(self):
        self.match(goals=[{'minute': 35, 'scorer_name': 'Altbestand'}])
        self.assertEqual(self.metrics()['Elfmeter-Tore']['value'], '—')

    def test_missing_goal_events_and_missing_season_are_explicit(self):
        self.match(report_data={'match_stats': {'home_yellow': 0, 'away_yellow': 0,
                                               'home_red': 0, 'away_red': 0}})
        self.assertEqual(self.metrics()['Elfmeter-Tore']['value'], '—')
        self.state.delete()
        self.assertFalse(current_referee_stats(self.ref.pk)['available'])

    def test_render_actual_season_values_and_color_explanation(self):
        self.match()
        stats = current_referee_stats(self.ref.pk)
        html = render_to_string('game/club_match_preview.html', {
            'preview': {'has_fixture': True, 'home': {'name': 'Heim'}, 'away': {'name': 'Gast'},
                        'opponent': {'name': 'Gast'},
                        'referee': {'name': 'Statistikref', 'season_stats': stats}},
        })
        self.assertIn('Aktuelle Saison · 7', html)
        self.assertIn('gesamte Sim', html)
        self.assertIn('Elfmeter-Tore', html)
        self.assertIn('mp-referee-season-values', html)
        self.assertNotIn('99', html)
