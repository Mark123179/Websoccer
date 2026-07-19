"""Tests Finanzsystem Phase 6 — KI-Käufer Stufe 2 (Spec Kap. 9.3).

Deckt ab: Kauftyp-Grenzen (Bedarf/Qualität/Talent), Gebotstreppe 70/90/100
mit Dringlichkeits-Gates (Stufe 2 nur Bedarf, Stufe 3 nur Lückenscore ≥ 10),
Manager-Kadenz (max. 2 offene / 4 je Fenster ins Postfach), Trockenlauf-
Semantik (status='berechnet', nichts im Postfach), Leak-Schutz der
Manager-Payloads (nie bewertung/max_gebot/noise_seed) sowie den
Ito-Referenzfall (Verkauf eines Beste-11-IV → Stammlücke → Bedarfskauf
im nächsten Prüflauf).
"""

from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from game.economy.ai_buyer.bedarf import bedarfs_analyse, beste_elf
from game.economy.ai_buyer.offers import (
    AIBuyerError, create_offer, gebot_fuer_stufe, manager_ablehnen,
    manager_annehmen, max_gebot_fuer, offer_manager_payload,
)
from game.economy.ai_buyer.pruflauf import run_club_pruflauf
from game.economy.kader import min_squad_size
from game.economy.params import get_param
from game.models import (
    AIBuyerRun, AITransferOffer, Club, EconomyParameter, GameSeasonState,
    League, Player, PlayerStrengthProfile, SeasonEconomySnapshot,
)
from game.views_transfermarkt import incoming_ai_offers

SAISON = '0'
WINDOW = f'{SAISON}-F1'

VERBOTENE_FELDER = ('bewertung', 'max_gebot', 'noise_seed')


def _mk_league(name='Phase6-Liga'):
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


def _mk_player(club, name, *, pos=None, staerke=None, age=25, mw=None,
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


def _mk_manager(club, username):
    user = User.objects.create_user(username, password='x')
    club.managed_by = user.manager_profile
    club.save(update_fields=['managed_by'])
    return user


def _wertung(schmerz, zukunft=None):
    return {
        'schmerzgrenze': Decimal(str(schmerz)),
        'zukunftswert': Decimal(str(zukunft if zukunft is not None
                                    else schmerz)),
    }


def _params():
    return get_param('KI_KAEUFER', SAISON)


class MaxGebotKauftypTests(TestCase):
    """Käufer-Maximum je Kauftyp (Bewertungssymmetrie, Spec 9.3)."""

    def setUp(self):
        self.params = _params()

    def test_bedarf_zahlt_volle_schmerzgrenze(self):
        wertung = _wertung('10000000', '4000000')
        self.assertEqual(
            max_gebot_fuer('bedarf', wertung, self.params),
            Decimal('10000000.00'),
        )

    def test_qualitaet_max_85_prozent_der_bewertung(self):
        wertung = _wertung('10000000', '4000000')
        self.assertEqual(
            max_gebot_fuer('qualitaet', wertung, self.params),
            Decimal('8500000.00'),
        )

    def test_talent_max_90_prozent_des_zukunftswerts(self):
        wertung = _wertung('10000000', '4000000')
        self.assertEqual(
            max_gebot_fuer('talent', wertung, self.params),
            Decimal('3600000.00'),
        )

    def test_max_null_verhindert_angebot(self):
        buyer = _mk_club('Nullkauf 01')
        seller = _mk_club('Nullverkauf 02', league=buyer.league)
        player = _mk_player(seller, 'Wert Los')
        with self.assertRaises(AIBuyerError):
            create_offer(
                buyer, player, kauftyp='bedarf', wertung=_wertung('0'),
                params=self.params, saison=SAISON, window_id=WINDOW,
                dry_run=True,
            )


class GebotstreppeTests(TestCase):
    """Gebotstreppe 70/90/100 mit Dringlichkeits-Gates."""

    def setUp(self):
        self.params = _params()
        self.league = _mk_league()
        self.buyer = _mk_club('KI Käufer 04', budget='50000000',
                              league=self.league)
        self.seller = _mk_club('Manager Verein 05', league=self.league)
        _mk_manager(self.seller, 'treppen-manager')
        self.player = _mk_player(self.seller, 'Treppen Kandidat')
        self.wertung = _wertung('10000000')

    def _offer(self, *, kauftyp='bedarf', luecken_score=None):
        return create_offer(
            self.buyer, self.player, kauftyp=kauftyp, wertung=self.wertung,
            params=self.params, saison=SAISON, window_id=WINDOW,
            dry_run=False, luecken_score=luecken_score,
        )

    def test_eroeffnung_70_prozent_mit_streuung(self):
        offer = self._offer(luecken_score=Decimal('12'))
        self.assertEqual(offer.status, AITransferOffer.STATUS_VERSENDET)
        self.assertEqual(offer.stufe, 1)
        maximum = offer.max_gebot
        # 70 % ± 5 % Streuung, quantisiert auf 10.000 €.
        untergrenze = maximum * Decimal('0.70') * Decimal('0.95') - 10000
        obergrenze = maximum * Decimal('0.70') * Decimal('1.05') + 10000
        self.assertGreaterEqual(offer.aktuelles_gebot, untergrenze)
        self.assertLessEqual(offer.aktuelles_gebot, obergrenze)
        self.assertLessEqual(offer.aktuelles_gebot, maximum)

    def test_keine_stufe_ueberschreitet_max_gebot(self):
        offer = self._offer(luecken_score=Decimal('12'))
        for stufe in (1, 2, 3):
            gebot = gebot_fuer_stufe(offer, stufe, self.params)
            self.assertLessEqual(gebot, offer.max_gebot,
                                 f'Stufe {stufe} über Käufer-Maximum')
            self.assertEqual(gebot % 10000, 0,
                             f'Stufe {stufe} nicht quantisiert')

    def test_bedarf_hohe_dringlichkeit_eskaliert_bis_stufe_3(self):
        offer = self._offer(luecken_score=Decimal('12'))
        ergebnis = manager_ablehnen(offer, params=self.params)
        self.assertEqual(ergebnis['ergebnis'], 'nachgebessert')
        self.assertEqual(ergebnis['offer'].stufe, 2)
        ergebnis = manager_ablehnen(ergebnis['offer'], params=self.params)
        self.assertEqual(ergebnis['ergebnis'], 'nachgebessert')
        self.assertEqual(ergebnis['offer'].stufe, 3)
        ergebnis = manager_ablehnen(ergebnis['offer'], params=self.params)
        self.assertEqual(ergebnis['ergebnis'], 'zurueckgezogen')
        offer.refresh_from_db()
        self.assertEqual(offer.status, AITransferOffer.STATUS_ABGELEHNT)
        # Bedarfs-Cooldown 7 Tage.
        self.assertIsNotNone(offer.cooldown_until)
        delta = offer.cooldown_until - timezone.now()
        self.assertAlmostEqual(delta.total_seconds(), 7 * 86400, delta=120)

    def test_bedarf_niedrige_dringlichkeit_endet_bei_stufe_2(self):
        offer = self._offer(luecken_score=Decimal('5'))
        ergebnis = manager_ablehnen(offer, params=self.params)
        self.assertEqual(ergebnis['offer'].stufe, 2)
        ergebnis = manager_ablehnen(ergebnis['offer'], params=self.params)
        self.assertEqual(ergebnis['ergebnis'], 'zurueckgezogen')

    def test_qualitaet_bessert_nie_nach(self):
        offer = self._offer(kauftyp='qualitaet')
        ergebnis = manager_ablehnen(offer, params=self.params)
        self.assertEqual(ergebnis['ergebnis'], 'zurueckgezogen')
        offer.refresh_from_db()
        # Qualitäts-Cooldown 14 Tage.
        delta = offer.cooldown_until - timezone.now()
        self.assertAlmostEqual(delta.total_seconds(), 14 * 86400, delta=120)

    def test_talent_bessert_nie_nach(self):
        offer = self._offer(kauftyp='talent')
        ergebnis = manager_ablehnen(offer, params=self.params)
        self.assertEqual(ergebnis['ergebnis'], 'zurueckgezogen')


class ManagerKadenzTests(TestCase):
    """Postfach-Hygiene: max. 2 offene / 4 je Fenster pro Manager-Verein."""

    def setUp(self):
        self.params = _params()
        self.league = _mk_league()
        self.seller = _mk_club('Postfach 06', league=self.league)
        _mk_manager(self.seller, 'kadenz-manager')
        self.spieler = [
            _mk_player(self.seller, f'Ziel Spieler{i}') for i in range(5)
        ]
        self.buyers = [
            _mk_club(f'KI Bieter {i:02d}', league=self.league)
            for i in range(5)
        ]

    def _offer(self, buyer, player, **kw):
        return create_offer(
            buyer, player, kauftyp=kw.pop('kauftyp', 'qualitaet'),
            wertung=_wertung('5000000'), params=self.params, saison=SAISON,
            window_id=WINDOW, dry_run=kw.pop('dry_run', False), **kw,
        )

    def test_max_zwei_offene_angebote(self):
        self._offer(self.buyers[0], self.spieler[0])
        self._offer(self.buyers[1], self.spieler[1])
        with self.assertRaises(AIBuyerError):
            self._offer(self.buyers[2], self.spieler[2])

    def test_ablehnung_gibt_offenen_slot_frei(self):
        self._offer(self.buyers[0], self.spieler[0])
        zweite = self._offer(self.buyers[1], self.spieler[1])
        manager_ablehnen(zweite, params=self.params)  # Qualität → Rückzug
        # Slot frei → drittes Angebot möglich.
        self._offer(self.buyers[2], self.spieler[2])

    def test_fensterlimit_vier_angebote(self):
        for i in range(4):
            offer = self._offer(self.buyers[i], self.spieler[i])
            manager_ablehnen(offer, params=self.params)  # schließt sofort
        with self.assertRaises(AIBuyerError):
            self._offer(self.buyers[4], self.spieler[4])

    def test_trockenlauf_zaehlt_berechnete_angebote(self):
        self._offer(self.buyers[0], self.spieler[0], dry_run=True)
        self._offer(self.buyers[1], self.spieler[1], dry_run=True)
        with self.assertRaises(AIBuyerError):
            self._offer(self.buyers[2], self.spieler[2], dry_run=True)


class DryRunTests(TestCase):
    """Trockenlauf: berechnen, aber NIE ins Postfach senden."""

    def setUp(self):
        self.params = _params()
        self.league = _mk_league()
        self.buyer = _mk_club('KI Trocken 07', league=self.league)
        self.seller = _mk_club('Manager Trocken 08', league=self.league)
        self.user = _mk_manager(self.seller, 'trocken-manager')
        self.player = _mk_player(self.seller, 'Trocken Ziel')
        self.offer = create_offer(
            self.buyer, self.player, kauftyp='bedarf',
            wertung=_wertung('8000000'), params=self.params, saison=SAISON,
            window_id=WINDOW, dry_run=True,
        )

    def test_status_berechnet_ohne_gueltigkeit(self):
        self.assertEqual(self.offer.status, AITransferOffer.STATUS_BERECHNET)
        self.assertTrue(self.offer.dry_run)
        self.assertIsNone(self.offer.gueltig_bis)

    def test_postfach_bleibt_leer(self):
        self.assertEqual(incoming_ai_offers(self.seller), [])

    def test_annahme_berechneter_angebote_unmoeglich(self):
        with self.assertRaises(AIBuyerError):
            manager_annehmen(self.offer)

    def test_view_findet_trockenlauf_angebot_nicht(self):
        self.client.force_login(self.user)
        resp = self.client.post(
            reverse('ai_offer_accept'), {'offer_id': self.offer.pk},
        )
        self.assertEqual(resp.status_code, 404)

    def test_scharfschalten_storniert_trockenlauf_altbestand(self):
        # 'berechnet'-Angebote aus dem Trockenlauf haben kein gueltig_bis und
        # würden nach dem Scharfschalten Kadenz-Limits und Kandidaten-Sperren
        # weiter belegen — der dry_run-Toggle muss sie stornieren.
        staff = User.objects.create_user(
            'scharf-admin', password='x', is_staff=True)
        self.client.force_login(staff)
        resp = self.client.post(
            reverse('creator_ki_transferzentrale'),
            {'action': 'dry_run', 'value': '0'},
        )
        self.assertEqual(resp.status_code, 302)
        self.offer.refresh_from_db()
        self.assertEqual(self.offer.status, AITransferOffer.STATUS_STORNIERT)
        self.assertIn('Trockenlauf-Altbestand', self.offer.begruendung)
        self.assertFalse(get_param('KI_KAEUFER', SAISON).get('dry_run'))
        # Zurückschalten auf Trockenlauf storniert nichts zusätzlich.
        resp = self.client.post(
            reverse('creator_ki_transferzentrale'),
            {'action': 'dry_run', 'value': '1'},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(get_param('KI_KAEUFER', SAISON).get('dry_run'))


class KaderplatzGateTests(TestCase):
    """Käufer ohne freien Kaderplatz sendet NIE Angebote (Spec 9.1)."""

    def setUp(self):
        # Kaderlimit klein setzen, damit „voll" billig herstellbar ist.
        EconomyParameter.objects.update_or_create(
            saison=SAISON, key='KADER_MAX_BASIS', defaults={'value': 12},
        )
        self.params = _params()
        self.league = _mk_league()
        self.buyer = _mk_club('KI Voll 15', budget='80000000',
                              league=self.league)
        _fill_squad(self.buyer, 12)
        self.seller = _mk_club('Manager Voll 16', league=self.league)
        self.user = _mk_manager(self.seller, 'voll-manager')
        self.player = _mk_player(self.seller, 'Voll Ziel')

    def test_create_offer_blockiert_ohne_kaderplatz(self):
        with self.assertRaises(AIBuyerError):
            create_offer(
                self.buyer, self.player, kauftyp='bedarf',
                wertung=_wertung('8000000'), params=self.params,
                saison=SAISON, window_id=WINDOW, dry_run=True,
            )
        self.assertFalse(
            AITransferOffer.objects.filter(buyer_club=self.buyer).exists())

    def test_pruflauf_ueberspringt_vollen_kader(self):
        state, _ = GameSeasonState.objects.get_or_create(pk=1)
        state.transfer_window_open = True
        state.transfer_window_id = WINDOW
        state.save()
        run = run_club_pruflauf(
            self.buyer, saison=SAISON, spieltag=1, trigger='test',
        )
        self.assertIsNotNone(run)
        self.assertIn('Kein freier Kaderplatz — keine Käufe.',
                      run.report['entscheidungen'])
        self.assertEqual(run.report.get('kaeufe', []), [])
        self.assertFalse(
            AITransferOffer.objects.filter(buyer_club=self.buyer).exists())

    def test_ein_freier_platz_erlaubt_angebot(self):
        Player.objects.filter(club=self.buyer).first().delete()
        offer = create_offer(
            self.buyer, self.player, kauftyp='bedarf',
            wertung=_wertung('8000000'), params=self.params,
            saison=SAISON, window_id=WINDOW, dry_run=True,
        )
        self.assertEqual(offer.status, AITransferOffer.STATUS_BERECHNET)


class SerializerLeakTests(TestCase):
    """bewertung/max_gebot/noise_seed verlassen NIE den Server."""

    def setUp(self):
        self.params = _params()
        self.league = _mk_league()
        self.buyer = _mk_club('KI Geheim 09', league=self.league)
        self.seller = _mk_club('Manager Geheim 10', league=self.league)
        self.user = _mk_manager(self.seller, 'leak-manager')
        self.player = _mk_player(self.seller, 'Geheim Ziel')
        self.offer = create_offer(
            self.buyer, self.player, kauftyp='bedarf',
            wertung=_wertung('9876543'), params=self.params, saison=SAISON,
            window_id=WINDOW, dry_run=False, luecken_score=Decimal('12'),
        )

    def test_offer_manager_payload_ohne_interna(self):
        payload = offer_manager_payload(self.offer)
        for feld in VERBOTENE_FELDER:
            self.assertNotIn(feld, payload)

    def test_incoming_rows_ohne_interna(self):
        rows = incoming_ai_offers(self.seller)
        self.assertEqual(len(rows), 1)
        for feld in VERBOTENE_FELDER:
            self.assertNotIn(feld, rows[0])
        werte = ' '.join(str(v) for v in rows[0].values())
        self.assertNotIn(self.offer.noise_seed, werte)
        self.assertNotIn('9876543', werte)

    def test_reject_response_ohne_interna(self):
        self.client.force_login(self.user)
        resp = self.client.post(
            reverse('ai_offer_reject'), {'offer_id': self.offer.pk},
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode()
        self.assertNotIn('bewertung', body)
        self.assertNotIn('max_gebot', body)
        self.assertNotIn('noise_seed', body)
        self.assertNotIn(self.offer.noise_seed, body)
        self.assertNotIn('9876543', body)


class ManagerAnnehmenTests(TestCase):
    """Annahme führt den Transfer zum aktuellen Gebot aus."""

    def setUp(self):
        self.params = _params()
        self.league = _mk_league()
        self.buyer = _mk_club('KI Zahler 11', budget='50000000',
                              league=self.league)
        self.seller = _mk_club('Manager Verkauf 12', league=self.league)
        _mk_manager(self.seller, 'deal-manager')
        n = min_squad_size(SAISON)
        _fill_squad(self.seller, n + 2)
        _fill_squad(self.buyer, n)
        self.player = _mk_player(self.seller, 'Deal Spieler')
        self.offer = create_offer(
            self.buyer, self.player, kauftyp='bedarf',
            wertung=_wertung('2000000'), params=self.params, saison=SAISON,
            window_id=WINDOW, dry_run=False,
        )

    def test_annahme_fuehrt_transfer_aus(self):
        konto_vorher = self.buyer.budget
        ergebnis = manager_annehmen(self.offer, saison=SAISON)
        self.assertEqual(ergebnis['offer'].status,
                         AITransferOffer.STATUS_DEAL)
        self.player.refresh_from_db()
        self.assertEqual(self.player.club_id, self.buyer.pk)
        self.buyer.refresh_from_db()
        self.assertEqual(
            konto_vorher - self.buyer.budget, self.offer.aktuelles_gebot,
        )

    def test_annahme_nur_einmal(self):
        manager_annehmen(self.offer, saison=SAISON)
        with self.assertRaises(AIBuyerError):
            manager_annehmen(self.offer, saison=SAISON)


def _mk_442_kader(club, *, staerke_feld=65, staerke_iv1=70,
                  talent_staerke=40, talent_potential=40):
    """4-4-2-Kader: TW, LV, IV, IV, RV, LM, ZM, ZM, RM, ST, ST + IV-Talent.

    Das Talent (Potential 200er = potential × 2) zählt als IV-Backup.
    """
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


class ItoReferenzTests(TestCase):
    """Referenzfall (Spec 9.3): Verkauf eines Beste-11-IV reißt eine
    Stammlücke — der nächste Prüflauf reagiert mit einem Bedarfskauf."""

    def setUp(self):
        self.params = _params()
        self.league = _mk_league('Ito-Liga')
        self.club = _mk_club('Ito FC 13', budget='80000000',
                             league=self.league)
        self.kader = _mk_442_kader(self.club)
        self.soll = Decimal('60')

    def _analyse(self):
        return bedarfs_analyse(self.club, self.soll, self.params)

    def test_vor_verkauf_keine_iv_stammluecke(self):
        analyse = self._analyse()
        iv_zeilen = [p for p in analyse['positionen']
                     if p['position'] == 'IV']
        self.assertEqual(len(iv_zeilen), 2)
        for zeile in iv_zeilen:
            self.assertEqual(zeile['stammluecke'], Decimal('0'))
            self.assertFalse(zeile['kritisch'])

    def test_verkauf_des_iv_erzeugt_akuten_bedarf(self):
        # Ito (Beste-11-IV, Stärke 70) verlässt den Verein.
        ito = self.kader['IV1']
        ito.club = None
        ito.save(update_fields=['club'])

        analyse = self._analyse()
        akut_iv = [p for p in analyse['akut'] if p['position'] == 'IV']
        self.assertTrue(akut_iv, 'IV muss nach dem Verkauf akut sein')
        # Talent (40) rückt in die Beste-11: Stammlücke 60 − 40 = 20,
        # kein Backup mehr → kritisch → Score 10 + 20 = 30.
        self.assertEqual(akut_iv[0]['stammluecke'], Decimal('20'))
        self.assertTrue(akut_iv[0]['kritisch'])
        self.assertGreaterEqual(akut_iv[0]['score'],
                                Decimal('10') + Decimal('20'))

    def test_pruflauf_reagiert_mit_bedarfskauf(self):
        # Snapshot + offenes Transferfenster vorbereiten.
        SeasonEconomySnapshot.objects.get_or_create(
            saison=SAISON, defaults={
                'mw_median': Decimal('1000000'),
                'gehalts_anker': Decimal('1000000'),
            },
        )
        state, _ = GameSeasonState.objects.get_or_create(pk=1)
        state.transfer_window_open = True
        state.transfer_window_id = WINDOW
        state.save()

        # Ito verlässt den Verein.
        ito = self.kader['IV1']
        ito.club = None
        ito.save(update_fields=['club'])

        # Kandidat: IV bei einem Manager-Verein, zum Verkauf markiert.
        fremde_liga = _mk_league('Ito-Fremdliga')
        verkaeufer = _mk_club('Verkäufer 14', league=fremde_liga)
        _mk_manager(verkaeufer, 'ito-verkaeufer')
        _fill_squad(verkaeufer, min_squad_size(SAISON) + 2)
        kandidat = _mk_player(
            verkaeufer, 'Neuer Verteidiger', pos='IV', staerke=65,
            age=26, mw='2000000', sichtbar=True, kategorie='GELD',
        )

        run = run_club_pruflauf(
            self.club, saison=SAISON, spieltag=1, trigger='test',
            soll=self.soll,
        )
        self.assertIsNotNone(run)
        self.assertTrue(run.dry_run)
        kaeufe = run.report.get('kaeufe', [])
        bedarf = [k for k in kaeufe if k['typ'] == 'bedarf']
        self.assertTrue(bedarf, f'Kein Bedarfskauf im Report: {run.report}')
        self.assertEqual(bedarf[0]['player_id'], kandidat.pk)
        self.assertEqual(bedarf[0]['aktion'], 'berechnet')

        offer = AITransferOffer.objects.get(
            buyer_club=self.club, player=kandidat,
        )
        self.assertEqual(offer.status, AITransferOffer.STATUS_BERECHNET)
        self.assertTrue(offer.dry_run)
        self.assertEqual(offer.kauftyp, AITransferOffer.KAUFTYP_BEDARF)
        # Trockenlauf → Postfach des Verkäufers bleibt leer.
        self.assertEqual(incoming_ai_offers(verkaeufer), [])

    def test_pruflauf_idempotent_je_spieltag(self):
        state, _ = GameSeasonState.objects.get_or_create(pk=1)
        state.transfer_window_open = False
        state.save()
        run1 = run_club_pruflauf(self.club, saison=SAISON, spieltag=3)
        run2 = run_club_pruflauf(self.club, saison=SAISON, spieltag=3)
        self.assertIsNotNone(run1)
        self.assertIsNone(run2)
        self.assertEqual(
            AIBuyerRun.objects.filter(club=self.club, spieltag=3).count(), 1,
        )
