"""Tests Transfersystem v2 — Backend-Fundament (Task-Abnahmekriterien).

Deckt ab: Reservierungsinvariante (Club.reserved-Cache + recalc_reserved),
Gebots-Arithmetik, Anti-Sniping, Sofortkauf, Auktionsabschluss (idempotent),
PendingTransfer (WP/SE), Jugendabgabe (8 % / min 50k / Eigengewächs /
Tausch-Bemessung), Wechselsperre, Deal-Anfragen-Lebenszyklus und
Leih-Grundregeln (Mindestgebühr, Partnerverein, Limits).
"""
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from game.economy.params import get_param
from game.models import (
    Club, EconomyParameter, FinanceReservation, FinanceTransaction,
    GameSeasonState, League, Player, PlayerClubHistory,
)
from game.transfer_v2 import escrow, jobs, services, youth_levy
from game.transfer_v2.models import (
    ClubPartnership, DealRequest, Loan, LoanListing, PendingTransfer,
    TransferBid, TransferListing, TransferRecord, YouthLevyPayment,
)
from game.transfer_v2.services import TransferActionError


def _mk_club(name, budget='50000000.00', league=None):
    if league is None:
        league, _ = League.objects.get_or_create(
            name='TV2-Testliga', country='Deutschland')
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


class Base(TestCase):
    def setUp(self):
        GameSeasonState.objects.create(current_season=0)
        # Kadergrenzen für die Fundament-Tests neutralisieren (die Vereine
        # haben hier nur 1–2 Spieler); SquadBoundsTests setzen eigene Werte.
        EconomyParameter.objects.update_or_create(
            saison='0', key='KADER_MIN', defaults={'value': 0})
        self.seller = _mk_club('FC Verkauf')
        self.buyer = _mk_club('FC Kauf')
        self.third = _mk_club('FC Dritte')
        self.player = _mk_player(self.seller)


class BidArithmeticTests(Base):
    def test_min_bid_systemminimum(self):
        with self.assertRaises(TransferActionError):
            services.create_listing(
                self.player, self.seller, min_bid=Decimal('400000'),
                duration_days=3)

    def test_min_increment_rounding(self):
        # 5 % von 10 Mio = 500k → bleibt 500k (Vielfaches von 50k).
        self.assertEqual(services.min_increment(Decimal('10000000')),
                         Decimal('500000.00'))
        # max(100k, 5 % von 1 Mio=50k) = 100k.
        self.assertEqual(services.min_increment(Decimal('1000000')),
                         Decimal('100000.00'))
        # 5 % von 12,3 Mio = 615k → auf 50er-Raster: 600k < 615k → 650k.
        val = services.min_increment(Decimal('12300000'))
        self.assertEqual(val % Decimal('50000'), 0)
        self.assertGreaterEqual(val, Decimal('615000'))


class ReservationInvariantTests(Base):
    def test_bid_reserves_and_overbid_releases(self):
        listing = services.create_listing(
            self.player, self.seller, min_bid=Decimal('1000000'),
            duration_days=3)
        services.place_bid(listing, self.buyer, Decimal('1000000'))
        self.buyer.refresh_from_db()
        self.assertEqual(self.buyer.reserved, Decimal('1000000.00'))
        self.assertEqual(escrow.available(self.buyer),
                         Decimal('49000000.00'))

        # Überbieten durch Dritten → Buyer-Reservierung frei.
        services.place_bid(listing, self.third, Decimal('1200000'))
        self.buyer.refresh_from_db()
        self.third.refresh_from_db()
        self.assertEqual(self.buyer.reserved, Decimal('0.00'))
        self.assertEqual(self.third.reserved, Decimal('1200000.00'))

    def test_available_blocks_second_bid_over_budget(self):
        poor = _mk_club('FC Pleite', budget='1500000.00')
        l1 = services.create_listing(
            self.player, self.seller, min_bid=Decimal('1000000'),
            duration_days=3)
        p2 = _mk_player(self.seller, name='Zwei Ter')
        l2 = services.create_listing(
            p2, self.seller, min_bid=Decimal('1000000'), duration_days=3)
        services.place_bid(l1, poor, Decimal('1000000'))
        with self.assertRaises(TransferActionError):
            services.place_bid(l2, poor, Decimal('1000000'))

    def test_recalc_reserved_repairs_cache(self):
        listing = services.create_listing(
            self.player, self.seller, min_bid=Decimal('1000000'),
            duration_days=3)
        services.place_bid(listing, self.buyer, Decimal('1000000'))
        # Cache absichtlich korrumpieren.
        Club.objects.filter(pk=self.buyer.pk).update(reserved=Decimal('999'))
        self.buyer.refresh_from_db()
        alt, neu = escrow.recalc_reserved(self.buyer)
        self.assertEqual(alt, Decimal('999'))
        self.assertEqual(neu, Decimal('1000000.00'))
        self.buyer.refresh_from_db()
        self.assertEqual(self.buyer.reserved, Decimal('1000000.00'))


class AntiSnipingTests(Base):
    def test_late_bid_extends_24h(self):
        listing = services.create_listing(
            self.player, self.seller, min_bid=Decimal('1000000'),
            duration_days=1)
        # Ende künstlich auf +30 min setzen.
        TransferListing.objects.filter(pk=listing.pk).update(
            ends_at=timezone.now() + timedelta(minutes=30))
        listing.refresh_from_db()
        old_end = listing.ends_at
        services.place_bid(listing, self.buyer, Decimal('1000000'))
        listing.refresh_from_db()
        self.assertEqual(listing.extensions, 1)
        self.assertGreater(listing.ends_at, old_end + timedelta(hours=23))

    def test_early_bid_does_not_extend(self):
        listing = services.create_listing(
            self.player, self.seller, min_bid=Decimal('1000000'),
            duration_days=3)
        old_end = listing.ends_at
        services.place_bid(listing, self.buyer, Decimal('1000000'))
        listing.refresh_from_db()
        self.assertEqual(listing.extensions, 0)
        self.assertEqual(listing.ends_at, old_end)


class BuyNowTests(Base):
    def test_buy_now_books_and_moves_player(self):
        listing = services.create_listing(
            self.player, self.seller, min_bid=Decimal('1000000'),
            buy_now=Decimal('8000000'), duration_days=3)
        record = services.buy_now(listing, self.buyer)
        listing.refresh_from_db()
        self.player.refresh_from_db()
        self.buyer.refresh_from_db()
        self.seller.refresh_from_db()
        self.assertEqual(listing.status, TransferListing.STATUS_SOLD)
        self.assertEqual(self.player.club_id, self.buyer.pk)
        self.assertEqual(self.buyer.budget, Decimal('42000000.00'))
        self.assertEqual(self.seller.budget, Decimal('58000000.00'))
        self.assertTrue(self.player.is_transfer_locked)
        self.assertEqual(record.kind, TransferRecord.KIND_CASH)
        # 21-Tage-Sperre.
        tage = int(get_param('TRANSFER_WECHSELSPERRE_TAGE', '0'))
        self.assertEqual(
            self.player.transfer_locked_until,
            timezone.localdate() + timedelta(days=tage))

    def test_buy_now_releases_other_bidders(self):
        listing = services.create_listing(
            self.player, self.seller, min_bid=Decimal('1000000'),
            buy_now=Decimal('8000000'), duration_days=3)
        services.place_bid(listing, self.third, Decimal('1000000'))
        services.buy_now(listing, self.buyer)
        self.third.refresh_from_db()
        self.assertEqual(self.third.reserved, Decimal('0.00'))

    def test_high_bid_removes_buy_now(self):
        listing = services.create_listing(
            self.player, self.seller, min_bid=Decimal('1000000'),
            buy_now=Decimal('2000000'), duration_days=3)
        services.place_bid(listing, self.buyer, Decimal('2500000'))
        listing.refresh_from_db()
        self.assertIsNone(listing.buy_now)


class CloseListingTests(Base):
    def test_close_settles_to_leader_and_is_idempotent(self):
        listing = services.create_listing(
            self.player, self.seller, min_bid=Decimal('1000000'),
            duration_days=1)
        services.place_bid(listing, self.buyer, Decimal('1500000'))
        TransferListing.objects.filter(pk=listing.pk).update(
            ends_at=timezone.now() - timedelta(minutes=1))
        listing.refresh_from_db()

        result = jobs.close_due_listings()
        self.assertEqual(result['abgeschlossen'], 1)
        listing.refresh_from_db()
        self.player.refresh_from_db()
        self.buyer.refresh_from_db()
        self.assertEqual(listing.status, TransferListing.STATUS_SOLD)
        self.assertEqual(self.player.club_id, self.buyer.pk)
        self.assertEqual(self.buyer.reserved, Decimal('0.00'))
        self.assertEqual(self.buyer.budget, Decimal('48500000.00'))
        # Zweiter Lauf: nichts mehr fällig.
        result2 = jobs.close_due_listings()
        self.assertEqual(result2['abgeschlossen'], 0)

    def test_close_without_bids_expires(self):
        listing = services.create_listing(
            self.player, self.seller, min_bid=Decimal('1000000'),
            duration_days=1)
        TransferListing.objects.filter(pk=listing.pk).update(
            ends_at=timezone.now() - timedelta(minutes=1))
        jobs.close_due_listings()
        listing.refresh_from_db()
        self.assertEqual(listing.status, TransferListing.STATUS_EXPIRED)
        self.player.refresh_from_db()
        self.assertEqual(self.player.club_id, self.seller.pk)


class PendingTransferTests(Base):
    def test_wp_purchase_money_now_player_later(self):
        listing = services.create_listing(
            self.player, self.seller, min_bid=Decimal('1000000'),
            buy_now=Decimal('4000000'), timing='WP', duration_days=3)
        services.buy_now(listing, self.buyer)
        self.player.refresh_from_db()
        self.buyer.refresh_from_db()
        # Geld sofort, Spieler bleibt.
        self.assertEqual(self.buyer.budget, Decimal('46000000.00'))
        self.assertEqual(self.player.club_id, self.seller.pk)
        pending = PendingTransfer.objects.get(player=self.player)
        self.assertEqual(pending.status, PendingTransfer.STATUS_PENDING)
        # Kein erneutes Listen bis zum Stichtag.
        self.assertFalse(self.player.is_on_transfer_list)

        # Stichtag simulieren: fällig machen und Job laufen lassen.
        PendingTransfer.objects.filter(pk=pending.pk).update(
            execute_at=timezone.localdate())
        result = jobs.execute_due_pendings()
        self.assertEqual(result['vollzogen'], 1)
        self.player.refresh_from_db()
        self.assertEqual(self.player.club_id, self.buyer.pk)
        self.assertTrue(self.player.is_transfer_locked)


class YouthLevyTests(Base):
    def _history(self, player, stationen):
        for season, club in stationen:
            PlayerClubHistory.objects.create(
                player=player, club=club, season=season)

    def test_eigengewaechs_keine_abgabe(self):
        # Spieler-Anlage beim Verkäufer erzeugt die (0, seller)-Station
        # automatisch (club_history-Tracking) → nur Eigenanteile → 0 €.
        young = _mk_player(self.seller, name='Eigen Gewaechs', age=19)
        v = youth_levy.calc_youth_levy(
            young, Decimal('10000000'), zahler_club=self.seller)
        self.assertEqual(v['summe'], Decimal('0.00'))
        self.assertEqual(v['anteile_gesamt'], 1)

    def test_acht_prozent_verteilt(self):
        jugend = _mk_club('FC Jugend')
        # age=25, Saison 0 → cutoff = 0 + (21-25) = -4 → keine Station zählt.
        # Für den Test einen jüngeren Spieler nutzen (auto-Station (0,seller)).
        young = _mk_player(self.seller, name='Ju Gend', age=19)
        self._history(young, [(1, jugend), (2, jugend)])
        v = youth_levy.calc_youth_levy(
            young, Decimal('10000000'), zahler_club=self.seller)
        # 8 % von 10 Mio = 800k über 3 Stationen; 2 fremd (jugend), 1 eigener
        # Anteil (seller) wird nicht erhoben → 800k/3*2 = 533.333,33 €.
        self.assertEqual(v['anteile_gesamt'], 3)
        self.assertEqual(v['anteile_fremd'], 2)
        self.assertEqual(v['summe'], Decimal('533333.33'))
        self.assertEqual(
            v['betraege_je_ausbildungsverein'][jugend.pk],
            Decimal('533333.33'))

    def test_mindestabgabe_50k(self):
        jugend = _mk_club('FC Mini')
        young = _mk_player(self.seller, name='Klein Geld', age=19)
        self._history(young, [(1, jugend)])
        v = youth_levy.calc_youth_levy(
            young, Decimal('100000'), zahler_club=self.seller)
        # 8 % von 100k = 8k über 2 Stationen → 4k fremd < 50k → Mindestabgabe.
        self.assertEqual(v['summe'], Decimal('50000.00'))

    def test_swap_bemessung(self):
        p = _mk_player(self.seller, name='Tausch Wert', mw='3000000')
        basis = youth_levy.swap_bemessung(p, Decimal('2000000'), 2)
        self.assertEqual(basis, Decimal('4000000.00'))  # 3 Mio + 2 Mio/2.

    def test_levy_booked_on_purchase(self):
        jugend = _mk_club('FC Talentschmiede', budget='0.00')
        young = _mk_player(self.seller, name='Gebucht Levy', age=20)
        # Auto-Station (0, seller) + fremde Station (1, jugend) → 800k/2 = 400k.
        PlayerClubHistory.objects.create(player=young, club=jugend, season=1)
        listing = services.create_listing(
            young, self.seller, min_bid=Decimal('1000000'),
            buy_now=Decimal('10000000'), duration_days=3)
        services.buy_now(listing, self.buyer)
        jugend.refresh_from_db()
        self.seller.refresh_from_db()
        self.assertEqual(jugend.budget, Decimal('400000.00'))
        # Verkäufer: +10 Mio Ablöse − 400k Abgabe.
        self.assertEqual(self.seller.budget, Decimal('59600000.00'))
        self.assertEqual(YouthLevyPayment.objects.count(), 1)
        self.assertTrue(FinanceTransaction.objects.filter(
            typ='AUSBILDUNG_EIN', club=jugend).exists())


class DealRequestTests(Base):
    def test_deal_reserves_and_expiry_releases(self):
        p_from = _mk_player(self.buyer, name='Geber Spieler')
        deal = services.create_deal_request(
            self.buyer, self.seller, typ=DealRequest.TYP_CASH,
            cash_from=Decimal('3000000'), to_players=[self.player])
        self.buyer.refresh_from_db()
        self.assertEqual(self.buyer.reserved, Decimal('3000000.00'))
        DealRequest.objects.filter(pk=deal.pk).update(
            expires_at=timezone.now() - timedelta(minutes=1))
        result = jobs.expire_due_deals()
        self.assertEqual(result['abgelaufen'], 1)
        self.buyer.refresh_from_db()
        self.assertEqual(self.buyer.reserved, Decimal('0.00'))

    def test_accept_cash_deal_moves_player_both_ways(self):
        deal = services.create_deal_request(
            self.buyer, self.seller, typ=DealRequest.TYP_CASH,
            cash_from=Decimal('3000000'), to_players=[self.player])
        record = services.accept_deal(deal)
        self.player.refresh_from_db()
        self.buyer.refresh_from_db()
        self.seller.refresh_from_db()
        self.assertEqual(self.player.club_id, self.buyer.pk)
        self.assertEqual(self.buyer.budget, Decimal('47000000.00'))
        self.assertEqual(self.seller.budget, Decimal('53000000.00'))
        self.assertEqual(self.buyer.reserved, Decimal('0.00'))
        self.assertTrue(self.player.is_transfer_locked)
        self.assertIsNotNone(record)

    def test_negative_cash_rejected(self):
        with self.assertRaises(TransferActionError):
            services.create_deal_request(
                self.buyer, self.seller, typ=DealRequest.TYP_CASH,
                cash_from=Decimal('-1000000'), to_players=[self.player])

    def test_loan_request_schema_enforced(self):
        # Leihanfrage mit mehreren Spielern / eigenen Spielern / Geldanteil
        # oder ungültigem Leihende → abgelehnt.
        zweiter = _mk_player(self.seller, name='Zweiter Leih')
        eigener = _mk_player(self.buyer, name='Eigener Leih')
        with self.assertRaises(TransferActionError):
            services.create_deal_request(
                self.buyer, self.seller, typ=DealRequest.TYP_LOAN,
                loan_until='SE', loan_fee=Decimal('1000000'),
                to_players=[self.player, zweiter])
        with self.assertRaises(TransferActionError):
            services.create_deal_request(
                self.buyer, self.seller, typ=DealRequest.TYP_LOAN,
                loan_until='SE', loan_fee=Decimal('1000000'),
                from_players=[eigener], to_players=[self.player])
        with self.assertRaises(TransferActionError):
            services.create_deal_request(
                self.buyer, self.seller, typ=DealRequest.TYP_LOAN,
                loan_until='SE', loan_fee=Decimal('1000000'),
                cash_from=Decimal('500000'), to_players=[self.player])
        with self.assertRaises(TransferActionError):
            services.create_deal_request(
                self.buyer, self.seller, typ=DealRequest.TYP_LOAN,
                loan_until='XX', loan_fee=Decimal('1000000'),
                to_players=[self.player])

    def test_invalid_type_and_timing_rejected(self):
        with self.assertRaises(TransferActionError):
            services.create_deal_request(
                self.buyer, self.seller, typ='UNSINN',
                cash_from=Decimal('1000000'), to_players=[self.player])
        with self.assertRaises(TransferActionError):
            services.create_deal_request(
                self.buyer, self.seller, typ=DealRequest.TYP_CASH,
                timing='MORGEN', cash_from=Decimal('1000000'),
                to_players=[self.player])

    def test_cash_deal_requires_positive_cash_and_no_own_players(self):
        eigener = _mk_player(self.buyer, name='Falsch Seite')
        with self.assertRaises(TransferActionError):
            services.create_deal_request(
                self.buyer, self.seller, typ=DealRequest.TYP_CASH,
                cash_from=Decimal('0'), to_players=[self.player])
        with self.assertRaises(TransferActionError):
            services.create_deal_request(
                self.buyer, self.seller, typ=DealRequest.TYP_CASH,
                cash_from=Decimal('1000000'), from_players=[eigener],
                to_players=[self.player])

    def test_loan_listing_state_validation(self):
        # Gesperrter Spieler nicht leihbar listbar.
        Player.objects.filter(pk=self.player.pk).update(
            transfer_locked_until=timezone.now().date() + timedelta(days=30))
        self.player.refresh_from_db()
        with self.assertRaises(TransferActionError):
            services.create_loan_listing(
                self.player, self.seller, fee_asking=Decimal('1000000'),
                until='SE')
        Player.objects.filter(pk=self.player.pk).update(
            transfer_locked_until=None)
        self.player.refresh_from_db()
        # Doppeltes aktives Leih-Listing verboten.
        services.create_loan_listing(
            self.player, self.seller, fee_asking=Decimal('1000000'),
            until='SE')
        with self.assertRaises(TransferActionError):
            services.create_loan_listing(
                self.player, self.seller, fee_asking=Decimal('1000000'),
                until='SE')

    def test_listing_blocked_below_min_squad(self):
        # Mindestkader: Verkäufer (1 Spieler) darf bei KADER_MIN=1 nicht listen.
        EconomyParameter.objects.update_or_create(
            saison='0', key='KADER_MIN', defaults={'value': 1})
        with self.assertRaises(TransferActionError):
            services.create_listing(
                self.player, self.seller, min_bid=Decimal('1000000'),
                duration_days=3)

    def test_purchase_blocked_when_buyer_squad_full(self):
        # Kaderlimit des Käufers ist beim Settlement hart.
        from game.transfer_v2.execution import ExecutionError
        listing = services.create_listing(
            self.player, self.seller, min_bid=Decimal('1000000'),
            buy_now=Decimal('5000000'), duration_days=3)
        _mk_player(self.buyer, name='Voll Kader')
        EconomyParameter.objects.update_or_create(
            saison='0', key='KADER_MAX_BASIS', defaults={'value': 1})
        with self.assertRaises((TransferActionError, ExecutionError)):
            services.buy_now(listing, self.buyer)
        self.player.refresh_from_db()
        self.assertEqual(self.player.club_id, self.seller.pk)

    def test_loan_blocked_when_loan_club_squad_full(self):
        # Aufnehmender Verein ohne freien Kaderplatz darf nicht leihen.
        _mk_player(self.buyer, name='Leih Blocker')
        EconomyParameter.objects.update_or_create(
            saison='0', key='KADER_MAX_BASIS', defaults={'value': 1})
        listing = services.create_loan_listing(
            self.player, self.seller, fee_asking=Decimal('1000000'),
            until='SE')
        with self.assertRaises(TransferActionError):
            services.request_loan(listing, self.buyer)

    def test_buy_option_exercise_full_purchase(self):
        # Leihe mit Kaufoption → Option ziehen: Geld, Leih-Ende, fester
        # Wechsel, Wechselsperre, OPTION-Record, Jugendabgabe auf Preis.
        jugend = _mk_club('FC Options Jugend', budget='0.00')
        young = _mk_player(self.seller, name='Options Spieler', age=19)
        PlayerClubHistory.objects.create(player=young, club=jugend, season=1)
        listing = services.create_loan_listing(
            young, self.seller, fee_asking=Decimal('1000000'), until='SE',
            buy_option_price=Decimal('10000000'))
        deal = services.request_loan(listing, self.buyer)
        services.accept_deal(deal)
        loan = Loan.objects.get(player=young, ended_at__isnull=True)
        record = services.exercise_buy_option(loan, self.buyer)
        loan.refresh_from_db()
        young.refresh_from_db()
        self.buyer.refresh_from_db()
        self.seller.refresh_from_db()
        jugend.refresh_from_db()
        self.assertIsNotNone(loan.ended_at)
        self.assertEqual(young.club_id, self.buyer.pk)
        self.assertEqual(young.loan_status, '')
        self.assertTrue(young.is_transfer_locked)
        self.assertEqual(record.kind, TransferRecord.KIND_OPTION)
        # Die Leihe selbst erzeugt eine Ausbildungsstation beim Leihverein
        # (Alter 19 < Cutoff) → 3 Stationen: seller (eigen, entfällt),
        # jugend und buyer. 8 % von 10 Mio = 800k / 3 = 266.666,67 je Station.
        self.assertEqual(jugend.budget, Decimal('266666.67'))
        # Käufer: 50 − 1 Gebühr − 10 Option + eigener Ausbildungsanteil.
        self.assertEqual(self.buyer.budget, Decimal('39266666.67'))
        # Verkäufer: 50 + 1 Gebühr + 10 Option − 533.333,34 Abgabe.
        self.assertEqual(self.seller.budget, Decimal('60466666.66'))

    def test_buy_option_failure_paths(self):
        # Ohne Option / falscher Verein / beendete Leihe / kein Budget.
        listing = services.create_loan_listing(
            self.player, self.seller, fee_asking=Decimal('1000000'),
            until='SE')
        deal = services.request_loan(listing, self.buyer)
        services.accept_deal(deal)
        loan = Loan.objects.get(player=self.player, ended_at__isnull=True)
        with self.assertRaises(TransferActionError):
            services.exercise_buy_option(loan, self.buyer)  # keine Option.
        Loan.objects.filter(pk=loan.pk).update(
            buy_option=Decimal('10000000'))
        loan.refresh_from_db()
        with self.assertRaises(TransferActionError):
            services.exercise_buy_option(loan, self.third)  # falscher Verein.
        Club.objects.filter(pk=self.buyer.pk).update(
            budget=Decimal('1000000'))
        with self.assertRaises(TransferActionError):
            services.exercise_buy_option(loan, self.buyer)  # keine Deckung.
        Club.objects.filter(pk=self.buyer.pk).update(
            budget=Decimal('50000000'))
        Loan.objects.filter(pk=loan.pk).update(ended_at=timezone.now())
        loan.refresh_from_db()
        with self.assertRaises(TransferActionError):
            services.exercise_buy_option(loan, self.buyer)  # beendet.

    def test_loan_listing_invalid_until_and_negative_fee(self):
        with self.assertRaises(TransferActionError):
            services.create_loan_listing(
                self.player, self.seller, fee_asking=Decimal('1000000'),
                until='XX')
        with self.assertRaises(TransferActionError):
            services.create_loan_listing(
                self.player, self.seller, fee_asking=Decimal('-1'),
                until='SE')

    def test_swap_with_cash_persists_as_swap_cash(self):
        # Tausch MIT Geldausgleich wird konsistent als SWAP_CASH persistiert.
        gegen = _mk_player(self.buyer, name='Swap Cash')
        deal = services.create_deal_request(
            self.buyer, self.seller, typ=DealRequest.TYP_SWAP,
            cash_from=Decimal('2000000'),
            from_players=[gegen], to_players=[self.player])
        self.assertEqual(deal.typ, DealRequest.TYP_SWAP_CASH)
        # Explizites SWAP_CASH ohne Geld → abgelehnt.
        with self.assertRaises(TransferActionError):
            services.create_deal_request(
                self.buyer, self.seller, typ=DealRequest.TYP_SWAP_CASH,
                from_players=[gegen], to_players=[self.player])

    def test_pending_over_limit_cancelled_with_refund(self):
        # WP-Kauf gültig, aber am Stichtag ist der Käufer-Kader voll →
        # Pending wird storniert, Geld (inkl. Jugendabgabe) zurückgebucht,
        # Spieler bleibt beim Verkäufer.
        jugend = _mk_club('FC Pending Jugend', budget='0.00')
        young = _mk_player(self.seller, name='Pending Limit', age=19)
        PlayerClubHistory.objects.create(player=young, club=jugend, season=1)
        listing = services.create_listing(
            young, self.seller, min_bid=Decimal('1000000'),
            buy_now=Decimal('10000000'), timing='WP', duration_days=3)
        services.buy_now(listing, self.buyer)
        jugend.refresh_from_db()
        self.assertEqual(jugend.budget, Decimal('400000.00'))
        # Kaderlimit auf aktuellen Stand einfrieren → +1 verletzt es.
        _mk_player(self.buyer, name='Kader Voll')
        EconomyParameter.objects.update_or_create(
            saison='0', key='KADER_MAX_BASIS', defaults={'value': 1})
        pending = PendingTransfer.objects.get(player=young)
        PendingTransfer.objects.filter(pk=pending.pk).update(
            execute_at=timezone.localdate())
        jobs.execute_due_pendings()
        pending.refresh_from_db()
        young.refresh_from_db()
        self.buyer.refresh_from_db()
        self.seller.refresh_from_db()
        jugend.refresh_from_db()
        self.assertEqual(pending.status,
                         PendingTransfer.STATUS_CANCELLED_LIMIT)
        self.assertEqual(young.club_id, self.seller.pk)
        # Käufer voll erstattet, Verkäufer und Jugendverein zurückgebucht.
        self.assertEqual(self.buyer.budget, Decimal('50000000.00'))
        self.assertEqual(self.seller.budget, Decimal('50000000.00'))
        self.assertEqual(jugend.budget, Decimal('0.00'))
        self.assertFalse(YouthLevyPayment.objects.filter(
            player=young).exists())

    def test_buy_now_price_must_be_valid(self):
        # 0 €, negativ oder unter Mindestgebot → kein Listing, keine Buchung.
        for preis in (Decimal('0'), Decimal('-1000000'), Decimal('900000')):
            with self.assertRaises(TransferActionError):
                services.create_listing(
                    self.player, self.seller, min_bid=Decimal('1000000'),
                    buy_now=preis, duration_days=3)
        self.assertFalse(TransferListing.objects.filter(
            player=self.player).exists())
        self.assertFalse(FinanceTransaction.objects.filter(
            referenz_typ='transfer_v2').exists())

    def test_listing_invalid_timing_rejected(self):
        with self.assertRaises(TransferActionError):
            services.create_listing(
                self.player, self.seller, min_bid=Decimal('1000000'),
                timing='MORGEN', duration_days=3)

    def test_auction_close_conflict_expires_and_releases_escrow(self):
        # Bieter-Kader ist zum Abschluss voll → Auktion EXPIRED, gesamtes
        # Escrow frei, Listing bleibt nicht mit gebundenem Geld hängen.
        listing = services.create_listing(
            self.player, self.seller, min_bid=Decimal('1000000'),
            duration_days=3)
        services.place_bid(listing, self.buyer, Decimal('1000000'))
        services.place_bid(listing, self.third, Decimal('2000000'))
        _mk_player(self.third, name='Voll Bieter')
        EconomyParameter.objects.update_or_create(
            saison='0', key='KADER_MAX_BASIS', defaults={'value': 1})
        TransferListing.objects.filter(pk=listing.pk).update(
            ends_at=timezone.now() - timedelta(minutes=1))
        listing.refresh_from_db()
        result = services.close_listing(listing)
        listing.refresh_from_db()
        self.player.refresh_from_db()
        self.buyer.refresh_from_db()
        self.third.refresh_from_db()
        self.assertEqual(listing.status, TransferListing.STATUS_EXPIRED)
        self.assertEqual(self.player.club_id, self.seller.pk)
        self.assertEqual(self.buyer.reserved, Decimal('0.00'))
        self.assertEqual(self.third.reserved, Decimal('0.00'))
        self.assertEqual(self.third.budget, Decimal('50000000.00'))
        # Idempotent: erneuter Abschluss ändert nichts.
        services.close_listing(listing)
        listing.refresh_from_db()
        self.assertEqual(listing.status, TransferListing.STATUS_EXPIRED)

    def test_deferred_swap_settles_atomically(self):
        # WP-Tausch 2-gegen-1 mit Geld: am Stichtag verletzt der NETTO-
        # Zugang (+1) beim Empfänger das Kaderlimit → ALLE Beine werden
        # storniert (kein einseitiger Spielertausch), Geld voll zurück.
        gegen1 = _mk_player(self.buyer, name='Atomar Eins')
        gegen2 = _mk_player(self.buyer, name='Atomar Zwei')
        deal = services.create_deal_request(
            self.buyer, self.seller, typ=DealRequest.TYP_SWAP,
            timing='WP', cash_from=Decimal('2000000'),
            from_players=[gegen1, gegen2], to_players=[self.player])
        services.accept_deal(deal)
        self.assertEqual(PendingTransfer.objects.filter(
            status=PendingTransfer.STATUS_PENDING).count(), 3)
        # seller-Kader voll machen → Netto +1 verletzt das Limit.
        _mk_player(self.seller, name='Voll Macher')
        EconomyParameter.objects.update_or_create(
            saison='0', key='KADER_MAX_BASIS', defaults={'value': 2})
        PendingTransfer.objects.filter(
            status=PendingTransfer.STATUS_PENDING).update(
            execute_at=timezone.localdate())
        jobs.execute_due_pendings()
        self.player.refresh_from_db()
        gegen1.refresh_from_db()
        gegen2.refresh_from_db()
        self.buyer.refresh_from_db()
        self.seller.refresh_from_db()
        # Kein Bein vollzogen — alle Spieler bleiben, Geld zurück.
        self.assertEqual(self.player.club_id, self.seller.pk)
        self.assertEqual(gegen1.club_id, self.buyer.pk)
        self.assertEqual(gegen2.club_id, self.buyer.pk)
        self.assertEqual(
            set(PendingTransfer.objects.values_list('status', flat=True)),
            {PendingTransfer.STATUS_CANCELLED_LIMIT})
        self.assertEqual(self.buyer.budget, Decimal('50000000.00'))
        self.assertEqual(self.seller.budget, Decimal('50000000.00'))

    def test_pending_cancelled_when_player_locked_before_cutoff(self):
        # Spieler wird NACH Zuschlag, aber VOR dem WP-Stichtag anderweitig
        # wechselgesperrt → Einheit storniert + Geld zurück, kein Zwangsumzug.
        listing = services.create_listing(
            self.player, self.seller, min_bid=Decimal('1000000'),
            buy_now=Decimal('10000000'), timing='WP', duration_days=3)
        services.buy_now(listing, self.buyer)
        Player.objects.filter(pk=self.player.pk).update(
            transfer_locked_until=timezone.localdate() + timedelta(days=60))
        PendingTransfer.objects.filter(player=self.player).update(
            execute_at=timezone.localdate())
        jobs.execute_due_pendings()
        pending = PendingTransfer.objects.get(player=self.player)
        self.player.refresh_from_db()
        self.buyer.refresh_from_db()
        self.seller.refresh_from_db()
        self.assertEqual(pending.status,
                         PendingTransfer.STATUS_CANCELLED_LIMIT)
        self.assertEqual(self.player.club_id, self.seller.pk)
        self.assertEqual(self.buyer.budget, Decimal('50000000.00'))
        self.assertEqual(self.seller.budget, Decimal('50000000.00'))

    def test_pending_cancelled_when_player_left_club_before_cutoff(self):
        # Spieler ist am Stichtag nicht mehr beim abgebenden Verein (z. B.
        # Admin-Umzug) → Storno statt Überschreiben der neuen Zuordnung.
        listing = services.create_listing(
            self.player, self.seller, min_bid=Decimal('1000000'),
            buy_now=Decimal('10000000'), timing='SE', duration_days=3)
        services.buy_now(listing, self.buyer)
        Player.objects.filter(pk=self.player.pk).update(club=self.third)
        PendingTransfer.objects.filter(player=self.player).update(
            execute_at=timezone.localdate())
        jobs.execute_due_pendings()
        pending = PendingTransfer.objects.get(player=self.player)
        self.player.refresh_from_db()
        self.buyer.refresh_from_db()
        self.assertEqual(pending.status,
                         PendingTransfer.STATUS_CANCELLED_LIMIT)
        self.assertEqual(self.player.club_id, self.third.pk)
        self.assertEqual(self.buyer.budget, Decimal('50000000.00'))

    def test_award_blocked_when_player_locked_after_listing(self):
        # Spieler wird NACH Listing-Erstellung wechselgesperrt → Zuschlag
        # darf nicht vollzogen werden; Auktion endet EXPIRED + Escrow frei.
        listing = services.create_listing(
            self.player, self.seller, min_bid=Decimal('1000000'),
            duration_days=3)
        services.place_bid(listing, self.buyer, Decimal('1000000'))
        Player.objects.filter(pk=self.player.pk).update(
            transfer_locked_until=timezone.localdate() + timedelta(days=10))
        TransferListing.objects.filter(pk=listing.pk).update(
            ends_at=timezone.now() - timedelta(minutes=1))
        listing.refresh_from_db()
        services.close_listing(listing)
        listing.refresh_from_db()
        self.player.refresh_from_db()
        self.buyer.refresh_from_db()
        self.assertEqual(listing.status, TransferListing.STATUS_EXPIRED)
        self.assertEqual(self.player.club_id, self.seller.pk)
        self.assertEqual(self.buyer.reserved, Decimal('0.00'))
        self.assertEqual(self.buyer.budget, Decimal('50000000.00'))

    def test_swap_deal_respects_squad_bounds(self):
        # Empfänger (seller) hätte nach 2-gegen-1 einen Spieler zu viel.
        EconomyParameter.objects.update_or_create(
            saison='0', key='KADER_MAX_BASIS', defaults={'value': 2})
        p1 = _mk_player(self.buyer, name='Paket Eins')
        p2 = _mk_player(self.buyer, name='Paket Zwei')
        _mk_player(self.seller, name='Fuell Kader')  # seller hat nun 2.
        with self.assertRaises(TransferActionError):
            services.create_deal_request(
                self.buyer, self.seller, typ=DealRequest.TYP_SWAP,
                from_players=[p1, p2], to_players=[self.player])

    def test_accept_revalidates_squad_bounds(self):
        # Deal gültig erstellt, aber vor der Annahme sinkt der Kader des
        # Verkäufers unter das Minimum → Annahme muss ablehnen.
        deal = services.create_deal_request(
            self.buyer, self.seller, typ=DealRequest.TYP_CASH,
            cash_from=Decimal('3000000'), to_players=[self.player])
        EconomyParameter.objects.update_or_create(
            saison='0', key='KADER_MIN', defaults={'value': 5})
        with self.assertRaises(TransferActionError):
            services.accept_deal(deal)
        self.player.refresh_from_db()
        self.assertEqual(self.player.club_id, self.seller.pk)

    def test_cash_deal_levy_uses_price_only(self):
        # Reiner Geld-Deal: Bemessung = NUR gezahlter Preis, nie MW obendrauf.
        # Spieler-MW 5 Mio, Preis 3 Mio → 8 % von 3 Mio = 240k über 2
        # Stationen (Auto-Station seller + jugend) → 120k an jugend.
        jugend = _mk_club('FC Cash Jugend', budget='0.00')
        young = _mk_player(self.seller, name='Cash Levy', age=19)
        PlayerClubHistory.objects.create(player=young, club=jugend, season=1)
        deal = services.create_deal_request(
            self.buyer, self.seller, typ=DealRequest.TYP_CASH,
            cash_from=Decimal('3000000'), to_players=[young])
        services.accept_deal(deal)
        jugend.refresh_from_db()
        self.assertEqual(jugend.budget, Decimal('120000.00'))

    def test_swap_deal_levy_uses_mw_plus_cash(self):
        # Tausch mit Geld: Bemessung = MW + anteiliges Gegenseiten-Geld.
        # to-Spieler (MW 5 Mio) + cash_from 2 Mio → Basis 7 Mio → 8 % = 560k
        # über 2 Stationen → 280k an jugend.
        jugend = _mk_club('FC Swap Jugend', budget='0.00')
        young = _mk_player(self.seller, name='Swap Levy', age=19,
                           mw='5000000')
        PlayerClubHistory.objects.create(player=young, club=jugend, season=1)
        gegen = _mk_player(self.buyer, name='Gegen Spieler', mw='1000000')
        deal = services.create_deal_request(
            self.buyer, self.seller, typ=DealRequest.TYP_SWAP,
            cash_from=Decimal('2000000'),
            from_players=[gegen], to_players=[young])
        services.accept_deal(deal)
        jugend.refresh_from_db()
        self.assertEqual(jugend.budget, Decimal('280000.00'))

    def test_max_paket_5(self):
        players = [_mk_player(self.buyer, name=f'Nr Fuenf{i}')
                   for i in range(6)]
        with self.assertRaises(TransferActionError):
            services.create_deal_request(
                self.buyer, self.seller, typ=DealRequest.TYP_SWAP,
                from_players=players)

    def test_from_player_must_belong_to_initiator(self):
        # Fremder Spieler (gehört third) auf der FROM-Seite → abgelehnt.
        fremd = _mk_player(self.third, name='Fremd Eigentum')
        with self.assertRaises(TransferActionError):
            services.create_deal_request(
                self.buyer, self.seller, typ=DealRequest.TYP_SWAP,
                from_players=[fremd], to_players=[self.player])

    def test_to_player_must_belong_to_recipient(self):
        # Spieler eines Dritten auf der TO-Seite → abgelehnt.
        fremd = _mk_player(self.third, name='Dritt Verein')
        with self.assertRaises(TransferActionError):
            services.create_deal_request(
                self.buyer, self.seller, typ=DealRequest.TYP_CASH,
                cash_from=Decimal('1000000'), to_players=[fremd])

    def test_accept_revalidates_ownership(self):
        # Gültig erstellt, aber Spieler wechselt vor Annahme den Verein →
        # Annahme muss ablehnen (Re-Validierung, kein Fremd-Transfer).
        deal = services.create_deal_request(
            self.buyer, self.seller, typ=DealRequest.TYP_CASH,
            cash_from=Decimal('3000000'), to_players=[self.player])
        Player.objects.filter(pk=self.player.pk).update(club=self.third)
        with self.assertRaises(TransferActionError):
            services.accept_deal(deal)
        # Deal bleibt offen, Reservierung bleibt bestehen (Rollback).
        deal.refresh_from_db()
        self.buyer.refresh_from_db()
        self.assertEqual(deal.status, DealRequest.STATUS_OPEN)
        self.assertEqual(self.buyer.reserved, Decimal('3000000.00'))

    def test_pending_transfer_blocks_deal_player(self):
        # Spieler mit ausstehendem WP-Transfer darf in keinen Deal.
        listing = services.create_listing(
            self.player, self.seller, min_bid=Decimal('1000000'),
            buy_now=Decimal('2000000'), timing='WP', duration_days=3)
        services.buy_now(listing, self.third)
        with self.assertRaises(TransferActionError):
            services.create_deal_request(
                self.buyer, self.seller, typ=DealRequest.TYP_CASH,
                cash_from=Decimal('1000000'), to_players=[self.player])

    def test_accept_high_value_cash_deal(self):
        # Escrow-Reihenfolge: 30-Mio-Anteil bei 50-Mio-Budget muss klappen —
        # die eigene Reservierung darf bei der Buchung nicht doppelt zählen.
        deal = services.create_deal_request(
            self.buyer, self.seller, typ=DealRequest.TYP_CASH,
            cash_from=Decimal('30000000'), to_players=[self.player])
        self.buyer.refresh_from_db()
        self.assertEqual(self.buyer.reserved, Decimal('30000000.00'))
        services.accept_deal(deal)
        self.buyer.refresh_from_db()
        self.seller.refresh_from_db()
        self.player.refresh_from_db()
        self.assertEqual(self.player.club_id, self.buyer.pk)
        self.assertEqual(self.buyer.budget, Decimal('20000000.00'))
        self.assertEqual(self.buyer.reserved, Decimal('0.00'))
        self.assertEqual(self.seller.budget, Decimal('80000000.00'))


class LoanRuleTests(Base):
    def test_min_fee_enforced(self):
        with self.assertRaises(TransferActionError):
            services.create_loan_listing(
                self.player, self.seller, fee_asking=Decimal('500000'),
                until='SE')

    def test_zero_fee_requires_partnership(self):
        with self.assertRaises(TransferActionError):
            services._validate_loan_fee(
                self.seller, self.buyer, Decimal('0'))
        ClubPartnership.objects.create(club_a=self.seller, club_b=self.buyer)
        # Jetzt erlaubt (auch in umgekehrter Richtung).
        self.assertEqual(
            services._validate_loan_fee(self.buyer, self.seller, Decimal('0')),
            Decimal('0.00'))

    def test_borrower_cannot_list_loaned_player(self):
        # Leih-Verein (player.club zeigt auf ihn!) darf den geliehenen
        # Spieler NICHT listen oder verkaufen.
        loan_listing = services.create_loan_listing(
            self.player, self.seller, fee_asking=Decimal('1000000'),
            until='SE')
        deal = services.request_loan(loan_listing, self.buyer)
        services.accept_deal(deal)
        self.player.refresh_from_db()
        self.assertEqual(self.player.club_id, self.buyer.pk)  # geliehen
        with self.assertRaises(TransferActionError):
            services.create_listing(
                self.player, self.buyer, min_bid=Decimal('1000000'),
                duration_days=3)
        # Auch der Eigentümer darf während der Leihe nicht listen.
        with self.assertRaises(TransferActionError):
            services.create_listing(
                self.player, self.seller, min_bid=Decimal('1000000'),
                duration_days=3)

    def test_purchase_revalidates_loan_state(self):
        # Leihe startet NACH Listing-Erstellung → Settlement muss ablehnen.
        from game.transfer_v2.execution import ExecutionError
        listing = services.create_listing(
            self.player, self.seller, min_bid=Decimal('1000000'),
            buy_now=Decimal('5000000'), duration_days=3)
        Loan.objects.create(
            player=self.player, owner_club=self.seller, loan_club=self.third,
            fee=Decimal('0'), until='SE')
        Player.objects.filter(pk=self.player.pk).update(
            loan_status='loaned_out')
        with self.assertRaises((TransferActionError, ExecutionError)):
            services.buy_now(listing, self.buyer)
        self.player.refresh_from_db()
        self.assertEqual(self.player.club_id, self.seller.pk)

    def test_foreign_reservation_blocks_bid(self):
        # Aktive Reservierung eines ANDEREN Subsystems (z. B. Show-Auktion)
        # muss die v2-Deckungsprüfung mindern — sonst platzt das Settlement
        # später in book_many.
        from game.economy import reservations
        reservations.reserve(
            self.buyer, referenz='showauction:test:1', zweck='show_auction',
            betrag=Decimal('49000000'))
        listing = services.create_listing(
            self.player, self.seller, min_bid=Decimal('2000000'),
            duration_days=3)
        with self.assertRaises(TransferActionError):
            services.place_bid(listing, self.buyer, Decimal('2000000'))
        # Nach Freigabe der Fremd-Reservierung klappt das Gebot.
        reservations.release('showauction:test:1')
        bid = services.place_bid(listing, self.buyer, Decimal('2000000'))
        self.assertEqual(bid.amount, Decimal('2000000.00'))

    def test_foreign_reservation_blocks_deal(self):
        from game.economy import reservations
        reservations.reserve(
            self.buyer, referenz='showauction:test:2', zweck='show_auction',
            betrag=Decimal('49000000'))
        with self.assertRaises(TransferActionError):
            services.create_deal_request(
                self.buyer, self.seller, typ=DealRequest.TYP_CASH,
                cash_from=Decimal('2000000'), to_players=[self.player])

    def test_self_overbid_excludes_own_reservation(self):
        # Führender überbietet sich selbst: eigene Reservierung zählt nicht
        # doppelt gegen die Deckung.
        listing = services.create_listing(
            self.player, self.seller, min_bid=Decimal('20000000'),
            duration_days=3)
        services.place_bid(listing, self.buyer, Decimal('30000000'))
        # 30 Mio reserviert bei 50 Mio Budget → 45 Mio wäre ohne
        # exclude-Logik nicht gedeckt (50−30=20 < 45), mit ihr schon.
        bid = services.place_bid(listing, self.buyer, Decimal('45000000'))
        self.assertEqual(bid.amount, Decimal('45000000.00'))
        self.buyer.refresh_from_db()
        self.assertEqual(self.buyer.reserved, Decimal('45000000.00'))

    def test_free_agent_listing_requires_clubless_player(self):
        # Spieler MIT Verein darf nicht als Vereinslosen-Listing laufen
        # (würde sonst den Eigentums-Check in execute_purchase umgehen).
        with self.assertRaises(TransferActionError):
            services.create_listing(self.player, None, min_bid=None)

    def test_listing_requires_ownership(self):
        # Fremder Verein kann keinen fremden Spieler listen.
        with self.assertRaises(TransferActionError):
            services.create_listing(
                self.player, self.buyer, min_bid=Decimal('1000000'),
                duration_days=3)

    def test_no_duplicate_active_listing(self):
        services.create_listing(
            self.player, self.seller, min_bid=Decimal('1000000'),
            duration_days=3)
        with self.assertRaises(TransferActionError):
            services.create_listing(
                self.player, self.seller, min_bid=Decimal('1000000'),
                duration_days=3)

    def test_buy_now_rejected_after_expiry(self):
        # Abgelaufene Auktion (Minuten-Job noch nicht gelaufen): Sofortkauf
        # muss wie place_bid ablehnen.
        listing = services.create_listing(
            self.player, self.seller, min_bid=Decimal('1000000'),
            buy_now=Decimal('5000000'), duration_days=1)
        TransferListing.objects.filter(pk=listing.pk).update(
            ends_at=timezone.now() - timezone.timedelta(minutes=1))
        listing.refresh_from_db()
        with self.assertRaises(TransferActionError):
            services.buy_now(listing, self.buyer)
        self.player.refresh_from_db()
        self.assertEqual(self.player.club_id, self.seller.pk)

    def test_loan_listing_closed_after_loan_start(self):
        listing = services.create_loan_listing(
            self.player, self.seller, fee_asking=Decimal('1000000'),
            until='SE')
        deal = services.request_loan(listing, self.buyer)
        services.accept_deal(deal)
        listing.refresh_from_db()
        self.assertEqual(listing.status, LoanListing.STATUS_LOANED)
        # Erneute Anfrage auf das geschlossene Listing → abgelehnt.
        with self.assertRaises(TransferActionError):
            services.request_loan(listing, self.third)

    def test_zero_fee_listing_allowed_without_partner(self):
        # 0-€-Listing ist erlaubt — die Partnerprüfung greift erst bei der
        # konkreten Anfrage mit echtem Leihverein.
        listing = services.create_loan_listing(
            self.player, self.seller, fee_asking=Decimal('0'), until='SE')
        self.assertEqual(listing.fee_asking, Decimal('0.00'))
        # Anfrage ohne Partnerschaft → abgelehnt.
        with self.assertRaises(TransferActionError):
            services.request_loan(listing, self.buyer)
        # Mit Partnerschaft → erlaubt.
        ClubPartnership.objects.create(club_a=self.seller, club_b=self.buyer)
        deal = services.request_loan(listing, self.buyer)
        self.assertEqual(deal.typ, DealRequest.TYP_LOAN)

    def test_loan_listing_requires_ownership(self):
        with self.assertRaises(TransferActionError):
            services.create_loan_listing(
                self.player, self.buyer, fee_asking=Decimal('1000000'),
                until='SE')

    def test_accept_high_value_loan_fee(self):
        # 30-Mio-Leihgebühr bei 50-Mio-Budget: Reservierung darf bei der
        # Buchung nicht doppelt zählen.
        listing = services.create_loan_listing(
            self.player, self.seller, fee_asking=Decimal('30000000'),
            until='SE')
        deal = services.request_loan(listing, self.buyer)
        self.buyer.refresh_from_db()
        self.assertEqual(self.buyer.reserved, Decimal('30000000.00'))
        services.accept_deal(deal)
        self.buyer.refresh_from_db()
        self.seller.refresh_from_db()
        self.player.refresh_from_db()
        self.assertEqual(self.player.club_id, self.buyer.pk)
        self.assertEqual(self.player.loan_status, 'loaned_in')
        self.assertEqual(self.buyer.budget, Decimal('20000000.00'))
        self.assertEqual(self.buyer.reserved, Decimal('0.00'))
        self.assertEqual(self.seller.budget, Decimal('80000000.00'))
        loan = Loan.objects.get(player=self.player)
        self.assertTrue(loan.is_active)

    def test_loan_limits(self):
        for i in range(int(get_param('LEIHE_LIMIT_JE_PAAR', '0'))):
            p = _mk_player(self.seller, name=f'Leih Kandidat{i}')
            Loan.objects.create(
                player=p, owner_club=self.seller, loan_club=self.buyer,
                fee=Decimal('1000000'), until='SE')
        with self.assertRaises(TransferActionError):
            services._check_loan_limits(self.seller, self.buyer)


class WithdrawAndHammerTests(Base):
    def test_withdraw_only_without_bids(self):
        listing = services.create_listing(
            self.player, self.seller, min_bid=Decimal('1000000'),
            duration_days=3)
        services.place_bid(listing, self.buyer, Decimal('1000000'))
        with self.assertRaises(TransferActionError):
            services.withdraw_listing(listing)

    def test_hammer_settles_immediately(self):
        listing = services.create_listing(
            self.player, self.seller, min_bid=Decimal('1000000'),
            duration_days=7)
        services.place_bid(listing, self.buyer, Decimal('2000000'))
        services.hammer(listing)
        listing.refresh_from_db()
        self.player.refresh_from_db()
        self.assertEqual(listing.status, TransferListing.STATUS_SOLD)
        self.assertEqual(self.player.club_id, self.buyer.pk)


class FreeAgentTests(Base):
    def test_free_agent_listing_24h_after_first_bid(self):
        vereinslos = _mk_player(None, name='Frei Agent', mw='2000000')
        listing = services.create_listing(vereinslos, None, min_bid=None)
        self.assertIsNone(listing.ends_at)
        self.assertEqual(listing.min_bid, Decimal('2000000.00'))
        services.place_bid(listing, self.buyer, Decimal('2000000'))
        listing.refresh_from_db()
        self.assertIsNotNone(listing.ends_at)
        self.assertLess(
            listing.ends_at,
            timezone.now() + timedelta(hours=24, minutes=1))

    def test_free_agent_settlement_burns_money(self):
        vereinslos = _mk_player(None, name='Geld Senke', mw='2000000')
        listing = services.create_listing(vereinslos, None, min_bid=None)
        services.place_bid(listing, self.buyer, Decimal('2000000'))
        TransferListing.objects.filter(pk=listing.pk).update(
            ends_at=timezone.now() - timedelta(minutes=1))
        jobs.close_due_listings()
        vereinslos.refresh_from_db()
        self.buyer.refresh_from_db()
        self.assertEqual(vereinslos.club_id, self.buyer.pk)
        self.assertEqual(self.buyer.budget, Decimal('48000000.00'))
        # Kein Verein hat die 2 Mio erhalten (Systemsenke).
        self.assertFalse(FinanceTransaction.objects.filter(
            typ='TRANSFER_EIN').exists())
