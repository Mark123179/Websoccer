"""game/tests/test_nationality_normalization.py

Tests für:
  - NATIONALITY_ALIASES (häufigste Fälle)
  - Player.nation_badge_url Property
  - normalize_player_nationalities Management-Command (inkl. --dry-run)
"""

from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from game.models import COUNTRY_FLAG_ASSETS, NATIONALITY_ALIASES, Player
from game.management.commands.normalize_player_nationalities import (
    _normalize_field,
    _normalize_segment,
)


# ── NATIONALITY_ALIASES ──────────────────────────────────────────────────────

class NationalityAliasesTests(TestCase):
    def test_germany_maps_to_deutschland(self):
        self.assertEqual(NATIONALITY_ALIASES.get('germany'), 'Deutschland')

    def test_holland_maps_to_niederlande(self):
        self.assertEqual(NATIONALITY_ALIASES.get('holland'), 'Niederlande')

    def test_netherlands_maps_to_niederlande(self):
        self.assertEqual(NATIONALITY_ALIASES.get('netherlands'), 'Niederlande')

    def test_ivory_coast_maps_to_elfenbeinküste(self):
        self.assertEqual(NATIONALITY_ALIASES.get('ivory coast'), 'Elfenbeinküste')

    def test_south_korea_maps_to_südkorea(self):
        self.assertEqual(NATIONALITY_ALIASES.get('south korea'), 'Südkorea')

    def test_united_states_maps_to_vereinigte_staaten(self):
        self.assertEqual(NATIONALITY_ALIASES.get('united states'), 'Vereinigte Staaten')

    def test_czech_republic_maps_to_tschechien(self):
        self.assertEqual(NATIONALITY_ALIASES.get('czech republic'), 'Tschechien')

    def test_all_canonical_values_exist_in_country_flag_assets(self):
        missing = [
            (alias, canonical)
            for alias, canonical in NATIONALITY_ALIASES.items()
            if canonical not in COUNTRY_FLAG_ASSETS
        ]
        self.assertEqual(
            missing, [],
            msg=f'Alias-Werte nicht in COUNTRY_FLAG_ASSETS: {missing[:10]}'
        )


# ── _normalize_segment / _normalize_field (Hilfsfunktionen) ─────────────────

class NormalizeSegmentTests(TestCase):
    def test_known_english_normalized(self):
        normalized, changed = _normalize_segment('Germany')
        self.assertEqual(normalized, 'Deutschland')
        self.assertTrue(changed)

    def test_already_canonical_not_changed(self):
        normalized, changed = _normalize_segment('Deutschland')
        self.assertEqual(normalized, 'Deutschland')
        self.assertFalse(changed)

    def test_case_insensitive(self):
        normalized, changed = _normalize_segment('GERMANY')
        self.assertEqual(normalized, 'Deutschland')
        self.assertTrue(changed)

    def test_unknown_passthrough(self):
        normalized, changed = _normalize_segment('Atlantis')
        self.assertEqual(normalized, 'Atlantis')
        self.assertFalse(changed)

    def test_empty_passthrough(self):
        normalized, changed = _normalize_segment('')
        self.assertEqual(normalized, '')
        self.assertFalse(changed)


class NormalizeFieldTests(TestCase):
    def test_single_english_segment(self):
        val, changed, unknowns = _normalize_field('Germany')
        self.assertEqual(val, 'Deutschland')
        self.assertTrue(changed)
        self.assertEqual(unknowns, [])

    def test_multi_segment_mixed(self):
        val, changed, unknowns = _normalize_field('Germany, Österreich')
        self.assertEqual(val, 'Deutschland, Österreich')
        self.assertTrue(changed)
        self.assertEqual(unknowns, [])

    def test_no_change_when_already_canonical(self):
        val, changed, unknowns = _normalize_field('Österreich, Deutschland')
        self.assertFalse(changed)
        self.assertEqual(unknowns, [])

    def test_unknown_segment_reported(self):
        val, changed, unknowns = _normalize_field('Deutschland, Atlantis')
        self.assertIn('Atlantis', unknowns)

    def test_empty_field_returns_unchanged(self):
        val, changed, unknowns = _normalize_field('')
        self.assertFalse(changed)
        self.assertEqual(unknowns, [])


# ── Player.nation_badge_url Property ────────────────────────────────────────

class NationBadgeUrlTests(TestCase):
    def _make_player(self, nt_nationality='', nationalities=''):
        return Player(
            first_name='Test',
            last_name='Spieler',
            age=25,
            nt_nationality=nt_nationality,
            nationalities=nationalities,
        )

    def test_returns_cdn_url_for_known_asset_id(self):
        player = self._make_player(nt_nationality='Deutschland')
        url = player.nation_badge_url
        self.assertEqual(url, 'https://playwebsoccer.de/assets/nations/771_nation.png')

    def test_falls_back_to_nationalities_when_nt_nationality_empty(self):
        player = self._make_player(nt_nationality='', nationalities='Frankreich, Deutschland')
        url = player.nation_badge_url
        self.assertEqual(url, 'https://playwebsoccer.de/assets/nations/769_nation.png')

    def test_nt_nationality_takes_precedence_over_nationalities(self):
        player = self._make_player(nt_nationality='England', nationalities='Frankreich')
        url = player.nation_badge_url
        self.assertEqual(url, 'https://playwebsoccer.de/assets/nations/765_nation.png')

    def test_returns_empty_string_when_no_asset_id(self):
        player = self._make_player(nt_nationality='Afghanistan')
        self.assertEqual(player.nation_badge_url, '')

    def test_returns_empty_string_when_nation_unknown(self):
        player = self._make_player(nt_nationality='Atlantis')
        self.assertEqual(player.nation_badge_url, '')

    def test_returns_empty_string_when_no_nationality(self):
        player = self._make_player()
        self.assertEqual(player.nation_badge_url, '')

    def test_known_nations_with_asset_id(self):
        cases = {
            'Belgien': '757',
            'Brasilien': '1651',
            'Elfenbeinküste': '24',
            'Irland': '789',
            'Japan': '116',
            'Kroatien': '761',
            'Niederlande': '784',
            'Norwegen': '786',
            'Polen': '787',
            'Schweden': '797',
            'Serbien': '802',
            'Spanien': '773',
            'Südkorea': '135',
        }
        for nation, asset_id in cases.items():
            with self.subTest(nation=nation):
                player = self._make_player(nt_nationality=nation)
                expected = f'https://playwebsoccer.de/assets/nations/{asset_id}_nation.png'
                self.assertEqual(player.nation_badge_url, expected)


# ── Management Command ───────────────────────────────────────────────────────

def _create_player(first_name, last_name, nt_nationality='', nationalities=''):
    from django.db import connection
    import random
    return Player.objects.create(
        first_name=first_name,
        last_name=last_name,
        age=25,
        nt_nationality=nt_nationality,
        nationalities=nationalities,
        wsc_player_id=f'TEST-{first_name}-{last_name}-{random.randint(1, 999999)}',
    )


class NormalizeCommandTests(TestCase):
    def test_dry_run_does_not_save(self):
        player = _create_player('Hans', 'Müller', nationalities='Germany')
        out = StringIO()
        call_command('normalize_player_nationalities', '--dry-run', stdout=out)
        player.refresh_from_db()
        self.assertEqual(player.nationalities, 'Germany')

    def test_dry_run_output_mentions_dry(self):
        _create_player('Test', 'Dry', nationalities='Germany')
        out = StringIO()
        call_command('normalize_player_nationalities', '--dry-run', stdout=out)
        output = out.getvalue()
        self.assertIn('dry', output.lower())

    def test_normalizes_english_nationality(self):
        player = _create_player('Max', 'Muster', nationalities='Germany')
        out = StringIO()
        call_command('normalize_player_nationalities', stdout=out)
        player.refresh_from_db()
        self.assertEqual(player.nationalities, 'Deutschland')

    def test_normalizes_nt_nationality(self):
        player = _create_player('Marco', 'Polo', nt_nationality='Netherlands')
        out = StringIO()
        call_command('normalize_player_nationalities', stdout=out)
        player.refresh_from_db()
        self.assertEqual(player.nt_nationality, 'Niederlande')

    def test_does_not_touch_already_canonical(self):
        player = _create_player('Lena', 'Schmidt', nationalities='Österreich')
        out = StringIO()
        call_command('normalize_player_nationalities', stdout=out)
        player.refresh_from_db()
        self.assertEqual(player.nationalities, 'Österreich')

    def test_multi_segment_nationality(self):
        player = _create_player('Jan', 'Multi', nationalities='Germany, Netherlands')
        out = StringIO()
        call_command('normalize_player_nationalities', stdout=out)
        player.refresh_from_db()
        self.assertEqual(player.nationalities, 'Deutschland, Niederlande')

    def test_report_contains_unknown_values(self):
        _create_player('Alien', 'X', nationalities='Atlantis')
        out = StringIO()
        call_command('normalize_player_nationalities', stdout=out)
        output = out.getvalue()
        self.assertIn('Atlantis', output)

    def test_report_shows_no_nationality_count(self):
        _create_player('Empty', 'Nation', nationalities='', nt_nationality='')
        out = StringIO()
        call_command('normalize_player_nationalities', stdout=out)
        output = out.getvalue()
        self.assertIn('ohne Nationalität', output)
