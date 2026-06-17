"""game/tests/test_club_import_pipeline.py

Kanonische CSV-Import-Pipeline (Task #549): Feldschema, Reconcile-Upsert,
Potential-Fallback, Validierungsregelwerk, Modi (Vollanlage/Aktualisierung),
Orchestrierung und Stapel-Fehlerisolierung.

Leitlinie aller Tests: Echtweltdaten werden importiert, Spielstand/Ökonomie
(Budget, Ticketpreise, Ausbaustufen, Zuschauerschnitt, Tribünen-Ausbau) bleibt
unangetastet; erneuter Import ist idempotent.
"""

import csv
import io
import os
import tempfile
from decimal import Decimal

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from game.models import (
    Club,
    ClubPlayerImportJob,
    ClubPublicProfile,
    League,
    Player,
    PlayerImportCandidate,
    PlayerSourceRating,
    Stadium,
)
from game.club_import import validation
from game.club_import.club_csv_import import (
    MODE_FULL,
    MODE_UPDATE,
    ClubImportError,
    import_club_csv,
    resolve_club,
)
from game.club_import.club_reconcile import (
    STADIUM_STAND_RATIOS,
    distribute_capacity,
    reconcile_club,
)
from game.club_import.import_service import import_candidate


# ── CSV-Helfer ───────────────────────────────────────────────────────────────

CSV_COLUMNS = (
    'club_name,club_short_name,founded_year,club_city,country,latitude,'
    'longitude,fmi_club_id,tm_club_id,stadium_name,stadium_city,'
    'stadium_capacity,season_id,season_label,ws_club,real_club,'
    'loaned_from,squad_status,fm_unique_id,tm_player_id,tm_url,fmi_url,'
    'sofifa_id,sofifa_url,first_name,last_name,display_name,'
    'date_of_birth,height_cm,preferred_foot,primary_nationality,'
    'nationalities,tm_market_value_eur,hp_positions,np_positions,'
    'position_method,fmi_rating,fmi_potential,fmi_pace,fmi_stamina'
).split(',')


def hsv_club_fields(**over):
    base = {
        'club_name': 'Hamburger SV', 'club_short_name': 'HSV',
        'founded_year': '1887', 'club_city': 'Hamburg', 'country': 'Deutschland',
        'latitude': '53.587222', 'longitude': '9.898611',
        'fmi_club_id': '947', 'tm_club_id': '41',
        'stadium_name': 'Volksparkstadion', 'stadium_city': 'Hamburg',
        'stadium_capacity': '57000', 'season_id': '2025',
        'season_label': '2025/26', 'ws_club': 'Hamburger SV',
    }
    base.update(over)
    return base


def player_fields(**over):
    base = {
        'squad_status': 'first_team', 'fm_unique_id': '900',
        'tm_player_id': '100', 'sofifa_id': '500',
        'first_name': 'Max', 'last_name': 'Muster', 'display_name': 'Max Muster',
        'date_of_birth': '2000-01-01', 'height_cm': '180',
        'preferred_foot': 'rechts', 'primary_nationality': 'Germany',
        'nationalities': 'Germany', 'tm_market_value_eur': '1000000',
        'hp_positions': 'ST', 'np_positions': '', 'position_method': 'm',
        'fmi_rating': '80', 'fmi_potential': '',
        'fmi_pace': '75', 'fmi_stamina': '70',
    }
    base.update(over)
    return base


def build_csv(club, players):
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CSV_COLUMNS)
    writer.writeheader()
    for p in players:
        row = {c: '' for c in CSV_COLUMNS}
        row.update(club)
        row.update(p)
        writer.writerow(row)
    return buf.getvalue()


def hsv_profile(**over):
    """Geparstes Profil-Dict (wie ``parse_club_profile`` es liefert)."""
    base = {
        'club_name': 'Hamburger SV', 'club_short_name': 'HSV',
        'founded_year': 1887, 'club_city': 'Hamburg', 'country': 'Deutschland',
        'latitude': 53.587222, 'longitude': 9.898611,
        'fmi_club_id': 947, 'tm_club_id': 41,
        'stadium_name': 'Volksparkstadion', 'stadium_city': 'Hamburg',
        'stadium_capacity': 57000, 'season_id': 2025, 'season_label': '2025/26',
        'club_tm_url': '', 'stadium_image_static_path': '',
        'city_image_static_path': '',
    }
    base.update(over)
    return base


# ── Validierungsregelwerk (reine Prädikate) ──────────────────────────────────

class ValidationRuleTests(SimpleTestCase):
    def test_capacity_zero_is_error(self):
        self.assertEqual(validation.check_capacity(0)['code'], 'stadium_capacity_zero')
        self.assertIsNone(validation.check_capacity(57000))

    def test_potential_rules(self):
        self.assertIsNone(validation.check_potential(None, None))
        self.assertEqual(validation.check_potential(80, None)['code'], 'potential_missing')
        self.assertEqual(validation.check_potential(80, 70)['code'], 'potential_below_rating')
        self.assertIsNone(validation.check_potential(80, 85))
        self.assertIsNone(validation.check_potential(80, 80))

    def test_potential_dynamic_warning(self):
        issue = validation.check_potential_raw('DYNAMIC', 'Vušković [FM]')
        self.assertIsNotNone(issue)
        self.assertEqual(issue['level'], validation.LEVEL_WARNING)
        self.assertEqual(issue['code'], 'potential_dynamic')
        self.assertIsNone(validation.check_potential_raw('', 'X'))
        self.assertIsNone(validation.check_potential_raw(None, 'X'))

    def test_validate_parsed_player_flags_dynamic_potential(self):
        nd = {
            'first_name': 'Luka', 'last_name': 'Vušković', 'strong_foot': 'R',
            'fmi_ratings': {
                'rating': 70, 'potential': None,
                'potential_raw': 'DYNAMIC',
                'attrs': {'tempo': 55},
            },
            'sofifa_ratings': None,
        }
        codes = [i['code'] for i in validation.validate_parsed_player(nd)]
        self.assertIn('potential_dynamic', codes)
        levels = [i['level'] for i in validation.validate_parsed_player(nd)]
        self.assertNotIn(validation.LEVEL_ERROR, levels)

    def test_attrs_rule(self):
        self.assertEqual(validation.check_attrs(80, False)['code'], 'rating_without_attrs')
        self.assertIsNone(validation.check_attrs(80, True))
        self.assertIsNone(validation.check_attrs(None, False))

    def test_foot_and_geo_are_warnings(self):
        self.assertEqual(validation.check_foot('')['level'], validation.LEVEL_WARNING)
        self.assertIsNone(validation.check_foot('R'))
        self.assertEqual(validation.check_geo(None, None)['level'], validation.LEVEL_WARNING)
        self.assertIsNone(validation.check_geo(53.5, 9.8))

    def test_exit_code_levels(self):
        err = [validation.check_capacity(0)]
        warn = [validation.check_foot('')]
        self.assertEqual(validation.exit_code([]), validation.EXIT_OK)
        self.assertEqual(validation.exit_code(err), validation.EXIT_ERRORS)
        self.assertEqual(validation.exit_code(warn, strict=False), validation.EXIT_OK)
        self.assertEqual(validation.exit_code(warn, strict=True), validation.EXIT_WARNINGS)

    def test_validate_parsed_player_flags_potential(self):
        nd = {
            'first_name': 'A', 'last_name': 'B', 'strong_foot': 'R',
            'fmi_ratings': {'rating': 80, 'potential': 70, 'attrs': {'tempo': 70}},
            'sofifa_ratings': None,
        }
        codes = [i['code'] for i in validation.validate_parsed_player(nd)]
        self.assertIn('potential_below_rating', codes)


# ── Potential-Fallback ───────────────────────────────────────────────────────

class PotentialFallbackTests(TestCase):
    def setUp(self):
        self.league = League.objects.create(name='L', country='DE')
        self.club = Club.objects.create(
            name='Hamburger SV', short_name='HSV', founded_year=1887,
            transfermarkt_id=41, budget=Decimal('0'), league=self.league,
        )

    def _candidate(self, nd):
        job = ClubPlayerImportJob.objects.create(
            ws_club=self.club, tm_club_id=41, tm_season_id=2025, season_label='x')
        return PlayerImportCandidate.objects.create(
            job=job, tm_player_id=nd['tm_player_id'], selected_for_import=True,
            overwrite_existing=True, normalized_data=nd)

    def test_missing_potential_falls_back_to_rating(self):
        nd = {
            'tm_player_id': 1, 'first_name': 'A', 'last_name': 'B',
            'date_of_birth': '2000-01-01', 'main_positions': ['ST'],
            'secondary_positions': [], 'nationalities': 'Deutschland',
            'loan_status': 'none',
            'fmi_ratings': {'rating': 71, 'potential': None, 'attrs': {'tempo': 70}},
            'sofifa_ratings': None,
        }
        import_candidate(self._candidate(nd), recalculate=False)
        psr = PlayerSourceRating.objects.get(source=PlayerSourceRating.SOURCE_FM)
        self.assertEqual(psr.rating, 71)
        self.assertEqual(psr.potential, 71)

    def test_below_potential_is_clamped_to_rating(self):
        # Vorhandenes, aber zu kleines Potential darf nicht persistiert werden:
        # Invariante potential ≥ rating gilt auf JEDEM Schreibpfad.
        nd = {
            'tm_player_id': 2, 'first_name': 'C', 'last_name': 'D',
            'date_of_birth': '2000-01-01', 'main_positions': ['ST'],
            'secondary_positions': [], 'nationalities': 'Deutschland',
            'loan_status': 'none',
            'fmi_ratings': {'rating': 80, 'potential': 70, 'attrs': {'tempo': 70}},
            'sofifa_ratings': None,
        }
        import_candidate(self._candidate(nd), recalculate=False)
        psr = PlayerSourceRating.objects.get(source=PlayerSourceRating.SOURCE_FM)
        self.assertEqual(psr.rating, 80)
        self.assertEqual(psr.potential, 80)


# ── Reconcile-Upsert / Idempotenz ────────────────────────────────────────────

class ReconcileTests(TestCase):
    def setUp(self):
        self.league = League.objects.create(name='L', country='DE')
        self.club = Club.objects.create(
            name='Hamburger SV', short_name='HSV', founded_year=1887,
            transfermarkt_id=41, budget=Decimal('5000000'), league=self.league,
        )

    def test_distribute_capacity_sums_exactly(self):
        stands = distribute_capacity(57000)
        self.assertEqual(sum(stands.values()), 57000)
        self.assertEqual(set(stands), set(STADIUM_STAND_RATIOS))

    def test_first_reconcile_creates_stadium_57000(self):
        reconcile_club(self.club, hsv_profile())
        self.club.refresh_from_db()
        self.assertEqual(self.club.stadium.capacity_total, 57000)

    def test_reimport_idempotent_keeps_capacity_and_game_state(self):
        reconcile_club(self.club, hsv_profile())
        stadium = self.club.stadium
        stadium.price_standing = Decimal('19.50')
        stadium.training_level = 2
        stadium.nlz_level = 1
        stadium.save()
        pp = self.club.public_profile
        pp.average_attendance = 41000
        pp.save()

        rec = reconcile_club(self.club, hsv_profile())

        stadium.refresh_from_db()
        pp.refresh_from_db()
        self.club.refresh_from_db()
        self.assertEqual(stadium.capacity_total, 57000)
        self.assertEqual(rec['warnings'], [])
        self.assertEqual(stadium.price_standing, Decimal('19.50'))
        self.assertEqual(stadium.training_level, 2)
        self.assertEqual(stadium.nlz_level, 1)
        self.assertEqual(pp.average_attendance, 41000)
        self.assertEqual(self.club.budget, Decimal('5000000'))

    def test_reconcile_preserves_expanded_capacity_and_warns(self):
        reconcile_club(self.club, hsv_profile())
        stadium = self.club.stadium
        stadium.nord_standing += 3000  # Ausbau auf 60000 (Spielstand)
        stadium.save()
        self.assertEqual(stadium.capacity_total, 60000)

        rec = reconcile_club(self.club, hsv_profile())

        stadium.refresh_from_db()
        self.assertEqual(stadium.capacity_total, 60000)
        self.assertTrue(rec['warnings'])

    def test_unique_ids_fill_if_empty_only(self):
        # tm_id ist bereits 41 → CSV-Wert 99 darf NICHT überschreiben.
        reconcile_club(self.club, hsv_profile(tm_club_id=99))
        self.club.refresh_from_db()
        self.assertEqual(self.club.transfermarkt_id, 41)


# ── Modi: Aktualisierung ─────────────────────────────────────────────────────

class UpdateModeTests(TestCase):
    def setUp(self):
        self.league = League.objects.create(name='L', country='DE')
        self.club = Club.objects.create(
            name='Hamburger SV', short_name='HSV', founded_year=1887,
            transfermarkt_id=41, budget=Decimal('0'), league=self.league,
        )

    def _candidate(self, nd):
        job = ClubPlayerImportJob.objects.create(
            ws_club=self.club, tm_club_id=41, tm_season_id=2025, season_label='x')
        return PlayerImportCandidate.objects.create(
            job=job, tm_player_id=nd['tm_player_id'], selected_for_import=True,
            overwrite_existing=True, normalized_data=nd)

    def _base_nd(self, **over):
        base = {
            'tm_player_id': 100, 'fm_inside_id': 900, 'first_name': 'Alt',
            'last_name': 'Spieler', 'date_of_birth': '2000-01-01',
            'height_cm': 180, 'strong_foot': 'R', 'nationalities': 'Deutschland',
            'main_positions': ['ST'], 'secondary_positions': [],
            'market_value': 1000000, 'loan_status': 'none',
            'fmi_ratings': {'rating': 70, 'potential': 75, 'attrs': {'tempo': 70}},
            'sofifa_ratings': None,
        }
        base.update(over)
        return base

    def test_update_skips_new_player(self):
        nd = self._base_nd(tm_player_id=777, fm_inside_id=777)
        result = import_candidate(self._candidate(nd), update_only=True, recalculate=False)
        self.assertEqual(result['action'], 'skipped')
        self.assertFalse(Player.objects.filter(transfermarkt_id=777).exists())

    def test_update_changes_volatile_keeps_identity(self):
        import_candidate(self._candidate(self._base_nd()), recalculate=False)

        upd = self._base_nd(
            first_name='Neu', last_name='Name', height_cm=999, strong_foot='L',
            market_value=5000000, main_positions=['IV'],
            fmi_ratings={'rating': 85, 'potential': 90, 'attrs': {'tempo': 80}},
        )
        import_candidate(self._candidate(upd), update_only=True, recalculate=False)

        p = Player.objects.get(transfermarkt_id=100)
        # Identität unverändert
        self.assertEqual(p.first_name, 'Alt')
        self.assertEqual(p.last_name, 'Spieler')
        self.assertEqual(p.height_cm, 180)
        self.assertEqual(p.strong_foot, 'R')
        # Volatile Felder aktualisiert
        self.assertEqual(p.market_value, 5000000)
        self.assertEqual(p.main_position_1, 'IV')
        psr = PlayerSourceRating.objects.get(player=p, source=PlayerSourceRating.SOURCE_FM)
        self.assertEqual(psr.rating, 85)


# ── Orchestrierung ───────────────────────────────────────────────────────────

class OrchestrationTests(TestCase):
    def setUp(self):
        self.league = League.objects.create(name='L', country='DE')
        self.club = Club.objects.create(
            name='Hamburger SV', short_name='HSV', founded_year=1887,
            transfermarkt_id=41, budget=Decimal('7000000'), league=self.league,
        )

    def test_full_import_end_to_end(self):
        text = build_csv(hsv_club_fields(), [player_fields(fmi_rating='80', fmi_potential='')])
        result = import_club_csv(text, mode=MODE_FULL, recalculate=False)

        self.assertEqual(result['exit_code'], validation.EXIT_OK)
        self.assertEqual(result['stats']['created'], 1)
        self.club.refresh_from_db()
        self.assertEqual(self.club.stadium.capacity_total, 57000)
        self.assertEqual(self.club.budget, Decimal('7000000'))
        p = Player.objects.get(transfermarkt_id=100)
        psr = PlayerSourceRating.objects.get(player=p, source=PlayerSourceRating.SOURCE_FM)
        self.assertEqual(psr.potential, 80)  # Fallback

    def test_resolve_unknown_club_raises(self):
        with self.assertRaises(ClubImportError):
            resolve_club({'tm_club_id': 999999, 'club_name': 'Unbekannt FC'})

    def test_dry_run_writes_nothing(self):
        text = build_csv(hsv_club_fields(), [player_fields()])
        result = import_club_csv(text, mode=MODE_FULL, dry_run=True)
        self.assertIsNone(result['stats'])
        self.assertFalse(Player.objects.filter(transfermarkt_id=100).exists())


# ── Stapel-Import: Fehlerisolierung ──────────────────────────────────────────

class BatchImportTests(TestCase):
    def setUp(self):
        self.league = League.objects.create(name='L', country='DE')
        self.club = Club.objects.create(
            name='Hamburger SV', short_name='HSV', founded_year=1887,
            transfermarkt_id=41, budget=Decimal('0'), league=self.league,
        )

    def test_batch_isolates_failing_file(self):
        tmp = tempfile.mkdtemp()
        good = build_csv(hsv_club_fields(), [player_fields(tm_player_id='100')])
        bad = build_csv(
            hsv_club_fields(club_name='Unbekannt FC', tm_club_id='999999',
                            ws_club='Unbekannt FC'),
            [player_fields(tm_player_id='200')],
        )
        with open(os.path.join(tmp, 'a_good.csv'), 'w', encoding='utf-8') as fh:
            fh.write(good)
        with open(os.path.join(tmp, 'b_bad.csv'), 'w', encoding='utf-8') as fh:
            fh.write(bad)

        with self.assertRaises(SystemExit) as ctx:
            call_command('import_clubs_batch', dir=tmp)
        self.assertEqual(ctx.exception.code, validation.EXIT_ERRORS)

        # Gute Datei wurde trotz Fehler in der anderen importiert.
        self.assertTrue(Player.objects.filter(transfermarkt_id=100).exists())
        self.assertFalse(Player.objects.filter(transfermarkt_id=200).exists())
