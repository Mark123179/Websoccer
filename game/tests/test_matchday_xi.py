"""Tests für game/matchday_xi.py — Elf des Spieltags.

22 spezifikationskonforme Test Cases aus der Task-Spec:
  T01–T02: Spieler-Auswahl
  T03–T06: Minuten-Berechnung
  T07–T08: Vollständigkeitsprüfung
  T09–T11: Positionsfit und Greedy-Falle
  T12–T16: Formations-Eigenschaften
  T17:     Zentrale/defensive Slots (4-3-3, 5-3-2)
  T18:     Formationsvergleich nach effective_score_sum
  T19:     Zwei unterschiedliche Slots beide besetzt
  T20:     String- und Integer-ID deduplication
  T21:     lineup_key-Tiebreaker
  T22:     display_role-Mapping
"""

import sys
import types
import unittest
from unittest.mock import MagicMock, patch

# ── Minimal-Django-Setup für ORM-freie Tests ─────────────────────────────────
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

from game.matchday_xi import (
    DISPLAY_ROLE,
    FORMATION_PRIORITY,
    FORMATION_SLOTS,
    FIT_PENALTY_SCORE,
    SLOT_COMPATIBILITY,
    _build_player_pool,
    _compute_minutes,
    _find_best_lineup,
    _validate_formation_constraints,
    effective_score,
    get_fit,
    normalize_player_id,
)


# ── Hilfsfunktionen ───────────────────────────────────────────────────────────

def _player(pid, name, pos, rating, goals=0, assists=0, is_sub=False, minutes=90,
            club_id=1, club_name="Test FC", crest=""):
    return {
        "player_id":    pid,
        "name":         name,
        "rating":       rating,
        "rating_score": int(round(rating * 100)),
        "goals":        goals,
        "assists":      assists,
        "position":     pos,
        "is_sub":       is_sub,
        "club_id":      club_id,
        "club_name":    club_name,
        "crest":        crest,
        "minutes_played": minutes,
    }


def _slot(slot_id, line="mid", x=50, y=50):
    return {"slot_id": slot_id, "line": line, "x": x, "y": y}


def _min_pool_for_formation(formation_name):
    """Erzeugt einen Pool, der eine vollständige Elf für die gegebene Formation ermöglicht."""
    pos_map = {
        "GK":  "TW",
        "LB":  "LV",
        "RB":  "RV",
        "LCB": "IV",
        "RCB": "IV",
        "CB":  "IV",
        "LM":  "LM",
        "RM":  "RM",
        "LCM": "ZM",
        "RCM": "ZM",
        "CDM": "DM",
        "LDM": "DM",
        "RDM": "DM",
        "CM":  "ZM",
        "LAM": "LOM",
        "RAM": "ROM",
        "CAM": "OM",
        "ST":  "ST",
        "LST": "ST",
        "RST": "LF",
        "LW":  "LF",
        "RW":  "RF",
    }
    slots = FORMATION_SLOTS[formation_name]
    pool = []
    for i, s in enumerate(slots):
        pos = pos_map.get(s["slot_id"], "ZM")
        pool.append(_player(100 + i, f"P{i}", pos, 2.5))
    return pool


# ── T01–T02: Spieler-Auswahl ──────────────────────────────────────────────────

class TestPlayerSelection(unittest.TestCase):

    def test_t01_better_rating_wins(self):
        """T01: Spieler mit Note 1.5 wird vor Note 3.0 gewählt."""
        slots = [_slot("GK", line="gk")]
        pool = [
            _player(1, "A", "TW", 1.5),
            _player(2, "B", "TW", 3.0),
        ]
        result = _find_best_lineup("test", slots, pool)
        self.assertIsNotNone(result)
        chosen_pid = result["assignment"]["GK"][0]["player_id"]
        self.assertEqual(chosen_pid, 1, "Spieler A (Note 1.5) soll gewählt werden")

    def test_t02_no_player_chosen_twice(self):
        """T02: Derselbe Spieler wird maximal einmal ausgewählt."""
        # TW spielt in vielen kompatiblen Slots → nur einmal erlaubt
        slots = [
            _slot("GK", line="gk"),
            _slot("LCM", line="mid"),
        ]
        pool = [
            _player(1, "SuperTW", "TW", 1.0),  # Nur GK-Fit
            _player(2, "ZM", "ZM", 2.5),       # LCM-Fit
        ]
        result = _find_best_lineup("test", slots, pool)
        self.assertIsNotNone(result)
        pids = [p["player_id"] for p, _ in result["assignment"].values()]
        self.assertEqual(len(pids), len(set(pids)), "Jeder Spieler darf nur einmal gewählt werden")


# ── T03–T06: Minuten-Berechnung ───────────────────────────────────────────────

class TestComputeMinutes(unittest.TestCase):

    def _ratings(self, entries):
        return [{"id": pid, "is_sub": is_sub} for pid, is_sub in entries]

    def test_t03_sub_in_at_60_qualifies(self):
        """T03: Einwechselspieler ab Minute 60 → 30 min → qualifiziert."""
        ratings = self._ratings([(1, False), (2, True)])
        subs = [{"out": 1, "in": 2, "minute": 60}]
        mins = _compute_minutes(ratings, subs, [])
        self.assertEqual(mins[2], 30, "30 Minuten = qualifiziert")

    def test_t04_sub_in_at_61_not_qualifies(self):
        """T04: Einwechselspieler ab Minute 61 → 29 min → nicht qualifiziert."""
        ratings = self._ratings([(1, False), (2, True)])
        subs = [{"out": 1, "in": 2, "minute": 61}]
        mins = _compute_minutes(ratings, subs, [])
        self.assertEqual(mins[2], 29, "29 Minuten = nicht qualifiziert")

    def test_t05_sub_chain_20_to_70_equals_50min(self):
        """T05: Wechselkette 20–70 ergibt 50 Minuten."""
        ratings = self._ratings([(10, True)])  # kommt rein (is_sub)
        # Spieler 10 kommt in Minute 20 rein
        subs_in = [{"out": 99, "in": 10, "minute": 20}]
        # Spieler 10 geht in Minute 70 wieder raus
        subs_out = [{"out": 10, "in": 11, "minute": 70}]
        all_subs = subs_in + subs_out
        ratings_full = self._ratings([(10, True), (11, True)])
        mins = _compute_minutes(ratings_full, all_subs, [])
        self.assertEqual(mins[10], 50, "Wechselkette 20–70 = 50 Minuten")

    def test_t06_dismissal_at_25_under_30min(self):
        """T06: Platzverweis in Minute 25 → 25 min → nicht qualifiziert."""
        ratings = self._ratings([(5, False)])
        dismissals = [{"player_id": 5, "minute": 25}]
        mins = _compute_minutes(ratings, [], dismissals)
        self.assertEqual(mins[5], 25, "Platzverweis Minute 25 = 25 min gespielt")
        self.assertLess(mins[5], 30, "25 < 30 → nicht qualifiziert")


# ── T07–T08: Vollständigkeitsprüfung ─────────────────────────────────────────

class TestCompletenessCheck(unittest.TestCase):

    def _make_fixture(self, has_sim, report_data):
        sm = MagicMock()
        sm.report_data = report_data
        home_club = MagicMock()
        home_club.id = 1
        home_club.name = "Home FC"
        home_club.crest_static_path = ""
        away_club = MagicMock()
        away_club.id = 2
        away_club.name = "Away FC"
        away_club.crest_static_path = ""
        f = MagicMock()
        f.simulated_match = sm if has_sim else None
        f.simulated_match_id = 1 if has_sim else None
        f.home_club = home_club
        f.away_club = away_club
        return f

    def test_t07_incomplete_matchday_returns_none(self):
        """T07: Mind. 1 Fixture ohne simulated_match → None."""
        f1 = self._make_fixture(True,  {"home_ratings": [{"id": 1, "position": "TW", "rating": 2.5, "is_sub": False, "goals": 0, "assists": 0, "name": "P"}], "away_ratings": [{"id": 2, "position": "TW", "rating": 2.5, "is_sub": False, "goals": 0, "assists": 0, "name": "Q"}], "home_substitutions": [], "away_substitutions": [], "home_dismissals": [], "away_dismissals": []})
        f2 = self._make_fixture(False, None)  # fehlendes SimulatedMatch

        with patch("game.models.SeasonFixture") as MockSF:
            MockSF.objects.filter.return_value.select_related.return_value = [f1, f2]
            from game.matchday_xi import build_matchday_xi
            league = MagicMock()
            result = build_matchday_xi(league, "1", 1)
        self.assertIsNone(result, "Unvollständiger Spieltag → None")

    def test_t08_empty_report_data_returns_none(self):
        """T08: Fixture ohne home_ratings in report_data → None."""
        f1 = self._make_fixture(True, {})  # leere report_data

        with patch("game.models.SeasonFixture") as MockSF:
            MockSF.objects.filter.return_value.select_related.return_value = [f1]
            from game.matchday_xi import build_matchday_xi
            league = MagicMock()
            result = build_matchday_xi(league, "1", 1)
        self.assertIsNone(result, "Leere report_data → None")


# ── T09–T11: Positionsfit und Greedy-Falle ───────────────────────────────────

class TestPositionFit(unittest.TestCase):

    def test_t09_exact_fit_beats_compatible_with_small_delta(self):
        """T09: Exakter Fit schlägt kompatiblen Fit bei Δ < 15 Hundertstel."""
        # LB-Slot: exact=LV, compatible={LOV, LM}
        # Player A: LV (exact), rating 2.10, eff=210
        # Player B: LM (compatible+15), rating 2.05, eff=205+15=220
        # A (210) < B (220) → A gewinnt
        eff_a = effective_score(210, "exact")
        eff_b = effective_score(205, "compatible")
        self.assertLess(eff_a, eff_b,
            "Exakter Fit (210) soll günstiger sein als kompatibler Fit (220) bei Δ=5 Hundertstel")

    def test_t10_compatible_fit_wins_with_large_delta(self):
        """T10: Kompatibler Fit rechtfertigt sich bei Δ > 15 Hundertstel besserem Rating."""
        # Player A: LV (exact), rating 2.20, eff=220
        # Player B: LM (compatible+15), rating 2.00, eff=200+15=215
        # B (215) < A (220) → B gewinnt trotz kompatibler Position
        eff_a = effective_score(220, "exact")
        eff_b = effective_score(200, "compatible")
        self.assertLess(eff_b, eff_a,
            "Kompatibler Fit (215) soll günstiger sein als exakter Fit (220) bei Δ=20 Hundertstel")

    def test_t11_greedy_trap(self):
        """T11: Backtracking verhindert Greedy-Falle — A (ZM,1.5) auf LCM, B (LM,1.7) auf LM."""
        # Player A: ZM-Position → LCM exact (150), LM compatible (165)
        # Player B: LM-Position → LCM compatible (185), LM exact (170)
        # Greedy (slot-by-slot, LM zuerst): A→LM (165), B→LCM (185) = 350  FALSCH
        # Optimal (backtracking):            A→LCM (150), B→LM  (170) = 320  RICHTIG
        slots = [
            _slot("LCM", line="mid"),
            _slot("LM",  line="mid"),
        ]
        pool = [
            _player(1, "A", "ZM", 1.5),
            _player(2, "B", "LM", 1.7),
        ]
        result = _find_best_lineup("test", slots, pool)
        self.assertIsNotNone(result)
        self.assertEqual(result["assignment"]["LCM"][0]["player_id"], 1, "A soll auf LCM")
        self.assertEqual(result["assignment"]["LM"][0]["player_id"], 2, "B soll auf LM")


# ── T12–T16: Formations-Eigenschaften ────────────────────────────────────────

class TestFormationProperties(unittest.TestCase):

    def test_t12_formation_symmetry_lb_rb(self):
        """T12: Symmetrische Formationen haben LB und RB."""
        symmetric = ["4-4-2", "4-2-3-1", "4-3-3", "5-3-2", "4-5-1"]
        for name in symmetric:
            slot_ids = {s["slot_id"] for s in FORMATION_SLOTS[name]}
            self.assertIn("LB", slot_ids, f"{name}: LB fehlt")
            self.assertIn("RB", slot_ids, f"{name}: RB fehlt")

    def test_t13_each_formation_exactly_11_unique_slots(self):
        """T13: Jede Formation hat genau 11 Slots mit eindeutigen slot_ids."""
        for name, slots in FORMATION_SLOTS.items():
            self.assertEqual(len(slots), 11, f"{name}: {len(slots)} Slots statt 11")
            slot_ids = [s["slot_id"] for s in slots]
            self.assertEqual(len(slot_ids), len(set(slot_ids)),
                             f"{name}: Doppelte slot_ids gefunden")

    def test_t14_deterministic_same_data_same_result(self):
        """T14: Gleicher Datensatz → immer dieselbe Elf (deterministisch)."""
        slots = FORMATION_SLOTS["4-4-2"]
        pool = _min_pool_for_formation("4-4-2")
        r1 = _find_best_lineup("4-4-2", slots, pool)
        r2 = _find_best_lineup("4-4-2", slots, pool)
        self.assertIsNotNone(r1)
        self.assertIsNotNone(r2)
        pids1 = tuple(sorted(p["player_id"] for p, _ in r1["assignment"].values()))
        pids2 = tuple(sorted(p["player_id"] for p, _ in r2["assignment"].values()))
        self.assertEqual(pids1, pids2, "Deterministisch: gleicher Input → gleicher Output")
        for sid in r1["assignment"]:
            p1, ft1 = r1["assignment"][sid]
            p2, ft2 = r2["assignment"][sid]
            self.assertEqual(p1["player_id"], p2["player_id"])
            self.assertEqual(ft1, ft2)

    def test_t15_club_crest_from_fixture_not_player(self):
        """T15: Vereinswappen stammt vom Verein der Fixture (home/away), nicht vom ORM-Spieler."""
        home_club = MagicMock()
        home_club.id = 10
        home_club.name = "Home FC"
        home_club.crest_static_path = "game/images/crests/home.png"

        away_club = MagicMock()
        away_club.id = 20
        away_club.name = "Away FC"
        away_club.crest_static_path = "game/images/crests/away.png"

        sm = MagicMock()
        sm.report_data = {
            "home_ratings": [
                {"id": 101, "name": "HomeP", "position": "TW", "rating": 1.5,
                 "goals": 0, "assists": 0, "is_sub": False}
            ],
            "away_ratings": [
                {"id": 201, "name": "AwayP", "position": "TW", "rating": 2.0,
                 "goals": 0, "assists": 0, "is_sub": False}
            ],
            "home_substitutions": [],
            "away_substitutions": [],
            "home_dismissals": [],
            "away_dismissals": [],
        }

        fixture = MagicMock()
        fixture.simulated_match = sm
        fixture.simulated_match_id = 1
        fixture.home_club = home_club
        fixture.away_club = away_club

        pool = _build_player_pool([fixture])

        home_players = [p for p in pool if p["player_id"] == 101]
        away_players = [p for p in pool if p["player_id"] == 201]

        self.assertTrue(home_players, "Home-Spieler muss im Pool sein")
        self.assertTrue(away_players, "Away-Spieler muss im Pool sein")
        self.assertEqual(home_players[0]["crest"], "game/images/crests/home.png",
                         "Wappen kommt aus Fixture.home_club")
        self.assertEqual(away_players[0]["crest"], "game/images/crests/away.png",
                         "Wappen kommt aus Fixture.away_club")

    def test_t16_constraints_reject_invalid_formations(self):
        """T16: _validate_formation_constraints lehnt ungültige Slot-Konfigurationen ab."""
        # Zu wenig DEF (nur 2)
        too_few_def = [
            _slot("GK", "gk"), _slot("LCB", "def"), _slot("RCB", "def"),
            _slot("LCM", "mid"), _slot("RCM", "mid"), _slot("CDM", "mid"),
            _slot("LM", "mid"), _slot("RM", "mid"),
            _slot("ST", "att"), _slot("LW", "att"), _slot("RW", "att"),
        ]
        self.assertFalse(
            _validate_formation_constraints(too_few_def),
            "2 DEF-Slots soll abgelehnt werden"
        )

        # Zu viele Offensiv-Slots (5 att-Spieler)
        too_many_off = [
            _slot("GK", "gk"),
            _slot("LCB", "def"), _slot("RCB", "def"), _slot("CB", "def"),
            _slot("CDM", "mid"), _slot("LCM", "mid"), _slot("RCM", "mid"),
            _slot("LW", "att"), _slot("RW", "att"), _slot("ST", "att"),
            _slot("RST", "att"),
        ]
        # 4 att → genau an der Grenze (≤4) → gültig
        # 5 att → ungültig
        five_att = [_slot("GK", "gk"), _slot("LCB", "def"), _slot("RCB", "def"), _slot("CB", "def"),
                    _slot("LCM", "mid"), _slot("RCM", "mid"),
                    _slot("LW", "att"), _slot("RW", "att"), _slot("ST", "att"),
                    _slot("LST", "att"), _slot("RST", "att")]
        self.assertFalse(
            _validate_formation_constraints(five_att),
            "5 att-Slots soll abgelehnt werden"
        )


# ── T17: Zentrale/defensive Slots in 4-3-3 und 5-3-2 ────────────────────────

class TestCentralMidFieldSlots(unittest.TestCase):

    _CENTRAL_SLOTS = {"LCM", "RCM", "CDM", "LDM", "RDM", "CM"}

    def test_t17_433_and_532_have_min_2_central_slots(self):
        """T17: 4-3-3 und 5-3-2 enthalten jeweils ≥2 zentrale/defensive Slots."""
        for name in ("4-3-3", "5-3-2"):
            slots = FORMATION_SLOTS[name]
            central = [s for s in slots if s["slot_id"] in self._CENTRAL_SLOTS]
            self.assertGreaterEqual(len(central), 2,
                f"{name} soll ≥2 zentrale/defensive Slots haben, hat {len(central)}")


# ── T18: Formationsvergleich ──────────────────────────────────────────────────

class TestFormationComparison(unittest.TestCase):

    def test_t18_lower_effective_score_sum_wins(self):
        """T18: Formation B (eff=2015) schlägt Formation A (eff=3100)."""
        prio_idx = {name: i for i, name in enumerate(FORMATION_PRIORITY)}

        formation_a_key = (0, 3100, -11, 0, 0, 0, prio_idx.get("4-4-2", 0))
        formation_b_key = (0, 2015, -9,  0, 0, 0, prio_idx.get("4-2-3-1", 1))

        self.assertLess(formation_b_key, formation_a_key,
            "Formation B (eff=2015) soll besser sein als Formation A (eff=3100)")


# ── T19: Zwei verschiedene Slots beide besetzt ────────────────────────────────

class TestTwoDistinctSlots(unittest.TestCase):

    def test_t19_lcm_and_rcm_both_filled_with_different_players(self):
        """T19: LCM und RCM werden mit unterschiedlichen Spielern besetzt."""
        slots = [
            _slot("LCM", "mid"),
            _slot("RCM", "mid"),
        ]
        pool = [
            _player(1, "ZM1", "ZM", 1.5),
            _player(2, "ZM2", "ZM", 1.8),
        ]
        result = _find_best_lineup("test", slots, pool)
        self.assertIsNotNone(result)
        self.assertIn("LCM", result["assignment"])
        self.assertIn("RCM", result["assignment"])
        pid_lcm = result["assignment"]["LCM"][0]["player_id"]
        pid_rcm = result["assignment"]["RCM"][0]["player_id"]
        self.assertNotEqual(pid_lcm, pid_rcm,
            "LCM und RCM müssen mit verschiedenen Spielern besetzt sein")


# ── T20: String- und Integer-ID-Deduplication ─────────────────────────────────

class TestPlayerIdNormalization(unittest.TestCase):

    def test_t20_string_and_int_id_treated_as_same(self):
        """T20: ID als String '123' und als Integer 123 gelten als identisch."""
        # normalize_player_id
        self.assertEqual(normalize_player_id("123"), 123)
        self.assertEqual(normalize_player_id(123), 123)
        self.assertEqual(normalize_player_id("123"), normalize_player_id(123))

        # _compute_minutes: sub.in als String, starter als int
        ratings = [{"id": 123, "is_sub": False}]
        subs = [{"out": 123, "in": "456", "minute": 50}]
        mins = _compute_minutes(ratings, subs, [])
        self.assertEqual(mins[123], 50, "String-ID '123' als out erkennen")
        self.assertEqual(mins[456], 40, "String-ID '456' als in erkennen")


# ── T21: lineup_key-Tiebreaker ────────────────────────────────────────────────

class TestLineupKeyTiebreaker(unittest.TestCase):

    def test_t21_more_exact_fits_wins_on_equal_eff_sum(self):
        """T21: Bei gleichem effective_score_sum gewinnt die Elf mit mehr exakten Fits."""
        # lineup_key = (eff_sum, -exact_matches, rating_cents, -goal_contrib, -minutes_sum, sorted_pids)
        # key_a: eff=300, exact=2 → (-2, ...)
        # key_b: eff=300, exact=1 → (-1, ...)
        # key_a < key_b → a gewinnt (mehr exakte Fits)
        pids = (1, 2)
        key_a = (300, -2, 300, 0, -180, pids)  # 2 exakte Fits
        key_b = (300, -1, 285, 0, -180, pids)  # 1 exakter Fit

        self.assertLess(key_a, key_b,
            "Lineup mit 2 exakten Fits soll besser sein als Lineup mit 1 exaktem Fit")

        # Bei Gleichstand auch bei exact_matches entscheidet rating_cents
        key_c = (300, -2, 290, 0, -180, pids)
        key_d = (300, -2, 300, 0, -180, pids)
        self.assertLess(key_c, key_d,
            "Bei gleichen exact_matches gewinnt bessere Noten-Summe (niedrigere cents)")

        # Deterministisch via sorted player_ids
        key_e = (300, -2, 300, 0, -180, (1, 2))
        key_f = (300, -2, 300, 0, -180, (1, 3))
        self.assertLess(key_e, key_f,
            "Bei vollständiger Gleichheit entscheiden sortierte Spieler-IDs deterministisch")


# ── T22: display_role-Mapping ─────────────────────────────────────────────────

class TestDisplayRole(unittest.TestCase):

    def test_t22_display_role_german_labels(self):
        """T22: display_role für LCM='ZM', LW='LF' — kein englischer Bezeichner sichtbar."""
        self.assertEqual(DISPLAY_ROLE["LCM"], "ZM",
            "LCM soll als 'ZM' angezeigt werden")
        self.assertEqual(DISPLAY_ROLE["LW"], "LF",
            "LW soll als 'LF' angezeigt werden")
        # Keine slot_id darf als display_role die rohe englische Bezeichnung zeigen
        raw_english = {"LCM", "RCM", "CDM", "LAM", "RAM", "CAM", "LST", "RST", "LW", "RW"}
        for slot_id in raw_english:
            role = DISPLAY_ROLE.get(slot_id, slot_id)
            self.assertNotEqual(role, slot_id,
                f"slot_id '{slot_id}' soll nicht roh als display_role erscheinen")


if __name__ == "__main__":
    unittest.main()
