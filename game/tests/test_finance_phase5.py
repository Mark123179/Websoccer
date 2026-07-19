"""Tests Finanzsystem Phase 5 — Ventile & Monitoring (Spec Kap. 11 / 12.3 / 12.5).

Deckt ab: Zahlungsunfähigkeits-Verfahren (Vermerk öffnet/schließt über
Buchungs-Hooks), Zwangsversteigerung (Guards, verdeckte Gebote, Settlement
mit Kaskade zum nächsthöheren Gebot), Verbandsabgabe (Formel + harter
Disable-Schalter) und Monitoring-Aggregationen (Typ-Klassifikation,
Schöpfung/Vernichtung, Ablöse/MW-Median).
"""

import datetime
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from game.economy import monitoring
from game.economy.booking import InsufficientFunds, book
from game.economy.forced_auction import (
    ForcedAuctionError, place_bid, resolve_due_auctions, start_auction,
)
from game.economy.kader import min_squad_size
from game.economy.verbandsabgabe import (
    VerbandsabgabeDisabled, berechne_abgabe, jahresumsatz, run_verbandsabgabe,
)
from game.models import (
    Club, ClubNewsItem, EconomyParameter, FinanceTransaction, ForcedAuction,
    InsolvencyCase, League, Player,
)

SAISON = '0'


def _mk_league(name='Phase5-Liga'):
    league, _ = League.objects.get_or_create(name=name, country='DE')
    return league


def _mk_club(name, budget='0.00', league=None):
    return Club.objects.create(
        name=name, short_name=name[:3].upper(), founded_year=1900,
        budget=Decimal(budget), league=league or _mk_league(),
    )


def _fill_squad(club, n, age=25):
    Player.objects.bulk_create([
        Player(club=club, first_name='Kader', last_name=f'{club.short_name}{i}',
               position='MID', age=age, potential=50)
        for i in range(n)
    ])


def _mk_player(club, name='Zwangs Verkauf', age=25, mw=None):
    vor, nach = name.split(' ', 1)
    return Player.objects.create(
        club=club, first_name=vor, last_name=nach, position='MID',
        age=age, market_value=mw, potential=50,
    )


class InsolvencyHookTests(TestCase):
    """Vermerk öffnet/schließt automatisch über die Buchungs-Hooks."""

    def setUp(self):
        self.club = _mk_club('Pleite 04', budget='1000')

    def test_pflichtbuchung_ins_minus_oeffnet_vermerk(self):
        book(self.club, 'GEHALT', Decimal('-5000'), saison=SAISON, pflicht=True)
        case = InsolvencyCase.objects.get(club=self.club)
        self.assertEqual(case.status, InsolvencyCase.STATUS_OPEN)
        self.assertEqual(case.betrag_bei_eroeffnung, Decimal('-4000.00'))
        frist = case.deadline_at - case.opened_at
        self.assertAlmostEqual(frist.total_seconds(), 7 * 86400, delta=60)

    def test_vermerk_ist_idempotent(self):
        book(self.club, 'GEHALT', Decimal('-5000'), saison=SAISON, pflicht=True)
        book(self.club, 'BETRIEB', Decimal('-1000'), saison=SAISON, pflicht=True)
        self.assertEqual(
            InsolvencyCase.objects.filter(club=self.club).count(), 1,
        )

    def test_rueckkehr_ins_plus_schliesst_vermerk(self):
        book(self.club, 'GEHALT', Decimal('-5000'), saison=SAISON, pflicht=True)
        book(self.club, 'TRANSFER_EIN', Decimal('10000'), saison=SAISON)
        case = InsolvencyCase.objects.get(club=self.club)
        self.assertEqual(case.status, InsolvencyCase.STATUS_RESOLVED)
        self.assertIsNotNone(case.resolved_at)

    def test_aktive_ausgabe_ohne_deckung_oeffnet_keinen_vermerk(self):
        with self.assertRaises(InsufficientFunds):
            book(self.club, 'SCOUTING', Decimal('-5000'), saison=SAISON)
        self.assertFalse(InsolvencyCase.objects.filter(club=self.club).exists())


class ForcedAuctionTests(TestCase):
    """Zwangsversteigerung: Guards, Gebote, Settlement mit Kaskade."""

    def setUp(self):
        self.league = _mk_league()
        self.minkader = min_squad_size()
        self.debtor = _mk_club('Schulden 09', budget='-100000',
                               league=self.league)
        _fill_squad(self.debtor, self.minkader)
        self.spieler = _mk_player(self.debtor, mw=Decimal('1000000'))
        self.case = InsolvencyCase.objects.create(
            club=self.debtor,
            deadline_at=timezone.now() - datetime.timedelta(days=1),
            betrag_bei_eroeffnung=Decimal('-100000'),
        )
        self.bieter_a = _mk_club('Bieter A', budget='60000', league=self.league)
        _fill_squad(self.bieter_a, self.minkader)
        self.bieter_b = _mk_club('Bieter B', budget='500000', league=self.league)
        _fill_squad(self.bieter_b, self.minkader)

    def test_start_vor_fristablauf_verweigert(self):
        self.case.deadline_at = timezone.now() + datetime.timedelta(days=3)
        self.case.save(update_fields=['deadline_at'])
        with self.assertRaisesRegex(ForcedAuctionError, 'Frist'):
            start_auction(self.case, self.spieler, Decimal('10000'))

    def test_start_bei_positivem_konto_verweigert(self):
        Club.objects.filter(pk=self.debtor.pk).update(budget=Decimal('5000'))
        with self.assertRaisesRegex(ForcedAuctionError, 'nicht mehr im Minus'):
            start_auction(self.case, self.spieler, Decimal('10000'))

    def test_start_fremder_spieler_verweigert(self):
        fremd = _mk_player(self.bieter_b, name='Fremder Mann')
        with self.assertRaisesRegex(ForcedAuctionError, 'gehört nicht'):
            start_auction(self.case, fremd, Decimal('10000'))

    def test_mindestkader_guard(self):
        # Kader = minkader + 1 (Ziel-Spieler): eine Auktion geht, zweite nicht.
        start_auction(self.case, self.spieler, Decimal('10000'))
        zweiter = Player.objects.filter(
            club=self.debtor).exclude(pk=self.spieler.pk).first()
        with self.assertRaisesRegex(ForcedAuctionError, 'Mindestkader'):
            start_auction(self.case, zweiter, Decimal('10000'))

    def test_start_setzt_vermerk_auf_enforced(self):
        start_auction(self.case, self.spieler, Decimal('10000'))
        self.case.refresh_from_db()
        self.assertEqual(self.case.status, InsolvencyCase.STATUS_ENFORCED)
        self.assertIsNotNone(self.case.enforced_at)

    def test_gebot_guards(self):
        auction = start_auction(self.case, self.spieler, Decimal('20000'))
        with self.assertRaisesRegex(ForcedAuctionError, 'Mindestgebot'):
            place_bid(auction, self.bieter_a, None, Decimal('10000'))
        with self.assertRaisesRegex(ForcedAuctionError, 'Schuldnerverein'):
            place_bid(auction, self.debtor, None, Decimal('30000'))
        with self.assertRaisesRegex(ForcedAuctionError, 'Kontostand'):
            place_bid(auction, self.bieter_a, None, Decimal('999999'))

    def test_gebot_erhoehen_ist_update(self):
        auction = start_auction(self.case, self.spieler, Decimal('10000'))
        place_bid(auction, self.bieter_a, None, Decimal('20000'))
        place_bid(auction, self.bieter_a, None, Decimal('30000'))
        self.assertEqual(auction.bids.count(), 1)
        self.assertEqual(auction.bids.get().amount, Decimal('30000.00'))

    def test_settlement_kaskade_zum_naechsthoeheren_gebot(self):
        auction = start_auction(self.case, self.spieler, Decimal('10000'))
        place_bid(auction, self.bieter_a, None, Decimal('50000'))
        place_bid(auction, self.bieter_b, None, Decimal('30000'))
        # Höchstbietender A verliert nach Gebotsabgabe die Deckung.
        Club.objects.filter(pk=self.bieter_a.pk).update(budget=Decimal('100'))

        heute = auction.ends_on
        summary = resolve_due_auctions(today=heute)
        self.assertEqual(summary['settled'], 1)

        auction.refresh_from_db()
        self.spieler.refresh_from_db()
        self.assertEqual(auction.status, ForcedAuction.STATUS_SETTLED)
        self.assertEqual(auction.winning_bid.club_id, self.bieter_b.pk)
        self.assertEqual(self.spieler.club_id, self.bieter_b.pk)
        # Erlös geht an den Verein (Zirkulation) — kein AUKTION-Senken-Typ.
        self.assertTrue(FinanceTransaction.objects.filter(
            club=self.debtor, typ='TRANSFER_EIN', betrag=Decimal('30000.00'),
        ).exists())
        self.assertFalse(FinanceTransaction.objects.filter(
            club=self.bieter_b, typ='AUKTION',
        ).exists())
        self.assertEqual(
            ClubNewsItem.objects.filter(club=self.debtor).count(), 1)
        self.assertEqual(
            ClubNewsItem.objects.filter(club=self.bieter_b).count(), 1)

    def test_settlement_ohne_gebote_endet_unsold(self):
        auction = start_auction(self.case, self.spieler, Decimal('10000'))
        summary = resolve_due_auctions(today=auction.ends_on)
        self.assertEqual(summary['unsold'], 1)
        auction.refresh_from_db()
        self.spieler.refresh_from_db()
        self.assertEqual(auction.status, ForcedAuction.STATUS_UNSOLD)
        self.assertEqual(self.spieler.club_id, self.debtor.pk)

    def test_konto_bereinigt_bricht_auktion_ab(self):
        # Konto während der Laufzeit zurück auf ≥ 0 → Abbruch statt Zuschlag.
        auction = start_auction(self.case, self.spieler, Decimal('10000'))
        place_bid(auction, self.bieter_b, None, Decimal('50000'))
        Club.objects.filter(pk=self.debtor.pk).update(budget=Decimal('5000'))

        summary = resolve_due_auctions(today=auction.ends_on)
        self.assertEqual(summary['cancelled'], 1)
        self.assertEqual(summary['settled'], 0)
        auction.refresh_from_db()
        self.spieler.refresh_from_db()
        self.assertEqual(auction.status, ForcedAuction.STATUS_CANCELLED)
        self.assertEqual(self.spieler.club_id, self.debtor.pk)
        self.assertIsNone(auction.winning_bid_id)
        self.assertTrue(ClubNewsItem.objects.filter(
            club=self.debtor, title__contains='abgebrochen').exists())

    def test_vermerk_resolved_bricht_auktion_ab(self):
        # Vermerk explizit bereinigt (Hook) → Abbruch auch bei Minus-Konto.
        auction = start_auction(self.case, self.spieler, Decimal('10000'))
        self.case.status = InsolvencyCase.STATUS_RESOLVED
        self.case.save(update_fields=['status'])

        summary = resolve_due_auctions(today=auction.ends_on)
        self.assertEqual(summary['cancelled'], 1)
        auction.refresh_from_db()
        self.assertEqual(auction.status, ForcedAuction.STATUS_CANCELLED)

    def test_unsold_news_wenn_spieler_bereits_weg(self):
        auction = start_auction(self.case, self.spieler, Decimal('10000'))
        Player.objects.filter(pk=self.spieler.pk).update(club=self.bieter_b)

        summary = resolve_due_auctions(today=auction.ends_on)
        self.assertEqual(summary['unsold'], 1)
        self.assertTrue(ClubNewsItem.objects.filter(
            club=self.debtor, title__contains='bereits verlassen').exists())


class VerbandsabgabeTests(TestCase):
    """Formel + harter Disable-Schalter (Spec 12.5, deaktiviert per Seed)."""

    def test_formel(self):
        abgabe = berechne_abgabe(
            Decimal('100000000'), Decimal('20000000'),
            faktor=2.0, satz=0.10,
        )
        self.assertEqual(abgabe, Decimal('6000000.00'))

    def test_unter_freibetrag_null(self):
        self.assertEqual(
            berechne_abgabe(Decimal('30000000'), Decimal('20000000'),
                            faktor=2.0, satz=0.10),
            Decimal('0.00'),
        )

    def test_jahresumsatz_nur_positive_buchungen(self):
        club = _mk_club('Umsatz FC', budget='0')
        book(club, 'TICKET', Decimal('5000'), saison='88')
        book(club, 'GEHALT', Decimal('-3000'), saison='88', pflicht=True)
        self.assertEqual(jahresumsatz(club, '88'), Decimal('5000.00'))

    def test_runner_verweigert_hart_bei_disabled(self):
        # Seed-Migration 0131: enabled=False.
        with self.assertRaises(VerbandsabgabeDisabled):
            run_verbandsabgabe(SAISON)

    def test_runner_bucht_bei_enabled(self):
        row = EconomyParameter.objects.get(saison=SAISON, key='VERBANDSABGABE')
        row.value = {'enabled': True, 'faktor': 2.0, 'satz': 0.10}
        row.save(update_fields=['value'])

        club = _mk_club('Reich 1900', budget='80000000')
        book(club, 'TICKET', Decimal('20000000'), saison=SAISON)
        # Kontostand 100 Mio, Umsatz 20 Mio → Abgabe 6 Mio.
        ergebnisse = run_verbandsabgabe(SAISON)
        eigene = [e for e in ergebnisse if e['club'].pk == club.pk]
        self.assertEqual(len(eigene), 1)
        self.assertEqual(eigene[0]['abgabe'], Decimal('6000000.00'))
        tx = FinanceTransaction.objects.get(club=club, typ='VERBANDSABGABE')
        self.assertEqual(tx.betrag, Decimal('-6000000.00'))
        club.refresh_from_db()
        self.assertEqual(club.budget, Decimal('94000000.00'))


class MonitoringTests(TestCase):
    """Ledger-Aggregationen (Spec 12.5) — Klassifikation und Alarmwerte."""

    def test_klassifikation(self):
        self.assertEqual(monitoring.klassifiziere('TICKET'), 'schoepfung')
        self.assertEqual(monitoring.klassifiziere('GEHALT'), 'vernichtung')
        self.assertEqual(monitoring.klassifiziere('AUKTION'), 'vernichtung')
        self.assertEqual(monitoring.klassifiziere('VERBANDSABGABE'),
                         'vernichtung')
        self.assertEqual(monitoring.klassifiziere('TRANSFER_AUS'),
                         'zirkulation')
        self.assertEqual(monitoring.klassifiziere('KORREKTUR_ADMIN'),
                         'neutral')

    def test_alle_buchungstypen_klassifiziert(self):
        for typ, _label in FinanceTransaction.TYP_CHOICES:
            if typ == 'KORREKTUR_ADMIN':
                continue
            self.assertNotEqual(
                monitoring.klassifiziere(typ), 'neutral',
                f'Buchungstyp {typ} ist nicht klassifiziert',
            )

    def test_saison_geldfluesse(self):
        saison = '77'
        club = _mk_club('Fluss FC', budget='0')
        partner = _mk_club('Partner SV', budget='100000')
        book(club, 'TICKET', Decimal('100000'), saison=saison)
        book(club, 'GEHALT', Decimal('-40000'), saison=saison, pflicht=True)
        book(partner, 'TRANSFER_AUS', Decimal('-50000'), saison=saison)
        book(club, 'TRANSFER_EIN', Decimal('50000'), saison=saison)

        f = monitoring.saison_geldfluesse(saison)
        self.assertEqual(f['schoepfung'], Decimal('100000.00'))
        self.assertEqual(f['vernichtung'], Decimal('40000.00'))
        self.assertEqual(f['netto'], Decimal('60000.00'))
        self.assertEqual(f['zirkulation_volumen'], Decimal('50000.00'))

    def test_abloese_mw_median_alarm(self):
        saison = '78'
        club = _mk_club('Median FC', budget='0')
        p1 = _mk_player(club, name='Eins Mann', mw=Decimal('1000000'))
        p2 = _mk_player(club, name='Zwei Mann', mw=Decimal('1000000'))
        for player, abloese in ((p1, '-2500000'), (p2, '-2300000')):
            FinanceTransaction.objects.create(
                club=club, saison=saison, typ='TRANSFER_AUS',
                betrag=Decimal(abloese), referenz_typ='transfer',
                referenz_id=player.pk, datum=datetime.date(2026, 7, 1),
            )
        r = monitoring.abloese_mw_median(saison)
        self.assertEqual(r['count'], 2)
        self.assertAlmostEqual(r['median'], 2.4, places=2)
        self.assertTrue(r['alarm'])
        self.assertFalse(r['gesund'])

    def test_abloese_mw_median_leer(self):
        r = monitoring.abloese_mw_median('79')
        self.assertIsNone(r['median'])
        self.assertFalse(r['alarm'])


class CreatorSeitenSmokeTests(TestCase):
    """Sportgericht- und Finanzanalyse-Seite rendern für Staff."""

    def setUp(self):
        self.staff = User.objects.create_user(
            'phase5-staff', password='x', is_staff=True,
        )
        self.client.force_login(self.staff)

    def test_creator_sportgericht_rendert(self):
        resp = self.client.get('/creator/sportgericht/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Zwangsversteigerung')

    def test_creator_finanzanalyse_mit_monitoring(self):
        resp = self.client.get('/creator/finanzen/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Monitoring')
        self.assertContains(resp, 'Ledger-Integrität')
        self.assertContains(resp, 'Geldmengen-Verlauf')
