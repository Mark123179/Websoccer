"""Tests Finanzsystem Phase 1 (Spec Kap. 2, 4, 10, 12, 15).

Deckt ab: book()/book_many() (Deckungsregel, Konto-Cache, Atomarität),
Gehaltsformel, Finanz-Spieltagslauf (Buchungskette + Idempotenz) und die
Ledger-Integritätsprüfung.
"""

from decimal import Decimal

from django.test import TestCase

from game.economy.booking import InsufficientFunds, book, book_many
from game.economy.integrity import check_ledger_integrity
from game.economy.matchday_run import run_matchday_finance
from game.economy.params import get_param
from game.economy.salary import (
    gehalt_pro_pflichtspiel, jahresgehalt, load_salary_params,
)
from game.models import (
    Club, FinanceMatchdayRun, FinanceTransaction, GameSeasonState, League,
    Player, SeasonFixture,
)


def _mk_club(name, budget='0.00', league=None):
    if league is None:
        league, _ = League.objects.get_or_create(
            name='Finanz-Testliga', country='Deutschland')
    return Club.objects.create(
        name=name, short_name=name[:3].upper(), founded_year=1900,
        budget=Decimal(budget), league=league,
    )


class EconomyParameterSeedTests(TestCase):
    def test_seed_parameters_present(self):
        self.assertEqual(get_param('GEHALT_DIVISOR', '0'), 40)
        self.assertEqual(get_param('BETRIEBSQUOTE', '0'), 0.34)
        toepfe = get_param('TV_TOEPFE', '0')
        self.assertIn('1', toepfe)
        self.assertIn('9', toepfe)

    def test_fallback_to_earlier_season(self):
        # Saison "5" ist nicht geseedet → Fallback auf Saison "0".
        self.assertEqual(get_param('GEHALT_DIVISOR', '5'), 40)


class BookingTests(TestCase):
    def setUp(self):
        GameSeasonState.objects.create(current_season=0)
        self.club = _mk_club('FC Buchung', budget='1000000.00')

    def test_income_writes_ledger_and_cache(self):
        tx = book(self.club, 'TICKET', Decimal('50000'),
                  beschreibung='Heimspiel', spieltag=3)
        self.assertEqual(tx.typ, 'TICKET')
        self.assertEqual(tx.saison, '0')
        self.assertEqual(tx.spieltag, 3)
        # Übergebene Instanz UND DB-Zeile sind aktualisiert.
        self.assertEqual(self.club.budget, Decimal('1050000.00'))
        self.club.refresh_from_db()
        self.assertEqual(self.club.budget, Decimal('1050000.00'))

    def test_active_expense_without_funds_rejected(self):
        with self.assertRaises(InsufficientFunds):
            book(self.club, 'TRANSFER_AUS', Decimal('-2000000'))
        self.club.refresh_from_db()
        self.assertEqual(self.club.budget, Decimal('1000000.00'))
        self.assertFalse(FinanceTransaction.objects.filter(club=self.club).exists())

    def test_pflicht_expense_may_go_negative(self):
        book(self.club, 'GEHALT', Decimal('-1500000'), pflicht=True)
        self.club.refresh_from_db()
        self.assertEqual(self.club.budget, Decimal('-500000.00'))

    def test_book_many_rolls_back_all_on_insufficient_funds(self):
        club2 = _mk_club('FC Zwei', budget='100.00')
        with self.assertRaises(InsufficientFunds):
            book_many([
                {'club': self.club, 'typ': 'TRANSFER_EIN', 'betrag': Decimal('500')},
                {'club': club2, 'typ': 'TRANSFER_AUS', 'betrag': Decimal('-500')},
            ])
        self.club.refresh_from_db()
        club2.refresh_from_db()
        self.assertEqual(self.club.budget, Decimal('1000000.00'))
        self.assertEqual(club2.budget, Decimal('100.00'))
        self.assertEqual(FinanceTransaction.objects.count(), 0)

    def test_book_many_transfer_between_clubs(self):
        club2 = _mk_club('FC Zwei', budget='5000000.00')
        book_many([
            {'club': club2, 'typ': 'TRANSFER_AUS', 'betrag': Decimal('-3000000')},
            {'club': self.club, 'typ': 'TRANSFER_EIN', 'betrag': Decimal('3000000')},
        ])
        self.club.refresh_from_db()
        club2.refresh_from_db()
        self.assertEqual(self.club.budget, Decimal('4000000.00'))
        self.assertEqual(club2.budget, Decimal('2000000.00'))


class SalaryFormulaTests(TestCase):
    def setUp(self):
        GameSeasonState.objects.create(current_season=0)
        self.params = load_salary_params('0')

    def test_jahresgehalt_at_anker_is_basis_prozent(self):
        # MW == Anker → log10(1) = 0 → GEHALT_BASIS (18 %).
        g = jahresgehalt(Decimal('1000000'), Decimal('1000000'), self.params)
        self.assertEqual(g, Decimal('180000.00'))

    def test_prozent_untergrenze_greift(self):
        # Kleinst-MW wird auf MW_MINIMUM geklemmt und auf 12 % gefloort.
        g = jahresgehalt(Decimal('1000'), Decimal('5000000'), self.params)
        self.assertEqual(g, Decimal('6000.00'))

    def test_gehalt_pro_pflichtspiel_divisor(self):
        g = gehalt_pro_pflichtspiel(
            Decimal('1000000'), Decimal('1000000'), self.params)
        self.assertEqual(g, Decimal('4500.00'))


class MatchdayFinanceRunTests(TestCase):
    def setUp(self):
        GameSeasonState.objects.create(current_season=0)
        self.league = League.objects.create(
            name='Finanz-Bundesliga', country='Deutschland')
        self.heim = _mk_club('FC Heim', budget='0.00', league=self.league)
        self.gast = _mk_club('FC Gast', budget='0.00', league=self.league)
        self.fixture = SeasonFixture.objects.create(
            league=self.league, season='0', matchday=1,
            home_club=self.heim, away_club=self.gast, is_played=True,
        )
        Player.objects.create(
            club=self.heim, first_name='Testo', last_name='Stürmer', age=25,
            position='Sturm', main_position_1='ST',
            nationalities='Deutschland', market_value=Decimal('2000000'),
        )

    def test_run_books_tv_gehalt_betrieb(self):
        summary = run_matchday_finance(self.league, '0', 1)
        self.assertEqual(summary['errors'], [])
        self.assertEqual(len(summary['clubs']), 2)

        for club in (self.heim, self.gast):
            self.assertTrue(FinanceTransaction.objects.filter(
                club=club, typ='TV_SOCKEL', spieltag=1).exists())
            self.assertTrue(FinanceTransaction.objects.filter(
                club=club, typ='BETRIEB', spieltag=1).exists())

        # Nur der Heimverein hat Kaderspieler → nur er zahlt Gehälter.
        self.assertTrue(FinanceTransaction.objects.filter(
            club=self.heim, typ='GEHALT', spieltag=1).exists())
        self.assertFalse(FinanceTransaction.objects.filter(
            club=self.gast, typ='GEHALT').exists())

        # Einnahmen vor Ausgaben (Kap. 12.2): TV rein, Gehalt+Betrieb raus.
        gehalt = FinanceTransaction.objects.get(club=self.heim, typ='GEHALT')
        self.assertLess(gehalt.betrag, 0)

    def test_run_is_idempotent(self):
        run_matchday_finance(self.league, '0', 1)
        count_before = FinanceTransaction.objects.count()
        summary = run_matchday_finance(self.league, '0', 1)
        self.assertEqual(FinanceTransaction.objects.count(), count_before)
        self.assertTrue(all(r['skipped'] for r in summary['clubs']))
        self.assertEqual(
            FinanceMatchdayRun.objects.filter(saison='0', spieltag=1).count(), 2)

    def test_cache_equals_ledger_after_run(self):
        run_matchday_finance(self.league, '0', 1)
        report = check_ledger_integrity()
        self.assertEqual(report['mismatches'], [])

    def test_betriebskosten_taxes_income_exactly_once(self):
        """Fenster (prev.run_at, run.run_at]: jede Einnahme genau EINMAL 34 %.

        Erstlauf: leeres Fenster → nur Sockel-Rate. Folgelauf: Einnahmen des
        Erstlaufs fallen genau einmal ins Fenster — keine Doppelbelastung.
        """
        from game.economy.params import get_decimal

        run_matchday_finance(self.league, '0', 1)
        SeasonFixture.objects.create(
            league=self.league, season='0', matchday=2,
            home_club=self.gast, away_club=self.heim, is_played=True,
        )
        run_matchday_finance(self.league, '0', 2)

        sockel_rate = (
            get_decimal('BETRIEB_SOCKEL', '0') / get_decimal('GEHALT_DIVISOR', '0')
        ).quantize(Decimal('0.01'))
        quote = get_decimal('BETRIEBSQUOTE', '0')

        # Alle Einnahmen des Erstlaufs (seit Phase 2: TV-Sockel + Sponsor-Fix).
        from django.db.models import Sum
        einnahmen1 = FinanceTransaction.objects.filter(
            club=self.heim, spieltag=1, betrag__gt=0,
        ).aggregate(s=Sum('betrag'))['s'] or Decimal('0')
        betrieb1 = FinanceTransaction.objects.get(
            club=self.heim, typ='BETRIEB', spieltag=1).betrag
        betrieb2 = FinanceTransaction.objects.get(
            club=self.heim, typ='BETRIEB', spieltag=2).betrag

        self.assertEqual(-betrieb1, sockel_rate)
        self.assertEqual(
            -betrieb2,
            (sockel_rate + quote * einnahmen1).quantize(Decimal('0.01')))

    def test_missing_matchday_reports_error(self):
        summary = run_matchday_finance(self.league, '0', 99)
        self.assertEqual(summary['clubs'], [])
        self.assertTrue(summary['errors'])


class LedgerIntegrityTests(TestCase):
    def setUp(self):
        GameSeasonState.objects.create(current_season=0)

    def test_detects_and_fixes_drift(self):
        club = _mk_club('FC Drift', budget='0.00')
        book(club, 'TICKET', Decimal('100000'))
        # Cache manipulieren (simulierter Alt-Code-Fehler).
        Club.objects.filter(pk=club.pk).update(budget=Decimal('999999'))

        report = check_ledger_integrity()
        drift = [m for m in report['mismatches'] if m['club_id'] == club.pk]
        self.assertEqual(len(drift), 1)
        self.assertEqual(drift[0]['diff'], Decimal('899999.00'))

        report = check_ledger_integrity(fix=True)
        self.assertGreaterEqual(report['fixed'], 1)
        club.refresh_from_db()
        self.assertEqual(club.budget, Decimal('100000.00'))

    def test_club_without_ledger_and_budget_ok(self):
        _mk_club('FC Null', budget='0.00')
        report = check_ledger_integrity()
        self.assertEqual(report['mismatches'], [])
