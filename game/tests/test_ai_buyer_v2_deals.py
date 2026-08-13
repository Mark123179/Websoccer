"""Tests KI-Käufer-Engine → v2-DealRequest (Task #824, letztes Teilstück).

Deckt ab:
a) Live-Modus (dry_run=False): _kauf_versuchen mit Manager-Verkäufer erzeugt
   eine OPEN DealRequest (typ CASH, from_club=KI-Klub, to_players=der Spieler,
   cash_from>0, Escrow-Reservierung vorhanden) und KEIN neues AITransferOffer.
b) dry_run=True: weiterhin AITransferOffer STATUS_BERECHNET, KEINE DealRequest.
c) Kadenz: existiert bereits eine OPEN KI-DealRequest des Klubs, wird kein
   weiteres Kaufinteresse erzeugt (max_offen_ki=1).
"""
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from game.economy.ai_buyer.pruflauf import _offene_ki_angebote, run_club_pruflauf
from game.economy.kader import min_squad_size
from game.economy.params import get_param
from game.models import (
    AITransferOffer, Club, EconomyParameter, FinanceReservation,
    GameSeasonState, League, Player, PlayerStrengthProfile,
    SeasonEconomySnapshot,
)
from game.transfer_v2.models import DealRequest
from game.transfer_v2.services import create_deal_request

SAISON = '0'
WINDOW = f'{SAISON}-F1'


# ---------------------------------------------------------------------------
# Hilfsfunktionen (analog zu test_finance_phase6.py / ItoReferenzTests)
# ---------------------------------------------------------------------------

def _mk_league(name='V2Deal-Liga'):
    league, _ = League.objects.get_or_create(name=name, country='DE')
    return league


def _mk_club(name, budget='80000000', league=None):
    return Club.objects.create(
        name=name, short_name=name[:3].upper(), founded_year=1900,
        budget=Decimal(budget), league=league or _mk_league(),
    )


def _mk_manager(club, username):
    user = User.objects.create_user(username, password='x')
    club.managed_by = user.manager_profile
    club.save(update_fields=['managed_by'])
    return user


def _fill_squad(club, n, age=25):
    Player.objects.bulk_create([
        Player(
            club=club, first_name='Kader', last_name=f'{club.short_name}{i}',
            position='MID', age=age, potential=50,
        )
        for i in range(n)
    ])


def _mk_player(club, name, *, pos='MID', staerke=None, age=25, mw=None,
               potential=50, sichtbar=False, kategorie='UVK'):
    vor, nach = name.split(' ', 1)
    player = Player.objects.create(
        club=club, first_name=vor, last_name=nach, position='MID',
        main_position_1=pos or '', age=age, market_value=mw,
        potential=potential, sale_category=kategorie,
        sale_visible_to_ai=sichtbar,
    )
    if staerke is not None:
        PlayerStrengthProfile.objects.create(
            player=player, base_strength=Decimal(str(staerke)),
        )
    return player


def _mk_442_kader(club, *, staerke_feld=65, staerke_iv1=70,
                  talent_staerke=40, talent_potential=40):
    """4-4-2-Kader: TW, LV, IV, IV, RV, LM, ZM, ZM, RM, ST, ST + IV-Talent."""
    slots = ['TW', 'LV', 'IV', 'IV', 'RV', 'LM', 'ZM', 'ZM', 'RM', 'ST', 'ST']
    spieler = {}
    for i, code in enumerate(slots):
        staerke = staerke_iv1 if (code == 'IV' and 'IV1' not in spieler) \
            else staerke_feld
        p = _mk_player(
            club, f'{code}{i} Stamm{i}', pos=code, staerke=staerke,
            mw='1000000',
        )
        if code == 'IV' and 'IV1' not in spieler:
            spieler['IV1'] = p
        spieler[f'{code}{i}'] = p
    spieler['TALENT'] = _mk_player(
        club, 'Junges Talent', pos='IV', staerke=talent_staerke, age=18,
        potential=talent_potential, mw='500000',
    )
    return spieler


def _setup_params(dry_run=False):
    """KI_KAEUFER-Parameter mit explizitem dry_run-Flag."""
    ki_kaeufer = {
        'dry_run': dry_run,
        'streuung': 0.05,
        'eroeffnung': 0.70,
        'nachbesserung': 0.90,
        'final': 1.00,
        'quali_faktor': 0.85,
        'talent_faktor': 0.90,
        'quali_ueberschuss_faktor': 2,
        'quali_staerke_delta': 10,
        'talent_max_alter': 21,
        'talent_potential_delta': 15,
        'luecken_schwellwert': 15,
        'backup_delta': 25,
        'dringlichkeit_min': 0.3,
        'cooldown_tage': {'bedarf': 7, 'qualitaet': 14},
        'max_offen_ki': 1,
        'max_pro_fenster_ki': 3,
        'max_offen_manager': 2,
        'max_pro_fenster_manager': 4,
        'gueltigkeit_stunden': 72,
        'puffer_spieltage': 17,
        'governor_anteil': 0.5,
        'forderung_faktor_min': 1.1,
        'forderung_faktor_max': 1.3,
        'gebot_quantisierung': 10000,
    }
    EconomyParameter.objects.update_or_create(
        saison=SAISON, key='KI_KAEUFER',
        defaults={'value': ki_kaeufer},
    )
    return ki_kaeufer


def _setup_common():
    """Gemeinsames Setup: Snapshot, Fenster, Parameter."""
    SeasonEconomySnapshot.objects.get_or_create(
        saison=SAISON,
        defaults={
            'mw_median': Decimal('1000000'),
            'gehalts_anker': Decimal('1000000'),
        },
    )
    state, _ = GameSeasonState.objects.get_or_create(pk=1)
    state.transfer_window_open = True
    state.transfer_window_id = WINDOW
    state.save()
    return state


def _setup_escrow_params():
    """Parameter für create_deal_request."""
    EconomyParameter.objects.update_or_create(
        saison=SAISON, key='TRANSFER_MAX_PAKET', defaults={'value': 5},
    )
    EconomyParameter.objects.update_or_create(
        saison=SAISON, key='TRANSFER_ANFRAGE_LAUFZEIT_TAGE', defaults={'value': 7},
    )
    EconomyParameter.objects.update_or_create(
        saison=SAISON, key='KADER_MIN', defaults={'value': 0},
    )


# ---------------------------------------------------------------------------
# Test a) Live-Modus: DealRequest erzeugt, KEIN AITransferOffer
# ---------------------------------------------------------------------------

class LiveModeDealRequestTests(TestCase):
    """dry_run=False: _kauf_versuchen erzeugt v2-DealRequest, kein AITransferOffer."""

    def setUp(self):
        _setup_escrow_params()
        _setup_common()
        _setup_params(dry_run=False)

        self.league = _mk_league()
        self.soll = Decimal('60')

        # KI-Klub mit Bedarfslücke (IV1 fehlt nach dem Test-Setup)
        self.club = _mk_club('KI Käufer Live', budget='80000000',
                             league=self.league)
        self.kader = _mk_442_kader(self.club)

        # IV1 verlässt den Verein → Bedarfslücke
        ito = self.kader['IV1']
        ito.club = None
        ito.save(update_fields=['club'])

        # Manager-Verein als Verkäufer
        fremde_liga = _mk_league('Live-Fremdliga')
        self.verkaeufer = _mk_club('Manager Verkauf Live', league=fremde_liga)
        _mk_manager(self.verkaeufer, 'live-manager')
        _fill_squad(self.verkaeufer, min_squad_size(SAISON) + 2)
        self.kandidat = _mk_player(
            self.verkaeufer, 'Neuer IV Live', pos='IV', staerke=65,
            age=26, mw='2000000', sichtbar=True, kategorie='GELD',
        )

    def test_pruflauf_erzeugt_deal_request_statt_offer(self):
        """Im Live-Modus entsteht eine OPEN DealRequest, kein AITransferOffer."""
        run = run_club_pruflauf(
            self.club, saison=SAISON, spieltag=1, trigger='test',
            soll=self.soll,
        )
        self.assertIsNotNone(run, 'Prüflauf sollte nicht None sein')
        self.assertFalse(run.dry_run, 'Prüflauf soll im Live-Modus laufen')

        kaeufe = run.report.get('kaeufe', [])
        bedarf = [k for k in kaeufe if k['typ'] == 'bedarf']
        self.assertTrue(bedarf, f'Kein Bedarfskauf im Report: {run.report}')

        kauf = bedarf[0]
        self.assertEqual(kauf['aktion'], 'angebot')
        self.assertIn('deal_id', kauf)
        self.assertEqual(kauf['player_id'], self.kandidat.pk)

        # Kein AITransferOffer erzeugt
        self.assertFalse(
            AITransferOffer.objects.filter(buyer_club=self.club).exists(),
            'Im Live-Modus soll KEIN AITransferOffer erzeugt werden',
        )

        # Eine DealRequest erzeugt
        deals = DealRequest.objects.filter(
            from_club=self.club, to_club=self.verkaeufer,
        )
        self.assertEqual(deals.count(), 1, 'Genau eine DealRequest soll erzeugt werden')
        deal = deals.first()
        self.assertEqual(deal.status, DealRequest.STATUS_OPEN)
        self.assertEqual(deal.typ, DealRequest.TYP_CASH)
        self.assertGreater(deal.cash_from, Decimal('0'),
                           'cash_from muss positiv sein')
        self.assertEqual(deal.pk, kauf['deal_id'])

    def test_deal_request_hat_korrekten_spieler(self):
        """Die DealRequest enthält den richtigen Spieler auf TO-Seite."""
        run_club_pruflauf(
            self.club, saison=SAISON, spieltag=1, trigger='test',
            soll=self.soll,
        )

        deal = DealRequest.objects.filter(
            from_club=self.club, to_club=self.verkaeufer,
            status=DealRequest.STATUS_OPEN,
        ).first()
        self.assertIsNotNone(deal, 'DealRequest nicht gefunden')

        # Spieler in DealRequestPlayer auf TO-Seite
        from game.transfer_v2.models import DealRequestPlayer
        eintrag = DealRequestPlayer.objects.filter(
            request=deal, player=self.kandidat, side=DealRequestPlayer.SIDE_TO,
        )
        self.assertTrue(eintrag.exists(), 'Spieler muss auf TO-Seite im Deal sein')

    def test_escrow_reservierung_vorhanden(self):
        """Nach dem Deal-Erstellen hat der KI-Klub eine aktive Escrow-Reservierung."""
        run_club_pruflauf(
            self.club, saison=SAISON, spieltag=1, trigger='test',
            soll=self.soll,
        )

        deal = DealRequest.objects.filter(
            from_club=self.club, status=DealRequest.STATUS_OPEN,
        ).first()
        self.assertIsNotNone(deal, 'DealRequest nicht gefunden')

        # Escrow-Referenz prüfen
        ref = f'tv2:deal:{deal.pk}'
        reservierung = FinanceReservation.objects.filter(
            club=self.club,
            referenz=ref,
            status=FinanceReservation.STATUS_ACTIVE,
        )
        self.assertTrue(
            reservierung.exists(),
            f'Keine aktive Escrow-Reservierung für DealRequest #{deal.pk}',
        )
        self.assertGreater(reservierung.first().betrag, Decimal('0'))

    def test_cash_from_positiv_und_innerhalb_budget(self):
        """cash_from > 0 und ≤ Käufer-Budget."""
        run_club_pruflauf(
            self.club, saison=SAISON, spieltag=1, trigger='test',
            soll=self.soll,
        )

        deal = DealRequest.objects.filter(from_club=self.club).first()
        self.assertIsNotNone(deal)
        self.assertGreater(deal.cash_from, Decimal('0'))
        self.assertLessEqual(deal.cash_from, Decimal('80000000'))


# ---------------------------------------------------------------------------
# Test b) Trockenlauf: AITransferOffer STATUS_BERECHNET, keine DealRequest
# ---------------------------------------------------------------------------

class DryRunStillUsesOfferTests(TestCase):
    """dry_run=True: AITransferOffer mit STATUS_BERECHNET, keine v2-DealRequest."""

    def setUp(self):
        _setup_escrow_params()
        _setup_common()
        _setup_params(dry_run=True)

        self.league = _mk_league('DryRun-Liga')
        self.soll = Decimal('60')

        # KI-Klub mit Bedarfslücke
        self.club = _mk_club('KI Käufer Dry', budget='80000000',
                             league=self.league)
        self.kader = _mk_442_kader(self.club)

        # IV1 verlässt den Verein → Bedarfslücke
        ito = self.kader['IV1']
        ito.club = None
        ito.save(update_fields=['club'])

        # Manager-Verein als Verkäufer
        fremde_liga = _mk_league('DryRun-Fremdliga')
        self.verkaeufer = _mk_club('Manager Dry Verkauf', league=fremde_liga)
        _mk_manager(self.verkaeufer, 'dry-manager')
        _fill_squad(self.verkaeufer, min_squad_size(SAISON) + 2)
        self.kandidat = _mk_player(
            self.verkaeufer, 'Neuer IV Dry', pos='IV', staerke=65,
            age=26, mw='2000000', sichtbar=True, kategorie='GELD',
        )

    def test_trockenlauf_erzeugt_ai_transfer_offer(self):
        """Im Trockenlauf entsteht ein AITransferOffer mit STATUS_BERECHNET."""
        run = run_club_pruflauf(
            self.club, saison=SAISON, spieltag=1, trigger='test',
            soll=self.soll,
        )
        self.assertIsNotNone(run)
        self.assertTrue(run.dry_run)

        kaeufe = run.report.get('kaeufe', [])
        bedarf = [k for k in kaeufe if k['typ'] == 'bedarf']
        self.assertTrue(bedarf, f'Kein Bedarfskauf im Report: {run.report}')
        self.assertEqual(bedarf[0]['aktion'], 'berechnet')

        offers = AITransferOffer.objects.filter(buyer_club=self.club)
        self.assertTrue(
            offers.exists(),
            'Im Trockenlauf soll ein AITransferOffer erzeugt werden',
        )
        offer = offers.first()
        self.assertEqual(offer.status, AITransferOffer.STATUS_BERECHNET)
        self.assertTrue(offer.dry_run)

    def test_trockenlauf_erzeugt_keine_deal_request(self):
        """Im Trockenlauf soll KEINE v2-DealRequest entstehen."""
        run_club_pruflauf(
            self.club, saison=SAISON, spieltag=1, trigger='test',
            soll=self.soll,
        )

        self.assertFalse(
            DealRequest.objects.filter(from_club=self.club).exists(),
            'Im Trockenlauf darf keine DealRequest entstehen',
        )

    def test_trockenlauf_report_enthaelt_berechnet_aktion(self):
        """Der Prüflauf-Report soll 'berechnet' als Aktion und offer_id enthalten."""
        run = run_club_pruflauf(
            self.club, saison=SAISON, spieltag=1, trigger='test',
            soll=self.soll,
        )
        kaeufe = run.report.get('kaeufe', [])
        bedarf = [k for k in kaeufe if k['typ'] == 'bedarf']
        self.assertTrue(bedarf, f'Keine Käufe im Report: {run.report}')
        kauf = bedarf[0]
        self.assertEqual(kauf['aktion'], 'berechnet')
        self.assertIn('offer_id', kauf)
        self.assertNotIn('deal_id', kauf)
        self.assertEqual(kauf['player_id'], self.kandidat.pk)


# ---------------------------------------------------------------------------
# Test c) Kadenz: Existierende OPEN KI-DealRequest blockiert neues Kaufinteresse
# ---------------------------------------------------------------------------

class KadenzMitV2DealRequestTests(TestCase):
    """max_offen_ki=1: Existiert eine OPEN DealRequest des KI-Klubs, soll kein
    weiteres Kaufinteresse erzeugt werden."""

    def setUp(self):
        _setup_escrow_params()
        _setup_common()
        _setup_params(dry_run=False)

        self.league = _mk_league('Kadenz-Liga')
        self.soll = Decimal('60')

        # KI-Klub
        self.club = _mk_club('KI Kadenz', budget='80000000',
                             league=self.league)
        self.kader = _mk_442_kader(self.club)

        # IV1 verlässt den Verein → Bedarfslücke
        ito = self.kader['IV1']
        ito.club = None
        ito.save(update_fields=['club'])

        # Erster Manager-Verein (wird für die vorab-DealRequest genutzt)
        fremde_liga = _mk_league('Kadenz-Fremdliga')
        self.verkaeufer1 = _mk_club('Manager Kadenz 1', league=fremde_liga)
        _mk_manager(self.verkaeufer1, 'kadenz-manager1')
        _fill_squad(self.verkaeufer1, min_squad_size(SAISON) + 2)
        self.spieler1 = _mk_player(
            self.verkaeufer1, 'IV Kandidat Eins', pos='IV', staerke=66,
            age=26, mw='2500000', sichtbar=True, kategorie='GELD',
        )

        # Zweiter Manager-Verein (alternativer Kandidat)
        self.verkaeufer2 = _mk_club('Manager Kadenz 2', league=fremde_liga)
        _mk_manager(self.verkaeufer2, 'kadenz-manager2')
        _fill_squad(self.verkaeufer2, min_squad_size(SAISON) + 2)
        self.spieler2 = _mk_player(
            self.verkaeufer2, 'IV Kandidat Zwei', pos='IV', staerke=67,
            age=25, mw='2600000', sichtbar=True, kategorie='GELD',
        )

    def test_bestehende_deal_request_blockiert_kadenz(self):
        """Ist eine OPEN KI-DealRequest vorhanden (max_offen_ki=1), soll der
        Prüflauf keine weiteren Käufe erzeugen."""
        # Vorab eine OPEN DealRequest für ki_club erzeugen (zu verkaeufer1)
        vorhandene_deal = create_deal_request(
            self.club, self.verkaeufer1,
            typ='CASH',
            cash_from=Decimal('1000000'),
            to_players=[self.spieler1],
            saison=SAISON,
        )
        self.assertEqual(vorhandene_deal.status, DealRequest.STATUS_OPEN)

        # Prüflauf starten — soll blockiert sein wegen max_offen_ki=1
        run = run_club_pruflauf(
            self.club, saison=SAISON, spieltag=2, trigger='test',
            soll=self.soll,
        )
        self.assertIsNotNone(run)

        # Keine weiteren DealRequests erzeugt (nur die eine vorab erstellte)
        alle_deals = DealRequest.objects.filter(from_club=self.club)
        self.assertEqual(
            alle_deals.count(), 1,
            f'Es sollen keine neuen DealRequests erzeugt werden; '
            f'gefunden: {alle_deals.count()}',
        )

        # Kein neues AITransferOffer erzeugt
        self.assertFalse(
            AITransferOffer.objects.filter(buyer_club=self.club).exists(),
        )

        # Report meldet Kadenz-Stop
        entscheidungen = run.report.get('entscheidungen', [])
        kadenz_meldungen = [e for e in entscheidungen if 'Kadenz' in e]
        self.assertTrue(
            kadenz_meldungen,
            f'Kein Kadenz-Stop im Report: {entscheidungen}',
        )

    def test_offene_ki_angebote_zaehlt_deal_requests_im_live_modus(self):
        """_offene_ki_angebote soll im Live-Modus v2-DealRequests mitzählen."""
        self.assertEqual(_offene_ki_angebote(self.club, dry_run=False), 0)

        create_deal_request(
            self.club, self.verkaeufer1,
            typ='CASH',
            cash_from=Decimal('1000000'),
            to_players=[self.spieler1],
            saison=SAISON,
        )
        self.assertEqual(_offene_ki_angebote(self.club, dry_run=False), 1)

    def test_offene_ki_angebote_ignoriert_deal_requests_im_trockenlauf(self):
        """_offene_ki_angebote soll im Trockenlauf v2-DealRequests NICHT mitzählen."""
        create_deal_request(
            self.club, self.verkaeufer1,
            typ='CASH',
            cash_from=Decimal('1000000'),
            to_players=[self.spieler1],
            saison=SAISON,
        )
        # Im Trockenlauf werden DealRequests nicht gezählt
        self.assertEqual(_offene_ki_angebote(self.club, dry_run=True), 0)
