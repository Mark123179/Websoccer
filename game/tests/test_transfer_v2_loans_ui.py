"""Tests Transfersystem v2 — Leihmarkt-Reiter & Leih-Regeln (Task #822).

Deckt ab: Rendering/Auth des Leihmarkts, Filter (Alle/WP/SE/Kaufoption),
Listing-Erstellung vom Board („Verleihen"), Zurückziehen, Leihanfrage inkl.
Escrow, Partnervereins-0€-Regel, Deadline-Pause (Anfrage blockiert + offene
Anfragen laufen aus), Leih-Limits, Rückruf-Workflow (einvernehmlich) und
Stichtag-Ende über den Job.
"""
from decimal import Decimal
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from game.models import Club, EconomyParameter, GameSeasonState, League, Player
from game.transfer_v2 import escrow, jobs, services
from game.transfer_v2.models import (
    ClubPartnership, DealRequest, Loan, LoanListing, TransferRecord,
)
from game.transfer_v2.services import TransferActionError


def _mk_club(name, budget='50000000.00', league=None):
    if league is None:
        league, _ = League.objects.get_or_create(
            name='TV2-Leih-Testliga', country='Deutschland')
    return Club.objects.create(
        name=name, short_name=name[:3].upper(), founded_year=1900,
        budget=Decimal(budget), league=league,
    )


def _mk_player(club, name='Leih Gabe', age=22, mw='3000000', hp='ST'):
    first, last = name.split(' ', 1)
    return Player.objects.create(
        club=club, first_name=first, last_name=last, age=age,
        position='Sturm', main_position_1=hp,
        nationalities='Deutschland', market_value=Decimal(mw),
    )


class Base(TestCase):
    def setUp(self):
        GameSeasonState.objects.create(current_season=0)
        EconomyParameter.objects.update_or_create(
            saison='0', key='KADER_MIN', defaults={'value': 0})
        self.mine = _mk_club('FC Leihgeber')
        self.other = _mk_club('FC Leihnehmer')
        self.p1 = _mk_player(self.mine, 'Leih Erster')
        self.f1 = _mk_player(self.other, 'Fremd Kader')
        self.user = User.objects.create_user('lm1', password='x')
        self.mine.managed_by = self.user.manager_profile
        self.mine.save(update_fields=['managed_by'])
        self.user2 = User.objects.create_user('lm2', password='x')
        self.other.managed_by = self.user2.manager_profile
        self.other.save(update_fields=['managed_by'])

    def login(self, user=None):
        self.client.force_login(user or self.user)

    def _listing(self, player=None, fee='1000000', until='SE', buy=None):
        return services.create_loan_listing(
            player or self.p1, self.mine,
            fee_asking=Decimal(fee), until=until,
            buy_option_price=Decimal(buy) if buy else None)

    def _active_loan(self, fee='1000000'):
        """Kompletter Weg Listing → Anfrage → Annahme → aktive Leihe."""
        listing = self._listing(fee=fee)
        deal = services.request_loan(listing, self.other)
        services.accept_loan_request(deal)
        return Loan.objects.get(player=self.p1, ended_at__isnull=True)


class LoanMarketPageTests(Base):
    def test_anonymous_redirects(self):
        resp = self.client.get(reverse('transfer_loan_market'))
        self.assertEqual(resp.status_code, 302)

    def test_renders_listing_rows_and_banner(self):
        self._listing(buy='5000000')
        self.login(self.user2)
        resp = self.client.get(reverse('transfer_loan_market'))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertIn('Leih Erster', html)
        self.assertIn('FC Leihgeber', html)
        self.assertIn('Leih-Deadline', html)
        self.assertIn('Leihanfrage', html)

    def test_filters(self):
        wp_player = _mk_player(self.mine, 'Winter Pause')
        self._listing(until='SE', buy='4000000')
        services.create_loan_listing(
            wp_player, self.mine, fee_asking=Decimal('1000000'), until='WP')
        self.login(self.user2)
        html = self.client.get(
            reverse('transfer_loan_market') + '?f=WP').content.decode()
        self.assertIn('Winter Pause', html)
        self.assertNotIn('Leih Erster', html)
        html = self.client.get(
            reverse('transfer_loan_market') + '?f=SE').content.decode()
        self.assertIn('Leih Erster', html)
        self.assertNotIn('Winter Pause', html)
        html = self.client.get(
            reverse('transfer_loan_market') + '?f=opt').content.decode()
        self.assertIn('Leih Erster', html)  # hat Kaufoption
        self.assertNotIn('Winter Pause', html)

    def test_own_listing_shows_withdraw(self):
        self._listing()
        self.login()
        html = self.client.get(
            reverse('transfer_loan_market')).content.decode()
        self.assertIn('Zurückziehen', html)

    def test_leihmarkt_tab_active_everywhere(self):
        self.login()
        html = self.client.get(
            reverse('transfer_loan_market')).content.decode()
        self.assertNotIn('bald verfügbar', html)
        self.assertIn('Leihmarkt', html)


class LoanListingEndpointTests(Base):
    def test_create_listing_from_board(self):
        self.login()
        resp = self.client.post(reverse('transfer_loan_listing_create'), {
            'player_id': self.p1.pk, 'loan_fee': '1.500.000',
            'loan_buy': '6.000.000', 'loan_until': 'WP',
        })
        self.assertEqual(resp.status_code, 302)
        ll = LoanListing.objects.get(player=self.p1)
        self.assertEqual(ll.fee_asking, Decimal('1500000'))
        self.assertEqual(ll.buy_option_price, Decimal('6000000'))
        self.assertEqual(ll.until, 'WP')

    def test_create_listing_below_min_fee_rejected(self):
        self.login()
        self.client.post(reverse('transfer_loan_listing_create'), {
            'player_id': self.p1.pk, 'loan_fee': '500.000',
            'loan_until': 'SE',
        })
        self.assertFalse(LoanListing.objects.filter(player=self.p1).exists())

    def test_create_listing_zero_fee_allowed(self):
        # 0 € beim Listen erlaubt — Partnerprüfung erst bei der Anfrage.
        self.login()
        self.client.post(reverse('transfer_loan_listing_create'), {
            'player_id': self.p1.pk, 'loan_fee': '0', 'loan_until': 'SE',
        })
        self.assertTrue(LoanListing.objects.filter(
            player=self.p1, fee_asking=0).exists())

    def test_create_listing_foreign_player_blocked(self):
        self.login()
        self.client.post(reverse('transfer_loan_listing_create'), {
            'player_id': self.f1.pk, 'loan_fee': '1.000.000',
            'loan_until': 'SE',
        })
        self.assertFalse(LoanListing.objects.filter(player=self.f1).exists())

    def test_withdraw_listing(self):
        ll = self._listing()
        self.login()
        self.client.post(reverse('transfer_loan_listing_withdraw'),
                         {'listing_id': ll.pk})
        ll.refresh_from_db()
        self.assertEqual(ll.status, LoanListing.STATUS_WITHDRAWN)

    def test_withdraw_foreign_listing_blocked(self):
        ll = self._listing()
        self.login(self.user2)
        self.client.post(reverse('transfer_loan_listing_withdraw'),
                         {'listing_id': ll.pk})
        ll.refresh_from_db()
        self.assertEqual(ll.status, LoanListing.STATUS_ACTIVE)


class LoanRequestTests(Base):
    def test_request_reserves_fee(self):
        ll = self._listing()
        self.login(self.user2)
        resp = self.client.post(reverse('transfer_loan_request'),
                                {'listing_id': ll.pk})
        self.assertEqual(resp.status_code, 302)
        deal = DealRequest.objects.get(typ=DealRequest.TYP_LOAN)
        self.assertEqual(deal.from_club_id, self.other.pk)
        self.assertEqual(deal.loan_fee, Decimal('1000000'))
        self.assertEqual(
            escrow._v2_reserved_total(self.other), Decimal('1000000'))

    def test_request_own_listing_blocked(self):
        ll = self._listing()
        self.login()
        self.client.post(reverse('transfer_loan_request'),
                         {'listing_id': ll.pk})
        self.assertFalse(
            DealRequest.objects.filter(typ=DealRequest.TYP_LOAN).exists())

    def test_zero_fee_requires_partnership(self):
        ll = self._listing(fee='0')
        with self.assertRaises(TransferActionError):
            services.request_loan(ll, self.other)
        ClubPartnership.objects.create(club_a=self.mine, club_b=self.other)
        deal = services.request_loan(ll, self.other)
        self.assertFalse(deal.loan_fee)  # 0 € → keine Gebühr gespeichert.
        self.assertEqual(escrow._v2_reserved_total(self.other), 0)

    def test_request_blocked_when_market_paused(self):
        ll = self._listing()
        with mock.patch(
                'game.transfer_v2.services.loan_market_paused',
                return_value=True):
            with self.assertRaises(TransferActionError):
                services.request_loan(ll, self.other)

    def test_accept_executes_loan_and_pays_fee(self):
        loan = self._active_loan()
        self.p1.refresh_from_db()
        self.mine.refresh_from_db()
        self.other.refresh_from_db()
        self.assertEqual(self.p1.club_id, self.other.pk)
        self.assertEqual(loan.owner_club_id, self.mine.pk)
        self.assertEqual(self.mine.budget, Decimal('51000000.00'))
        self.assertEqual(self.other.budget, Decimal('49000000.00'))
        self.assertEqual(escrow._v2_reserved_total(self.other), 0)
        # Listing auf LOANED, Historieneintrag Leihstart vorhanden.
        self.assertTrue(LoanListing.objects.filter(
            player=self.p1, status=LoanListing.STATUS_LOANED).exists())
        self.assertTrue(TransferRecord.objects.filter(
            kind=TransferRecord.KIND_LOAN,
            loan_event=TransferRecord.LOAN_EVENT_START).exists())

    def test_pair_limit_enforced(self):
        EconomyParameter.objects.update_or_create(
            saison='0', key='LEIHE_LIMIT_JE_PAAR', defaults={'value': 1})
        self._active_loan()
        zweiter = _mk_player(self.mine, 'Leih Zweiter')
        ll2 = services.create_loan_listing(
            zweiter, self.mine, fee_asking=Decimal('1000000'), until='SE')
        with self.assertRaises(TransferActionError):
            services.request_loan(ll2, self.other)


class LoanDeadlineJobTests(Base):
    def test_open_loan_requests_expire_when_paused(self):
        ll = self._listing()
        deal = services.request_loan(ll, self.other)
        self.assertEqual(
            escrow._v2_reserved_total(self.other), Decimal('1000000'))
        with mock.patch(
                'game.transfer_v2.calendar_dates.loan_deadline_date',
                return_value=timezone.localdate()):
            result = jobs.expire_paused_loan_requests()
        self.assertEqual(result['abgelaufen'], 1)
        deal.refresh_from_db()
        self.assertEqual(deal.status, DealRequest.STATUS_EXPIRED)
        self.assertEqual(escrow._v2_reserved_total(self.other), 0)

    def test_default_command_run_expires_paused_requests(self):
        # Operativer Pfad: run_transfer_v2_jobs OHNE Argumente (Celery-Beat)
        # muss offene Leihanfragen an der Deadline auslaufen lassen und die
        # Reservierung freigeben.
        from django.core.management import call_command
        ll = self._listing()
        deal = services.request_loan(ll, self.other)
        self.assertEqual(
            escrow._v2_reserved_total(self.other), Decimal('1000000'))
        with mock.patch(
                'game.transfer_v2.calendar_dates.loan_deadline_date',
                return_value=timezone.localdate()):
            call_command('run_transfer_v2_jobs')
        deal.refresh_from_db()
        self.assertEqual(deal.status, DealRequest.STATUS_EXPIRED)
        self.assertEqual(escrow._v2_reserved_total(self.other), 0)

    def test_command_only_loan_anfragen(self):
        from django.core.management import call_command
        ll = self._listing()
        deal = services.request_loan(ll, self.other)
        with mock.patch(
                'game.transfer_v2.calendar_dates.loan_deadline_date',
                return_value=timezone.localdate()):
            call_command('run_transfer_v2_jobs', '--only', 'loan_anfragen')
        deal.refresh_from_db()
        self.assertEqual(deal.status, DealRequest.STATUS_EXPIRED)
        self.assertEqual(escrow._v2_reserved_total(self.other), 0)

    def test_open_requests_untouched_before_deadline(self):
        ll = self._listing()
        deal = services.request_loan(ll, self.other)
        result = jobs.expire_paused_loan_requests()
        self.assertEqual(result['abgelaufen'], 0)
        deal.refresh_from_db()
        self.assertEqual(deal.status, DealRequest.STATUS_OPEN)

    def test_due_loans_end_at_stichtag(self):
        loan = self._active_loan()
        with mock.patch(
                'game.transfer_v2.calendar_dates.season_end_date',
                return_value=timezone.localdate()):
            result = jobs.end_due_loans()
        self.assertEqual(result['beendet'], 1)
        loan.refresh_from_db()
        self.p1.refresh_from_db()
        self.assertIsNotNone(loan.ended_at)
        self.assertEqual(self.p1.club_id, self.mine.pk)
        self.assertTrue(TransferRecord.objects.filter(
            kind=TransferRecord.KIND_LOAN,
            loan_event=TransferRecord.LOAN_EVENT_RETURN).exists())


class RecallTests(Base):
    def test_recall_requires_owner(self):
        loan = self._active_loan()
        with self.assertRaises(TransferActionError):
            services.request_recall(loan, self.other)

    def test_recall_flow_accept(self):
        loan = self._active_loan()
        self.login()
        self.client.post(reverse('transfer_loan_recall_request'),
                         {'loan_id': loan.pk})
        loan.refresh_from_db()
        self.assertTrue(loan.recall_requested)
        # Leihverein stimmt zu → Leihe endet sofort, Spieler zurück.
        self.login(self.user2)
        self.client.post(reverse('transfer_loan_recall_respond'),
                         {'loan_id': loan.pk, 'antwort': 'annehmen'})
        loan.refresh_from_db()
        self.p1.refresh_from_db()
        self.assertIsNotNone(loan.ended_at)
        self.assertEqual(self.p1.club_id, self.mine.pk)
        self.assertEqual(self.p1.loan_status, '')

    def test_recall_flow_decline_resets_flag(self):
        loan = self._active_loan()
        services.request_recall(loan, self.mine)
        self.login(self.user2)
        self.client.post(reverse('transfer_loan_recall_respond'),
                         {'loan_id': loan.pk, 'antwort': 'ablehnen'})
        loan.refresh_from_db()
        self.p1.refresh_from_db()
        self.assertIsNone(loan.ended_at)
        self.assertFalse(loan.recall_requested)
        self.assertEqual(self.p1.club_id, self.other.pk)

    def test_respond_requires_loan_club(self):
        loan = self._active_loan()
        services.request_recall(loan, self.mine)
        with self.assertRaises(TransferActionError):
            services.respond_recall(loan, self.mine, accept=True)

    def test_recall_double_request_blocked(self):
        loan = self._active_loan()
        services.request_recall(loan, self.mine)
        with self.assertRaises(TransferActionError):
            services.request_recall(loan, self.mine)

    def test_recall_allowed_during_pause(self):
        loan = self._active_loan()
        with mock.patch(
                'game.transfer_v2.calendar_dates.loan_deadline_date',
                return_value=timezone.localdate()):
            services.request_recall(loan, self.mine)
            services.respond_recall(loan, self.other, accept=True)
        loan.refresh_from_db()
        self.assertIsNotNone(loan.ended_at)

    def test_deals_page_shows_recall_actions(self):
        loan = self._active_loan()
        services.request_recall(loan, self.mine)
        self.login(self.user2)
        html = self.client.get(
            reverse('transfer_my_deals') + '?seg=leihen').content.decode()
        self.assertIn('Rückruf angefragt', html)
        self.assertIn('Zustimmen', html)
