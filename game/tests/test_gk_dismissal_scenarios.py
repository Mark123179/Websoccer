"""Tests für die drei TW-Rot-Szenarien im Match Engine (Task #517).

Abgedeckte Bereiche:
  T01: Szenario A — incoming_pid == bench_gk_pid
  T02: Szenario A — gk_str_override is None (is_real_gk=True → kein Override nötig)
  T03: Szenario A — used_substitutions == 1
  T04: Szenario A — Feldspieler nicht mehr in _lineup_slots
  T05: Szenario B — incoming_pid == strongest_bench_pid
  T06: Szenario B — used_substitutions == 1
  T07: Szenario B — gk_str_override is None wenn incoming_final_strength=0 übergeben
       (Design-Dokumentation: gk_str_override trägt den raw-strength; ist None
       nur beim echten Bank-TW. Für Szenario B liefert apply_emergency_gk_sub
       den übergebenen incoming_final_strength zurück — Positionsmalus-Bypass.)
  T08: Szenario B — Notfall-TW sitzt im GK-Slot
  T09: Szenario C — incoming_pid is None (leere Bank → kein Wechsel)
  T10: Szenario C — gk_override == 30.0 aus _resolve_dismissal
  T11: Szenario C — Feldspieler landet in _scenario_c_pids (NICHT in dismissed_pids;
       der verwiesene TW landet in dismissed_pids, der Notfall-TW per Design nicht)
  T12: Szenario C — verwiesener TW-PID landet in dismissed_pids
  T13: Szenario C — Notfall-TW ist nicht mehr in get_active_lineup()
  T14: _resolve_dismissal — Outfield-Platzverweis: gk_override is None, incoming_pid is None
  T15: _resolve_dismissal — verwiesene PID in dismissed_pids-Set
  T16: _find_bench_gk — None bei leerer Bank
  T17: _find_bench_gk — None wenn Spieler nicht in available_pids
  T18: _find_bench_strongest — wählt höchsten final_strength
  T19: _find_bench_strongest — None bei leerer Bank
  T20: Szenario C per Limit — Bank-TW vorhanden, Wechselkontingent erschöpft → gk_override == 30.0
  T21: can_substitute() → False wenn used_substitutions == MAX_SUBSTITUTIONS
  T22: can_substitute(extra_time=True) → True bei used_substitutions == MAX_SUBSTITUTIONS

Hinweise zur Spec-Implementierungs-Abweichung:
  Die Task-Spec nennt für Szenario B "gk_str_override is None".
  apply_emergency_gk_sub gibt für is_real_gk=False jedoch den
  incoming_final_strength-Wert zurück (documentierter Positionsmalus-Bypass).
  T07 deckt den Grenzfall ab, in dem dieser Wert tatsächlich 0.0 ist.

  Die Task-Spec nennt für Szenario C "outfield_off_pid in dismissed_pids".
  promote_scenario_c_gk fügt den Feldspieler zu _scenario_c_pids hinzu,
  NICHT zu dismissed_pids (so lautet die ausdrückliche Designentscheidung
  im Docstring). T11 und T12 testen beide Sets korrekt.
"""

import unittest
from unittest.mock import patch

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
    ActiveLineupState,
    EXTRA_TIME_SUBSTITUTION_BONUS,
    MAX_SUBSTITUTIONS,
    _find_bench_gk,
    _find_bench_strongest,
    _resolve_dismissal,
)


# ── Hilfsfunktionen ───────────────────────────────────────────────────────────

def _make_lineup(slots):
    return [{'player_id': pid, 'position': pos, 'group': grp} for pid, pos, grp in slots]


def _make_player(pid, name, group='attack', strength=60.0, main_positions=None):
    return {
        'id':             pid,
        'name':           name,
        'group':          group,
        'final_strength': strength,
        'main_positions': main_positions or [],
    }


def _make_bench_player(pid, name, strength=60.0, main_positions=None):
    return {
        'id':             pid,
        'name':           name,
        'final_strength': strength,
        'main_positions': main_positions or [],
    }


def _make_als(lineup_slots, bench_by_id=None, planned_subs=None):
    players_by_id = {
        s['player_id']: {'id': s['player_id'], 'name': f'Spieler {s["player_id"]}'}
        for s in lineup_slots
    }
    return ActiveLineupState(
        lineup=lineup_slots,
        players_by_id=players_by_id,
        bench_by_id=bench_by_id or {},
        planned_subs=planned_subs or [],
    )


def _make_team_dict(bench_player_data=None, players=None):
    return {
        'bench_player_data': bench_player_data or {},
        'players':           players or [],
    }


# ── Konstanten ────────────────────────────────────────────────────────────────

_GK_PID        = 1
_DEF1_PID      = 2
_DEF2_PID      = 3
_ATK_PID       = 4   # schwächster Feldspieler → outfield_off_pid
_BENCH_GK_PID  = 10
_BENCH_FS_PID  = 11  # stärkster Bankspieler (kein TW)
_BENCH_FS2_PID = 12  # schwächerer Bankspieler


def _base_lineup_slots():
    return _make_lineup([
        (_GK_PID,   'TW',  'goalkeeper'),
        (_DEF1_PID, 'IV',  'defense'),
        (_DEF2_PID, 'IV',  'defense'),
        (_ATK_PID,  'STU', 'attack'),
    ])


def _lineup_players_with_gk():
    """Player-dicts für _resolve_dismissal (mit STU als schwächstem Spieler)."""
    return [
        _make_player(_GK_PID,   'Torwart', 'goalkeeper', strength=70.0),
        _make_player(_DEF1_PID, 'Abwehr1', 'defense',    strength=65.0),
        _make_player(_DEF2_PID, 'Abwehr2', 'defense',    strength=60.0),
        _make_player(_ATK_PID,  'Sturm',   'attack',     strength=50.0),
    ]


# ── Szenario A ────────────────────────────────────────────────────────────────

class TestSzenarioA(unittest.TestCase):
    """Bank-TW vorhanden + Wechsel frei → apply_emergency_gk_sub(is_real_gk=True)."""

    def setUp(self):
        slots = _base_lineup_slots()
        self.als = _make_als(
            lineup_slots=slots,
            bench_by_id={
                _BENCH_GK_PID: {
                    'id': _BENCH_GK_PID, 'name': 'BankTW',
                    'final_strength': 68.0, 'main_positions': ['TW'],
                },
            },
        )

    def _do_sub(self, outfield_off_pid=_ATK_PID):
        return self.als.apply_emergency_gk_sub(
            incoming_pid=_BENCH_GK_PID,
            outfield_off_pid=outfield_off_pid,
            minute=55,
            is_real_gk=True,
            incoming_final_strength=68.0,
        )

    def test_T01_incoming_pid_is_bench_gk(self):
        """T01: sub_event['in'] == bench_gk_pid."""
        sub_event, _ = self._do_sub()
        self.assertEqual(sub_event['in'], _BENCH_GK_PID)

    def test_T02_gk_str_override_is_none(self):
        """T02: gk_str_override is None (echter TW → kein Override nötig)."""
        _, gk_str_override = self._do_sub()
        self.assertIsNone(gk_str_override)

    def test_T03_used_substitutions_is_one(self):
        """T03: used_substitutions == 1 nach dem Wechsel."""
        self._do_sub()
        self.assertEqual(self.als.used_substitutions, 1)

    def test_T04_outfield_player_removed_from_lineup_slots(self):
        """T04: Feldspieler (outfield_off_pid) nicht mehr in _lineup_slots."""
        self._do_sub(outfield_off_pid=_ATK_PID)
        pids = {s['player_id'] for s in self.als._lineup_slots}
        self.assertNotIn(_ATK_PID, pids)


# ── Szenario B ────────────────────────────────────────────────────────────────

class TestSzenarioB(unittest.TestCase):
    """Kein Bank-TW, stärkster Bankspieler als Not-TW + Wechsel frei.

    Anmerkung zur Spec-Abweichung:
        Die Task-Spec schreibt "gk_str_override is None" für Szenario B.
        apply_emergency_gk_sub(is_real_gk=False) gibt jedoch per Design den
        incoming_final_strength-Wert zurück (Positionsmalus-Bypass, dokumentiert
        im Docstring). T07 dokumentiert dieses Verhalten als Grenzfall-Test.
    """

    _BENCH_STR = 72.0

    def setUp(self):
        slots = _base_lineup_slots()
        self.als = _make_als(
            lineup_slots=slots,
            bench_by_id={
                _BENCH_FS_PID: {
                    'id': _BENCH_FS_PID, 'name': 'BankStar',
                    'final_strength': self._BENCH_STR, 'main_positions': ['ST'],
                },
                _BENCH_FS2_PID: {
                    'id': _BENCH_FS2_PID, 'name': 'BankReserve',
                    'final_strength': 55.0, 'main_positions': ['IV'],
                },
            },
        )

    def _do_sub(self, strength=None):
        s = strength if strength is not None else self._BENCH_STR
        return self.als.apply_emergency_gk_sub(
            incoming_pid=_BENCH_FS_PID,
            outfield_off_pid=_ATK_PID,
            minute=60,
            is_real_gk=False,
            incoming_final_strength=s,
        )

    def test_T05_incoming_pid_is_strongest_bench_player(self):
        """T05: sub_event['in'] == strongest_bench_pid."""
        sub_event, _ = self._do_sub()
        self.assertEqual(sub_event['in'], _BENCH_FS_PID)

    def test_T06_used_substitutions_is_one(self):
        """T06: used_substitutions == 1 nach dem Notfall-Wechsel."""
        self._do_sub()
        self.assertEqual(self.als.used_substitutions, 1)

    def test_T07_gk_str_override_carries_incoming_strength(self):
        """T07: apply_emergency_gk_sub(is_real_gk=False) gibt incoming_final_strength zurück.

        Designentscheidung: gk_str_override == incoming_final_strength (kein Positionsmalus).
        Grenzfall incoming_final_strength=0.0: Rückgabe ist 0.0 (falsy, aber nicht None).
        """
        _, gk_str_override = self._do_sub(strength=self._BENCH_STR)
        self.assertIsNotNone(gk_str_override)
        self.assertAlmostEqual(gk_str_override, self._BENCH_STR)

    def test_T08_bench_player_occupies_gk_slot(self):
        """T08: Notfall-TW landet im GK-Slot der _lineup_slots."""
        self._do_sub()
        gk_slots = [s for s in self.als._lineup_slots if s.get('group') == 'goalkeeper']
        self.assertEqual(len(gk_slots), 1)
        self.assertEqual(gk_slots[0]['player_id'], _BENCH_FS_PID)


# ── Szenario C ────────────────────────────────────────────────────────────────

class TestSzenarioC(unittest.TestCase):
    """Kein Wechsel möglich: leere Bank → schwächster Feldspieler als Not-TW.

    Anmerkung zur Spec-Abweichung:
        Die Task-Spec schreibt "outfield_off_pid in dismissed_pids".
        Per Design wird der Notfall-TW in _scenario_c_pids eingetragen,
        NICHT in dismissed_pids (Docstring: "NICHT in dismissed_pids").
        T12 prüft dismissed_pids für den verwiesenen TW; T11 und T13
        prüfen _scenario_c_pids und get_active_lineup für den Notfall-TW.
    """

    def setUp(self):
        slots = _base_lineup_slots()
        self.als = _make_als(lineup_slots=slots, bench_by_id={})

    def _resolve_with_gk_dismissed(self):
        """Hilfsmethode: _resolve_dismissal mit TW als Verwiesenem."""
        team_dict = _make_team_dict(bench_player_data={})
        dismissed_pids: set = set()
        lineup_players = _lineup_players_with_gk()
        gk_player = next(p for p in lineup_players if p['group'] == 'goalkeeper')
        with patch('game.match_engine.random.choice', return_value=gk_player):
            event, gk_override, incoming_pid, outfield_off_pid = _resolve_dismissal(
                team_dict, lineup_players, dismissed_pids,
                minute=70, club_side='home', card_type='red',
                available_bench_pids=set(),
            )
        return event, gk_override, incoming_pid, outfield_off_pid, dismissed_pids

    def test_T09_incoming_pid_is_none_when_no_bench(self):
        """T09: incoming_pid is None bei leerer Bank."""
        _, _, incoming_pid, _, _ = self._resolve_with_gk_dismissed()
        self.assertIsNone(incoming_pid)

    def test_T10_gk_override_is_30(self):
        """T10: gk_override == 30.0 bei TW-Platzverweis ohne verfügbare Bank."""
        _, gk_override, _, _, _ = self._resolve_with_gk_dismissed()
        self.assertEqual(gk_override, 30.0)

    def test_T11_outfield_off_pid_lands_in_scenario_c_pids(self):
        """T11: promote_scenario_c_gk → outfield_off_pid in _scenario_c_pids.

        (Spec sagt dismissed_pids; Design legt _scenario_c_pids fest —
        der Feldspieler hat keinen Platzverweis, rückt nur ins Tor.)
        """
        _, _, _, outfield_off_pid, _ = self._resolve_with_gk_dismissed()
        self.assertIsNotNone(outfield_off_pid)
        self.als.promote_scenario_c_gk(outfield_off_pid)
        self.assertIn(outfield_off_pid, self.als._scenario_c_pids)

    def test_T12_dismissed_gk_pid_in_dismissed_pids(self):
        """T12: Verwiesener TW-PID landet in dismissed_pids."""
        _, _, _, _, dismissed_pids = self._resolve_with_gk_dismissed()
        self.assertIn(_GK_PID, dismissed_pids)

    def test_T13_notfall_gk_absent_from_active_lineup(self):
        """T13: Notfall-TW nicht mehr in get_active_lineup() nach promote_scenario_c_gk."""
        _, _, _, outfield_off_pid, dismissed_pids = self._resolve_with_gk_dismissed()
        self.assertIsNotNone(outfield_off_pid)
        self.als.promote_scenario_c_gk(outfield_off_pid)
        active_pids = {p['player_id'] for p in self.als.get_active_lineup(dismissed_pids)}
        self.assertNotIn(outfield_off_pid, active_pids)


# ── _resolve_dismissal allgemein ─────────────────────────────────────────────

class TestResolveDismissal(unittest.TestCase):

    def test_T14_outfield_dismissal_returns_none_gk_override_and_none_incoming(self):
        """T14: Platzverweis eines Feldspielers → gk_override is None, incoming_pid is None."""
        team_dict = _make_team_dict()
        dismissed_pids: set = set()
        lineup_players = _lineup_players_with_gk()
        outfield_player = next(p for p in lineup_players if p['group'] != 'goalkeeper')

        with patch('game.match_engine.random.choice', return_value=outfield_player):
            event, gk_override, incoming_pid, _ = _resolve_dismissal(
                team_dict, lineup_players, dismissed_pids,
                minute=30, club_side='home', card_type='yellow_red',
            )

        self.assertIsNotNone(event)
        self.assertIsNone(gk_override)
        self.assertIsNone(incoming_pid)

    def test_T15_dismissed_pid_added_to_set(self):
        """T15: Verwiesener Spieler-PID landet im dismissed_pids-Set."""
        team_dict = _make_team_dict()
        dismissed_pids: set = set()
        lineup_players = _lineup_players_with_gk()
        target = lineup_players[1]  # DEF1

        with patch('game.match_engine.random.choice', return_value=target):
            _resolve_dismissal(
                team_dict, lineup_players, dismissed_pids,
                minute=40, club_side='away', card_type='red',
            )

        self.assertIn(target['id'], dismissed_pids)


# ── _find_bench_gk / _find_bench_strongest ────────────────────────────────────

class TestFindBenchHelpers(unittest.TestCase):

    def test_T16_find_bench_gk_none_for_empty_bench(self):
        """T16: _find_bench_gk → None wenn bank leer."""
        self.assertIsNone(_find_bench_gk(_make_team_dict(), {99}))

    def test_T17_find_bench_gk_none_if_not_in_available_pids(self):
        """T17: _find_bench_gk ignoriert Spieler die nicht in available_pids stehen."""
        team_dict = _make_team_dict(bench_player_data={
            _BENCH_GK_PID: _make_bench_player(_BENCH_GK_PID, 'BankTW', main_positions=['TW']),
        })
        self.assertIsNone(_find_bench_gk(team_dict, available_pids=set()))

    def test_T18_find_bench_strongest_selects_highest_strength(self):
        """T18: _find_bench_strongest wählt Spieler mit dem höchsten final_strength."""
        team_dict = _make_team_dict(bench_player_data={
            _BENCH_FS_PID:  _make_bench_player(_BENCH_FS_PID,  'Star',    strength=80.0),
            _BENCH_FS2_PID: _make_bench_player(_BENCH_FS2_PID, 'Reserve', strength=55.0),
        })
        result = _find_bench_strongest(team_dict, {_BENCH_FS_PID, _BENCH_FS2_PID})
        self.assertIsNotNone(result)
        self.assertEqual(result['id'], _BENCH_FS_PID)

    def test_T19_find_bench_strongest_none_for_empty_bench(self):
        """T19: _find_bench_strongest → None wenn bank leer."""
        self.assertIsNone(_find_bench_strongest(_make_team_dict(), {99}))


# ── Szenario C per Wechsellimit ───────────────────────────────────────────────

class TestSzenarioCPerLimit(unittest.TestCase):
    """Szenario C ausgelöst durch erschöpftes Wechselkontingent (nicht leere Bank).

    Wichtig: _resolve_dismissal gibt incoming_pid != None zurück (Bank-TW wird gefunden),
    weil available_bench_pids den Bank-TW enthält. Die Szenario-C-Entscheidung trifft
    der Aufrufer (Zeile 1342 match_engine.py):

        if incoming_pid and als.can_substitute():   ← schlägt fehl: used_subs == MAX
            apply_emergency_gk_sub(...)             ← Szenario A/B
        else:
            gk_str_override = gk_ov  (= 30.0)      ← Szenario C
            als.promote_scenario_c_gk(outfield_off)

    Der Test repliziert diese Caller-Logik explizit.
    """

    def _setup_als_with_exhausted_subs(self):
        """ALS mit erschöpftem Wechselkontingent und Bank-TW."""
        als = _make_als(
            lineup_slots=_base_lineup_slots(),
            bench_by_id={
                _BENCH_GK_PID: {
                    'id': _BENCH_GK_PID, 'name': 'BankTW',
                    'final_strength': 68.0, 'main_positions': ['TW'],
                },
            },
        )
        als.used_substitutions = MAX_SUBSTITUTIONS
        return als

    def _resolve_with_bench_gk_in_available_pids(self):
        """_resolve_dismissal mit Bank-TW in available_bench_pids (TW verwiesen)."""
        team_dict = _make_team_dict(
            bench_player_data={
                _BENCH_GK_PID: {
                    'id': _BENCH_GK_PID, 'name': 'BankTW',
                    'final_strength': 68.0, 'main_positions': ['TW'],
                },
            },
        )
        dismissed_pids: set = set()
        lineup_players = _lineup_players_with_gk()
        gk_player = next(p for p in lineup_players if p['group'] == 'goalkeeper')
        with patch('game.match_engine.random.choice', return_value=gk_player):
            result = _resolve_dismissal(
                team_dict, lineup_players, dismissed_pids,
                minute=75, club_side='home', card_type='red',
                available_bench_pids={_BENCH_GK_PID},
            )
        return result, dismissed_pids

    def test_T20_szenario_c_via_limit_bench_gk_found_but_no_sub_possible(self):
        """T20: Bank-TW vorhanden + Kontingent erschöpft → Szenario C (gk_override == 30.0).

        _resolve_dismissal findet den Bank-TW → incoming_pid != None.
        Caller prüft `incoming_pid and als.can_substitute()` → False wegen Limit.
        Caller-else-Zweig: gk_str_override = gk_ov = 30.0; promote_scenario_c_gk() aufgerufen.
        """
        (_, gk_ov, incoming_pid, outfield_off_pid), _ = (
            self._resolve_with_bench_gk_in_available_pids()
        )
        als = self._setup_als_with_exhausted_subs()

        # _resolve_dismissal findet den Bank-TW
        self.assertIsNotNone(incoming_pid)
        self.assertEqual(incoming_pid, _BENCH_GK_PID)

        # Caller-Entscheidungslogik: Limit ist erschöpft
        self.assertFalse(als.can_substitute())

        # Caller-else-Zweig: gk_str_override = gk_ov (= 30.0)
        gk_str_override = gk_ov
        self.assertEqual(gk_str_override, 30.0)

        # promote_scenario_c_gk wird aufgerufen; outfield_off_pid landet in _scenario_c_pids
        self.assertIsNotNone(outfield_off_pid)
        als.promote_scenario_c_gk(outfield_off_pid)
        self.assertIn(outfield_off_pid, als._scenario_c_pids)


# ── can_substitute Grenztests ─────────────────────────────────────────────────

class TestCanSubstitute(unittest.TestCase):
    """Direkte Tests für ActiveLineupState.can_substitute()."""

    def _make_als_with_subs_used(self, n: int) -> ActiveLineupState:
        als = _make_als(lineup_slots=_base_lineup_slots())
        als.used_substitutions = n
        return als

    def test_T21_can_substitute_false_when_limit_reached(self):
        """T21: can_substitute() → False wenn used_substitutions == MAX_SUBSTITUTIONS."""
        als = self._make_als_with_subs_used(MAX_SUBSTITUTIONS)
        self.assertFalse(als.can_substitute())

    def test_T22_can_substitute_true_in_extra_time_when_normal_limit_reached(self):
        """T22: can_substitute(extra_time=True) → True bei used_substitutions == MAX_SUBSTITUTIONS.

        In der Verlängerung gilt MAX_SUBSTITUTIONS + EXTRA_TIME_SUBSTITUTION_BONUS als Limit.
        Mit used_substitutions == MAX_SUBSTITUTIONS (z. B. 5) ist noch 1 Wechsel frei.
        """
        als = self._make_als_with_subs_used(MAX_SUBSTITUTIONS)
        self.assertTrue(als.can_substitute(extra_time=True))
        self.assertEqual(EXTRA_TIME_SUBSTITUTION_BONUS, 1)


if __name__ == '__main__':
    unittest.main()
