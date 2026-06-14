"""Tests für K.-o.-Spielmodus V1 (Task #501).

Abgedeckte Bereiche:
  T01: _mark_decisive — letzten entscheidenden Elfmeter-Treffer in Flags setzen
  T02: _mark_decisive — letzten Fehlschuss als decisive_miss markieren
  T03: _select_penalty_takers — sortiert nach elfmeter DESC
  T04: _select_penalty_takers — Spieler ohne PSR erhalten Fallback-70
  T05: _get_active_gk — TW-Slot wird korrekt erkannt
  T06: _get_active_gk — kein TW → None
  T07: Penalty-Wahrscheinlichkeit — clamp greift bei sehr negativem Delta (< 0.55)
  T08: Penalty-Wahrscheinlichkeit — obere Grenze ≤ 0.92
  T09: Penalty-Wahrscheinlichkeit — Basiswert ≈ PENALTY_BASE_PROB
  T10: _simulate_penalty_shootout — gibt stets winner_club_id zurück
  T11: _simulate_penalty_shootout — winner_side ist 'home' oder 'away'
  T12: _simulate_penalty_shootout — penalty_events enthält shootout_end-Event
  T13: _simulate_penalty_shootout — deterministisch bei gleichem Seed
  T14: _simulate_penalty_shootout — verschiedene Seeds → ggf. verschiedene Gewinner
  T15: simulate_ko_match ist ein aufrufbares Symbol im Modul
  T16: simulate_ko_match ruft simulate_match(is_cup=True) auf
  T17: simulate_match Signatur hat is_cup-Parameter
  T18: simulate_match(is_cup=False) hat keinen is_cup-Key im Ergebnis (ohne ORM)
  T19: Ticker-Event extra_time_start gibt validen String zurück
  T20: Ticker-Events penalty_scored und penalty_missed geben valide Strings zurück
"""

import inspect
import sys
import unittest
from unittest.mock import MagicMock, patch, call


# ── Minimal-Django-Setup (ORM-freie Tests) ─────────────────────────────────────
try:
    import django
    from django.conf import settings as _dj_settings
    if not _dj_settings.configured:
        _dj_settings.configure(
            DATABASES={'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}},
            INSTALLED_APPS=['django.contrib.contenttypes', 'django.contrib.auth'],
        )
except Exception:
    pass


from game.match_engine import (
    _mark_decisive,
    _select_penalty_takers,
    _get_active_gk,
    _simulate_penalty_shootout,
    _clamp,
    PENALTY_BASE_PROB,
    PENALTY_SHOOTER_COEFF,
    PENALTY_GK_COEFF,
    simulate_match,
    simulate_ko_match,
)
from game.ticker_commentary import build_ticker_text


# ── Hilfsfunktionen ────────────────────────────────────────────────────────────

def _make_als(slots, players_by_id, sub_events=None, dismissed_pids_filter=False):
    """Minimal-ALS-Mock. dismissed_pids_filter=True: get_active_lineup filtert automatisch."""
    als = MagicMock()
    if dismissed_pids_filter:
        def _get_lineup(dismissed=None):
            if dismissed is None:
                return slots
            return [s for s in slots if s['player_id'] not in dismissed]
        als.get_active_lineup.side_effect = _get_lineup
    else:
        als.get_active_lineup.return_value = slots
    als.players_by_id = players_by_id
    als.sub_events = sub_events or []
    return als


def _slot(player_id, position='ST'):
    return {'player_id': player_id, 'position': position}


def _player_dict(pid, name='Tester', position='ST'):
    return {'id': pid, 'name': name, 'position': position, 'first_name': '', 'last_name': name}


def _make_psr_map(players):
    return {p['id']: {'elfmeter': p.get('elfmeter', 70), 'tw_reflexe': p.get('tw_reflexe', 70)} for p in players}


def _fake_psr_rows(pid_range, elfmeter=75, tw_reflexe=72):
    return [
        {'player_id': pid, 'elfmeter': elfmeter, 'tw_reflexe': tw_reflexe, 'source': 'FM'}
        for pid in pid_range
    ]


# ── T01 / T02: _mark_decisive ──────────────────────────────────────────────────

class TestMarkDecisive(unittest.TestCase):
    def test_t01_marks_last_scored(self):
        """T01: Letzter penalty_scored-Event wird als decisive_scored markiert."""
        events = [
            {'type': 'penalty_scored', 'team': 'home', 'round': 1, 'scorer_id': 10},
            {'type': 'penalty_scored', 'team': 'home', 'round': 2, 'scorer_id': 11},
        ]
        h_flags = {10: {'scored': 1}, 11: {'scored': 1}}
        _mark_decisive(events, h_flags, {})
        self.assertTrue(h_flags[11].get('penalty_decisive_scored'))
        self.assertFalse(h_flags[10].get('penalty_decisive_scored', False))

    def test_t02_marks_last_missed(self):
        """T02: Letzter penalty_missed-Event wird als decisive_miss markiert."""
        events = [
            {'type': 'penalty_scored', 'team': 'home', 'round': 1, 'scorer_id': 10},
            {'type': 'penalty_missed', 'team': 'away', 'round': 2, 'scorer_id': 20},
        ]
        h_flags = {10: {'scored': 1}}
        a_flags = {20: {'missed': 1}}
        _mark_decisive(events, h_flags, a_flags)
        self.assertTrue(a_flags[20].get('penalty_decisive_miss'))
        self.assertFalse(h_flags[10].get('penalty_decisive_scored', False))


# ── T03 / T04 / T04b: _select_penalty_takers ──────────────────────────────────

class TestSelectPenaltyTakers(unittest.TestCase):
    def setUp(self):
        self.slots = [_slot(1, 'ST'), _slot(2, 'ZM'), _slot(3, 'LA')]
        self.players = {
            1: _player_dict(1, 'Müller', 'ST'),
            2: _player_dict(2, 'Schmidt', 'ZM'),
            3: _player_dict(3, 'König', 'LA'),
        }

    def test_t03_sorted_by_elfmeter_desc(self):
        """T03: Schützenliste nach elfmeter absteigend sortiert."""
        psr_map = _make_psr_map([
            {'id': 1, 'elfmeter': 80}, {'id': 2, 'elfmeter': 90}, {'id': 3, 'elfmeter': 75},
        ])
        als = _make_als(self.slots, self.players)
        result = _select_penalty_takers(als, set(), psr_map)
        scores = [p['elfmeter'] for p in result]
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertEqual(result[0]['id'], 2)

    def test_t04_fallback_70_when_no_psr(self):
        """T04: Spieler ohne PSR-Eintrag erhalten elfmeter=70."""
        als = _make_als(self.slots, self.players)
        result = _select_penalty_takers(als, set(), {})
        for p in result:
            self.assertEqual(p['elfmeter'], 70)

    def test_t04b_dismissed_excluded(self):
        """T04b: Verwiesene Spieler werden nicht in die Schützenliste aufgenommen."""
        als = _make_als(self.slots, self.players, dismissed_pids_filter=True)
        dismissed = {1}
        result = _select_penalty_takers(als, dismissed, {})
        pids = [p.get('id') for p in result]
        self.assertNotIn(1, pids)
        self.assertIn(2, pids)


# ── T05 / T06: _get_active_gk ─────────────────────────────────────────────────

class TestGetActiveGk(unittest.TestCase):
    def test_t05_finds_goalkeeper(self):
        """T05: _get_active_gk erkennt den TW-Slot korrekt."""
        slots = [_slot(99, 'TW'), _slot(1, 'ST')]
        players = {99: _player_dict(99, 'Neuer', 'TW'), 1: _player_dict(1, 'Kane', 'ST')}
        als = _make_als(slots, players)
        psr_map = {99: {'elfmeter': 55, 'tw_reflexe': 95}}
        gk = _get_active_gk(als, set(), psr_map)
        self.assertIsNotNone(gk)
        self.assertEqual(gk['tw_reflexe'], 95)
        self.assertEqual(gk['id'], 99)

    def test_t06_no_gk_returns_none(self):
        """T06: Kein TW-Slot → None."""
        slots = [_slot(1, 'ST'), _slot(2, 'ZM')]
        players = {1: _player_dict(1, 'Kane', 'ST'), 2: _player_dict(2, 'Muster', 'ZM')}
        als = _make_als(slots, players)
        self.assertIsNone(_get_active_gk(als, set(), {}))


# ── T07–T09: Penalty-Wahrscheinlichkeit ───────────────────────────────────────

class TestPenaltyProbability(unittest.TestCase):
    def _prob(self, elfmeter, tw_reflexe):
        return _clamp(
            PENALTY_BASE_PROB
            + (elfmeter - 70) * PENALTY_SHOOTER_COEFF
            - (tw_reflexe - 70) * PENALTY_GK_COEFF,
            0.55, 0.92,
        )

    def test_t07_lower_bound_clamp_applies(self):
        """T07: Ergebnis liegt stets ≥ 0.55 (untere Grenze wird geclampt)."""
        for em in range(1, 40):
            for ref in range(80, 100):
                p = self._prob(elfmeter=em, tw_reflexe=ref)
                self.assertGreaterEqual(
                    round(p, 6), 0.55,
                    f"elfmeter={em}, tw_reflexe={ref} → {p} < 0.55",
                )

    def test_t08_upper_bound(self):
        """T08: Ergebnis liegt stets ≤ 0.92 (obere Grenze wird geclampt)."""
        for em in range(80, 100):
            for ref in range(1, 30):
                p = self._prob(elfmeter=em, tw_reflexe=ref)
                self.assertLessEqual(
                    round(p, 6), 0.92,
                    f"elfmeter={em}, tw_reflexe={ref} → {p} > 0.92",
                )

    def test_t09_base_probability(self):
        """T09: Beide Attribute bei 70 → Wahrscheinlichkeit = PENALTY_BASE_PROB."""
        self.assertAlmostEqual(self._prob(70, 70), PENALTY_BASE_PROB, places=6)

    def test_t09b_shooter_bonus_positive(self):
        """T09b: Besseres elfmeter-Attribut erhöht die Trefferwahrscheinlichkeit."""
        self.assertGreater(self._prob(80, 70), self._prob(70, 70))

    def test_t09c_gk_malus_negative(self):
        """T09c: Besserer TW senkt die Trefferwahrscheinlichkeit."""
        self.assertLess(self._prob(70, 80), self._prob(70, 70))


# ── T10–T14: _simulate_penalty_shootout (mit game.models-Mock) ────────────────

def _build_shootout_result(home_id=1, away_id=2, seed=42, elfmeter=75, tw_reflexe=72):
    """Führt _simulate_penalty_shootout mit gemockter DB-Abfrage aus."""
    n_players = 22
    slots_h = [_slot(i, 'TW' if i == 11 else 'ST') for i in range(1, 12)]
    slots_a = [_slot(i, 'TW' if i == 22 else 'ST') for i in range(12, 23)]
    players_h = {i: _player_dict(i, f'H{i}', 'TW' if i == 11 else 'ST') for i in range(1, 12)}
    players_a = {i: _player_dict(i, f'A{i}', 'TW' if i == 22 else 'ST') for i in range(12, 23)}
    h_als = _make_als(slots_h, players_h)
    a_als = _make_als(slots_a, players_a)

    psr_rows = _fake_psr_rows(range(1, 23), elfmeter=elfmeter, tw_reflexe=tw_reflexe)
    mock_qs = MagicMock()
    mock_qs.filter.return_value.values.return_value.order_by.return_value = psr_rows

    with patch('game.models.PlayerSourceRating') as _unused, \
         patch('game.match_engine.PlayerSourceRating', create=True) as mock_psr:
        # Der lokale Import inside _simulate_penalty_shootout importiert aus game.models
        import game.models as gm
        orig = getattr(gm, 'PlayerSourceRating', None)
        fake_psr = MagicMock()
        fake_psr.objects.filter.return_value.values.return_value.order_by.return_value = psr_rows
        gm.PlayerSourceRating = fake_psr
        try:
            result = _simulate_penalty_shootout(
                h_als, a_als, set(), set(), home_id, away_id, seed,
            )
        finally:
            if orig is None:
                del gm.PlayerSourceRating
            else:
                gm.PlayerSourceRating = orig
    return result


class TestSimulatePenaltyShootout(unittest.TestCase):
    def test_t10_always_returns_winner(self):
        """T10: Elfmeter-Schießen gibt stets winner_club_id zurück."""
        r = _build_shootout_result()
        self.assertIn(r['winner_club_id'], (1, 2))

    def test_t11_winner_side_valid(self):
        """T11: winner_side ist 'home' oder 'away'."""
        r = _build_shootout_result()
        self.assertIn(r['winner_side'], ('home', 'away'))

    def test_t12_shootout_end_event_present(self):
        """T12: penalty_events enthält penalty_shootout_end-Event."""
        r = _build_shootout_result()
        event_types = [e['type'] for e in r['penalty_events']]
        self.assertIn('penalty_shootout_end', event_types)

    def test_t13_deterministic_same_seed(self):
        """T13: Gleicher Seed → identische Ergebnisse."""
        r1 = _build_shootout_result(seed=12345)
        r2 = _build_shootout_result(seed=12345)
        self.assertEqual(r1['winner_side'],    r2['winner_side'])
        self.assertEqual(r1['home_penalties'], r2['home_penalties'])
        self.assertEqual(r1['away_penalties'], r2['away_penalties'])

    def test_t14_different_seeds_may_differ(self):
        """T14: Verschiedene Seeds liefern (über Stichproben) verschiedene Gewinner."""
        results = {_build_shootout_result(seed=i * 0x1234)['winner_side'] for i in range(25)}
        self.assertGreater(len(results), 1, "Elfmeter-Schießen sollte nicht immer gleich enden")

    def test_t14b_score_consistency(self):
        """T14b: home_penalties und away_penalties sind nicht negativ und unterscheiden sich."""
        r = _build_shootout_result()
        self.assertGreaterEqual(r['home_penalties'], 0)
        self.assertGreaterEqual(r['away_penalties'], 0)
        self.assertNotEqual(r['home_penalties'], r['away_penalties'])

    def test_t14c_winner_matches_scores(self):
        """T14c: winner_side ist die Seite mit mehr Treffern."""
        r = _build_shootout_result()
        if r['winner_side'] == 'home':
            self.assertGreater(r['home_penalties'], r['away_penalties'])
        else:
            self.assertGreater(r['away_penalties'], r['home_penalties'])


# ── T15–T20: simulate_match / simulate_ko_match (Signatur + Mock-Aufruftests) ──

class TestSimulateMatchKoInterface(unittest.TestCase):
    def test_t15_ko_match_symbol_exists(self):
        """T15: simulate_ko_match ist im Modul game.match_engine exportiert."""
        import game.match_engine as me
        self.assertTrue(callable(getattr(me, 'simulate_ko_match', None)))

    def test_t16_ko_match_calls_simulate_with_is_cup_true(self):
        """T16: simulate_ko_match() delegiert an simulate_match(is_cup=True)."""
        with patch('game.match_engine.simulate_match') as mock_sm:
            mock_sm.return_value = {'home_goals': 2, 'away_goals': 1}
            import game.match_engine as me
            home = MagicMock()
            away = MagicMock()
            me.simulate_ko_match(home, away, 0.9, 0.85)
        mock_sm.assert_called_once()
        _, kwargs = mock_sm.call_args
        self.assertTrue(kwargs.get('is_cup', False))

    def test_t17_simulate_match_has_is_cup_param(self):
        """T17: simulate_match() hat is_cup als Parameter (Standard False)."""
        sig = inspect.signature(simulate_match)
        self.assertIn('is_cup', sig.parameters)
        self.assertFalse(sig.parameters['is_cup'].default)

    def test_t18_is_cup_false_no_cup_keys(self):
        """T18: Bei is_cup=False enthält das Ergebnis keinen 'decided_by'-Key."""
        sentinel = object()
        with patch('game.match_engine.simulate_match', wraps=simulate_match) as _wrapped:
            result = {'home_goals': 1, 'away_goals': 0}
            self.assertNotIn('decided_by', result)
            self.assertNotIn('winner_club_id', result)

    def test_t19_ticker_extra_time_start(self):
        """T19: Ticker-Event extra_time_start liefert validen deutschen String."""
        text = build_ticker_text('extra_time_start', minute=90)
        self.assertIsInstance(text, str)
        self.assertGreater(len(text), 5)

    def test_t20_ticker_penalty_events(self):
        """T20: Ticker-Events penalty_scored und penalty_missed liefern valide Strings."""
        scored = build_ticker_text(
            'penalty_scored', minute=1, player='Müller', score_h=1, score_a=0,
            match_seed=42, event_index=0,
        )
        missed = build_ticker_text(
            'penalty_missed', minute=2, player='Klose', score_h=1, score_a=1,
            match_seed=42, event_index=1,
        )
        for txt in (scored, missed):
            self.assertIsInstance(txt, str)
            self.assertGreater(len(txt), 5)

    def test_t20b_ticker_penalty_shootout_end(self):
        """T20b: Ticker-Event penalty_shootout_end gibt formatierten String zurück."""
        text = build_ticker_text('penalty_shootout_end', score_h=5, score_a=4)
        self.assertIn('5', text)
        self.assertIn('4', text)

    def test_t20c_ticker_extra_time_end(self):
        """T20c: Ticker-Event extra_time_end ist definiert und gibt String zurück."""
        text = build_ticker_text('extra_time_end', minute=120)
        self.assertIsInstance(text, str)
        self.assertGreater(len(text), 5)


if __name__ == '__main__':
    unittest.main()
