"""Tests für den Legacy-Buchungs-Wrapper (game/finance.py) und die
Creator-Finanzanalyse.

Seit Finanzsystem Phase 1 delegiert log_club_transaction() an
game.economy.booking.book(): es schreibt eine FinanceTransaction-Zeile
UND mutiert Club.budget atomar. Diese Tests decken den Wrapper
(Saison-Konvention, Typ-Mapping, Kürzung, Budget-Wirkung), die
Ticketbuchung in record_matchday_revenue sowie die Analyse-Seite ab.
"""

from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from game.finance import current_sim_season, log_club_transaction
from game.models import (
    Club, FinanceTransaction, GameSeasonState, League, Stadium,
)
from game.stadium_revenue import record_matchday_revenue


def _mk_club(name='FC Test', budget='10000000.00', league=None):
    if league is None:
        league, _ = League.objects.get_or_create(name='Fixture-Liga', country='DE')
    return Club.objects.create(
        name=name, short_name=name[:3].upper(), founded_year=1900,
        budget=Decimal(budget), league=league,
    )


class FinanceHelperTests(TestCase):
    def test_current_sim_season_reads_game_state(self):
        GameSeasonState.objects.create(current_season=3)
        self.assertEqual(current_sim_season(), '3')

    def test_current_sim_season_empty_without_state(self):
        self.assertEqual(current_sim_season(), '')

    def test_log_defaults_to_sim_season(self):
        GameSeasonState.objects.create(current_season=2)
        club = _mk_club()
        tx = log_club_transaction(club, 'sonstige_ausgabe', 'Test', Decimal('-100'))
        self.assertEqual(tx.saison, '2')
        self.assertEqual(tx.typ, 'KORREKTUR_ADMIN')
        self.assertEqual(tx.referenz_typ, 'legacy:sonstige_ausgabe')
        self.assertEqual(tx.betrag, Decimal('-100'))

    def test_log_mutates_budget(self):
        GameSeasonState.objects.create(current_season=2)
        club = _mk_club()
        log_club_transaction(club, 'praemie', 'Bonus', Decimal('250000'))
        club.refresh_from_db()
        self.assertEqual(club.budget, Decimal('10250000.00'))

    def test_log_truncates_description(self):
        club = _mk_club()
        tx = log_club_transaction(club, 'sonstige_ausgabe', 'x' * 300, Decimal('-1'))
        self.assertEqual(len(tx.beschreibung), 200)

    def test_log_explicit_season_wins(self):
        GameSeasonState.objects.create(current_season=5)
        club = _mk_club()
        tx = log_club_transaction(club, 'praemie', 'Bonus', Decimal('50'), season=1)
        self.assertEqual(tx.saison, '1')

    def test_legacy_category_mapping(self):
        GameSeasonState.objects.create(current_season=0)
        club = _mk_club()
        tx = log_club_transaction(club, 'ticketverkauf', 'Heimspiel', Decimal('1000'))
        self.assertEqual(tx.typ, 'TICKET')
        tx = log_club_transaction(club, 'stadionkosten', 'Ausbau', Decimal('-1000'))
        self.assertEqual(tx.typ, 'AUSBAU')


class TicketRevenueLoggingTests(TestCase):
    def setUp(self):
        GameSeasonState.objects.create(current_season=1)
        self.club = _mk_club()
        self.stadium = Stadium.objects.create(
            club=self.club, name='Arena', city='Stadt',
            nord_standing=2000, nord_seating=3000, nord_vip=100,
        )

    def test_matchday_revenue_creates_ledger_row(self):
        before = self.club.budget
        entry = record_matchday_revenue(self.club, competition_name='Bundesliga')
        self.club.refresh_from_db()
        self.assertEqual(self.club.budget, before + entry.revenue_total)

        tx = FinanceTransaction.objects.get(club=self.club)
        self.assertEqual(tx.typ, 'TICKET')
        self.assertEqual(tx.betrag, entry.revenue_total)
        self.assertEqual(tx.saison, '1')
        self.assertIn('Spieltagseinnahmen', tx.beschreibung)


class FinanzanalyseViewTests(TestCase):
    def setUp(self):
        GameSeasonState.objects.create(current_season=0)
        self.staff = User.objects.create_user(
            'creator', password='x', is_staff=True)
        self.league = League.objects.create(name='Testliga', country='DE')
        self.club = _mk_club(league=self.league)
        log_club_transaction(self.club, 'ticketverkauf', 'Heimspiel', Decimal('500000'))
        log_club_transaction(self.club, 'stadionkosten', 'Ausbau', Decimal('-200000'))

    def test_requires_staff(self):
        resp = self.client.get(reverse('creator_finanzanalyse'))
        self.assertEqual(resp.status_code, 302)

    def test_page_renders_with_data(self):
        self.client.force_login(self.staff)
        resp = self.client.get(reverse('creator_finanzanalyse'))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertIn('Finanzanalyse', html)
        self.assertIn('Geld im Umlauf', html)
        self.assertIn('Testliga', html)
        self.assertIn('Ticketverkauf', html)
        self.assertIn('Stadionausbau', html)

    def test_season_filter_param(self):
        self.client.force_login(self.staff)
        log_club_transaction(
            self.club, 'praemie', 'Altsaison-Prämie', Decimal('99000'), season=7)
        resp = self.client.get(reverse('creator_finanzanalyse') + '?season=7')
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertIn('Kategorien — Saison 7', html)
        self.assertIn('Pokalprämie', html)
