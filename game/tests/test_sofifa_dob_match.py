"""DOB-basiertes Matching im SoFIFA/CMTracker-CSV-Import.

Hintergrund: Namen aus Transfermarkt und CMTracker weichen oft ab (Zweitnamen,
Schreibweise), und ausgeliehene Spieler werden in der CSV unter ihrem
Stammverein gefuehrt. Das Matching laeuft daher primaer ueber das Geburtsdatum,
vereinsuebergreifend und unabhaengig vom Namen.

Getestet wird der produktive Pfad (game.sofifa_import_service.run_sofifa_import),
der sowohl vom CLI-Command als auch vom Creator-Upload genutzt wird.
"""

from datetime import date
from decimal import Decimal

from django.test import TestCase

from game.models import (
    Club,
    DataSource,
    League,
    Player,
    PlayerSourceRating,
)
from game.sofifa_import_service import parse_dob, run_sofifa_import


class ParseDobTests(TestCase):
    def test_iso_with_time_and_z(self):
        self.assertEqual(
            parse_dob('1999-04-15T00:00:00.000Z'), date(1999, 4, 15))

    def test_plain_iso(self):
        self.assertEqual(parse_dob('2001-09-13'), date(2001, 9, 13))

    def test_german_format(self):
        self.assertEqual(parse_dob('13.09.2001'), date(2001, 9, 13))

    def test_empty_and_garbage(self):
        self.assertIsNone(parse_dob(''))
        self.assertIsNone(parse_dob('keine Zahl'))
        self.assertIsNone(parse_dob('2001-13-40'))  # ungueltiges Datum


class SofifaDobMatchTests(TestCase):
    def setUp(self):
        league = League.objects.create(name='Testliga', country='Deutschland')
        self.hsv = Club.objects.create(
            name='Hamburger SV', short_name='HSV', founded_year=1887,
            budget=Decimal('1000000.00'), league=league)
        self.basel = Club.objects.create(
            name='FC Basel', short_name='FCB', founded_year=1893,
            budget=Decimal('1000000.00'), league=league)
        DataSource.objects.get_or_create(
            code=DataSource.CODE_SOFIFA, defaults={'name': 'SoFIFA'})

    def _player(self, first, last, dob, club, **extra):
        return Player.objects.create(
            first_name=first, last_name=last, age=25, position='ST',
            main_position_1='ST', potential=80,
            market_value=Decimal('1000000.00'),
            salary_per_match=Decimal('10000.00'),
            club=club, date_of_birth=dob, **extra)

    def _rating(self, player):
        return PlayerSourceRating.objects.filter(
            player=player, source=PlayerSourceRating.SOURCE_EA).first()

    def _run(self, csv_text):
        return run_sofifa_import(csv_text, dry_run=False, skip_recalculate=True)

    # ── Leihspieler: CSV-Verein weicht ab, DOB matcht trotzdem ───────────────
    def test_dob_matches_across_clubs_for_loaned_player(self):
        """Otele-Fall: im Spiel beim HSV, in der CSV beim (existierenden)
        Stammverein FC Basel. Der Namens-Fallback wuerde auf Basel filtern und
        scheitern; ueber das DOB wird er trotzdem gefunden."""
        otele = self._player('Philip', 'Otele', date(1999, 4, 15), self.hsv)
        csv = ('sofifa_id,name,club,overall,dob\n'
               '266395,Philip Otele,FC Basel,73,1999-04-15\n')
        res = self._run(csv)

        self.assertEqual(res['stats']['new'], 1)
        self.assertEqual(res['stats']['unmatched'], 0)
        self.assertEqual(res['row_results'][0]['match_mode'], 'dob')
        rating = self._rating(otele)
        self.assertIsNotNone(rating)
        self.assertEqual(rating.rating, 73)

    # ── Abweichender Name (Zweitname) wird ignoriert ─────────────────────────
    def test_dob_matches_despite_name_difference(self):
        """Koenigsdoerffer-Fall: CSV nennt einen Zweitnamen, im Spiel fehlt er.
        Reines Namens-Matching wuerde scheitern; ueber das DOB matcht es."""
        koenig = self._player(
            'Ransford', 'Königsdörffer', date(2001, 9, 13), self.hsv)
        csv = ('sofifa_id,name,club,overall,dob\n'
               '255036,Ransford-Yeboah Königsdörffer,Hamburger SV,70,'
               '2001-09-13\n')
        res = self._run(csv)

        self.assertEqual(res['row_results'][0]['match_mode'], 'dob')
        self.assertIsNotNone(self._rating(koenig))

    # ── Gleiches DOB: Namensaehnlichkeit entscheidet ─────────────────────────
    def test_shared_dob_resolved_by_name(self):
        a = self._player('Max', 'Mustermann', date(2000, 1, 1), self.hsv)
        b = self._player('Erik', 'Beispiel', date(2000, 1, 1), self.hsv)
        csv = ('sofifa_id,name,overall,dob\n'
               '111,Max Mustermann,75,2000-01-01\n')
        res = self._run(csv)

        self.assertEqual(res['row_results'][0]['match_mode'], 'dob')
        self.assertIsNotNone(self._rating(a))
        self.assertIsNone(self._rating(b))

    # ── CMTracker-Header info.birthdate wird erkannt ─────────────────────────
    def test_cmtracker_birthdate_header(self):
        otele = self._player('Philip', 'Otele', date(1999, 4, 15), self.hsv)
        csv = ('info.playerid,info.name.knownas,info.overallrating,'
               'info.birthdate\n'
               '266395,Philip Otele,73,1999-04-15T00:00:00.000Z\n')
        res = self._run(csv)

        self.assertEqual(res['row_results'][0]['match_mode'], 'dob')
        self.assertIsNotNone(self._rating(otele))

    # ── Gleiches DOB UND gleicher Name: kein erzwungenes Matching ────────────
    def test_shared_dob_equal_name_not_forced(self):
        """Zwei Spieler mit identischem Geburtsdatum UND identischem Namen
        duerfen nicht erzwungen gematcht werden – der Tie-Break bleibt
        mehrdeutig und faellt sauber durch (unmatched statt Fehlzuordnung)."""
        self._player('Lars', 'Zwilling', date(2003, 3, 3), self.hsv)
        self._player('Lars', 'Zwilling', date(2003, 3, 3), self.basel)
        csv = ('sofifa_id,name,overall,dob\n'
               '333,Lars Zwilling,75,2003-03-03\n')
        res = self._run(csv)

        self.assertEqual(res['stats']['unmatched'], 1)
        self.assertEqual(res['row_results'][0]['action'], 'unmatched')

    # ── Ohne DOB-Spalte bleibt das alte Namens-Matching erhalten ─────────────
    def test_without_dob_falls_back_to_name(self):
        p = self._player('Thomas', 'Mueller', date(1989, 9, 13), self.hsv)
        csv = ('sofifa_id,name,club,overall\n'
               '222,Thomas Mueller,Hamburger SV,82\n')
        res = self._run(csv)

        self.assertEqual(res['row_results'][0]['match_mode'], 'name')
        self.assertIsNotNone(self._rating(p))
