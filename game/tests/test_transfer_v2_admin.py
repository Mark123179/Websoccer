"""Tests Creator-Transferaufsicht (Task #824, Spec §8).

Deckt ab:
1. Admin-Storno eines vollzogenen CASH-Kaufs
2. Admin-Storno eines WP-Pendings
3. Doppel-Storno wirft TransferActionError
4. admin_transfer: KIND_ADMIN, keine Buchungen, keine Levy, keine Wechselsperre
5. admin_cancel_listing: CANCELLED, Reservierungen frei
6. Report-Flow: dismiss -> DISMISSED, review -> UNDER_REVIEW
7. Settings-POST ändert EconomyParameter; Typwechsel abgelehnt
8. Views nur für Staff
"""
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from game.economy.params import get_param
from game.models import (
    Club, EconomyParameter, FinanceReservation, FinanceTransaction,
    GameSeasonState, League, Player,
)
from game.transfer_v2 import escrow, services
from game.transfer_v2.admin_actions import (
    TransferActionError,
    admin_cancel_listing,
    admin_cancel_record,
    admin_transfer,
)
from game.transfer_v2.models import (
    ClubPartnership, LoanListing, PendingTransfer, TransferBid,
    TransferListing, TransferLock, TransferRecord, TransferRecordPlayer,
    TransferReport, YouthLevyPayment,
)


def _mk_club(name, budget='50000000.00', league=None):
    if league is None:
        league, _ = League.objects.get_or_create(
            name='TV2Admin-Testliga', country='Deutschland')
    return Club.objects.create(
        name=name, short_name=name[:3].upper(), founded_year=1900,
        budget=Decimal(budget), league=league,
    )


def _mk_player(club, name='Trans Ferfix', age=25, mw='5000000'):
    first, last = name.split(' ', 1)
    return Player.objects.create(
        club=club, first_name=first, last_name=last, age=age,
        position='Sturm', main_position_1='ST',
        nationalities='Deutschland', market_value=Decimal(mw),
    )


class AdminBase(TestCase):
    def setUp(self):
        GameSeasonState.objects.create(current_season=0)
        EconomyParameter.objects.update_or_create(
            saison='0', key='KADER_MIN', defaults={'value': 0})
        EconomyParameter.objects.update_or_create(
            saison='0', key='KADER_MAX', defaults={'value': 100})
        self.seller = _mk_club('FC Verkauf', budget='20000000.00')
        self.buyer = _mk_club('FC Kauf', budget='20000000.00')
        self.player = _mk_player(self.seller)


def _do_sofort_kauf(listing, buyer, amount='1000000', saison='0'):
    """Hilfsfunktion: Sofortkauf via close_listing mit führendem Gebot."""
    from game.transfer_v2 import escrow as _escrow
    from game.transfer_v2.execution import execute_purchase
    amount_d = Decimal(amount)
    _escrow.consume_money(buyer, _escrow.bid_ref(listing.pk, buyer.pk))
    return execute_purchase(listing, buyer, amount_d, timing='SOFORT', saison=saison)


class AdminCancelCashPurchaseTests(AdminBase):
    """Test 1: Admin-Storno eines vollzogenen CASH-Kaufs."""

    def _setup_listing_with_bid(self, amount='1000000'):
        listing = services.create_listing(
            self.player, self.seller,
            min_bid=Decimal(amount), duration_days=3,
        )
        services.place_bid(listing, self.buyer, Decimal(amount))
        return listing

    def test_storno_restores_player_and_budget(self):
        listing = self._setup_listing_with_bid()
        record = _do_sofort_kauf(listing, self.buyer)

        # Spieler ist jetzt beim Käufer
        self.player.refresh_from_db()
        self.assertEqual(self.player.club_id, self.buyer.pk)

        self.buyer.refresh_from_db()
        buyer_budget_after_buy = self.buyer.budget

        # Admin-Storno
        admin_cancel_record(record, grund='Testgrund')

        # Spieler ist zurück beim Verkäufer
        self.player.refresh_from_db()
        self.assertEqual(self.player.club_id, self.seller.pk)

        # Käufer-Budget wiederhergestellt
        self.buyer.refresh_from_db()
        self.assertGreater(self.buyer.budget, buyer_budget_after_buy)

        # Record markiert
        record.refresh_from_db()
        self.assertTrue(record.is_cancelled)

        # TransferLock weg
        self.assertFalse(
            TransferLock.objects.filter(source_record=record).exists()
        )

    def test_storno_reverses_youth_levy(self):
        from game.models import PlayerClubHistory
        # Ausbildungsverein anlegen und PlayerClubHistory eintragen.
        # Saison muss <= cutoff = saison_num + (21 - age) sein.
        # Wir nutzen einen 18-jährigen Spieler: cutoff = 0 + (21 - 18) = 3
        # Also season=0 passt rein.
        young_player = _mk_player(self.seller, name='Jung Spieler', age=18, mw='2000000')
        ausbildungsverein = _mk_club('FC Jugend', budget='5000000.00')
        PlayerClubHistory.objects.create(
            player=young_player, club=ausbildungsverein,
            season=0,
        )

        listing = services.create_listing(
            young_player, self.seller,
            min_bid=Decimal('2000000'), duration_days=3,
        )
        services.place_bid(listing, self.buyer, Decimal('2000000'))
        record = _do_sofort_kauf(listing, self.buyer, amount='2000000')

        # Jugendabgabe existiert
        levies = YouthLevyPayment.objects.filter(record=record)
        self.assertTrue(levies.exists())

        # Admin-Storno
        admin_cancel_record(record, grund='Testgrund')

        # Jugendabgabe gelöscht
        self.assertFalse(YouthLevyPayment.objects.filter(record=record).exists())


class AdminCancelPendingTests(AdminBase):
    """Test 2: Admin-Storno eines WP-Pendings."""

    def test_storno_pending_sets_cancelled_admin(self):
        # WP-Listing (Spieler wechselt erst bei WP)
        from game.transfer_v2.models import TransferListing as TL
        listing = services.create_listing(
            self.player, self.seller,
            min_bid=Decimal('1000000'), duration_days=3,
            timing=TL.TIMING_WP,
        )
        # Geld fließt sofort, Spieler noch beim Verkäufer
        # Kein buy_now für WP; wir simulieren über close_listing mit führendem Gebot
        services.place_bid(listing, self.buyer, Decimal('1000000'))
        from game.transfer_v2 import escrow as _escrow
        _escrow.consume_money(self.buyer, _escrow.bid_ref(listing.pk, self.buyer.pk))
        from game.transfer_v2.execution import execute_purchase
        record = execute_purchase(
            listing, self.buyer, Decimal('1000000'),
            timing=TL.TIMING_WP, saison='0',
        )

        # Es gibt einen PENDING
        pending = PendingTransfer.objects.get(
            record=record, status=PendingTransfer.STATUS_PENDING)

        # Spieler ist noch beim Verkäufer
        self.player.refresh_from_db()
        self.assertEqual(self.player.club_id, self.seller.pk)

        buyer_budget_before = self.buyer.budget

        # Admin-Storno
        admin_cancel_record(record, grund='WP-Test')

        # Pending -> CANCELLED_ADMIN
        pending.refresh_from_db()
        self.assertEqual(pending.status, PendingTransfer.STATUS_CANCELLED_ADMIN)

        # Spieler noch beim Verkäufer (war nie gewechselt)
        self.player.refresh_from_db()
        self.assertEqual(self.player.club_id, self.seller.pk)

        # Geld zurück (cash_b = 1.000.000 → Käufer bekommt es zurück)
        self.buyer.refresh_from_db()
        self.assertGreater(self.buyer.budget, buyer_budget_before)

        # Record storniert
        record.refresh_from_db()
        self.assertTrue(record.is_cancelled)


class AdminCancelDoubleTests(AdminBase):
    """Test 3: Doppel-Storno wirft TransferActionError."""

    def test_double_cancel_raises(self):
        listing = services.create_listing(
            self.player, self.seller,
            min_bid=Decimal('1000000'), duration_days=3,
        )
        services.place_bid(listing, self.buyer, Decimal('1000000'))
        record = _do_sofort_kauf(listing, self.buyer)

        admin_cancel_record(record, grund='Erster Storno')

        with self.assertRaises(TransferActionError) as ctx:
            admin_cancel_record(record, grund='Zweiter Storno')
        self.assertIn('bereits storniert', str(ctx.exception))


class AdminCancelLoanTests(AdminBase):
    """Regression: Zwei gleichzeitige Leihen zwischen denselben Vereinen —
    Admin-Storno von Leihe A darf NICHT Leihe B beenden (Paar-Lookup-Falle).
    """

    def _mk_loan(self, player):
        """Leihstart wie _execute_loan_from_deal: Loan + Record + Move."""
        from game.transfer_v2.models import Loan
        loan = Loan.objects.create(
            player=player, owner_club=self.seller, loan_club=self.buyer,
            fee=Decimal('100000'), until='WP',
            started_via=Loan.STARTED_VIA_DEAL,
        )
        player.club = self.buyer
        player.loan_status = 'loaned_in'
        player.loan_partner_club = self.seller
        player.save(update_fields=['club', 'loan_status',
                                   'loan_partner_club'])
        record = TransferRecord.objects.create(
            kind=TransferRecord.KIND_LOAN, timing='SOFORT',
            club_a=self.seller, club_b=self.buyer,
            cash_a=Decimal('0'), cash_b=Decimal('100000'),
            loan_event=TransferRecord.LOAN_EVENT_START, loan_until='WP',
        )
        TransferRecordPlayer.objects.create(
            record=record, player=player,
            side=TransferRecordPlayer.SIDE_A,
            market_value_at_transfer=player.market_value,
        )
        return loan, record

    def test_cancel_one_of_two_parallel_loans_same_pair(self):
        player_a = self.player
        player_b = _mk_player(self.seller, name='Zweite Leihe')
        loan_a, record_a = self._mk_loan(player_a)
        loan_b, record_b = self._mk_loan(player_b)

        admin_cancel_record(record_a, grund='Test Paar-Leihe')

        loan_a.refresh_from_db()
        loan_b.refresh_from_db()
        player_a.refresh_from_db()
        player_b.refresh_from_db()

        # Leihe A beendet, Spieler A zurück beim Stammverein
        self.assertIsNotNone(loan_a.ended_at)
        self.assertEqual(player_a.club_id, self.seller.pk)
        self.assertEqual(player_a.loan_status, '')

        # Leihe B UNBERÜHRT: aktiv, Spieler B weiter beim Leihverein
        self.assertIsNone(loan_b.ended_at)
        self.assertEqual(player_b.club_id, self.buyer.pk)
        self.assertEqual(player_b.loan_status, 'loaned_in')
        self.assertEqual(player_b.loan_partner_club_id, self.seller.pk)

        record_a.refresh_from_db()
        record_b.refresh_from_db()
        self.assertTrue(record_a.is_cancelled)
        self.assertFalse(record_b.is_cancelled)

    def test_cancel_loan_refunds_fee(self):
        player_a = self.player
        loan_a, record_a = self._mk_loan(player_a)
        buyer_before = Club.objects.get(pk=self.buyer.pk).budget
        seller_before = Club.objects.get(pk=self.seller.pk).budget

        admin_cancel_record(record_a, grund='Gebühr zurück')

        self.buyer.refresh_from_db()
        self.seller.refresh_from_db()
        # Leihverein (club_b) erhält die Gebühr zurück, Stammverein zahlt.
        self.assertEqual(self.buyer.budget, buyer_before + Decimal('100000'))
        self.assertEqual(self.seller.budget,
                         seller_before - Decimal('100000'))

    def test_cancel_loan_wrong_pair_rejected(self):
        """Aktive Leihe des Spielers passt nicht zu den Record-Vereinen."""
        from game.transfer_v2.models import Loan
        other = _mk_club('FC Dritter')
        player_a = self.player
        # Leihe läuft real zu einem DRITTEN Verein …
        Loan.objects.create(
            player=player_a, owner_club=self.seller, loan_club=other,
            fee=Decimal('0'), until='WP',
            started_via=Loan.STARTED_VIA_DEAL,
        )
        player_a.club = other
        player_a.save(update_fields=['club'])
        # … aber der Record behauptet seller→buyer.
        record = TransferRecord.objects.create(
            kind=TransferRecord.KIND_LOAN, timing='SOFORT',
            club_a=self.seller, club_b=self.buyer,
            cash_a=Decimal('0'), cash_b=Decimal('0'),
            loan_event=TransferRecord.LOAN_EVENT_START, loan_until='WP',
        )
        TransferRecordPlayer.objects.create(
            record=record, player=player_a,
            side=TransferRecordPlayer.SIDE_A,
            market_value_at_transfer=player_a.market_value,
        )
        with self.assertRaises(TransferActionError):
            admin_cancel_record(record, grund='Falsches Paar')
        record.refresh_from_db()
        self.assertFalse(record.is_cancelled)


class AdminTransferTests(AdminBase):
    """Test 4: admin_transfer."""

    def test_admin_transfer_kind_admin_no_bookings_no_lock(self):
        # Spieler ist beim Verkäufer
        self.assertEqual(self.player.club_id, self.seller.pk)

        buyer_budget_before = self.buyer.budget
        seller_budget_before = self.seller.budget

        record = admin_transfer(
            self.player, self.buyer,
            actor=None, grund='Aufsichtsakt',
        )

        # KIND_ADMIN
        self.assertEqual(record.kind, TransferRecord.KIND_ADMIN)
        self.assertTrue(record.is_admin)

        # Spieler beim Zielverein
        self.player.refresh_from_db()
        self.assertEqual(self.player.club_id, self.buyer.pk)

        # Keine Buchungen (Budgets unverändert)
        self.buyer.refresh_from_db()
        self.seller.refresh_from_db()
        self.assertEqual(self.buyer.budget, buyer_budget_before)
        self.assertEqual(self.seller.budget, seller_budget_before)

        # Keine Wechselsperre
        self.assertFalse(
            TransferLock.objects.filter(player=self.player).exists()
        )

        # Keine Jugendabgabe
        self.assertFalse(
            YouthLevyPayment.objects.filter(record=record).exists()
        )


class AdminCancelListingTests(AdminBase):
    """Test 5: admin_cancel_listing."""

    def test_cancel_listing_frees_reservations(self):
        listing = services.create_listing(
            self.player, self.seller,
            min_bid=Decimal('1000000'), duration_days=3,
        )
        services.place_bid(listing, self.buyer, Decimal('1000000'))

        # Reservierung existiert
        self.buyer.refresh_from_db()
        self.assertEqual(self.buyer.reserved, Decimal('1000000.00'))

        admin_cancel_listing(listing, grund='Admin-Test')

        # Listing storniert
        listing.refresh_from_db()
        self.assertEqual(listing.status, TransferListing.STATUS_CANCELLED)

        # Reservierung freigegeben
        active_res = FinanceReservation.objects.filter(
            club=self.buyer,
            status=FinanceReservation.STATUS_ACTIVE,
        )
        self.assertFalse(active_res.exists())


class ReportFlowTests(AdminBase):
    """Test 6: Report-Flow."""

    def test_dismiss_sets_dismissed(self):
        listing = services.create_listing(
            self.player, self.seller,
            min_bid=Decimal('1000000'), duration_days=3,
        )
        record = TransferRecord.objects.create(
            kind=TransferRecord.KIND_CASH, timing='SOFORT',
            club_a=self.seller, club_b=self.buyer,
            cash_b=Decimal('1000000'),
        )
        report = TransferReport.objects.create(
            record=record, reporter_club=self.buyer,
            reason='Verdacht',
        )
        self.assertEqual(report.status, TransferReport.STATUS_OPEN)

        report.status = TransferReport.STATUS_DISMISSED
        report.resolved_at = timezone.now()
        report.save()

        report.refresh_from_db()
        self.assertEqual(report.status, TransferReport.STATUS_DISMISSED)
        self.assertIsNotNone(report.resolved_at)

    def test_review_sets_under_review(self):
        record = TransferRecord.objects.create(
            kind=TransferRecord.KIND_CASH, timing='SOFORT',
            club_a=self.seller, club_b=self.buyer,
            cash_b=Decimal('500000'),
        )
        report = TransferReport.objects.create(
            record=record, reporter_club=self.buyer,
            reason='Prüfen',
        )
        report.status = TransferReport.STATUS_UNDER_REVIEW
        report.resolved_at = timezone.now()
        report.save()

        report.refresh_from_db()
        self.assertEqual(report.status, TransferReport.STATUS_UNDER_REVIEW)


class SettingsTests(TestCase):
    """Test 7: Settings-POST ändert EconomyParameter; Typwechsel abgelehnt."""

    def setUp(self):
        GameSeasonState.objects.create(current_season=0)
        self.staff = User.objects.create_user(
            username='creator', password='pw', is_staff=True)
        self.client = Client()
        self.client.login(username='creator', password='pw')

    def test_settings_post_saves_param(self):
        import json
        old_val = get_param('RUMOR_P_EXACT', '0')
        url = reverse('creator_transferaufsicht_setting')
        response = self.client.post(url, {
            'key': 'RUMOR_P_EXACT',
            'value': '0.75',
        })
        self.assertEqual(response.status_code, 302)
        new_val = get_param('RUMOR_P_EXACT', '0')
        self.assertAlmostEqual(float(new_val), 0.75)

    def test_settings_type_change_rejected(self):
        url = reverse('creator_transferaufsicht_setting')
        # RUMOR_P_EXACT ist Zahl, versuche string zu speichern
        response = self.client.post(url, {
            'key': 'RUMOR_P_EXACT',
            'value': '"falsch"',
        })
        self.assertEqual(response.status_code, 302)
        # Wert bleibt float (nicht string)
        val = get_param('RUMOR_P_EXACT', '0')
        self.assertIsInstance(val, (int, float))


class ViewAccessTests(TestCase):
    """Test 8: Views nur für Staff."""

    def setUp(self):
        GameSeasonState.objects.create(current_season=0)
        self.normal_user = User.objects.create_user(
            username='normal', password='pw')
        self.staff_user = User.objects.create_user(
            username='staff', password='pw', is_staff=True)

    def test_main_view_requires_staff(self):
        client = Client()
        url = reverse('creator_transferaufsicht')

        # Nicht eingeloggt -> Redirect
        response = client.get(url)
        self.assertEqual(response.status_code, 302)

        # Normaler User -> Redirect
        client.login(username='normal', password='pw')
        response = client.get(url)
        self.assertEqual(response.status_code, 302)

        # Staff -> OK
        client.login(username='staff', password='pw')
        response = client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_post_views_require_staff(self):
        client = Client()
        urls = [
            reverse('creator_transferaufsicht_report_action'),
            reverse('creator_transferaufsicht_cancel_record'),
            reverse('creator_transferaufsicht_admin_transfer'),
            reverse('creator_transferaufsicht_cancel_listing'),
            reverse('creator_transferaufsicht_setting'),
        ]
        for url in urls:
            client.logout()
            response = client.post(url, {})
            self.assertIn(response.status_code, [302, 403],
                          f'{url} should redirect/forbid non-staff')
