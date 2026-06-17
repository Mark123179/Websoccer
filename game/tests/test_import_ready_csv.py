"""game/tests/test_import_ready_csv.py

Adapter für „import_ready"-CSV (Komma-getrennt, englische Header) + die additive
Leihstatus-Logik im Importdienst.

Abgedeckte Bereiche:
  - Nationalitäten-Normalisierung (Englisch→Deutsch, Dedup, ``|``-Trennung)
  - Positions-Parsing (interne Codes, keine TM-Übersetzung)
  - FMI-/SoFIFA-Attribut-Mapping inkl. NULL-Erhalt
  - Leihstatus-Ableitung im Adapter (loaned_in/loaned_out/none)
  - Importdienst: loaned_out → vereinslos + Eigentümer; loaned_in → Leihgeber
"""

from decimal import Decimal

from django.test import TestCase

from game.models import (
    Club,
    ClubPlayerImportJob,
    League,
    Player,
    PlayerImportCandidate,
    PlayerSourceRating,
)
from game.club_import.import_ready_csv import (
    normalize_nationalities,
    parse_import_ready_csv,
    row_to_normalized,
    translate_country,
)
from game.club_import.import_service import import_candidate


# ── Adapter (reine Logik) ───────────────────────────────────────────────────

class ImportReadyAdapterTests(TestCase):
    def test_translate_country_english_to_german(self):
        self.assertEqual(translate_country('Germany'), 'Deutschland')
        self.assertEqual(translate_country('United States'), 'Vereinigte Staaten')
        self.assertEqual(translate_country('Norway'), 'Norwegen')

    def test_translate_country_keeps_german_and_unknown(self):
        self.assertEqual(translate_country('Deutschland'), 'Deutschland')
        self.assertEqual(translate_country('Suriname'), 'Suriname')
        self.assertEqual(translate_country('Atlantis'), 'Atlantis')

    def test_normalize_nationalities_dedup_and_order(self):
        primary, joined = normalize_nationalities('Portugal', 'Portugal|Portugal')
        self.assertEqual(primary, 'Portugal')
        self.assertEqual(joined, 'Portugal')

    def test_normalize_nationalities_mixed_language(self):
        primary, joined = normalize_nationalities('Nigeria', 'Nigeria|Deutschland')
        self.assertEqual(primary, 'Nigeria')
        self.assertEqual(joined, 'Nigeria, Deutschland')

    def test_positions_are_internal_codes_split_on_pipe(self):
        row = self._row(hp_positions='LV', np_positions='RM|LM')
        nd, _ = row_to_normalized(row)
        self.assertEqual(nd['main_positions'], ['LV'])
        self.assertEqual(nd['secondary_positions'], ['RM', 'LM'])

    def test_fmi_and_sofifa_attr_mapping(self):
        row = self._row(
            fmi_rating='80', fmi_pace='75', fmi_gk_reflexes='12',
            sofifa_rating='78', sofifa_short_passing='70',
            sofifa_long_passing='66', sofifa_gk_passing='11',
        )
        nd, _ = row_to_normalized(row)
        self.assertEqual(nd['fmi_ratings']['rating'], 80)
        self.assertEqual(nd['fmi_ratings']['attrs']['tempo'], 75)
        self.assertEqual(nd['fmi_ratings']['attrs']['tw_reflexe'], 12)
        self.assertEqual(nd['sofifa_ratings']['attrs']['passspiel'], 70)
        self.assertEqual(nd['sofifa_ratings']['attrs']['tw_passen'], 11)
        # long_passing hat kein internes Feld → verworfen.
        self.assertNotIn('uebersicht', nd['sofifa_ratings']['attrs'])

    def test_missing_rating_yields_none(self):
        row = self._row(fmi_rating='', sofifa_rating='')
        nd, _ = row_to_normalized(row)
        self.assertIsNone(nd['fmi_ratings'])
        self.assertIsNone(nd['sofifa_ratings'])

    def test_loan_status_loaned_in(self):
        row = self._row(squad_status='loaned_in', loaned_from='Tottenham Hotspur')
        nd, _ = row_to_normalized(row)
        self.assertEqual(nd['loan_status'], 'loaned_in')
        self.assertEqual(nd['loaned_from']['name'], 'Tottenham Hotspur')

    def test_loan_status_loaned_out_has_no_club_refs(self):
        row = self._row(squad_status='loaned_out',
                        real_club='AS Saint-Étienne', loaned_from='Hamburger SV')
        nd, _ = row_to_normalized(row)
        self.assertEqual(nd['loan_status'], 'loaned_out')
        self.assertIsNone(nd['loaned_from'])
        self.assertIsNone(nd['real_club'])

    def test_first_team_is_status_none(self):
        row = self._row(squad_status='first_team')
        nd, _ = row_to_normalized(row)
        self.assertEqual(nd['loan_status'], 'none')

    def test_parse_full_csv(self):
        text = self._csv_text()
        parsed = parse_import_ready_csv(text)
        self.assertEqual(parsed['club']['club_name'], 'Hamburger SV')
        self.assertEqual(parsed['club']['founded_year'], 1887)
        self.assertEqual(parsed['club']['stadium_capacity'], 57000)
        self.assertEqual(len(parsed['players']), 2)

    # ── Helfer ──────────────────────────────────────────────────────────────
    def _row(self, **over):
        base = {
            'display_name': 'Test Spieler', 'first_name': 'Test',
            'last_name': 'Spieler', 'tm_player_id': '100',
            'fm_unique_id': '900', 'sofifa_id': '500',
            'tm_url': '', 'fmi_url': '', 'sofifa_url': '',
            'date_of_birth': '2000-01-01', 'height_cm': '180',
            'preferred_foot': 'rechts',
            'primary_nationality': 'Deutschland', 'nationalities': 'Deutschland',
            'tm_market_value_eur': '1000000',
            'hp_positions': 'ST', 'np_positions': '',
            'squad_status': 'first_team', 'real_club': '', 'loaned_from': '',
        }
        base.update(over)
        return base

    def _csv_text(self):
        header = (
            'club_name,club_short_name,founded_year,club_city,country,latitude,'
            'longitude,fmi_club_id,tm_club_id,stadium_name,stadium_city,'
            'stadium_capacity,season_id,season_label,ws_club,real_club,'
            'loaned_from,squad_status,fm_unique_id,tm_player_id,tm_url,fmi_url,'
            'sofifa_id,sofifa_url,first_name,last_name,display_name,'
            'date_of_birth,height_cm,preferred_foot,primary_nationality,'
            'nationalities,tm_market_value_eur,hp_positions,np_positions,'
            'position_method,fmi_rating,fmi_potential'
        )
        club = ('Hamburger SV,HSV,1887,Hamburg,Deutschland,53.587222,9.898611,'
                '947,41,Volksparkstadion,Hamburg,57000,2025,2025/26,')
        r1 = (club + 'Hamburger SV,,first_team,900,100,,,500,,Max,Muster,'
              'Max Muster,2000-01-01,180,rechts,Germany,Germany,1000000,ST,,m,80,82')
        r2 = (club + 'Hamburger SV,,loaned_in,901,101,,,501,,Luka,Vuskovic,'
              'Luka Vuskovic,2007-01-01,190,rechts,Croatia,Croatia,5000000,IV,,m,70,85')
        return '\n'.join([header, r1, r2])


# ── Importdienst: additive Leihstatus-Logik ─────────────────────────────────

class ImportServiceLoanStatusTests(TestCase):
    def setUp(self):
        self.league = League.objects.create(name='LeihLiga', country='DE')
        self.ws_club = Club.objects.create(
            name='Hamburger SV', short_name='HSV', founded_year=1887,
            transfermarkt_id=41, budget=Decimal('0'), league=self.league,
        )

    def _job(self):
        return ClubPlayerImportJob.objects.create(
            ws_club=self.ws_club, tm_club_id=41, tm_season_id=2025,
            season_label='2025/26',
        )

    def _candidate(self, nd, tm_player_id=1):
        nd = dict(nd, tm_player_id=tm_player_id)
        return PlayerImportCandidate.objects.create(
            job=self._job(), tm_player_id=tm_player_id,
            selected_for_import=True, overwrite_existing=True,
            normalized_data=nd,
        )

    def _nd(self, **over):
        base = {
            'tm_player_id': 1, 'first_name': 'A', 'last_name': 'B',
            'date_of_birth': '2000-01-01', 'main_positions': ['ST'],
            'secondary_positions': [], 'nationalities': 'Deutschland',
            'real_club': None, 'loaned_from': None, 'loan_status': 'none',
            'fmi_ratings': {'rating': 70, 'potential': 72, 'attrs': {'tempo': 70}},
            'sofifa_ratings': None,
        }
        base.update(over)
        return base

    def test_loaned_out_player_is_clubless_owned_by_ws_club(self):
        cand = self._candidate(self._nd(loan_status='loaned_out'), tm_player_id=10)
        import_candidate(cand)
        p = Player.objects.get(transfermarkt_id=10)
        self.assertIsNone(p.club)
        self.assertEqual(p.real_life_club, self.ws_club)
        self.assertIsNone(p.loan_partner_club)
        self.assertEqual(p.loan_status, 'loaned_out')
        self.assertTrue(p.is_loaned_out)

    def test_loaned_in_player_at_ws_club_with_parent(self):
        nd = self._nd(
            loan_status='loaned_in',
            loaned_from={'tm_id': None, 'name': 'Tottenham Hotspur',
                         'profile_url': ''},
        )
        cand = self._candidate(nd, tm_player_id=11)
        import_candidate(cand)
        p = Player.objects.get(transfermarkt_id=11)
        self.assertEqual(p.club, self.ws_club)
        parent = Club.objects.get(name='Tottenham Hotspur')
        self.assertEqual(p.real_life_club, parent)
        self.assertEqual(p.loan_partner_club, parent)
        self.assertEqual(p.loan_status, 'loaned_in')

    def test_first_team_player_belongs_to_ws_club(self):
        cand = self._candidate(self._nd(loan_status='none'), tm_player_id=12)
        import_candidate(cand)
        p = Player.objects.get(transfermarkt_id=12)
        self.assertEqual(p.club, self.ws_club)
        self.assertEqual(p.real_life_club, self.ws_club)
        self.assertEqual(p.loan_status, 'none')
        fm = PlayerSourceRating.objects.get(
            player=p, source=PlayerSourceRating.SOURCE_FM)
        self.assertEqual(fm.tempo, 70)
