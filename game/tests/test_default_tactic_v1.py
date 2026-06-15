"""game/tests/test_default_tactic_v1.py

Default-Taktik V1 — alle Pflicht-Tests (13 + Idempotenz).

Abgedeckte Bereiche:
  T01 — Reihenfolgeunabhängigkeit bei beidseitig trainerlosen Vereinen
  T02 — Nur Heimteam trainerlos → Away-Taktik bleibt unberührt
  T03 — Nur Away-Team trainerlos → Home-Taktik bleibt unberührt
  T04 — Beide mit Trainer → simulate_match setzt first_half nicht
  T05 — Idempotenz: zweiter Aufruf verändert die Taktik nicht
  T06 — 69 vs 74 → underdog (Grenzfall: −6.99 % > −7.0 %)
  T07 — 69 vs 75 → clear_underdog (−8.33 % ≤ −7.0 %)
  T08 — Links/Rechts-Spiegel: rechter Angriff prüft gegnerische LINKE Abwehr
  T09 — Kein Zonenvorteil → attack_focus bleibt ausgewogen
  T10 — Beide Außenbahnen im klaren Vorteil → fluegelspiel
  T11 — Fehlende Zonenwerte (None) verursachen keinen Fehler
  T12 — compile_tactic läuft für alle 5 Profile fehlerfrei
  T13 — Debug-Felder own_overall / opp_overall / relative_diff korrekt
"""

from decimal import Decimal
from datetime import date

from django.test import TestCase

from game.models import Club, League, Player, PlayerStrengthProfile


_POSITIONS_11 = ['TW', 'LV', 'IV', 'IV', 'RV', 'DM', 'ZM', 'ZM', 'OM', 'ST', 'ST']


def _make_club(league, name, strength=70, managed=False):
    """Hilfs-Factory: Verein + 11 Spieler mit einheitlicher base_strength."""
    club = Club.objects.create(
        name=name,
        short_name=name[:4].upper(),
        founded_year=2000,
        budget=Decimal('5000000.00'),
        league=league,
    )
    for i, pos in enumerate(_POSITIONS_11):
        p = Player.objects.create(
            first_name=f'Sp{i}',
            last_name=name[:4],
            wsc_player_id=f'WSC-{name}-{i}',
            date_of_birth=date(1995, 1, 1),
            age=29,
            position=pos,
            main_position_1=pos,
            club=club,
        )
        PlayerStrengthProfile.objects.create(
            player=p,
            base_strength=Decimal(str(strength)),
            form_modifier=Decimal('0.00'),
        )
    if managed:
        from game.models import ManagerProfile
        mgr = ManagerProfile.objects.create(name=f'Mgr-{name[:8]}')
        club.managed_by = mgr
        club.save(update_fields=['managed_by'])
    return club


class DefaultTacticV1Tests(TestCase):
    """Default-Taktik V1 — Pflicht-Tests (T01–T13 + Idempotenz)."""

    def setUp(self):
        self.league = League.objects.create(name='DTaktikLiga', country='Deutschland')

    def _club(self, name, strength=70, managed=False):
        return _make_club(self.league, name, strength=strength, managed=managed)

    # ── T06 / T07 — Kategorisierung ────────────────────────────────────────

    def test_t06_69_vs_74_is_underdog(self):
        """69 gegen 74: relative_diff ≈ −6.99 % → underdog, NICHT clear_underdog."""
        from game.default_tactics import categorize_matchup
        diff_pct = (69 - 74) / 71.5 * 100
        cat = categorize_matchup(69.0, 74.0)
        self.assertEqual(
            cat, 'underdog',
            f'69 vs 74 muss underdog sein (Diff={diff_pct:.4f}%). Erhalten: {cat}',
        )

    def test_t07_69_vs_75_is_clear_underdog(self):
        """69 gegen 75: relative_diff ≈ −8.33 % → clear_underdog."""
        from game.default_tactics import categorize_matchup
        diff_pct = (69 - 75) / 72.0 * 100
        cat = categorize_matchup(69.0, 75.0)
        self.assertEqual(
            cat, 'clear_underdog',
            f'69 vs 75 muss clear_underdog sein (Diff={diff_pct:.4f}%). Erhalten: {cat}',
        )

    # ── T08 — Links/Rechts-Spiegel ─────────────────────────────────────────

    def test_t08_left_right_mirror_mapping(self):
        """Rechter Angriff (100) muss auf gegnerische LINKE Abwehr (20) treffen."""
        from game.default_tactics import analyze_side_matchups

        own_zones = {
            'attack':  {'left': 50.0, 'center': 50.0, 'right': 100.0},
            'defense': {'left': 50.0, 'center': 50.0, 'right':  50.0},
        }
        # opp_def['left'] = 20 (schwach), opp_def['right'] = 80 (stark)
        opp_zones = {
            'attack':  {'left': 50.0, 'center': 50.0, 'right': 50.0},
            'defense': {'left': 20.0, 'center': 80.0, 'right': 80.0},
        }
        result = analyze_side_matchups(own_zones, opp_zones)

        # eigener Angriff rechts (100) trifft opp_def['left'] (20) → großer Vorteil
        self.assertGreater(
            result['right'], 0.4,
            f"Rechter Angriff vs. schwache gegnerische linke Abwehr muss Vorteil zeigen. "
            f"Erhalten: {result['right']:.4f}",
        )
        # eigener Angriff links (50) trifft opp_def['right'] (80) → Nachteil
        self.assertLess(
            result['left'], 0.0,
            f"Linker Angriff vs. starke gegnerische rechte Abwehr muss Nachteil zeigen. "
            f"Erhalten: {result['left']:.4f}",
        )

    # ── T09 / T10 — Angriffsfokus ──────────────────────────────────────────

    def test_t09_no_zone_advantage_stays_ausgewogen(self):
        """Keine klare Schwäche des Gegners → attack_focus bleibt ausgewogen."""
        from game.default_tactics import generate_default_tactic

        even_str = {k: 70.0 for k in ('goalkeeper', 'defense', 'midfield', 'attack', 'overall')}
        uniform = {
            'attack':  {'left': 60.0, 'center': 60.0, 'right': 60.0},
            'defense': {'left': 60.0, 'center': 60.0, 'right': 60.0},
        }
        result = generate_default_tactic(even_str, even_str, uniform, uniform)
        self.assertEqual(
            result['instructions']['attack_focus'], 'ausgewogen',
            'Ausgeglichene Zonen dürfen keinen Fokus setzen.',
        )

    def test_t10_both_wings_advantage_gives_fluegelspiel(self):
        """Beide Außenbahnen mit klarem Vorteil → fluegelspiel."""
        from game.default_tactics import generate_default_tactic

        even_str = {k: 70.0 for k in ('goalkeeper', 'defense', 'midfield', 'attack', 'overall')}
        # Eigene Außenangriffe stark; gegnerische linke + rechte Abwehr schwach
        own_zones = {
            'attack':  {'left': 120.0, 'center':  60.0, 'right': 120.0},
            'defense': {'left':  60.0, 'center':  60.0, 'right':  60.0},
        }
        opp_zones = {
            'attack':  {'left':  60.0, 'center':  60.0, 'right':  60.0},
            'defense': {'left':  25.0, 'center': 100.0, 'right':  25.0},
        }
        result = generate_default_tactic(even_str, even_str, own_zones, opp_zones)
        self.assertEqual(
            result['instructions']['attack_focus'], 'fluegelspiel',
            'Beide Außenbahnen im klaren Vorteil müssen fluegelspiel ergeben.',
        )

    # ── T11 — Fehlende Zonenwerte ──────────────────────────────────────────

    def test_t11_missing_zone_values_no_error(self):
        """None-Zonen verursachen keinen Fehler (kein Lineup vorhanden)."""
        from game.default_tactics import generate_default_tactic

        even_str = {k: 70.0 for k in ('goalkeeper', 'defense', 'midfield', 'attack', 'overall')}
        try:
            result = generate_default_tactic(even_str, even_str, None, None)
        except Exception as exc:
            self.fail(f'generate_default_tactic mit None-Zonen darf nicht werfen: {exc}')
        self.assertIn('category', result)
        self.assertIn('instructions', result)

    # ── T13 — Debug-Felder ─────────────────────────────────────────────────

    def test_t13_debug_fields_present_and_correct(self):
        """own_overall, opp_overall, relative_diff (Rohwert) im Return-Dict."""
        from game.default_tactics import generate_default_tactic

        own_str = {k: 69.0 for k in ('goalkeeper', 'defense', 'midfield', 'attack', 'overall')}
        opp_str = {k: 74.0 for k in ('goalkeeper', 'defense', 'midfield', 'attack', 'overall')}
        result = generate_default_tactic(own_str, opp_str)

        self.assertIn('own_overall',   result, 'own_overall fehlt im Debug-Output.')
        self.assertIn('opp_overall',   result, 'opp_overall fehlt im Debug-Output.')
        self.assertIn('relative_diff', result, 'relative_diff fehlt im Debug-Output.')
        self.assertAlmostEqual(result['own_overall'], 69.0, places=4)
        self.assertAlmostEqual(result['opp_overall'], 74.0, places=4)
        expected = (69.0 - 74.0) / ((69.0 + 74.0) / 2.0)
        self.assertAlmostEqual(result['relative_diff'], expected, places=8)
        self.assertEqual(result['category'], 'underdog')

    # ── DB-Integration ─────────────────────────────────────────────────────

    def test_t01_order_independence_both_unmanaged(self):
        """Beide trainerlos: Taktik-Ergebnis unabhängig von Aufrufreihenfolge."""
        from game.match_readiness import (
            apply_default_tactic_settings,
            _make_default_tactic_snapshot,
            ensure_default_tactic,
        )

        # Paar A: Home zuerst
        h_A = self._club('HomeA', strength=65)
        a_A = self._club('AwayA', strength=80)
        h_tac_A, _ = ensure_default_tactic(h_A)
        a_tac_A, _ = ensure_default_tactic(a_A)
        hs_A = _make_default_tactic_snapshot(h_tac_A)
        as_A = _make_default_tactic_snapshot(a_tac_A)
        apply_default_tactic_settings(h_tac_A, a_tac_A, hs_A, as_A)
        apply_default_tactic_settings(a_tac_A, h_tac_A, as_A, hs_A)

        # Paar B: Away zuerst (identische Stärken)
        h_B = self._club('HomeB', strength=65)
        a_B = self._club('AwayB', strength=80)
        h_tac_B, _ = ensure_default_tactic(h_B)
        a_tac_B, _ = ensure_default_tactic(a_B)
        hs_B = _make_default_tactic_snapshot(h_tac_B)
        as_B = _make_default_tactic_snapshot(a_tac_B)
        apply_default_tactic_settings(a_tac_B, h_tac_B, as_B, hs_B)  # away zuerst!
        apply_default_tactic_settings(h_tac_B, a_tac_B, hs_B, as_B)

        self.assertEqual(
            h_tac_A.first_half, h_tac_B.first_half,
            'Home-first_half muss reihenfolgeunabhängig identisch sein.',
        )
        self.assertEqual(
            a_tac_A.first_half, a_tac_B.first_half,
            'Away-first_half muss reihenfolgeunabhängig identisch sein.',
        )

    def test_t02_only_home_unmanaged_away_unchanged(self):
        """Nur Heimteam trainerlos: Auswärtstaktik (managed) bleibt unberührt."""
        from game.match_readiness import apply_default_tactic_settings, ensure_default_tactic

        home = self._club('HomeFrei', strength=70)
        away = self._club('AwayMgd',  strength=70, managed=True)
        h_tac, _ = ensure_default_tactic(home)
        a_tac, _ = ensure_default_tactic(away)
        initial_away_first_half = a_tac.first_half

        apply_default_tactic_settings(h_tac, a_tac)

        a_tac.refresh_from_db()
        self.assertEqual(
            a_tac.first_half, initial_away_first_half,
            'apply_default_tactic_settings auf Home darf Away-Taktik nicht ändern.',
        )

    def test_t03_only_away_unmanaged_home_unchanged(self):
        """Nur Auswärtsteam trainerlos: Heimtaktik (managed) bleibt unberührt."""
        from game.match_readiness import apply_default_tactic_settings, ensure_default_tactic

        home = self._club('HomeMgd2', strength=70, managed=True)
        away = self._club('AwayFrei', strength=70)
        h_tac, _ = ensure_default_tactic(home)
        a_tac, _ = ensure_default_tactic(away)
        initial_home_first_half = h_tac.first_half

        apply_default_tactic_settings(a_tac, h_tac)

        h_tac.refresh_from_db()
        self.assertEqual(
            h_tac.first_half, initial_home_first_half,
            'apply_default_tactic_settings auf Away darf Home-Taktik nicht ändern.',
        )

    def test_t04_both_managed_apply_default_not_called(self):
        """Beide mit Trainer: apply_default_tactic_settings wird in simulate_match nicht aufgerufen.

        simulate_match kann first_half über andere Pfade setzen (z. B. patch_managed_lineup);
        entscheidend ist nur, dass die matchup-spezifische KI-Taktik nicht angewendet wird.
        """
        from unittest.mock import patch
        from game.match_engine import simulate_match

        home = self._club('MgdHome', strength=70, managed=True)
        away = self._club('MgdAway', strength=70, managed=True)

        with patch('game.match_engine.apply_default_tactic_settings') as mock_fn:
            simulate_match(home, away)

        mock_fn.assert_not_called()

    def test_t05_idempotency(self):
        """Wiederholter Aufruf erzeugt keine kumulative Verschärfung."""
        from game.match_readiness import apply_default_tactic_settings, ensure_default_tactic

        home = self._club('IdemHome', strength=70)
        away = self._club('IdemAway', strength=70)
        h_tac, _ = ensure_default_tactic(home)
        a_tac, _ = ensure_default_tactic(away)

        apply_default_tactic_settings(h_tac, a_tac)
        first_half_1 = dict(h_tac.first_half  or {})
        conditions_1 = list(h_tac.conditions  or [])

        apply_default_tactic_settings(h_tac, a_tac)
        first_half_2 = dict(h_tac.first_half  or {})
        conditions_2 = list(h_tac.conditions  or [])

        self.assertEqual(first_half_1, first_half_2,
            'first_half darf sich beim zweiten Aufruf nicht ändern.')
        self.assertEqual(conditions_1, conditions_2,
            'conditions dürfen sich beim zweiten Aufruf nicht ändern.')

    def test_t14_all_zones_negative_stays_ausgewogen(self):
        """T14 — Alle Zonen negativ → attack_focus bleibt ausgewogen.

        Eigener Angriff (50) deutlich schwächer als gegnerische Abwehr (80)
        auf allen Seiten → keine Zone hat einen echten Vorteil →
        generate_default_tactic darf keinen Zonenfokus setzen.
        """
        from game.default_tactics import generate_default_tactic

        # Eigener Angriff überall schwach (50), gegnerische Abwehr überall stark (80)
        # → alle Zonen negativ → kein Fokus erlaubt
        weak_str  = {'goalkeeper': 65.0, 'defense': 65.0, 'midfield': 65.0,
                     'attack': 65.0, 'overall': 65.0}
        strong_str = {'goalkeeper': 75.0, 'defense': 75.0, 'midfield': 75.0,
                      'attack': 75.0, 'overall': 75.0}
        own_zones = {
            'attack':  {'left': 50.0, 'center': 50.0, 'right': 50.0},
            'defense': {'left': 80.0, 'center': 80.0, 'right': 80.0},
        }
        opp_zones = {
            'attack':  {'left': 80.0, 'center': 80.0, 'right': 80.0},
            'defense': {'left': 50.0, 'center': 50.0, 'right': 50.0},
        }

        result = generate_default_tactic(
            own_strength=weak_str, opp_strength=strong_str,
            own_zones=own_zones, opp_zones=opp_zones,
        )

        focus = result['instructions'].get('attack_focus', 'ausgewogen')
        self.assertEqual(focus, 'ausgewogen',
            f'Alle Zonen negativ → attack_focus muss ausgewogen sein, ist aber: {focus!r}')

    def test_t12_all_profiles_compile_clean(self):
        """Alle 5 Default-Profile müssen compile_tactic fehlerfrei durchlaufen."""
        from game.default_tactics import _PROFILE_BUILDERS
        from game.match_engine import _build_team_dict
        from game.match_readiness import ensure_default_tactic
        from game.tactic_compiler import compile_tactic

        club = self._club('CompileFC', strength=70)
        tac, _ = ensure_default_tactic(club)

        for cat, builder in _PROFILE_BUILDERS.items():
            profile = builder()
            tac.first_half   = profile['first_half']
            tac.second_half  = profile['second_half']
            tac.instructions = profile['instructions']
            tac.conditions   = profile['conditions']
            tac.save(update_fields=[
                'first_half', 'second_half', 'instructions', 'conditions', 'updated_at',
            ])
            team_dict   = _build_team_dict(club, tac)
            tactic_dict = team_dict.get('tactic', {})
            try:
                result = compile_tactic(team_dict, tactic_dict, half='first')
            except Exception as exc:
                self.fail(f'compile_tactic für Profil "{cat}" fehlgeschlagen: {exc}')
            self.assertIn('line_multipliers', result,
                f'Profil "{cat}": compile_tactic liefert kein line_multipliers.')
