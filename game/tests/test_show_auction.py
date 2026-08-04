"""Tests Show-Auktion (Task #814) — Validator, Raum, Gebotspfade, Settlement.

Deckt die kritischen Pfade der Spec ab: Validator-Querregeln, Escrow-
Reservierungen je Freigabemodus, Coin-Eintrittsticket (einmalig, kein
Refund), Haltezeit-Treppe, Deadline-Verlängerung (Blitz), Holländisch
(Sofort-Buchung), Bereichs-Auktion (verborgenes Ziel), Gleichstand → Los,
Settlement-Idempotenz, Platzen (pool_status-Restaurierung) und die
Raum-Ausblendung in Suche/Creator-Liste.
"""

from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from game.economy import reservations
from game.models import (
    Club,
    FinanceReservation,
    FinanceTransaction,
    HoenessCoin,
    League,
    ManagerProfile,
    Player,
)
from showauction import service
from showauction.models import ShowAuction, ShowAuctionPreset
from showauction.service import AuctionError
from showauction.validator import validate_config


def _preset(slug):
    return ShowAuctionPreset.objects.get(slug=slug)


def _clubless_player(last='Auktionsware', mw='10000000'):
    return Player.objects.create(
        first_name='Show', last_name=last, age=24,
        position='Sturm', main_position_1='ST',
        market_value=Decimal(mw), pool_status=Player.POOL_STATUS_NONE,
    )


NO_CONDS = {'teilnahmebedingungen': []}


class ShowAuctionBase(TestCase):
    def setUp(self):
        self.now = timezone.now()
        self.league = League.objects.create(name='Testliga', country='Deutschland')
        self.club_a = Club.objects.create(
            name='FC Alpha', short_name='ALP', founded_year=1900,
            budget=Decimal('100000000.00'), league=self.league,
        )
        self.club_b = Club.objects.create(
            name='FC Beta', short_name='BET', founded_year=1901,
            budget=Decimal('100000000.00'), league=self.league,
        )
        self.mgr_a = ManagerProfile.objects.create(name='Manager A')
        self.mgr_b = ManagerProfile.objects.create(name='Manager B')
        self.player = _clubless_player()

    def _running(self, slug, overrides=None, now=None):
        a = service.create_auction(
            player=self.player, preset=_preset(slug),
            config_overrides=overrides,
        )
        service.start_auction_now(a, now=now or self.now)
        a.refresh_from_db()
        return a

    def _active_res(self, club):
        return FinanceReservation.objects.filter(
            club=club, status=FinanceReservation.STATUS_ACTIVE,
            zweck='showauction',
        )


class ValidatorTests(TestCase):
    def test_seed_presets_valide(self):
        for p in ShowAuctionPreset.objects.all():
            normalisiert = validate_config(p.config)  # wirft bei Fehlern
            self.assertIsInstance(normalisiert, dict,
                                  f'Preset {p.slug} muss valide sein')
        self.assertEqual(ShowAuctionPreset.objects.count(), 5)

    def test_fallend_ohne_preisverfall_abgelehnt(self):
        cfg = dict(_preset('hollaendisch').config)
        cfg['preisverfall'] = 'aus'
        with self.assertRaises(ValidationError):
            validate_config(cfg)

    def test_unbekannter_schluessel_abgelehnt(self):
        cfg = dict(_preset('halte').config)
        cfg['quatsch_achse'] = 1
        with self.assertRaises(ValidationError):
            validate_config(cfg)

    def test_haltezeit_ohne_verlauf_abgelehnt(self):
        cfg = dict(_preset('halte').config)
        cfg.pop('haltezeit_verlauf', None)
        with self.assertRaises(ValidationError):
            validate_config(cfg)


class RaumTests(ShowAuctionBase):
    def test_create_setzt_raum_und_cancel_restauriert(self):
        self.player.pool_status = Player.POOL_STATUS_SCOUTABLE
        self.player.save(update_fields=['pool_status'])
        a = service.create_auction(player=self.player, preset=_preset('halte'))
        self.player.refresh_from_db()
        self.assertEqual(self.player.pool_status, Player.POOL_STATUS_SHOW_AUCTION)
        self.assertEqual(a.player_prev_pool_status, Player.POOL_STATUS_SCOUTABLE)

        service.cancel_auction(a)
        self.player.refresh_from_db()
        self.assertEqual(self.player.pool_status, Player.POOL_STATUS_SCOUTABLE)

    def test_suche_blendet_raum_aus(self):
        from game.views_scouting import _search_players
        a = service.create_auction(player=self.player, preset=_preset('halte'))
        search = {'q': self.player.last_name, 'pos': '', 'sort': 'mw', 'land': ''}
        results = _search_players(search, set())
        ids = {r['id'] for r in results} if results and isinstance(results[0], dict) else {
            getattr(r, 'id', getattr(r, 'pk', None)) for r in results
        }
        self.assertNotIn(self.player.pk, ids)
        service.cancel_auction(a)

    def test_doppelte_auktion_fuer_spieler_blockiert(self):
        service.create_auction(player=self.player, preset=_preset('halte'))
        with self.assertRaises(AuctionError):
            service.create_auction(player=self.player, preset=_preset('blitz'))

    def test_conditions_override_wird_validiert(self):
        with self.assertRaises(ValidationError):
            service.create_auction(
                player=self.player, preset=_preset('halte'),
                conditions=[{'art': 'quatsch_bedingung'}],
            )
        # Gültige Overrides landen im Snapshot UND in auction.conditions.
        a = service.create_auction(
            player=self.player, preset=_preset('halte'),
            conditions=[{'art': 'coins', 'anzahl': 2}],
        )
        self.assertEqual(a.conditions, [{'art': 'coins', 'anzahl': 2}])
        self.assertEqual(
            a.config_snapshot['teilnahmebedingungen'],
            [{'art': 'coins', 'anzahl': 2}],
        )


class HalteAuktionTests(ShowAuctionBase):
    """Aufsteigend + Haltezeit-Treppe + Freigabe bei Überbietung + Coin."""

    def test_coin_ticket_einmalig_und_pflicht(self):
        a = self._running('halte')
        # Ohne Coin: Teilnahme verweigert.
        with self.assertRaises(AuctionError):
            service.place_bid(a.pk, self.club_a, self.mgr_a,
                              Decimal('6000000'), now=self.now)
        HoenessCoin.objects.create(manager=self.mgr_a, amount=2)
        service.place_bid(a.pk, self.club_a, self.mgr_a,
                          Decimal('6000000'), now=self.now)
        coin = HoenessCoin.objects.get(manager=self.mgr_a)
        self.assertEqual(coin.amount, 1, 'Ticket kostet genau 1 Coin')
        # Zweites Gebot desselben Managers: KEIN zweites Ticket.
        service.place_bid(a.pk, self.club_a, self.mgr_a,
                          Decimal('12000000'), now=self.now)
        coin.refresh_from_db()
        self.assertEqual(coin.amount, 1)

    def test_haltezeit_treppe_und_ueberbietung_gibt_frei(self):
        a = self._running('halte', overrides=NO_CONDS)
        service.place_bid(a.pk, self.club_a, self.mgr_a,
                          Decimal('6000000'), now=self.now)
        a.refresh_from_db()
        self.assertIsNotNone(a.ends_at)
        # 1 Gebot → erste Treppenstufe 24h.
        self.assertAlmostEqual(
            (a.ends_at - self.now).total_seconds(), 24 * 3600, delta=5)
        self.assertEqual(self._active_res(self.club_a).count(), 1)

        # Überbietung: Mindesterhöhung max(100k, 5%) auf 6 Mio → 300k, gerundet.
        with self.assertRaises(AuctionError):
            service.place_bid(a.pk, self.club_b, self.mgr_b,
                              Decimal('6100000'), now=self.now)
        service.place_bid(a.pk, self.club_b, self.mgr_b,
                          Decimal('6300000'), now=self.now)
        # Freigabemodus bei_ueberbietung: Alpha-Reservierung weg, Beta aktiv.
        self.assertEqual(self._active_res(self.club_a).count(), 0)
        self.assertEqual(self._active_res(self.club_b).count(), 1)
        a.refresh_from_db()
        # 2 Gebote → zweite Stufe 12h.
        self.assertAlmostEqual(
            (a.ends_at - self.now).total_seconds(), 12 * 3600, delta=5)

    def test_settlement_idempotent_und_wechselsperre(self):
        a = self._running('halte', overrides=NO_CONDS)
        service.place_bid(a.pk, self.club_a, self.mgr_a,
                          Decimal('6000000'), now=self.now)
        later = self.now + timedelta(hours=25)
        stats = service.resolve_due(now=later)
        self.assertEqual(stats['zugeschlagen'], 1)

        a.refresh_from_db()
        self.player.refresh_from_db()
        self.club_a.refresh_from_db()
        self.assertEqual(a.status, ShowAuction.STATUS_SETTLED)
        self.assertEqual(self.player.club_id, self.club_a.pk)
        self.assertEqual(self.player.pool_status, Player.POOL_STATUS_NONE)
        self.assertEqual(
            self.player.transfer_locked_until,
            timezone.localdate() + timedelta(days=21),
        )
        self.assertEqual(self.club_a.budget, Decimal('94000000.00'))
        self.assertEqual(self._active_res(self.club_a).count(), 0)

        # Zweiter Lauf: nichts passiert doppelt (Status-Guard + Unique-Buchung).
        stats2 = service.resolve_due(now=later + timedelta(hours=1))
        self.assertEqual(stats2['zugeschlagen'], 0)
        self.assertEqual(
            FinanceTransaction.objects.filter(
                referenz_typ='showauction_settle', referenz_id=a.pk,
            ).count(),
            1,
        )
        self.club_a.refresh_from_db()
        self.assertEqual(self.club_a.budget, Decimal('94000000.00'))


class UndercoverTests(ShowAuctionBase):
    """Verdeckt, genau_1, änderbar, Freigabe erst bei Auktionsende."""

    def test_genau_ein_gebot_aber_aenderbar(self):
        a = self._running('undercover', overrides=NO_CONDS)
        service.place_bid(a.pk, self.club_a, self.mgr_a,
                          Decimal('7000000'), now=self.now)
        # Änderung erlaubt (gebot_aenderbar=ja) → Reservierung angepasst.
        service.place_bid(a.pk, self.club_a, self.mgr_a,
                          Decimal('9000000'), now=self.now)
        res = self._active_res(self.club_a)
        self.assertEqual(res.count(), 1)
        self.assertEqual(res.first().betrag, Decimal('9000000'))
        self.assertEqual(a.bids.filter(club=self.club_a).count(), 1)

    def test_reservierung_bleibt_bis_ende_und_hoechstes_gewinnt(self):
        a = self._running('undercover', overrides=NO_CONDS)
        service.place_bid(a.pk, self.club_a, self.mgr_a,
                          Decimal('7000000'), now=self.now)
        service.place_bid(a.pk, self.club_b, self.mgr_b,
                          Decimal('8000000'), now=self.now)
        # bei_auktionsende: BEIDE Reservierungen bleiben aktiv.
        self.assertEqual(self._active_res(self.club_a).count(), 1)
        self.assertEqual(self._active_res(self.club_b).count(), 1)

        service.resolve_due(now=self.now + timedelta(minutes=4321))
        a.refresh_from_db()
        self.assertEqual(a.status, ShowAuction.STATUS_SETTLED)
        self.assertEqual(a.winner_club_id, self.club_b.pk)
        self.assertEqual(a.winning_amount, Decimal('8000000.00'))
        # Verlierer-Reservierung freigegeben.
        self.assertEqual(self._active_res(self.club_a).count(), 0)
        self.assertEqual(self._active_res(self.club_b).count(), 0)

    def test_gleichstand_entscheidet_los(self):
        a = self._running('undercover', overrides=NO_CONDS)
        service.place_bid(a.pk, self.club_a, self.mgr_a,
                          Decimal('7000000'), now=self.now)
        service.place_bid(a.pk, self.club_b, self.mgr_b,
                          Decimal('7000000'), now=self.now)
        service.resolve_due(now=self.now + timedelta(minutes=4321))
        a.refresh_from_db()
        self.assertEqual(a.status, ShowAuction.STATUS_SETTLED)
        self.assertIn(a.winner_club_id, {self.club_a.pk, self.club_b.pk})


class HollaendischTests(ShowAuctionBase):
    """Fallender Preis, erster Zuschlag bucht sofort."""

    def test_preis_faellt_und_zuschlag_bucht_sofort(self):
        a = self._running('hollaendisch', overrides=NO_CONDS)
        # Start: 200% MW = 20 Mio. Schritt = 2% vom MW (10 Mio) = 200k pro
        # 30-min-Intervall. Nach 60 min (2 Intervalle): 19,6 Mio.
        later = self.now + timedelta(minutes=60)
        auction = service.buy_now(a.pk, self.club_a, self.mgr_a, now=later)
        self.assertEqual(auction.status, ShowAuction.STATUS_SETTLED)
        self.assertEqual(auction.winner_club_id, self.club_a.pk)
        erwartet = Decimal('20000000') - 2 * (Decimal('0.02') * Decimal('10000000'))
        self.assertEqual(auction.winning_amount, erwartet.quantize(Decimal('0.01')))
        self.club_a.refresh_from_db()
        self.assertEqual(
            self.club_a.budget,
            Decimal('100000000.00') - auction.winning_amount,
        )
        self.player.refresh_from_db()
        self.assertEqual(self.player.club_id, self.club_a.pk)

    def test_place_bid_auf_dutch_verboten(self):
        a = self._running('hollaendisch', overrides=NO_CONDS)
        with self.assertRaises(AuctionError):
            service.place_bid(a.pk, self.club_a, self.mgr_a,
                              Decimal('5000000'), now=self.now)


class BereichTests(ShowAuctionBase):
    """Verborgenes Ziel: nächstliegendes Gebot im Korridor gewinnt."""

    def test_ziel_gezogen_und_naechstliegend_gewinnt(self):
        a = self._running('bereich', overrides=NO_CONDS)
        self.assertIsNotNone(a.hidden_target)
        # Korridor: Ziel in [80%, 130%] MW = [8, 13] Mio, Breite 10% MW = 1 Mio.
        self.assertGreaterEqual(a.hidden_target, Decimal('8000000'))
        self.assertLessEqual(a.hidden_target, Decimal('13000000'))

        target = a.hidden_target
        width = a.hidden_width
        # A trifft exakt, B liegt am Rand des Fensters.
        service.place_bid(a.pk, self.club_a, self.mgr_a, target, now=self.now)
        service.place_bid(a.pk, self.club_b, self.mgr_b,
                          target + width / 2, now=self.now)
        service.resolve_due(now=self.now + timedelta(minutes=4321))
        a.refresh_from_db()
        self.assertEqual(a.status, ShowAuction.STATUS_SETTLED)
        self.assertEqual(a.winner_club_id, self.club_a.pk)
        self.assertEqual(a.winning_amount, target.quantize(Decimal('0.01')))

    def test_kein_treffer_im_korridor_platzt(self):
        a = self._running('bereich', overrides=NO_CONDS)
        daneben = a.hidden_target + a.hidden_width * 2
        service.place_bid(a.pk, self.club_a, self.mgr_a, daneben, now=self.now)
        service.resolve_due(now=self.now + timedelta(minutes=4321))
        a.refresh_from_db()
        self.player.refresh_from_db()
        self.assertEqual(a.status, ShowAuction.STATUS_FAILED)
        self.assertEqual(self.player.pool_status, Player.POOL_STATUS_NONE)
        self.assertIsNone(self.player.club_id)
        self.assertEqual(self._active_res(self.club_a).count(), 0)


class BlitzTests(ShowAuctionBase):
    def test_gebot_im_fenster_verlaengert(self):
        a = self._running('blitz', overrides=NO_CONDS)
        ende_vorher = a.ends_at
        self.assertAlmostEqual(
            (ende_vorher - self.now).total_seconds(), 90 * 60, delta=5)
        # Gebot 2 Minuten vor Schluss → +5 Minuten.
        kurz_vor_ende = ende_vorher - timedelta(minutes=2)
        service.place_bid(a.pk, self.club_a, self.mgr_a,
                          Decimal('6050000'), now=kurz_vor_ende)
        a.refresh_from_db()
        self.assertEqual(a.ends_at, ende_vorher + timedelta(minutes=5))
        self.assertEqual(a.extension_count, 1)

    def test_ohne_gebot_platzt(self):
        a = self._running('blitz', overrides=NO_CONDS)
        stats = service.resolve_due(now=self.now + timedelta(minutes=95))
        self.assertEqual(stats['geplatzt'], 1)
        a.refresh_from_db()
        self.player.refresh_from_db()
        self.assertEqual(a.status, ShowAuction.STATUS_FAILED)
        self.assertEqual(self.player.pool_status, Player.POOL_STATUS_NONE)


class TeilnahmeTests(ShowAuctionBase):
    def test_budget_deckung_inkl_reservierungen(self):
        a = self._running('halte', overrides=NO_CONDS)
        reservations.reserve(
            self.club_a, referenz='test:anders', zweck='transfer',
            betrag=Decimal('99000000'), slots=0,
        )
        with self.assertRaises(AuctionError):
            service.place_bid(a.pk, self.club_a, self.mgr_a,
                              Decimal('6000000'), now=self.now)

    def test_max_mw_schnitt_blockiert(self):
        a = self._running('halte', overrides={
            'teilnahmebedingungen': [
                {'art': 'max_mw_schnitt', 'betrag': 1000000},
            ],
        })
        Player.objects.create(
            first_name='Teurer', last_name='Star', age=27, position='Sturm',
            main_position_1='ST', market_value=Decimal('50000000'),
            club=self.club_a, pool_status=Player.POOL_STATUS_NONE,
        )
        grund = service.check_participation(a, self.club_a, self.mgr_a)
        self.assertIsNotNone(grund)
        self.assertIn('MW-Schnitt', grund)


class WatchTests(ShowAuctionBase):
    def test_toggle_watch(self):
        a = self._running('halte', overrides=NO_CONDS)
        self.assertTrue(service.toggle_watch(a, self.club_a))
        self.assertFalse(service.toggle_watch(a, self.club_a))
