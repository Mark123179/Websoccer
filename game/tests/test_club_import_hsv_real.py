"""game/tests/test_club_import_hsv_real.py

Regressionstest gegen den ECHTEN HSV-Datensatz (Task #552).

Die übrigen Pipeline-Tests nutzen synthetische Mini-CSVs. Der eigentliche
Produktionsfall ist der real angelieferte HSV-Export (32 Spieler, inkl. zwei
Spielern mit Quell-Rating ohne Attribute). Dieser Test sichert dauerhaft ab:

* Vereinsauflösung über die echte CSV (TM-ID 41).
* Stadion-Idempotenz: Kapazität bleibt 57000, auch bei Re-Import.
* Potential-Invariante (potential ≥ rating) auf jedem Schreibpfad.
* Nicht-blockierendes Melden realer Defekte: die zwei „Rating ohne Attribute"-
  Fälle werden als Validierungsfehler gemeldet, die guten Daten werden trotzdem
  geschrieben.
"""

import os
from decimal import Decimal

from django.test import TestCase

from game.models import (
    Club,
    League,
    Player,
    PlayerSourceRating,
)
from game.club_import import validation
from game.club_import.club_csv_import import MODE_FULL, import_club_csv

FIXTURE = os.path.join(
    os.path.dirname(__file__), 'fixtures', 'hsv_import_ready_2025_26.csv'
)

# Spieler im echten Export mit Quell-Rating, aber ohne Attribute desselben
# Quellblocks (echte Defekte, die dauerhaft als Fehler gemeldet werden müssen).
DEFECT_RATING_WITHOUT_ATTRS = {'Daniel Elfadli', 'Mario Vušković'}

TOTAL_PLAYERS = 32


def _load_fixture():
    # Der echte Export trägt ein UTF-8-BOM — wie in der Produktion gelesen.
    with open(FIXTURE, encoding='utf-8-sig') as fh:
        return fh.read()


class HsvRealImportTests(TestCase):
    def setUp(self):
        self.league = League.objects.create(name='Bundesliga', country='DE')
        self.club = Club.objects.create(
            name='Hamburger SV', short_name='HSV', founded_year=1887,
            transfermarkt_id=41, budget=Decimal('7000000'), league=self.league,
        )

    def test_full_import_writes_good_data_and_reports_real_defects(self):
        text = _load_fixture()
        result = import_club_csv(text, mode=MODE_FULL, recalculate=False)

        # Die zwei echten „Rating ohne Attribute"-Defekte werden als Fehler
        # gemeldet — und nur diese.
        rating_issues = [
            i for i in result['validation_issues']
            if i['code'] == 'rating_without_attrs'
        ]
        self.assertEqual(len(rating_issues), len(DEFECT_RATING_WITHOUT_ATTRS))
        flagged = {i['ref'].rsplit(' [', 1)[0] for i in rating_issues}
        self.assertEqual(flagged, DEFECT_RATING_WITHOUT_ATTRS)
        for issue in rating_issues:
            self.assertEqual(issue['level'], validation.LEVEL_ERROR)

        # Defekte sind harte Fehler → Exit-Code 1, aber der Import bleibt
        # nicht-blockierend: die guten Daten werden trotzdem geschrieben.
        self.assertEqual(result['exit_code'], validation.EXIT_ERRORS)
        self.assertEqual(result['stats']['created'], TOTAL_PLAYERS)
        self.assertEqual(result['stats']['failed'], 0)
        self.assertEqual(Player.objects.count(), TOTAL_PLAYERS)

        # Stadion korrekt aus den Stammdaten angelegt.
        self.club.refresh_from_db()
        self.assertEqual(self.club.stadium.capacity_total, 57000)
        # Spielstand/Ökonomie unangetastet.
        self.assertEqual(self.club.budget, Decimal('7000000'))

        # Potential-Invariante auf jedem geschriebenen Quell-Rating.
        for psr in PlayerSourceRating.objects.all():
            if psr.rating is not None:
                self.assertIsNotNone(psr.potential)
                self.assertGreaterEqual(psr.potential, psr.rating)

        # Auch die Defekt-Spieler selbst wurden importiert (nicht-blockierend).
        for full_name in DEFECT_RATING_WITHOUT_ATTRS:
            first, last = full_name.split(' ', 1)
            self.assertTrue(
                Player.objects.filter(first_name=first, last_name=last).exists(),
                f'{full_name} sollte trotz Defekt importiert sein.',
            )

    def test_reimport_is_idempotent_and_preserves_game_state(self):
        text = _load_fixture()
        import_club_csv(text, mode=MODE_FULL, recalculate=False)

        self.club.refresh_from_db()
        stadium = self.club.stadium
        # Spielstand simulieren: Preise/Ausbaustufen setzen.
        stadium.price_standing = Decimal('19.50')
        stadium.training_level = 2
        stadium.nlz_level = 1
        stadium.save()

        # Zweiter, identischer Import.
        result = import_club_csv(text, mode=MODE_FULL, recalculate=False)

        # Keine neuen Spieler, nur Aktualisierung.
        self.assertEqual(result['stats']['created'], 0)
        self.assertEqual(Player.objects.count(), TOTAL_PLAYERS)

        stadium.refresh_from_db()
        self.club.refresh_from_db()
        self.assertEqual(stadium.capacity_total, 57000)
        self.assertEqual(stadium.price_standing, Decimal('19.50'))
        self.assertEqual(stadium.training_level, 2)
        self.assertEqual(stadium.nlz_level, 1)
        self.assertEqual(self.club.budget, Decimal('7000000'))
        # Re-Import meldet weiterhin dieselben echten Defekte.
        rating_issues = [
            i for i in result['validation_issues']
            if i['code'] == 'rating_without_attrs'
        ]
        self.assertEqual(len(rating_issues), len(DEFECT_RATING_WITHOUT_ATTRS))
