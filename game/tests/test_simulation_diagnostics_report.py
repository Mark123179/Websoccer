"""Logik-Tests der Simulation-Diagnose (reine Funktionen + Report-Vertrag)."""
import json

from django.test import TestCase

from game.simulation_diagnostics.report import (
    build_simulation_diagnostics_report, SECTION_KEYS,
)
from game.simulation_diagnostics.constants import DIAGNOSTIC_CORRIDORS
from game.simulation_diagnostics.utils import evaluate_corridor
from game.simulation_diagnostics.balance import build_balance
from game.simulation_diagnostics.features import build_features
from game.simulation_diagnostics.positions import aggregate_positions
from game.simulation_diagnostics.tactics import build_tactics
from game.simulation_diagnostics.ticker import (
    detect_occurred_families, build_ticker_coverage,
)


class ReportContractTests(TestCase):
    def test_report_has_exactly_eight_sections(self):
        report = build_simulation_diagnostics_report()
        self.assertEqual(set(report), set(SECTION_KEYS))
        self.assertEqual(len(report), 8)
        for key in SECTION_KEYS:
            self.assertIn('title', report[key])
            self.assertIn('available', report[key])

    def test_empty_db_yields_nv_not_errors(self):
        report = build_simulation_diagnostics_report()
        # Auf leerer DB sind datengetriebene Abschnitte n/v, brechen aber nicht.
        self.assertFalse(report['recent_matches']['available'])
        self.assertFalse(report['positions']['available'])
        self.assertTrue(report['recent_matches']['note'])

    def test_no_internal_strength_leak(self):
        report = build_simulation_diagnostics_report()
        blob = json.dumps(report, default=str)
        self.assertNotIn('base_strength', blob)
        self.assertNotIn('potential', blob)


class CorridorTests(TestCase):
    def test_goals_per_game_corridor_boundaries(self):
        c = DIAGNOSTIC_CORRIDORS['goals_per_game']
        self.assertEqual(evaluate_corridor(2.5, c), 'green')
        self.assertEqual(evaluate_corridor(2.15, c), 'yellow')
        self.assertEqual(evaluate_corridor(3.35, c), 'yellow')
        self.assertEqual(evaluate_corridor(1.5, c), 'red')
        self.assertEqual(evaluate_corridor(5.0, c), 'red')
        self.assertEqual(evaluate_corridor(None, c), 'na')


class BalanceTests(TestCase):
    def test_empty_metrics_all_na(self):
        section = build_balance({})
        self.assertFalse(section['available'])
        self.assertTrue(all(r['status'] == 'na' for r in section['rows']))
        self.assertTrue(all(r['value'] == 'n/v' for r in section['rows']))

    def test_healthy_metrics_green(self):
        section = build_balance({
            'goals_per_game': 2.6, 'home_pct': 0.45,
            'draw_pct': 0.25, 'away_pct': 0.30,
        })
        self.assertTrue(section['available'])
        statuses = {r['key']: r['status'] for r in section['rows']}
        self.assertEqual(statuses['goals_per_game'], 'green')
        self.assertEqual(statuses['home_pct'], 'green')


class FeatureTests(TestCase):
    def test_empty_sample_all_na(self):
        section = build_features([])
        self.assertFalse(section['available'])
        self.assertTrue(all(r['status'] == 'na' for r in section['rows']))

    def test_feature_ok_vs_warn(self):
        reports = [{
            'home_goals': 2, 'away_goals': 1,
            'report': {
                'goal_events': [{'goal_type': 'goal'}],
                'card_events': [{'minute': 30}],
            },
        }]
        section = build_features(reports)
        by_feature = {r['feature']: r['status'] for r in section['rows']}
        # Karten kommen vor → ok; Verletzungen nicht in Stichprobe → warn (Code da).
        self.assertEqual(by_feature['Karten & Platzverweise'], 'ok')
        self.assertEqual(by_feature['Verletzungen'], 'warn')


class PositionTests(TestCase):
    def test_baseline_relative_ampel(self):
        snaps = (
            [{'position': 'IV', 'rating': 3.0, 'goals': 0, 'assists': 0, 'minutes': 90}] * 10
            + [{'position': 'ST', 'rating': 3.0, 'goals': 1, 'assists': 0, 'minutes': 90}] * 10
            + [{'position': 'XX', 'rating': 5.0, 'goals': 0, 'assists': 0, 'minutes': 90}] * 10
            + [{'position': 'ZZ', 'rating': 3.0, 'goals': 0, 'assists': 0, 'minutes': 90}] * 2
        )
        agg = aggregate_positions(snaps)
        self.assertIsNotNone(agg['baseline_note'])
        rows = {r['position']: r for r in agg['rows']}
        # XX liegt mit 5.0 deutlich über der Baseline → rot.
        self.assertEqual(rows['XX']['note_status'], 'red')
        # ZZ unterschreitet die Mindeststichprobe → na.
        self.assertEqual(rows['ZZ']['note_status'], 'na')

    def test_empty_positions(self):
        agg = aggregate_positions([])
        self.assertIsNone(agg['baseline_note'])
        self.assertEqual(agg['rows'], [])


class TickerTests(TestCase):
    def test_detect_families(self):
        fams = detect_occurred_families({
            'goal_events': [{'goal_type': 'corner'}],
            'sp_near_miss_events': [{'type': 'fk_saved'}],
            'card_events': [{'minute': 10}],
        })
        self.assertIn('goal', fams)
        self.assertIn('corner', fams)
        self.assertIn('save', fams)
        self.assertIn('chance', fams)
        self.assertIn('card', fams)

    def test_coverage_and_never_triggered(self):
        reports = [{'report': {'goal_events': [{'goal_type': 'goal'}]}}]
        section = build_ticker_coverage(reports)
        self.assertTrue(section['available'])
        self.assertGreater(section['coverage_percent'], 0)
        self.assertEqual(section['occurred_count'], 1)
        # Auswechslungen kamen nicht vor → in 'never_triggered'.
        self.assertIn('Auswechslungen', section['never_triggered'])


class TacticsTests(TestCase):
    def test_formation_grouping(self):
        reports = [{
            'home_goals': 2, 'away_goals': 1,
            'report': {'home_formation': '4-4-2', 'away_formation': '4-3-3'},
        }]
        section = build_tactics(reports)
        self.assertTrue(section['available'])
        formations = {r['formation'] for r in section['rows']}
        self.assertEqual(formations, {'4-4-2', '4-3-3'})

    def test_no_formation_data_nv(self):
        section = build_tactics([{'home_goals': 1, 'away_goals': 1, 'report': {}}])
        self.assertFalse(section['available'])
        self.assertTrue(section['note'])
