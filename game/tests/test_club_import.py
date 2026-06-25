"""game/tests/test_club_import.py

Creator-Mode Vereins-/Spielerimport — Engine & Datenmodelle (Task 1).

Abgedeckte Bereiche:
  - Saison-ID-Automatik (Europe/Berlin, Halbjahresgrenze)
  - Positions-Mapping + HP/NP-Algorithmus (§12–§14)
  - Namens-/Vereinsnormalisierung (§15)
  - Wert-Parsing (Höhe, Marktwert, Fuß, Nationalitäten) inkl. NULL-statt-0
  - Bestehende-Spieler-Erkennung (TM / FMI / CMTracker / Name+Geburtsdatum)
  - Verbindlicher Datenbankimport (Anlegen, Überschreiben, Platzhalter, Leihe,
    Quell-Ratings ersetzen/löschen, NULL-Erhalt, Stapel-Robustheit)
  - Lease-Token-Zufälligkeit
"""

from datetime import date
from decimal import Decimal

from django.test import TestCase

from game.models import (
    Club,
    ClubPlayerImportJob,
    DataSource,
    League,
    Player,
    PlayerExternalId,
    PlayerImportCandidate,
    PlayerSourceRating,
)
from game.club_import import (
    compute_positions,
    find_existing_player,
    get_current_tm_season_id,
    map_tm_position,
    normalize_name,
    parse_foot,
    parse_height,
    parse_market_value,
    parse_nationalities,
    season_label,
)
from game.club_import.import_service import (
    import_candidate,
    import_selected_candidates,
)


# ── Saison-ID ──────────────────────────────────────────────────────────────

class SeasonIdTests(TestCase):
    def test_first_half_year_maps_to_previous_year(self):
        self.assertEqual(get_current_tm_season_id(date(2026, 6, 16)), 2025)
        self.assertEqual(get_current_tm_season_id(date(2026, 1, 1)), 2025)
        self.assertEqual(get_current_tm_season_id(date(2026, 6, 30)), 2025)

    def test_second_half_year_maps_to_current_year(self):
        self.assertEqual(get_current_tm_season_id(date(2026, 7, 1)), 2026)
        self.assertEqual(get_current_tm_season_id(date(2026, 12, 31)), 2026)

    def test_season_label_format(self):
        self.assertEqual(season_label(2025), '2025/26')
        self.assertEqual(season_label(1999), '1999/00')


# ── Positions-Mapping & HP/NP ──────────────────────────────────────────────

class PositionMappingTests(TestCase):
    def test_known_and_unknown_mapping(self):
        self.assertEqual(map_tm_position('Innenverteidiger'), 'IV')
        self.assertEqual(map_tm_position('  LINKSAUßEN '), 'LF')
        self.assertEqual(map_tm_position('Mittelstürmer'), 'ST')
        self.assertIsNone(map_tm_position('Quarterback'))
        self.assertIsNone(map_tm_position(''))

    def test_regular_two_hp_two_np(self):
        result = compute_positions([
            ('Innenverteidiger', 90),
            ('Defensives Mittelfeld', 42),
            ('Zentrales Mittelfeld', 22),
            ('Rechter Verteidiger', 14),
            ('Mittelstürmer', 7),
        ])
        self.assertEqual(result['main_positions'], ['IV', 'DM'])
        self.assertEqual(result['secondary_positions'], ['ZM', 'RV'])

    def test_at_least_one_hp_when_none_reaches_threshold(self):
        result = compute_positions([
            ('Innenverteidiger', 22),
            ('Defensives Mittelfeld', 15),
        ])
        self.assertEqual(result['main_positions'], ['IV'])
        self.assertEqual(result['secondary_positions'], ['DM'])

    def test_more_than_two_over_threshold_caps_hp_at_two(self):
        result = compute_positions([
            ('Innenverteidiger', 100),
            ('Defensives Mittelfeld', 80),
            ('Zentrales Mittelfeld', 60),
            ('Rechter Verteidiger', 30),
        ])
        self.assertEqual(result['main_positions'], ['IV', 'DM'])
        self.assertEqual(result['secondary_positions'], ['ZM', 'RV'])

    def test_derived_combo_when_both_hp(self):
        result = compute_positions([
            ('Linker Verteidiger', 40),
            ('Linkes Mittelfeld', 30),
        ])
        self.assertEqual(result['main_positions'], ['LV', 'LM', 'LOV'])
        self.assertEqual(result['secondary_positions'], [])

    def test_no_derived_combo_when_second_is_only_np(self):
        result = compute_positions([
            ('Linker Verteidiger', 40),
            ('Linkes Mittelfeld', 15),
        ])
        self.assertEqual(result['main_positions'], ['LV'])
        self.assertEqual(result['secondary_positions'], ['LM'])
        self.assertNotIn('LOV', result['main_positions'])

    def test_appearances_aggregated_across_labels(self):
        result = compute_positions([
            ('Mittelstürmer', 20),
            ('Sturm', 20),
        ])
        self.assertEqual(result['main_positions'], ['ST'])

    def test_youth_fallback_uses_profile_position(self):
        result = compute_positions([], profile_position='Mittelstürmer')
        self.assertEqual(result['main_positions'], ['ST'])
        self.assertTrue(result['used_profile_fallback'])
        self.assertEqual(result['errors'], [])

    def test_no_data_and_no_mappable_profile_is_error(self):
        result = compute_positions([], profile_position='Quarterback')
        self.assertEqual(result['main_positions'], [])
        self.assertTrue(result['errors'])

    def test_unknown_position_warns_but_continues(self):
        result = compute_positions([
            ('Quarterback', 30),
            ('Innenverteidiger', 30),
        ])
        self.assertEqual(result['main_positions'], ['IV'])
        self.assertTrue(any('Quarterback' in w for w in result['warnings']))


# ── Normalisierung ─────────────────────────────────────────────────────────

class NormalizationTests(TestCase):
    def test_strips_accents_punctuation_whitespace_case(self):
        self.assertEqual(normalize_name("O'Brien-Smith  Jr."), 'obriensmithjr')
        self.assertEqual(normalize_name('José Mourinho'), 'josemourinho')
        self.assertEqual(normalize_name('Müller'), 'muller')
        self.assertEqual(normalize_name(None), '')


# ── Wert-Parsing ───────────────────────────────────────────────────────────

class ParsingTests(TestCase):
    def test_parse_height(self):
        self.assertEqual(parse_height('1,93 m'), 193)
        self.assertEqual(parse_height('193 cm'), 193)
        self.assertEqual(parse_height('1.85 m'), 185)

    def test_parse_height_missing_is_none_not_zero(self):
        self.assertIsNone(parse_height(''))
        self.assertIsNone(parse_height(None))
        self.assertIsNone(parse_height('-'))

    def test_parse_market_value(self):
        self.assertEqual(parse_market_value('35,00 Mio. €'), 35_000_000)
        self.assertEqual(parse_market_value('500 Tsd. €'), 500_000)
        self.assertEqual(parse_market_value('1,20 Mrd. €'), 1_200_000_000)
        self.assertEqual(parse_market_value('25.000.000 €'), 25_000_000)

    def test_parse_market_value_missing_is_none_not_zero(self):
        self.assertIsNone(parse_market_value(''))
        self.assertIsNone(parse_market_value(None))
        self.assertIsNone(parse_market_value('-'))

    def test_parse_foot(self):
        self.assertEqual(parse_foot('linker Fuß'), 'L')
        self.assertEqual(parse_foot('rechts'), 'R')
        self.assertEqual(parse_foot('beidfüßig'), 'B')
        self.assertEqual(parse_foot(''), '')

    def test_parse_nationalities(self):
        self.assertEqual(
            parse_nationalities(['Deutschland', 'Türkei']),
            ('Deutschland', 'Deutschland, Türkei'),
        )
        self.assertEqual(
            parse_nationalities('Deutschland, Türkei'),
            ('Deutschland', 'Deutschland, Türkei'),
        )
        self.assertEqual(parse_nationalities([]), ('', ''))


# ── Matching ───────────────────────────────────────────────────────────────

class MatchingTests(TestCase):
    def setUp(self):
        self.league = League.objects.create(name='MatchLiga', country='DE')
        self.club = Club.objects.create(
            name='MatchClub', short_name='MC', founded_year=2000,
            budget=Decimal('0'), league=self.league,
        )

    def _player(self, **kwargs):
        defaults = dict(
            first_name='Max', last_name='Muster', age=25,
            date_of_birth=date(2000, 1, 1), club=self.club,
        )
        defaults.update(kwargs)
        return Player.objects.create(**defaults)

    def test_match_by_transfermarkt_id_is_strong(self):
        p = self._player(transfermarkt_id=555)
        match = find_existing_player(tm_player_id=555)
        self.assertEqual(match['player'], p)
        self.assertEqual(match['match_type'], 'tm')
        self.assertTrue(match['is_strong'])

    def test_match_by_fm_inside_id_is_strong(self):
        p = self._player(fm_inside_id=777)
        match = find_existing_player(fm_inside_id=777)
        self.assertEqual(match['player'], p)
        self.assertEqual(match['match_type'], 'fmi')

    def test_match_by_sofifa_id_is_strong(self):
        p = self._player()
        source, _ = DataSource.objects.get_or_create(
            code=DataSource.CODE_CMTRACKER, defaults={'name': 'CMTracker'})
        PlayerExternalId.objects.create(player=p, source=source, external_id='9001')
        match = find_existing_player(sofifa_id='9001')
        self.assertEqual(match['player'], p)
        self.assertEqual(match['match_type'], 'sofifa')

    def test_match_by_name_and_dob_is_weak(self):
        p = self._player(first_name='Léo', last_name='Messi',
                         date_of_birth=date(1987, 6, 24))
        match = find_existing_player(name='Leo Messi',
                                     date_of_birth=date(1987, 6, 24))
        self.assertEqual(match['player'], p)
        self.assertEqual(match['match_type'], 'name_dob')
        self.assertFalse(match['is_strong'])

    def test_no_match_returns_none(self):
        match = find_existing_player(tm_player_id=123456789)
        self.assertIsNone(match['player'])


# ── Import-Dienst ──────────────────────────────────────────────────────────

class ImportServiceTests(TestCase):
    def setUp(self):
        self.league = League.objects.create(name='ImportLiga', country='DE')
        self.ws_club = Club.objects.create(
            name='FC Import', short_name='FCI', founded_year=2000,
            budget=Decimal('1000000'), league=self.league,
        )

    def _job(self):
        return ClubPlayerImportJob.objects.create(
            ws_club=self.ws_club, tm_club_id=27, tm_season_id=2025,
            season_label='2025/26',
        )

    def _candidate(self, job, normalized, tm_player_id=1,
                   selected=True, overwrite=False):
        return PlayerImportCandidate.objects.create(
            job=job, tm_player_id=tm_player_id,
            selected_for_import=selected, overwrite_existing=overwrite,
            normalized_data=normalized,
        )

    def _full_nd(self, **overrides):
        nd = {
            'tm_player_id': 28049320,
            'transfermarkt_profile_url': 'https://www.transfermarkt.de/x/28049320',
            'first_name': 'Harry', 'last_name': 'Kane',
            'date_of_birth': '1993-07-28',
            'height_cm': 188, 'strong_foot': 'R',
            'primary_nationality': 'England', 'nationalities': 'England',
            'market_value': 100_000_000,
            'main_positions': ['ST'], 'secondary_positions': ['OM'],
            'fm_inside_id': 123456,
            'sofifa_id': '202126',
            'sofifa_profile_url': 'https://sofifa.com/player/202126',
            'real_club': None, 'loaned_from': None,
            'fmi_ratings': {'rating': 88, 'potential': 90,
                            'attrs': {'abschluss': 95, 'kopfball': 90}},
            'sofifa_ratings': {'rating': 90, 'potential': 91,
                               'attrs': {'abschluss': 93}},
        }
        nd.update(overrides)
        return nd

    def test_create_new_player_full(self):
        job = self._job()
        cand = self._candidate(job, self._full_nd())
        result = import_candidate(cand)

        self.assertEqual(result['action'], 'created')
        player = Player.objects.get(transfermarkt_id=28049320)
        self.assertEqual(player.first_name, 'Harry')
        self.assertEqual(player.last_name, 'Kane')
        self.assertEqual(player.main_position_1, 'ST')
        self.assertEqual(player.secondary_position_1, 'OM')
        self.assertEqual(player.market_value, 100_000_000)
        self.assertEqual(player.club, self.ws_club)
        self.assertEqual(player.real_life_club, self.ws_club)
        self.assertIsNone(player.loan_partner_club)
        self.assertEqual(player.fm_inside_id, 123456)

        fm = PlayerSourceRating.objects.get(player=player, source=PlayerSourceRating.SOURCE_FM)
        self.assertEqual(fm.abschluss, 95)
        self.assertEqual(fm.kopfball, 90)
        self.assertIsNone(fm.tempo)  # nicht gesetzt → NULL
        ea = PlayerSourceRating.objects.get(player=player, source=PlayerSourceRating.SOURCE_CMTRACKER)
        self.assertEqual(ea.abschluss, 93)

        ext = PlayerExternalId.objects.get(player=player, source__code=DataSource.CODE_CMTRACKER)
        self.assertEqual(ext.external_id, '202126')

        cand.refresh_from_db()
        self.assertEqual(cand.status, PlayerImportCandidate.STATUS_IMPORTED)
        self.assertEqual(cand.existing_player, player)

    def test_null_values_preserved_never_zero(self):
        job = self._job()
        nd = self._full_nd(market_value=None, height_cm=None)
        cand = self._candidate(job, nd, tm_player_id=999)
        import_candidate(cand)
        player = Player.objects.get(transfermarkt_id=28049320)
        self.assertIsNone(player.market_value)
        self.assertIsNone(player.height_cm)

    def test_overwrite_replaces_and_clears_source_ratings(self):
        job = self._job()
        import_candidate(self._candidate(job, self._full_nd()))
        player = Player.objects.get(transfermarkt_id=28049320)

        job2 = self._job()
        nd2 = self._full_nd(
            market_value=50_000_000,
            fmi_ratings={'rating': 80, 'potential': 82, 'attrs': {'tempo': 70}},
            sofifa_id=None,
            sofifa_ratings=None,
        )
        cand2 = self._candidate(job2, nd2, tm_player_id=2, overwrite=True)
        result = import_candidate(cand2)

        self.assertEqual(result['action'], 'updated')
        player.refresh_from_db()
        self.assertEqual(player.market_value, 50_000_000)
        fm = PlayerSourceRating.objects.get(player=player, source=PlayerSourceRating.SOURCE_FM)
        self.assertEqual(fm.tempo, 70)
        self.assertIsNone(fm.abschluss)  # Altwert vollständig gelöscht
        self.assertFalse(
            PlayerSourceRating.objects.filter(
                player=player, source=PlayerSourceRating.SOURCE_CMTRACKER).exists()
        )
        self.assertFalse(
            PlayerExternalId.objects.filter(
                player=player, source__code=DataSource.CODE_CMTRACKER).exists()
        )

    def test_existing_without_overwrite_is_skipped(self):
        job = self._job()
        import_candidate(self._candidate(job, self._full_nd()))
        player = Player.objects.get(transfermarkt_id=28049320)
        original_mv = player.market_value

        job2 = self._job()
        cand2 = self._candidate(
            job2, self._full_nd(market_value=1), tm_player_id=3, overwrite=False)
        result = import_candidate(cand2)

        self.assertEqual(result['action'], 'skipped')
        player.refresh_from_db()
        self.assertEqual(player.market_value, original_mv)
        cand2.refresh_from_db()
        self.assertEqual(cand2.existing_player, player)

    def test_loan_sets_real_and_partner_club_placeholder(self):
        job = self._job()
        nd = self._full_nd(
            tm_player_id=555,
            loaned_from={'tm_id': 148, 'name': 'Tottenham Hotspur',
                         'profile_url': 'https://tm/148'},
        )
        cand = self._candidate(job, nd)
        import_candidate(cand)

        player = Player.objects.get(transfermarkt_id=555)
        self.assertEqual(player.club, self.ws_club)
        parent = Club.objects.get(transfermarkt_id=148)
        self.assertTrue(parent.is_import_placeholder)
        self.assertEqual(player.real_life_club, parent)
        self.assertEqual(player.loan_partner_club, parent)

    def test_placeholder_club_dedup_by_transfermarkt_id(self):
        job = self._job()
        ref = {'tm_id': 148, 'name': 'Tottenham', 'profile_url': ''}
        import_candidate(self._candidate(
            job, self._full_nd(tm_player_id=1, real_club=ref), tm_player_id=1))
        import_candidate(self._candidate(
            job, self._full_nd(tm_player_id=2, real_club=ref), tm_player_id=2))
        self.assertEqual(Club.objects.filter(transfermarkt_id=148).count(), 1)

    def test_invalid_candidate_marked_failed(self):
        job = self._job()
        nd = self._full_nd(main_positions=[])
        cand = self._candidate(job, nd)
        result = import_candidate(cand)
        self.assertEqual(result['action'], 'failed')
        cand.refresh_from_db()
        self.assertEqual(cand.status, PlayerImportCandidate.STATUS_INVALID)
        self.assertTrue(cand.validation_errors)

    def test_batch_single_failure_does_not_abort(self):
        job = self._job()
        self._candidate(job, self._full_nd(), tm_player_id=11)
        self._candidate(job, self._full_nd(main_positions=[]), tm_player_id=12)
        outcome = import_selected_candidates(job)
        self.assertEqual(outcome['stats']['created'], 1)
        self.assertEqual(outcome['stats']['failed'], 1)
        self.assertTrue(Player.objects.filter(transfermarkt_id=28049320).exists())

    def test_strength_profile_recalculated_when_computable(self):
        job = self._job()
        cand = self._candidate(job, self._full_nd())
        import_candidate(cand, recalculate=True)
        player = Player.objects.get(transfermarkt_id=28049320)
        from game.strength_service import compute_strength_for_player
        if compute_strength_for_player(player)['computable']:
            self.assertTrue(hasattr(player, 'strength_profile'))


# ── Lease-Token ────────────────────────────────────────────────────────────

class LeaseTokenTests(TestCase):
    def test_new_lease_token_is_random_and_long(self):
        a = ClubPlayerImportJob.new_lease_token()
        b = ClubPlayerImportJob.new_lease_token()
        self.assertEqual(len(a), 64)
        self.assertNotEqual(a, b)
