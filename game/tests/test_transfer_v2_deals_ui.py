"""Tests Transfersystem v2 — Kader anbieten, Meine Deals, Deal-Builder (Task #821).

Deckt ab: Auth/Rendering aller drei Seiten, Statusboard (Ownership),
Listing-Erstellung vom Board, Forum-Post, Anfragen erhalten/gesendet inkl.
Annehmen/Ablehnen/Zurückziehen mit Autorisierung, Escrow-Reservierung/-Freigabe,
Max-5-Paket-Validierung, Builder-Ziel-Spieler-Endpunkt und Preisfindung.
"""
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from game.models import (
    Club, EconomyParameter, GameSeasonState, League, Player, SquadOffer,
    WatchlistEntry,
)
from game.transfer_v2 import escrow, services
from game.transfer_v2.models import (
    DealRequest, TransferListing, TransferRecord, TransferRecordPlayer,
)


def _mk_club(name, budget='50000000.00', league=None):
    if league is None:
        league, _ = League.objects.get_or_create(
            name='TV2-Deals-Testliga', country='Deutschland')
    return Club.objects.create(
        name=name, short_name=name[:3].upper(), founded_year=1900,
        budget=Decimal(budget), league=league,
    )


def _mk_player(club, name='Trans Ferfix', age=25, mw='5000000', hp='ST'):
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
        self.mine = _mk_club('FC Eigen')
        self.other = _mk_club('FC Fremd')
        self.p1 = _mk_player(self.mine, 'Eigen Erster')
        self.p2 = _mk_player(self.mine, 'Eigen Zwei', age=19)
        self.f1 = _mk_player(self.other, 'Fremd Erster')
        self.user = User.objects.create_user('m1', password='x')
        self.mine.managed_by = self.user.manager_profile
        self.mine.save(update_fields=['managed_by'])
        self.user2 = User.objects.create_user('m2', password='x')
        self.other.managed_by = self.user2.manager_profile
        self.other.save(update_fields=['managed_by'])

    def login(self, user=None):
        self.client.force_login(user or self.user)


class OfferBoardTests(Base):
    def test_anonymous_redirects(self):
        resp = self.client.get(reverse('transfer_offer_board'))
        self.assertEqual(resp.status_code, 302)

    def test_renders_profis_and_u21_segments(self):
        self.login()
        resp = self.client.get(reverse('transfer_offer_board'))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertIn('Eigen Erster', html)
        self.assertNotIn('Eigen Zwei', html)  # U21 nicht im Profis-Segment
        resp = self.client.get(reverse('transfer_offer_board') + '?seg=u21')
        html = resp.content.decode()
        self.assertIn('Eigen Zwei', html)
        self.assertNotIn('Eigen Erster', html)

    def test_status_chip_persists(self):
        self.login()
        resp = self.client.post(reverse('transfer_offer_status'), {
            'player_id': self.p1.pk, 'status': 'SWAP_CASH', 'seg': 'profis',
        })
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(
            SquadOffer.objects.get(player=self.p1).status, 'SWAP_CASH')

    def test_status_requires_ownership(self):
        self.login()
        self.client.post(reverse('transfer_offer_status'), {
            'player_id': self.f1.pk, 'status': 'CASH',
        })
        self.assertFalse(SquadOffer.objects.filter(player=self.f1).exists())

    def test_create_listing_from_board(self):
        self.login()
        resp = self.client.post(reverse('transfer_offer_create_listing'), {
            'player_id': self.p1.pk, 'min_bid': '2.000.000',
            'buy_now': '', 'timing': 'SOFORT', 'duration': '3',
        })
        self.assertEqual(resp.status_code, 302)
        listing = TransferListing.objects.get(player=self.p1)
        self.assertEqual(listing.min_bid, Decimal('2000000'))
        self.assertEqual(listing.status, TransferListing.STATUS_ACTIVE)

    def test_create_listing_foreign_player_blocked(self):
        self.login()
        self.client.post(reverse('transfer_offer_create_listing'), {
            'player_id': self.f1.pk, 'min_bid': '2.000.000',
            'timing': 'SOFORT', 'duration': '3',
        })
        self.assertFalse(
            TransferListing.objects.filter(player=self.f1).exists())

    def test_watchers_visible(self):
        WatchlistEntry.objects.create(
            manager=self.user2.manager_profile, player=self.p1)
        self.login()
        html = self.client.get(reverse('transfer_offer_board')).content.decode()
        self.assertIn('FC Fremd', html)

    def test_forum_post_lists_non_uvk(self):
        services.set_squad_offer_status(self.p1, self.mine, 'CASH')
        self.login()
        resp = self.client.get(reverse('transfer_offer_forum'))
        data = resp.json()
        self.assertIn('Eigen Erster', data['text'])
        self.assertIn('[b]', data['text'])

    def test_forum_post_empty_when_all_uvk(self):
        self.login()
        self.assertEqual(
            self.client.get(reverse('transfer_offer_forum')).json()['text'], '')


class PriceGuidanceTests(Base):
    def _record(self, price, hp='ST'):
        p = _mk_player(self.other, f'Ref Nr{TransferRecord.objects.count()}',
                       hp=hp)
        rec = TransferRecord.objects.create(
            kind=TransferRecord.KIND_CASH, club_a=self.other, club_b=self.mine,
            cash_b=Decimal(str(price)))
        TransferRecordPlayer.objects.create(
            record=rec, player=p, side='A',
            market_value_at_transfer=Decimal(str(price)))
        return rec

    def test_hidden_below_three_comparables(self):
        self._record(4000000)
        self._record(5000000)
        self.assertFalse(services.price_guidance(self.p1)['show'])

    def test_shown_with_three_comparables(self):
        for pr in (4000000, 5000000, 6000000):
            self._record(pr)
        g = services.price_guidance(self.p1)
        self.assertTrue(g['show'])
        self.assertLessEqual(g['lo'], g['hi'])
        self.assertEqual(len(g['refs']), 3)

    def test_other_position_not_comparable(self):
        for pr in (4000000, 5000000, 6000000):
            self._record(pr, hp='TW')
        self.assertFalse(services.price_guidance(self.p1)['show'])


class MyDealsTests(Base):
    def _deal(self):
        return services.create_deal_request(
            self.other, self.mine, typ=DealRequest.TYP_CASH,
            cash_from=Decimal('3000000'), from_players=[],
            to_players=[self.p1])

    def test_renders_all_segments(self):
        self.login()
        for seg in ('gebote', 'erhalten', 'gesendet', 'optionen', 'leihen'):
            resp = self.client.get(reverse('transfer_my_deals') + f'?seg={seg}')
            self.assertEqual(resp.status_code, 200)

    def test_received_request_shown_with_badge(self):
        self._deal()
        self.login()
        html = self.client.get(
            reverse('transfer_my_deals') + '?seg=erhalten').content.decode()
        self.assertIn('Von FC Fremd', html)
        self.assertIn('Annehmen', html)

    def test_accept_executes_and_reserves_release(self):
        deal = self._deal()
        self.assertGreater(escrow._v2_reserved_total(self.other), 0)
        self.login()
        resp = self.client.post(reverse('transfer_deal_accept'),
                                {'deal_id': deal.pk})
        self.assertEqual(resp.status_code, 302)
        deal.refresh_from_db()
        self.p1.refresh_from_db()
        self.assertEqual(deal.status, DealRequest.STATUS_ACCEPTED)
        self.assertEqual(self.p1.club_id, self.other.pk)
        self.assertEqual(escrow._v2_reserved_total(self.other), 0)

    def test_accept_requires_recipient(self):
        deal = self._deal()
        self.login(self.user2)  # Initiator darf NICHT annehmen
        self.client.post(reverse('transfer_deal_accept'), {'deal_id': deal.pk})
        deal.refresh_from_db()
        self.assertEqual(deal.status, DealRequest.STATUS_OPEN)

    def test_decline_releases_escrow(self):
        deal = self._deal()
        self.login()
        self.client.post(reverse('transfer_deal_decline'), {'deal_id': deal.pk})
        deal.refresh_from_db()
        self.assertEqual(deal.status, DealRequest.STATUS_DECLINED)
        self.assertEqual(escrow._v2_reserved_total(self.other), 0)

    def test_withdraw_only_initiator(self):
        deal = self._deal()
        self.login()  # Empfänger darf nicht zurückziehen
        self.client.post(reverse('transfer_deal_withdraw'), {'deal_id': deal.pk})
        deal.refresh_from_db()
        self.assertEqual(deal.status, DealRequest.STATUS_OPEN)
        self.login(self.user2)
        self.client.post(reverse('transfer_deal_withdraw'), {'deal_id': deal.pk})
        deal.refresh_from_db()
        self.assertEqual(deal.status, DealRequest.STATUS_WITHDRAWN)
        self.assertEqual(escrow._v2_reserved_total(self.other), 0)


class BuilderTests(Base):
    def test_renders_with_cascade_data(self):
        self.login()
        resp = self.client.get(reverse('transfer_deal_builder'))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertIn('tv2-countries-data', html)
        self.assertIn('Eigen Erster', html)

    def test_target_players_endpoint(self):
        self.login()
        resp = self.client.get(
            reverse('transfer_builder_target_players'),
            {'club_id': self.other.pk})
        names = [p['name'] for p in resp.json()['players']]
        self.assertIn('Fremd Erster', names)

    def test_send_creates_request_and_reserves(self):
        self.login()
        resp = self.client.post(reverse('transfer_builder_send'), {
            'to_club_id': self.other.pk,
            'from_players': '', 'to_players': str(self.f1.pk),
            'cash_from': '2.500.000', 'cash_to': '',
            'timing': 'SOFORT', 'message': 'Testanfrage',
        })
        self.assertEqual(resp.status_code, 302)
        deal = DealRequest.objects.get(from_club=self.mine)
        self.assertEqual(deal.typ, DealRequest.TYP_CASH)
        self.assertEqual(deal.cash_from, Decimal('2500000.00'))
        self.assertEqual(escrow._v2_reserved_total(self.mine),
                         Decimal('2500000.00'))

    def test_send_swap_without_cash(self):
        self.login()
        self.client.post(reverse('transfer_builder_send'), {
            'to_club_id': self.other.pk,
            'from_players': str(self.p1.pk), 'to_players': str(self.f1.pk),
            'cash_from': '', 'cash_to': '', 'timing': 'WP',
        })
        deal = DealRequest.objects.get(from_club=self.mine)
        self.assertEqual(deal.typ, DealRequest.TYP_SWAP)
        self.assertEqual(deal.timing, 'WP')

    def test_send_max_five_per_side(self):
        extra = [
            _mk_player(self.mine, f'Paket Nr{i}') for i in range(6)
        ]
        self.login()
        self.client.post(reverse('transfer_builder_send'), {
            'to_club_id': self.other.pk,
            'from_players': ','.join(str(p.pk) for p in extra),
            'to_players': str(self.f1.pk),
            'cash_from': '', 'cash_to': '', 'timing': 'SOFORT',
        })
        self.assertFalse(
            DealRequest.objects.filter(from_club=self.mine).exists())

    def test_send_foreign_player_mismatch_blocked(self):
        self.login()
        self.client.post(reverse('transfer_builder_send'), {
            'to_club_id': self.other.pk,
            'from_players': str(self.f1.pk),  # gehört NICHT mir
            'to_players': str(self.p1.pk),
            'cash_from': '', 'cash_to': '', 'timing': 'SOFORT',
        })
        self.assertFalse(
            DealRequest.objects.filter(from_club=self.mine).exists())


class TabsTests(Base):
    def test_tabs_link_active(self):
        self.login()
        html = self.client.get(reverse('transfer_market')).content.decode()
        self.assertIn(reverse('transfer_my_deals'), html)
        self.assertIn(reverse('transfer_offer_board'), html)


class SellDirectionTests(Base):
    """Verkauf: eigene Spieler gegen Geld des Empfängers (cash_to)."""

    def _sell_deal(self):
        return services.create_deal_request(
            self.mine, self.other, typ=DealRequest.TYP_CASH,
            cash_to=Decimal('4000000'), from_players=[self.p1],
            to_players=[])

    def test_service_accepts_sell_schema(self):
        deal = self._sell_deal()
        self.assertEqual(deal.typ, DealRequest.TYP_CASH)
        self.assertEqual(deal.cash_to, Decimal('4000000.00'))
        # Verkäufer reserviert NICHTS (kein eigener Geldanteil).
        self.assertEqual(escrow._v2_reserved_total(self.mine), 0)

    def test_service_rejects_sell_without_recipient_cash(self):
        with self.assertRaises(services.TransferActionError):
            services.create_deal_request(
                self.mine, self.other, typ=DealRequest.TYP_CASH,
                from_players=[self.p1], to_players=[])

    def test_service_rejects_cash_on_both_sides(self):
        with self.assertRaises(services.TransferActionError):
            services.create_deal_request(
                self.mine, self.other, typ=DealRequest.TYP_CASH,
                cash_from=Decimal('1000000'), cash_to=Decimal('2000000'),
                from_players=[self.p1], to_players=[])

    def test_builder_send_sell_direction(self):
        self.login()
        resp = self.client.post(reverse('transfer_builder_send'), {
            'to_club_id': self.other.pk,
            'from_players': str(self.p1.pk), 'to_players': '',
            'cash_from': '', 'cash_to': '4.000.000',
            'timing': 'SOFORT', 'message': 'Kaufst du ihn?',
        })
        self.assertEqual(resp.status_code, 302)
        deal = DealRequest.objects.get(from_club=self.mine)
        self.assertEqual(deal.typ, DealRequest.TYP_CASH)
        self.assertEqual(deal.cash_to, Decimal('4000000.00'))

    def test_accept_sell_moves_player_and_money(self):
        deal = self._sell_deal()
        mine_before = self.mine.budget
        other_before = self.other.budget
        self.login(self.user2)  # Empfänger (Käufer) nimmt an
        resp = self.client.post(reverse('transfer_deal_accept'),
                                {'deal_id': deal.pk})
        self.assertEqual(resp.status_code, 302)
        deal.refresh_from_db()
        self.p1.refresh_from_db()
        self.mine.refresh_from_db()
        self.other.refresh_from_db()
        self.assertEqual(deal.status, DealRequest.STATUS_ACCEPTED)
        self.assertEqual(self.p1.club_id, self.other.pk)
        self.assertEqual(self.mine.budget - mine_before,
                         Decimal('4000000.00'))
        self.assertEqual(other_before - self.other.budget,
                         Decimal('4000000.00'))

    def test_accept_sell_fails_without_recipient_funds(self):
        poor = _mk_club('FC Pleite', budget='100000.00')
        u3 = User.objects.create_user('m3', password='x')
        poor.managed_by = u3.manager_profile
        poor.save(update_fields=['managed_by'])
        deal = services.create_deal_request(
            self.mine, poor, typ=DealRequest.TYP_CASH,
            cash_to=Decimal('4000000'), from_players=[self.p1],
            to_players=[])
        self.login(u3)
        self.client.post(reverse('transfer_deal_accept'), {'deal_id': deal.pk})
        deal.refresh_from_db()
        self.p1.refresh_from_db()
        self.assertEqual(deal.status, DealRequest.STATUS_OPEN)
        self.assertEqual(self.p1.club_id, self.mine.pk)
