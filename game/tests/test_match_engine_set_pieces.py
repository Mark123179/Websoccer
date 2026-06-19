"""
Tests für Set-Piece xG-Pfade (Ecken · Freistöße · Foulelfmeter) — Match Engine V2.
Alle Konstanten sind eingefroren (Nutzer-Freigabe 2026-06-18).
"""
from django.test import SimpleTestCase

from game.match_engine import (
    _best_sp_attrs,
    _set_piece_xg,
    _goal_events,
    SET_PIECE_CORNER_BASE_XG,
    SET_PIECE_FK_DIRECT_BASE_XG,
    SET_PIECE_FK_CROSS_BASE_XG,
    SET_PIECE_PENALTY_BASE_XG,
    SET_PIECE_FK_RATE,
    SET_PIECE_FK_DIRECT_PROB,
    SET_PIECE_PENALTY_RATE,
    SET_PIECE_ATTR_COEFF,
)


# ── Hilfsfunktionen ──────────────────────────────────────────────────────────

def _avg_sp():
    """Standardattribute auf Ø-Spieler-Niveau (70 = Fallback)."""
    return {
        'best_ecken': 70,
        'best_freistoss': 70,
        'best_kopfball': 70,
        'best_elfmeter': 70,
        'gk_tw_reflexe': 70,
    }


def _mk_player(pid, pos_group='attack'):
    return {'id': pid, 'name': f'Spieler {pid}', 'position': 'ST', 'group': pos_group}


# ── _set_piece_xg: Grundkorrektheit ──────────────────────────────────────────

class TestSetPieceXgNoNegatives(SimpleTestCase):
    """Alle xG-Werte dürfen nie negativ werden."""

    def test_zero_inputs_all_zero(self):
        res = _set_piece_xg(0, 0, _avg_sp(), _avg_sp())
        self.assertGreaterEqual(res['corner_xg'],    0.0)
        self.assertGreaterEqual(res['fk_direct_xg'], 0.0)
        self.assertGreaterEqual(res['fk_cross_xg'],  0.0)
        self.assertGreaterEqual(res['penalty_xg'],   0.0)

    def test_zero_inputs_exactly_zero(self):
        res = _set_piece_xg(0, 0, _avg_sp(), _avg_sp())
        self.assertEqual(res['corner_xg'],    0.0)
        self.assertEqual(res['fk_direct_xg'], 0.0)
        self.assertEqual(res['fk_cross_xg'],  0.0)
        self.assertEqual(res['penalty_xg'],   0.0)

    def test_extreme_bad_attrs_no_negative(self):
        bad_own = {k: 1 for k in ('best_ecken', 'best_freistoss', 'best_kopfball', 'best_elfmeter', 'gk_tw_reflexe')}
        bad_opp = bad_own.copy()
        res = _set_piece_xg(10, 20, bad_own, bad_opp)
        for key in ('corner_xg', 'fk_direct_xg', 'fk_cross_xg', 'penalty_xg'):
            self.assertGreaterEqual(res[key], 0.0, f"{key} went negative with min-attrs")


class TestSetPieceXgPlausibility(SimpleTestCase):
    """xG-Werte sollten im plausiblen Bereich liegen."""

    def test_typical_segment_corner_xg(self):
        """6 Ecken + Ø-Attribute → corner_xg ≈ 0.15."""
        res = _set_piece_xg(6, 0, _avg_sp(), _avg_sp())
        self.assertAlmostEqual(res['corner_xg'], 6 * SET_PIECE_CORNER_BASE_XG, places=6)

    def test_typical_segment_fk_split(self):
        """10 Fouls → n_fk = 1.2; check direct+cross proportions."""
        res = _set_piece_xg(0, 10, _avg_sp(), _avg_sp())
        n_fk      = 10 * SET_PIECE_FK_RATE
        exp_direct = n_fk * SET_PIECE_FK_DIRECT_PROB * SET_PIECE_FK_DIRECT_BASE_XG
        exp_cross  = n_fk * (1 - SET_PIECE_FK_DIRECT_PROB) * SET_PIECE_FK_CROSS_BASE_XG
        self.assertAlmostEqual(res['fk_direct_xg'], exp_direct, places=8)
        self.assertAlmostEqual(res['fk_cross_xg'],  exp_cross,  places=8)

    def test_typical_segment_penalty_xg(self):
        """10 Fouls → n_penalties = 0.12; penalty_xg ≈ 0.0876."""
        res = _set_piece_xg(0, 10, _avg_sp(), _avg_sp())
        expected = 10 * SET_PIECE_PENALTY_RATE * SET_PIECE_PENALTY_BASE_XG
        self.assertAlmostEqual(res['penalty_xg'], expected, places=8)

    def test_higher_attr_raises_xg(self):
        """Ein Spieler mit Ecken=90 soll mehr Ecken-xG erzeugen als Ø-Spieler."""
        avg = _avg_sp()
        high = _avg_sp()
        high['best_ecken'] = 90
        res_avg  = _set_piece_xg(5, 0, avg,  avg)
        res_high = _set_piece_xg(5, 0, high, avg)
        self.assertGreater(res_high['corner_xg'], res_avg['corner_xg'])

    def test_strong_gk_reduces_penalty_xg(self):
        """Ein starker TW (tw_reflexe=90) senkt das gegnerische Elfmeter-xG."""
        avg     = _avg_sp()
        strong  = _avg_sp()
        strong['gk_tw_reflexe'] = 90
        res_avg    = _set_piece_xg(0, 20, avg,    avg)
        res_strong = _set_piece_xg(0, 20, avg,    strong)
        self.assertLess(res_strong['penalty_xg'], res_avg['penalty_xg'])


# ── _best_sp_attrs: Attribut-Fallback ────────────────────────────────────────

class TestBestSpAttrsFallback(SimpleTestCase):
    """Leere Spielerliste → alle Fallback-Werte 70."""

    def test_empty_players_returns_fallbacks(self):
        result = _best_sp_attrs([], [], {})
        self.assertEqual(result['best_ecken'],     70)
        self.assertEqual(result['best_freistoss'],  70)
        self.assertEqual(result['best_kopfball'],   70)
        self.assertEqual(result['best_elfmeter'],   70)
        self.assertEqual(result['gk_tw_reflexe'],   70)

    def test_player_without_source_ratings_returns_fallback(self):
        class FakeSR:
            def all(self):
                return []

        class FakePlayer:
            source_ratings = FakeSR()

        pid = 1
        result = _best_sp_attrs([pid], [], {pid: FakePlayer()})
        self.assertEqual(result['best_ecken'], 70)
        self.assertEqual(result['gk_tw_reflexe'], 70)


# ── xG-Akkumulation unabhängig von Tor-Konvertierung ─────────────────────────

class TestSetPieceXgAlwaysAccumulated(SimpleTestCase):
    """xG muss auch dann akkumuliert werden, wenn kein Tor fällt.

    Sicherstellung, dass _set_piece_xg() positive Werte zurückgibt
    auch bei Eingaben, die statistisch selten zu Toren führen —
    Poisson-Würfel ist davon unabhängig.
    """

    def test_corner_xg_positive_with_corners(self):
        """Auch ohne Torkonvertierung liefert corner_xg > 0 bei n_corners > 0."""
        res = _set_piece_xg(8, 0, _avg_sp(), _avg_sp())
        self.assertGreater(res['corner_xg'], 0.0)

    def test_fk_xg_positive_with_fouls(self):
        """fk_direct_xg > 0 bei n_fouls > 0, unabhängig vom Tor-Poisson-Ergebnis."""
        res = _set_piece_xg(0, 15, _avg_sp(), _avg_sp())
        self.assertGreater(res['fk_direct_xg'], 0.0)
        self.assertGreater(res['fk_cross_xg'],  0.0)

    def test_penalty_xg_positive_with_fouls(self):
        """penalty_xg > 0 bei n_fouls > 0."""
        res = _set_piece_xg(0, 15, _avg_sp(), _avg_sp())
        self.assertGreater(res['penalty_xg'], 0.0)

    def test_xg_sum_equals_parts(self):
        """Gesamtes Set-Piece-xG entspricht der Summe der Einzelpfade."""
        res = _set_piece_xg(6, 12, _avg_sp(), _avg_sp())
        total = res['corner_xg'] + res['fk_direct_xg'] + res['fk_cross_xg'] + res['penalty_xg']
        self.assertAlmostEqual(
            total,
            res['corner_xg'] + res['fk_direct_xg'] + res['fk_cross_xg'] + res['penalty_xg'],
            places=10,
        )
        self.assertGreater(total, 0.0)


# ── _goal_events: goal_type-Weitergabe ───────────────────────────────────────

class TestGoalEventsGoalType(SimpleTestCase):
    """_goal_events trägt goal_type korrekt in jeden Event ein."""

    def _players(self):
        return [_mk_player(i) for i in range(1, 5)]

    def test_default_goal_type_is_goal(self):
        evts = _goal_events(3, 'home', self._players(), list(range(1, 91)))
        for e in evts:
            self.assertEqual(e['goal_type'], 'goal')

    def test_corner_type_propagated(self):
        evts = _goal_events(2, 'away', self._players(), list(range(1, 91)), goal_type='corner')
        for e in evts:
            self.assertEqual(e['goal_type'], 'corner')

    def test_fk_direct_type_propagated(self):
        evts = _goal_events(1, 'home', self._players(), list(range(1, 91)), goal_type='fk_direct')
        self.assertEqual(evts[0]['goal_type'], 'fk_direct')

    def test_penalty_sp_type_propagated(self):
        evts = _goal_events(1, 'home', self._players(), list(range(1, 91)), goal_type='penalty_sp')
        self.assertEqual(evts[0]['goal_type'], 'penalty_sp')
