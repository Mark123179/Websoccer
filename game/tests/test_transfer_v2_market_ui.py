"""Tests Transfersystem v2 — Reiter Transfermarkt (Task #820).

Deckt ab: Auth/Rendering, Headliner-Auswahl, Filter-Daten, Gebotsverlauf,
Pinnen, Gerüchte-Reaktion (einmalig, nur betroffener Verein), Gebots- und
Sofortkauf-Endpunkte inkl. Ownership-Regeln.
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from game import views_transfer_v2 as views_tv2
from game.models import Club, EconomyParameter, GameSeasonState, League, Player
from game.transfer_v2 import services
from game.transfer_v2.models import ListingPin, RumorNews, TransferListing


def _mk_club(name, budget='50000000.00', league=None):
    if league is None:
        league, _ = League.objects.get_or_create(
            name='TV2-UI-Testliga', country='Deutschland')
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
        EconomyParameter.objects.update_or_create(
            saison='0', key='KADER_MIN', defaults={'value': 0})
        self.seller = _mk_club('FC Verkauf')
        self.buyer = _mk_club('FC Kauf')
        self.player = _mk_player(self.seller)
        # Manager-User → buyer (Signal legt das Profil automatisch an).
        self.user = User.objects.create_user('manager1', password='x')
        self.buyer.managed_by = self.user.manager_profile
        self.buyer.save(update_fields=['managed_by'])

    def login(self):
        self.client.force_login(self.user)

    def listing(self, **kw):
        kw.setdefault('min_bid', Decimal('1000000'))
        kw.setdefault('duration_days', 3)
        return services.create_listing(self.player, self.seller, **kw)


class AuthAndRenderTests(Base):
    def test_anonymous_redirects_to_login(self):
        resp = self.client.get(reverse('transfer_market'))
        self.assertEqual(resp.status_code, 302)

    def test_clubless_manager_redirects(self):
        u = User.objects.create_user('ohneclub', password='x')
        self.client.force_login(u)
        resp = self.client.get(reverse('transfer_market'))
        self.assertEqual(resp.status_code, 302)
        self.assertIn('management', resp['Location'])

    def test_renders_shell_and_listing(self):
        self.listing()
        self.login()
        resp = self.client.get(reverse('transfer_market'))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        # 7-Tab-Shell
        for tab in ['Transfermarkt', 'Leihmarkt', 'Meine Deals',
                    'Kader anbieten', 'Historie', 'Scouting',
                    'Beobachtungsliste']:
            self.assertIn(tab, html)
        # Budget-Kopf mit deutscher Formatierung
        self.assertIn('Kontostand', html)
        self.assertIn('50.000.000 €', html)
        # Listing-Zeile
        self.assertIn('Trans Ferfix', html)
        self.assertIn('1.000.000 €', html)
        # Kein horizontales Chaos: Marktwert-Link auf Transfermarkt
        self.assertIn('transfermarkt.de/schnellsuche', html)

    def test_headliners_are_three_soonest(self):
        now = timezone.now()
        listings = []
        for i, h in enumerate([5, 1, 9, 3]):
            p = _mk_player(self.seller, name=f'Head Liner{i}')
            l = services.create_listing(
                p, self.seller, min_bid=Decimal('1000000'), duration_days=3)
            TransferListing.objects.filter(pk=l.pk).update(
                ends_at=now + timedelta(hours=h))
            listings.append((h, p.full_name))
        self.login()
        resp = self.client.get(reverse('transfer_market'))
        heads = resp.context['headliners']
        self.assertEqual(len(heads), 3)
        expected = [n for h, n in sorted(listings)][:3]
        self.assertEqual([h['name'] for h in heads], expected)

    def test_bid_history_rendered(self):
        l = self.listing()
        services.place_bid(l, self.buyer, Decimal('1000000'))
        self.login()
        resp = self.client.get(reverse('transfer_market'))
        html = resp.content.decode()
        self.assertIn('Gebotsverlauf', html)
        self.assertIn('FC Kauf', html)
        self.assertIn('Du führst!', html)

    def test_table_row_offers_buy_now_for_regular_listing(self):
        # Sofortkauf muss auch aus der normalen Tabelle heraus möglich sein
        # (nicht nur über die Headliner-Karten).
        l = self.listing(buy_now=Decimal('2000000'))
        self.login()
        html = self.client.get(reverse('transfer_market')).content.decode()
        import re
        rows = re.findall(r'data-listing[\s\S]*?tv2-bids-panel', html)
        self.assertTrue(rows, 'Keine Tabellenzeile gefunden')
        self.assertIn(f'data-sheet-open="{l.pk}" data-buy="1"', rows[0])

    def test_table_row_hides_buy_now_without_option(self):
        self.listing()  # kein buy_now
        self.login()
        html = self.client.get(reverse('transfer_market')).content.decode()
        import re
        rows = re.findall(r'data-listing[\s\S]*?tv2-bids-panel', html)
        self.assertTrue(rows)
        self.assertNotIn('data-buy="1"', rows[0])

    def test_free_agent_listing_renders(self):
        fa = _mk_player(None, name='Frei Agent', mw='2800000')
        services.create_listing(fa, None, min_bid=Decimal('1'))
        self.login()
        html = self.client.get(reverse('transfer_market')).content.decode()
        self.assertIn('Frei Agent', html)
        self.assertIn('Vereinslos', html)
        self.assertIn('24h ab 1. Gebot', html)
        self.assertIn('data-scope="frei"', html)

    def test_filter_data_attributes(self):
        self.listing(timing='WP')
        self.login()
        html = self.client.get(reverse('transfer_market')).content.decode()
        self.assertIn('data-timing="WP"', html)
        self.assertIn('data-scope="verein"', html)
        self.assertIn('data-hp="ST"', html)


class LevyPreviewTests(Base):
    """Deal-Sheet-Vorschau muss die konfigurierten Abgabe-Parameter nutzen
    (Single Source of Truth = calc_youth_levy), nicht hartkodierte Werte."""

    def _train(self, player, club, seasons):
        from game.models import PlayerClubHistory
        for s in seasons:
            PlayerClubHistory.objects.get_or_create(
                player=player, club=club, season=s)

    def test_sheet_uses_configured_levy_params(self):
        # Nicht-Default-Parameter: 10 % Gesamtabgabe, 75.000 € Minimum.
        EconomyParameter.objects.update_or_create(
            saison='0', key='JUGENDABGABE_PCT', defaults={'value': 0.10})
        EconomyParameter.objects.update_or_create(
            saison='0', key='JUGENDABGABE_MIN_JE_VEREIN',
            defaults={'value': 75000})
        ausbilder = _mk_club('FC Ausbildung')
        young = _mk_player(self.seller, name='Jung Talent', age=20)
        # Alter 20, Saison 0 → Cutoff 1: Stationen bis Saison 1 zählen.
        self._train(young, ausbilder, [0, 1])    # 2 Fremd-Stationen
        self._train(young, self.seller, [0, 1])  # 2 Eigenanteile (frei)
        services.create_listing(
            young, self.seller, min_bid=Decimal('1000000'), duration_days=3)
        self.login()
        resp = self.client.get(reverse('transfer_market'))
        sheet = next(s for s in resp.context['sheets_json']
                     if s['name'] == 'Jung Talent')
        # Konfiguriertes Minimum landet im Sheet (kein hartkodiertes 50k).
        self.assertEqual(sheet['levyMin'], 75000.0)
        self.assertEqual(sheet['levyPctLabel'], '10 %')
        # Anteil = calc_youth_levy: 10 % × (2 von 4 Stationen) = 5 %.
        self.assertEqual(len(sheet['levy']), 1)
        self.assertEqual(sheet['levy'][0]['club'], 'FC Ausbildung')
        self.assertAlmostEqual(sheet['levy'][0]['pct_raw'], 0.05, places=6)
        # Kontrolle gegen die Buchungsquelle bei realer Summe.
        from game.transfer_v2.youth_levy import calc_youth_levy
        res = calc_youth_levy(young, Decimal('10000000'),
                              zahler_club=self.seller)
        expected = max(
            Decimal('10000000') * Decimal('0.05'), Decimal('75000'))
        self.assertEqual(res['summe'], expected)

    def test_eigengewaechs_has_no_levy_rows(self):
        young = _mk_player(self.seller, name='Eigen Zoegling', age=20)
        self._train(young, self.seller, [0, 1])
        services.create_listing(
            young, self.seller, min_bid=Decimal('1000000'), duration_days=3)
        self.login()
        resp = self.client.get(reverse('transfer_market'))
        sheet = next(s for s in resp.context['sheets_json']
                     if s['name'] == 'Eigen Zoegling')
        self.assertEqual(sheet['levy'], [])


class PinTests(Base):
    def test_pin_and_unpin(self):
        l = self.listing()
        self.login()
        url = reverse('transfer_market_pin')
        self.client.post(url, {'listing_id': l.pk})
        self.assertTrue(
            ListingPin.objects.filter(listing=l, club=self.buyer).exists())
        # Gepinnt-Sektion erscheint
        html = self.client.get(reverse('transfer_market')).content.decode()
        self.assertIn('Gepinnt', html)
        # Toggle entfernt den Pin
        self.client.post(url, {'listing_id': l.pk})
        self.assertFalse(
            ListingPin.objects.filter(listing=l, club=self.buyer).exists())

    def test_pin_requires_login(self):
        l = self.listing()
        resp = self.client.post(
            reverse('transfer_market_pin'), {'listing_id': l.pk})
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(ListingPin.objects.filter(listing=l).exists())


class BidEndpointTests(Base):
    def test_place_bid_success(self):
        l = self.listing()
        self.login()
        resp = self.client.post(reverse('transfer_market_bid'), {
            'listing_id': l.pk, 'amount': '1.200.000'})
        self.assertRedirects(resp, reverse('transfer_market'))
        l.refresh_from_db()
        bid = l.bids.get(is_leading=True)
        self.assertEqual(bid.club, self.buyer)
        self.assertEqual(bid.amount, Decimal('1200000'))

    def test_bid_below_minimum_rejected(self):
        l = self.listing()
        self.login()
        resp = self.client.post(reverse('transfer_market_bid'), {
            'listing_id': l.pk, 'amount': '900000'}, follow=True)
        self.assertEqual(l.bids.count(), 0)
        msgs = [str(m) for m in resp.context['messages']]
        self.assertTrue(any('mindestens' in m.lower() or 'gebot' in m.lower()
                            for m in msgs))

    def test_own_listing_bid_rejected(self):
        # Käufer-Manager verkauft selbst → Gebot auf eigenes Listing verboten.
        p2 = _mk_player(self.buyer, name='Eigen Gewaechs')
        l = services.create_listing(
            p2, self.buyer, min_bid=Decimal('1000000'), duration_days=3)
        self.login()
        self.client.post(reverse('transfer_market_bid'), {
            'listing_id': l.pk, 'amount': '1000000'})
        self.assertEqual(l.bids.count(), 0)

    def test_garbage_amount_rejected(self):
        l = self.listing()
        self.login()
        self.client.post(reverse('transfer_market_bid'), {
            'listing_id': l.pk, 'amount': 'abc'})
        self.assertEqual(l.bids.count(), 0)


class BuyNowEndpointTests(Base):
    def test_buy_now_transfers_player(self):
        l = self.listing(buy_now=Decimal('2000000'))
        self.login()
        resp = self.client.post(reverse('transfer_market_buy_now'), {
            'listing_id': l.pk})
        self.assertRedirects(resp, reverse('transfer_market'))
        l.refresh_from_db()
        self.player.refresh_from_db()
        self.assertEqual(l.status, TransferListing.STATUS_SOLD)
        self.assertEqual(self.player.club, self.buyer)

    def test_buy_now_without_option_rejected(self):
        l = self.listing()  # kein buy_now
        self.login()
        self.client.post(reverse('transfer_market_buy_now'), {
            'listing_id': l.pk})
        l.refresh_from_db()
        self.assertEqual(l.status, TransferListing.STATUS_ACTIVE)


class RumorReactionTests(Base):
    def _rumor(self, club=None):
        return RumorNews.objects.create(
            event_type=RumorNews.EVENT_BID_PLACED,
            player=self.player,
            affected_club=club if club is not None else self.buyer,
            outlet='SPORTECHO',
            headline='FC Kauf soll an Trans Ferfix dran sein.',
        )

    def test_react_once(self):
        r = self._rumor()
        self.login()
        self.client.post(reverse('transfer_rumor_react'), {
            'rumor_id': r.pk, 'reaction': 'denied'})
        r.refresh_from_db()
        self.assertEqual(r.reaction, RumorNews.REACTION_DENIED)
        self.assertIsNotNone(r.reaction_at)
        # Zweite Reaktion bleibt wirkungslos.
        self.client.post(reverse('transfer_rumor_react'), {
            'rumor_id': r.pk, 'reaction': 'confirmed'})
        r.refresh_from_db()
        self.assertEqual(r.reaction, RumorNews.REACTION_DENIED)

    def test_foreign_club_cannot_react(self):
        r = self._rumor(club=self.seller)
        self.login()
        self.client.post(reverse('transfer_rumor_react'), {
            'rumor_id': r.pk, 'reaction': 'confirmed'})
        r.refresh_from_db()
        self.assertEqual(r.reaction, '')

    def test_react_buttons_only_for_affected_club(self):
        self._rumor(club=self.seller)
        self.login()
        html = self.client.get(reverse('transfer_market')).content.decode()
        self.assertIn('Transfergerücht', html)
        self.assertNotIn('Dementieren', html)

    def test_concurrent_reactions_cannot_overwrite_first(self):
        """Race-Regression: Zwei 'gleichzeitige' Requests bestehen beide den
        Python-Check (leere Reaktion beim Lesen) — der atomare
        Compare-and-Set in der DB darf trotzdem nur den ersten gewinnen
        lassen."""
        from unittest.mock import patch
        r = self._rumor()
        self.login()

        real_get = views_tv2.get_object_or_404

        def stale_get(klass, **kw):
            obj = real_get(klass, **kw)
            # Simuliert den verlorenen Wettlauf: NACH dem Lesen (Reaktion
            # noch leer) persistiert ein paralleler Request seine Reaktion.
            RumorNews.objects.filter(pk=obj.pk, reaction='').update(
                reaction=RumorNews.REACTION_DENIED,
                reaction_at=timezone.now())
            return obj  # In-Memory-Objekt sieht weiterhin reaction=''

        with patch.object(views_tv2, 'get_object_or_404', stale_get):
            self.client.post(reverse('transfer_rumor_react'), {
                'rumor_id': r.pk, 'reaction': 'confirmed'})

        r.refresh_from_db()
        # Die zuerst persistierte Reaktion bleibt bestehen.
        self.assertEqual(r.reaction, RumorNews.REACTION_DENIED)

    def test_invalid_reaction_value(self):
        r = self._rumor()
        self.login()
        self.client.post(reverse('transfer_rumor_react'), {
            'rumor_id': r.pk, 'reaction': 'hackz'})
        r.refresh_from_db()
        self.assertEqual(r.reaction, '')
