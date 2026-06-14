"""Tests für game/matchday_xi.py — Elf des Spieltags.

22 Test Cases: normalize_player_id, get_fit, effective_score,
_compute_minutes, _build_player_pool (mit Mocks),
_find_best_lineup, get_fit-Kompatibilitäten, DISPLAY_ROLE,
FORMATION_SLOTS-Vollständigkeit und build_matchday_xi (mit Mocks).
"""

import sys
import types
import unittest
from unittest.mock import MagicMock, patch

# ── ORM-freies Import-Setup ──────────────────────────────────────────────────
# Stub django.db.models und verwandte Module bevor matchday_xi geladen wird
if 'django' not in sys.modules:
    django_stub = types.ModuleType('django')
    sys.modules['django'] = django_stub

# Minimal-Stubs damit der Import klappt (falls Django nicht vollständig konfiguriert)
try:
    import django
    from django.conf import settings
    if not settings.configured:
        settings.configure(DATABASES={}, INSTALLED_APPS=[])
except Exception:
    pass

from game.matchday_xi import (
    DISPLAY_ROLE,
    FORMATION_PRIORITY,
    FORMATION_SLOTS,
    FIT_PENALTY_SCORE,
    SLOT_COMPATIBILITY,
    _compute_minutes,
    _find_best_lineup,
    effective_score,
    get_fit,
    normalize_player_id,
)


class TestNormalizePlayerId(unittest.TestCase):
    """T01–T04: normalize_player_id"""

    def test_int_passthrough(self):
        self.assertEqual(normalize_player_id(42), 42)

    def test_string_int(self):
        self.assertEqual(normalize_player_id("99"), 99)

    def test_none_returns_none(self):
        self.assertIsNone(normalize_player_id(None))

    def test_non_numeric_string_returns_none(self):
        self.assertIsNone(normalize_player_id("abc"))


class TestGetFit(unittest.TestCase):
    """T05–T08: get_fit"""

    def test_exact_gk(self):
        self.assertEqual(get_fit("GK", "TW"), "exact")

    def test_compatible_lb_lom(self):
        self.assertEqual(get_fit("LB", "LM"), "compatible")

    def test_no_fit_gk_vs_lv(self):
        self.assertIsNone(get_fit("GK", "LV"))

    def test_exact_st_slot(self):
        self.assertEqual(get_fit("ST", "ST"), "exact")


class TestEffectiveScore(unittest.TestCase):
    """T09–T10: effective_score"""

    def test_exact_no_penalty(self):
        self.assertEqual(effective_score(150, "exact"), 150)

    def test_compatible_penalty(self):
        self.assertEqual(effective_score(150, "compatible"), 165)


class TestComputeMinutes(unittest.TestCase):
    """T11–T14: _compute_minutes"""

    def _make_ratings(self, entries):
        return [{"id": e[0], "is_sub": e[1]} for e in entries]

    def test_starter_full_90(self):
        ratings = self._make_ratings([(1, False)])
        result = _compute_minutes(ratings, [], [])
        self.assertEqual(result[1], 90)

    def test_subbed_out_at_60(self):
        ratings = self._make_ratings([(1, False), (2, True)])
        subs = [{"out": 1, "in": 2, "minute": 60}]
        result = _compute_minutes(ratings, subs, [])
        self.assertEqual(result[1], 60)
        self.assertEqual(result[2], 30)

    def test_dismissed_at_70(self):
        ratings = self._make_ratings([(5, False)])
        dismissals = [{"player_id": 5, "minute": 70}]
        result = _compute_minutes(ratings, [], dismissals)
        self.assertEqual(result[5], 70)

    def test_min_clamp_at_zero(self):
        ratings = self._make_ratings([(7, True)])
        subs = [{"out": 99, "in": 7, "minute": 0}]
        result = _compute_minutes(ratings, subs, [])
        self.assertEqual(result[7], 90)


class TestSlotCompatibility(unittest.TestCase):
    """T15–T16: SLOT_COMPATIBILITY-Vollständigkeit"""

    def test_all_formation_slots_have_compat_entry(self):
        all_slot_ids = {
            s["slot_id"]
            for slots in FORMATION_SLOTS.values()
            for s in slots
        }
        for sid in all_slot_ids:
            self.assertIn(sid, SLOT_COMPATIBILITY, f"Slot {sid!r} fehlt in SLOT_COMPATIBILITY")

    def test_all_compat_entries_have_both_keys(self):
        for sid, compat in SLOT_COMPATIBILITY.items():
            self.assertIn("exact", compat, f"{sid} hat keinen 'exact'-Key")
            self.assertIn("compatible", compat, f"{sid} hat keinen 'compatible'-Key")


class TestFormationSlots(unittest.TestCase):
    """T17–T18: FORMATION_SLOTS-Vollständigkeit"""

    def test_all_formations_have_11_slots(self):
        for name, slots in FORMATION_SLOTS.items():
            self.assertEqual(len(slots), 11, f"{name} hat nicht 11 Slots")

    def test_each_formation_has_exactly_one_gk_slot(self):
        for name, slots in FORMATION_SLOTS.items():
            gk_count = sum(1 for s in slots if s["slot_id"] == "GK")
            self.assertEqual(gk_count, 1, f"{name} hat {gk_count} GK-Slots")


class TestDisplayRole(unittest.TestCase):
    """T19: DISPLAY_ROLE-Mapping"""

    def test_known_slots_have_german_labels(self):
        self.assertEqual(DISPLAY_ROLE["GK"], "TW")
        self.assertEqual(DISPLAY_ROLE["LW"], "LF")
        self.assertEqual(DISPLAY_ROLE["CAM"], "OM")


class TestFindBestLineup(unittest.TestCase):
    """T20–T21: _find_best_lineup mit synthetischem Pool"""

    def _make_pool(self):
        """22 Spieler — eine vollständige Elf für 4-4-2 möglich."""
        entries = [
            # TW
            {"player_id": 1, "name": "Müller", "rating": 2.0, "rating_score": 200,
             "goals": 0, "assists": 0, "position": "TW", "is_sub": False,
             "club_id": 1, "club_name": "Club A", "crest": "", "minutes_played": 90},
            # LV
            {"player_id": 2, "name": "Schmidt", "rating": 2.5, "rating_score": 250,
             "goals": 0, "assists": 0, "position": "LV", "is_sub": False,
             "club_id": 1, "club_name": "Club A", "crest": "", "minutes_played": 90},
            # IV x2
            {"player_id": 3, "name": "Bauer", "rating": 2.5, "rating_score": 250,
             "goals": 0, "assists": 0, "position": "IV", "is_sub": False,
             "club_id": 1, "club_name": "Club A", "crest": "", "minutes_played": 90},
            {"player_id": 4, "name": "Fischer", "rating": 2.5, "rating_score": 250,
             "goals": 0, "assists": 0, "position": "IV", "is_sub": False,
             "club_id": 2, "club_name": "Club B", "crest": "", "minutes_played": 90},
            # RV
            {"player_id": 5, "name": "Weber", "rating": 2.5, "rating_score": 250,
             "goals": 0, "assists": 0, "position": "RV", "is_sub": False,
             "club_id": 2, "club_name": "Club B", "crest": "", "minutes_played": 90},
            # LM
            {"player_id": 6, "name": "Koch", "rating": 2.0, "rating_score": 200,
             "goals": 1, "assists": 0, "position": "LM", "is_sub": False,
             "club_id": 1, "club_name": "Club A", "crest": "", "minutes_played": 90},
            # ZM x2
            {"player_id": 7, "name": "Richter", "rating": 2.0, "rating_score": 200,
             "goals": 0, "assists": 1, "position": "ZM", "is_sub": False,
             "club_id": 1, "club_name": "Club A", "crest": "", "minutes_played": 90},
            {"player_id": 8, "name": "Klein", "rating": 2.5, "rating_score": 250,
             "goals": 0, "assists": 0, "position": "ZM", "is_sub": False,
             "club_id": 2, "club_name": "Club B", "crest": "", "minutes_played": 90},
            # RM
            {"player_id": 9, "name": "Wolf", "rating": 2.5, "rating_score": 250,
             "goals": 0, "assists": 0, "position": "RM", "is_sub": False,
             "club_id": 2, "club_name": "Club B", "crest": "", "minutes_played": 90},
            # ST x2
            {"player_id": 10, "name": "Braun", "rating": 1.5, "rating_score": 150,
             "goals": 2, "assists": 0, "position": "ST", "is_sub": False,
             "club_id": 1, "club_name": "Club A", "crest": "", "minutes_played": 90},
            {"player_id": 11, "name": "Hoffmann", "rating": 2.0, "rating_score": 200,
             "goals": 1, "assists": 1, "position": "LF", "is_sub": False,
             "club_id": 2, "club_name": "Club B", "crest": "", "minutes_played": 90},
        ]
        return entries

    def test_complete_lineup_found_for_4_4_2(self):
        pool = self._make_pool()
        slots = FORMATION_SLOTS["4-4-2"]
        result = _find_best_lineup("4-4-2", slots, pool)
        self.assertIsNotNone(result)
        self.assertTrue(result["complete"])
        self.assertEqual(len(result["assignment"]), 11)

    def test_all_players_unique_in_lineup(self):
        pool = self._make_pool()
        slots = FORMATION_SLOTS["4-4-2"]
        result = _find_best_lineup("4-4-2", slots, pool)
        pids = [p["player_id"] for p, _ in result["assignment"].values()]
        self.assertEqual(len(pids), len(set(pids)), "Doppelte Spieler in Elf")


class TestBuildMatchdayXiIntegration(unittest.TestCase):
    """T22: build_matchday_xi mit vollständig gemockten ORM-Daten."""

    def _make_mock_fixture(self, home_ratings, away_ratings):
        sm = MagicMock()
        sm.report_data = {
            "home_ratings":       home_ratings,
            "away_ratings":       away_ratings,
            "home_substitutions": [],
            "away_substitutions": [],
            "home_dismissals":    [],
            "away_dismissals":    [],
        }

        home_club = MagicMock()
        home_club.id = 1
        home_club.name = "Club A"
        home_club.crest_static_path = ""

        away_club = MagicMock()
        away_club.id = 2
        away_club.name = "Club B"
        away_club.crest_static_path = ""

        fixture = MagicMock()
        fixture.simulated_match = sm
        fixture.simulated_match_id = 1
        fixture.home_club = home_club
        fixture.away_club = away_club
        return fixture

    def _full_team_ratings(self, side_offset=0, is_home=True):
        """Erzeugt 11 gültige Spieler-Ratings für eine Seite."""
        lineup = [
            (101 + side_offset, "Tor", "TW"),
            (102 + side_offset, "LV", "LV"),
            (103 + side_offset, "IV1", "IV"),
            (104 + side_offset, "IV2", "IV"),
            (105 + side_offset, "RV", "RV"),
            (106 + side_offset, "LM", "LM"),
            (107 + side_offset, "ZM1", "ZM"),
            (108 + side_offset, "ZM2", "ZM"),
            (109 + side_offset, "RM", "RM"),
            (110 + side_offset, "ST1", "ST"),
            (111 + side_offset, "ST2", "LF"),
        ]
        return [
            {"id": pid, "name": name, "position": pos,
             "rating": 2.5, "goals": 0, "assists": 0,
             "is_sub": False, "pos_group": "MID"}
            for pid, name, pos in lineup
        ]

    def test_returns_valid_xi_with_22_players(self):
        home_r = self._full_team_ratings(0, True)
        away_r = self._full_team_ratings(20, False)
        fixture = self._make_mock_fixture(home_r, away_r)

        mock_qs = MagicMock()
        mock_qs.__iter__ = MagicMock(return_value=iter([fixture]))

        league = MagicMock()
        season = "1"
        matchday = 1

        with patch("game.models.SeasonFixture") as MockSF:
            MockSF.objects.filter.return_value.select_related.return_value = [fixture]
            from game.matchday_xi import build_matchday_xi
            result = build_matchday_xi(league, season, matchday)

        self.assertIsNotNone(result, "build_matchday_xi sollte eine Elf zurückgeben")
        self.assertIn("formation", result)
        self.assertIn("slots", result)
        self.assertEqual(len(result["slots"]), 11)
        slot_ids = [s["player_id"] for s in result["slots"]]
        self.assertEqual(len(slot_ids), len(set(slot_ids)), "Doppelte Spieler im Ergebnis")


if __name__ == "__main__":
    unittest.main()
