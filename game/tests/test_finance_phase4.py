"""Tests Finanzsystem Phase 4 — Transfermarkt (Spec Kap. 9).

Deckt ab: Kaderlimits (Basis + NLZ-Aufschlag), Ausbildungsabgabe-
Verteilrechnung (Koloto-Spec-Beispiele), atomare Transferabwicklung,
Schmerzgrenze v2 (synthetische MW-Kurve, Interpolation/Extrapolation,
Kernspieler-Zuschlag) sowie die reaktive Verhandlungsmaschine
(Deal / Gegenforderung / Absage + Cooldown, max. Runden) und die
Transfermarkt-Endpunkte (Ownership, UVK-Regel, kein Schmerzgrenzen-Leak).
"""

from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from game.economy.kader import (
    effective_squad_limit, min_squad_size, squad_count,
)
from game.economy.negotiation import (
    NegotiationError, accept_counter, cancel, place_bid,
)
from game.economy.schmerzgrenze import bewertung, kurve_wert
from game.economy.transfers import (
    KaderVoll, MindestkaderUnterschritten, TransferError,
    compute_ausbildungsabgabe, execute_free_transfer,
    execute_money_transfer, execute_swap,
)
from game.models import (
    Club, FinanceTransaction, GameSeasonState, League, ManagerProfile,
    Player, PlayerClubHistory, PlayerStrengthProfile, SeasonEconomySnapshot,
    Stadium, TransferNegotiation,
)


def _mk_league(name='Phase4-Liga'):
    league, _ = League.objects.get_or_create(name=name, country='DE')
    return league


def _mk_club(name, budget='0.00', league=None):
    return Club.objects.create(
        name=name, short_name=name[:3].upper(), founded_year=1900,
        budget=Decimal(budget), league=league or _mk_league(),
    )


def _fill_squad(club, n, age=25):
    """n Kaderspieler ohne Signal-Nebenwirkungen (bulk_create)."""
    Player.objects.bulk_create([
        Player(club=club, first_name='Kader', last_name=f'{club.short_name}{i}',
               position='MID', age=age, potential=50)
        for i in range(n)
    ])


def _mk_player(club, name='Ziel Spieler', age=25, mw=None, potential=50):
    vor, nach = name.split(' ', 1)
    return Player.objects.create(
        club=club, first_name=vor, last_name=nach, position='MID',
        age=age, market_value=mw, potential=potential,
    )


class KaderlimitTests(TestCase):
    """Kaderlimit = KADER_MAX_BASIS + NLZ-Aufschlag; Mindestkader (Kap. 9.1)."""

    def setUp(self):
        self.club = _mk_club('FC Limit')

    def test_basislimit_ohne_stadion(self):
        self.assertEqual(effective_squad_limit(self.club), 60)

    def test_nlz_aufschlag(self):
        stadium = Stadium.objects.create(
            club=self.club, name='Limit-Arena', city='Teststadt',
        )
        for level, erwartet in [(0, 60), (1, 63), (2, 66), (3, 70)]:
            stadium.nlz_level = level
            stadium.save(update_fields=['nlz_level'])
            club = Club.objects.get(pk=self.club.pk)
            self.assertEqual(effective_squad_limit(club), erwartet)

    def test_mindestkader_und_zaehlung(self):
        self.assertEqual(min_squad_size(), 18)
        _fill_squad(self.club, 4)
        self.assertEqual(squad_count(self.club), 4)


class AusbildungsabgabeTests(TestCase):
    """Verteilrechnung nach den Koloto-Spec-Beispielen (Kap. 9.1)."""

    def setUp(self):
        GameSeasonState.objects.create(current_season=6)
        league = _mk_league()
        self.basel = _mk_club('FC Basel', league=league)
        self.manutd = _mk_club('Man Utd', league=league)
        self.leipzig = _mk_club('RB Leipzig', league=league)
        self.kaeufer = _mk_club('Käufer FC', budget='200000000', league=league)

    def _stationen(self, player, stationen):
        PlayerClubHistory.objects.filter(player=player).delete()
        PlayerClubHistory.objects.bulk_create([
            PlayerClubHistory(player=player, club=club, season=season)
            for club, season in stationen
        ])

    def test_tausch_beispiel_koloto_19(self):
        # 19-Jähriger, Basis 15 Mio: 3 Anteile à 250k; Zahler-Anteil entfällt.
        koloto = _mk_player(None, 'Koloto Jung', age=19)
        self._stationen(koloto, [
            (self.basel, 3), (self.basel, 4), (self.manutd, 5),
        ])
        v = compute_ausbildungsabgabe(
            koloto, self.manutd, Decimal('15000000'), '5')
        self.assertEqual(v['anteile_gesamt'], 3)
        self.assertEqual(v['anteile_fremd'], 2)
        self.assertEqual(v['empfaenger'], {self.basel.pk: Decimal('500000.00')})
        self.assertEqual(v['gesamt'], Decimal('500000.00'))

    def test_verkauf_beispiel_koloto_23(self):
        # 23-Jähriger, Basis 60 Mio, cutoff = 6+(21−23) = 4: Stationen S0–S4
        # zählen (5 Anteile à 600k), S5 nicht mehr; Eigenanteile entfallen.
        koloto = _mk_player(None, 'Koloto Alt', age=23)
        verkaeufer = _mk_club('Verkäufer AC')
        self._stationen(koloto, [
            (self.basel, 0), (self.basel, 1), (self.leipzig, 2),
            (verkaeufer, 3), (verkaeufer, 4), (verkaeufer, 5),
        ])
        v = compute_ausbildungsabgabe(
            koloto, verkaeufer, Decimal('60000000'), '6')
        self.assertEqual(v['anteile_gesamt'], 5)
        self.assertEqual(v['empfaenger'], {
            self.basel.pk: Decimal('1200000.00'),
            self.leipzig.pk: Decimal('600000.00'),
        })
        # Verkäufer netto: 60 Mio − 1,8 Mio erhobene Fremdanteile = 58,2 Mio.
        self.assertEqual(v['gesamt'], Decimal('1800000.00'))

    def test_geldtransfer_atomar_mit_abgabe(self):
        verkaeufer = _mk_club('Verkauf 04')
        _fill_squad(verkaeufer, 18)
        spieler = _mk_player(verkaeufer, 'Tim Talent', age=21, mw=8_000_000)
        spieler.sale_category = 'GELD'
        spieler.sale_visible_to_ai = True
        spieler.save(update_fields=['sale_category', 'sale_visible_to_ai'])
        # Auto-Station (Verkäufer, S6) + Basel S0 → 2 Anteile, 1 fremd.
        PlayerClubHistory.objects.create(
            player=spieler, club=self.basel, season=0)

        execute_money_transfer(spieler, self.kaeufer, Decimal('10000000'))

        spieler.refresh_from_db()
        for club in (verkaeufer, self.kaeufer, self.basel):
            club.refresh_from_db()
        self.assertEqual(spieler.club_id, self.kaeufer.pk)
        self.assertEqual(spieler.sale_category, 'UVK')
        self.assertFalse(spieler.sale_visible_to_ai)
        self.assertFalse(spieler.is_on_transfer_list)
        self.assertEqual(self.kaeufer.budget, Decimal('190000000.00'))
        # Abgabe 5 % × 10 Mio = 500k, 2 Anteile → Basel 250k, Eigenanteil weg.
        self.assertEqual(self.basel.budget, Decimal('250000.00'))
        self.assertEqual(verkaeufer.budget, Decimal('9750000.00'))
        typen = set(
            FinanceTransaction.objects
            .filter(referenz_typ='transfer', referenz_id=spieler.pk)
            .values_list('typ', flat=True)
        )
        self.assertEqual(
            typen, {'TRANSFER_AUS', 'TRANSFER_EIN',
                    'AUSBILDUNG_AUS', 'AUSBILDUNG_EIN'})

    def test_kaderplatz_prueft_limit(self):
        verkaeufer = _mk_club('Voll United')
        _fill_squad(verkaeufer, 18)
        spieler = _mk_player(verkaeufer, 'Max Voll', age=25)
        voller_kaeufer = _mk_club('Randvoll FC', budget='50000000')
        _fill_squad(voller_kaeufer, 60)
        with self.assertRaises(KaderVoll):
            execute_money_transfer(spieler, voller_kaeufer, Decimal('1000000'))

    def test_mindestkader_blockiert_verkauf(self):
        verkaeufer = _mk_club('Dünn 09')
        _fill_squad(verkaeufer, 17)
        spieler = _mk_player(verkaeufer, 'Letzter Mann', age=25)  # → 18 gesamt
        with self.assertRaises(MindestkaderUnterschritten):
            execute_money_transfer(spieler, self.kaeufer, Decimal('1000000'))

    def test_doppelkauf_schutz_bei_veralteter_instanz(self):
        # Simuliert das Race zweier Bieter: Die In-Memory-Instanz kennt noch
        # den alten Verein, in der DB ist der Spieler schon weg → Abbruch.
        verkaeufer = _mk_club('Race United')
        _fill_squad(verkaeufer, 19)
        spieler = _mk_player(verkaeufer, 'Heiß Begehrt', age=25)
        anderer = _mk_club('Schnell FC')
        Player.objects.filter(pk=spieler.pk).update(club=anderer)
        with self.assertRaises(TransferError):
            execute_money_transfer(spieler, self.kaeufer, Decimal('1000000'))
        self.kaeufer.refresh_from_db()
        self.assertEqual(self.kaeufer.budget, Decimal('200000000.00'))

    def test_doppelwechsel_schutz_abloesefrei(self):
        # Gleicher Schutz im ablösefreien Pfad: Instanz veraltet → Abbruch.
        spieler = _mk_player(None, 'Frei Vogel', age=25, mw=100_000)
        anderer = _mk_club('Zugriff 07')
        Player.objects.filter(pk=spieler.pk).update(club=anderer)
        with self.assertRaises(TransferError):
            execute_free_transfer(spieler, self.kaeufer)

    def test_doppelwechsel_schutz_tausch(self):
        user_a = User.objects.create_user('tausch_a', password='x')
        user_b = User.objects.create_user('tausch_b', password='x')
        club_a = _mk_club('Tausch A')
        club_a.managed_by = user_a.manager_profile
        club_a.save(update_fields=['managed_by'])
        club_b = _mk_club('Tausch B')
        club_b.managed_by = user_b.manager_profile
        club_b.save(update_fields=['managed_by'])
        pa = _mk_player(club_a, 'Anton Ass', age=25, mw=100_000)
        pb = _mk_player(club_b, 'Bruno Bär', age=25, mw=100_000)
        Player.objects.filter(pk=pb.pk).update(club=self.kaeufer)
        with self.assertRaises(TransferError):
            execute_swap(pa, pb)
        pa.refresh_from_db()
        self.assertEqual(pa.club_id, club_a.pk)


def _mk_snapshot(saison='7'):
    return SeasonEconomySnapshot.objects.create(
        saison=saison,
        mw_median=Decimal('1000000'),
        gehalts_anker=Decimal('1000000'),
        staerke_median=Decimal('60'),
        potential_median=Decimal('70'),
        mw_kurve_json={'55': 1_000_000, '60': 1_500_000, '65': 2_000_000},
    )


def _profil(player, staerke):
    return PlayerStrengthProfile.objects.create(
        player=player, base_strength=Decimal(str(staerke)),
    )


class SchmerzgrenzeTests(TestCase):
    """Schmerzgrenze v2 mit synthetischer MW-Kurve (Kap. 9.2)."""

    def setUp(self):
        GameSeasonState.objects.create(current_season=7)
        self.snap = _mk_snapshot()
        self.club = _mk_club('KI Verein')
        # Drei klar stärkere Profis → Zielspieler ist kein Top-3-Kernspieler.
        for i in range(3):
            star = _mk_player(self.club, f'Star Nr{i}', age=28)
            _profil(star, 90)

    def test_kurve_interpolation_und_untergrenze(self):
        kurve = self.snap.mw_kurve_json
        self.assertEqual(kurve_wert(kurve, 50), Decimal('1000000.0'))
        self.assertEqual(float(kurve_wert(kurve, 57.5)), 1_250_000.0)

    def test_kurve_extrapolation_letzter_gradient(self):
        # Letzter Gradient: 500k je 5 Punkte → 75 ⇒ 2 Mio + 10×100k = 3 Mio.
        self.assertEqual(float(kurve_wert(self.snap.mw_kurve_json, 75)),
                         3_000_000.0)

    def test_gegenwartswert_pfad_mw(self):
        p = _mk_player(self.club, 'Peter Präsenz', age=27, mw=2_000_000,
                       potential=60)
        _profil(p, 60)
        w = bewertung(p, saison='7')
        # Pfad 1: 2 Mio × 1,0 (Median) × 1,0 (26–29) schlägt Kurve×Restnutzwert.
        self.assertEqual(w['schmerzgrenze'], Decimal('2000000.00'))
        self.assertEqual(w['zukunftswert'], Decimal('0.00'))
        self.assertFalse(w['kernspieler'])

    def test_zukunftswert_fuer_talent(self):
        # Anderes U21-Toptalent zuerst → Zielspieler kein Kernspieler.
        anderes = _mk_player(self.club, 'Top Talent', age=19, potential=90)
        self.assertIsNotNone(anderes)
        p = _mk_player(self.club, 'Junger Rohdiamant', age=18, mw=50_000,
                       potential=80)
        _profil(p, 55)
        w = bewertung(p, saison='7')
        # Zukunft: Kurve(80)=3,5 Mio × Realisierung(0,45−25×0,002−1×0,015=0,385).
        self.assertEqual(w['zukunftswert'], Decimal('1347500.00'))
        self.assertEqual(w['schmerzgrenze'], w['zukunftswert'])
        self.assertFalse(w['kernspieler'])

    def test_kernspieler_zuschlag(self):
        p = _mk_player(self.club, 'Kern Kraft', age=27, mw=2_000_000,
                       potential=60)
        _profil(p, 95)  # Top-3 des Kaders.
        w = bewertung(p, saison='7')
        self.assertTrue(w['kernspieler'])
        self.assertEqual(w['schmerzgrenze'],
                         w['gegenwartswert'] * Decimal('1.5'))

    def test_ohne_profil_keine_bewertung(self):
        p = _mk_player(self.club, 'Ohne Profil', age=25)
        self.assertIsNone(bewertung(p, saison='7'))


class NegotiationTests(TestCase):
    """Reaktive KI-Verkäufer: Deal / Gegenforderung / Absage (Kap. 9.2/9.3)."""

    def setUp(self):
        GameSeasonState.objects.create(current_season=7)
        _mk_snapshot()
        league = _mk_league()
        self.seller = _mk_club('KI Kickers', league=league)  # managerlos
        _fill_squad(self.seller, 18, age=28)
        for i in range(3):
            _profil(_mk_player(self.seller, f'Anker Nr{i}', age=29), 90)
        # Zielspieler: Grenze deterministisch 2 Mio (±5 % Streuung).
        self.ziel = _mk_player(self.seller, 'Ziel Objekt', age=27,
                               mw=2_000_000, potential=60)
        _profil(self.ziel, 60)
        self.buyer = _mk_club('Bieter BC', budget='50000000', league=league)

    def test_hohes_gebot_fuehrt_zum_deal(self):
        res = place_bid(self.ziel, self.buyer, Decimal('2200000'))
        self.assertEqual(res['ergebnis'], 'deal')
        self.ziel.refresh_from_db()
        self.buyer.refresh_from_db()
        self.seller.refresh_from_db()
        self.assertEqual(self.ziel.club_id, self.buyer.pk)
        self.assertEqual(self.buyer.budget, Decimal('47800000.00'))
        self.assertEqual(self.seller.budget, Decimal('2200000.00'))
        self.assertEqual(res['negotiation'].status,
                         TransferNegotiation.STATUS_DEAL)

    def test_moderates_gebot_gegenforderung_und_annahme(self):
        res = place_bid(self.ziel, self.buyer, Decimal('1600000'))
        self.assertEqual(res['ergebnis'], 'gegenforderung')
        forderung = res['gegenforderung']
        # Grenze_eff ∈ [1,9; 2,1] Mio × 1,1, quantisiert auf 10k.
        self.assertGreaterEqual(forderung, Decimal('2080000'))
        self.assertLessEqual(forderung, Decimal('2320000'))
        self.assertEqual(forderung % Decimal('10000'), 0)

        deal = accept_counter(res['negotiation'])
        self.assertEqual(deal['ergebnis'], 'deal')
        self.ziel.refresh_from_db()
        self.seller.refresh_from_db()
        self.assertEqual(self.ziel.club_id, self.buyer.pk)
        self.assertEqual(self.seller.budget, forderung)

    def test_niedriges_gebot_absage_mit_cooldown(self):
        res = place_bid(self.ziel, self.buyer, Decimal('1000000'))
        self.assertEqual(res['ergebnis'], 'abgelehnt')
        self.assertIsNotNone(res['negotiation'].cooldown_until)
        with self.assertRaises(NegotiationError):
            place_bid(self.ziel, self.buyer, Decimal('2200000'))
        self.ziel.refresh_from_db()
        self.assertEqual(self.ziel.club_id, self.seller.pk)

    def test_max_runden_beendet_verhandlung(self):
        r1 = place_bid(self.ziel, self.buyer, Decimal('1600000'))
        self.assertEqual(r1['ergebnis'], 'gegenforderung')
        r2 = place_bid(self.ziel, self.buyer, Decimal('1610000'))
        self.assertEqual(r2['ergebnis'], 'gegenforderung')
        self.assertEqual(r2['negotiation'].runde, 2)
        r3 = place_bid(self.ziel, self.buyer, Decimal('1620000'))
        self.assertEqual(r3['ergebnis'], 'abgelehnt')
        self.assertEqual(r3['negotiation'].runde, 3)

    def test_abbrechen_setzt_cooldown(self):
        res = place_bid(self.ziel, self.buyer, Decimal('1600000'))
        nego = cancel(res['negotiation'])
        self.assertEqual(nego.status, TransferNegotiation.STATUS_ABGELEHNT)
        self.assertIsNotNone(nego.cooldown_until)

    def test_managergefuehrter_verein_verkauft_nicht(self):
        user = User.objects.create_user('boss', password='x')
        self.seller.managed_by = user.manager_profile
        self.seller.save(update_fields=['managed_by'])
        with self.assertRaises(NegotiationError):
            place_bid(self.ziel, self.buyer, Decimal('2200000'))


class TransfermarktViewTests(TestCase):
    """Endpunkte: Ownership, UVK-Regel, kein Schmerzgrenzen-Leak."""

    def setUp(self):
        GameSeasonState.objects.create(current_season=7)
        _mk_snapshot()
        league = _mk_league()
        self.user_a = User.objects.create_user('managera', password='x')
        self.club_a = _mk_club('Eigner FC', budget='50000000', league=league)
        self.club_a.managed_by = self.user_a.manager_profile
        self.club_a.save(update_fields=['managed_by'])
        self.eigener = _mk_player(self.club_a, 'Eigen Gewächs', age=24)

        self.user_b = User.objects.create_user('managerb', password='x')
        self.club_b = _mk_club('Rivale 05', budget='50000000', league=league)
        self.club_b.managed_by = self.user_b.manager_profile
        self.club_b.save(update_fields=['managed_by'])

        self.ki_club = _mk_club('KI 1900', league=league)
        _fill_squad(self.ki_club, 18, age=28)
        self.ki_spieler = _mk_player(self.ki_club, 'Kauf Objekt', age=27,
                                     mw=2_000_000, potential=60)
        _profil(self.ki_spieler, 60)

        self.sale_url = reverse('squad_set_sale_status', args=[self.club_a.pk])

    def test_sale_status_nur_fuer_eigentuemer(self):
        self.client.force_login(self.user_b)
        r = self.client.post(self.sale_url, {
            'player_ids': [self.eigener.pk], 'sale_category': 'GELD',
        })
        self.assertEqual(r.status_code, 403)

    def test_sale_status_setzt_kategorie_und_sichtbarkeit(self):
        self.client.force_login(self.user_a)
        r = self.client.post(self.sale_url, {
            'player_ids': [self.eigener.pk],
            'sale_category': 'GELD_TAUSCH', 'sale_visible_to_ai': '1',
        })
        self.assertEqual(r.status_code, 200)
        self.eigener.refresh_from_db()
        self.assertEqual(self.eigener.sale_category, 'GELD_TAUSCH')
        self.assertTrue(self.eigener.sale_visible_to_ai)

    def test_uvk_erzwingt_unsichtbar(self):
        self.client.force_login(self.user_a)
        self.client.post(self.sale_url, {
            'player_ids': [self.eigener.pk],
            'sale_category': 'UVK', 'sale_visible_to_ai': '1',
        })
        self.eigener.refresh_from_db()
        self.assertFalse(self.eigener.sale_visible_to_ai)

    def test_fremde_spieler_nicht_setzbar(self):
        self.client.force_login(self.user_a)
        r = self.client.post(self.sale_url, {
            'player_ids': [self.ki_spieler.pk], 'sale_category': 'GELD',
        })
        self.assertEqual(r.status_code, 404)
        self.ki_spieler.refresh_from_db()
        self.assertEqual(self.ki_spieler.sale_category, 'UVK')

    def test_gebot_leakt_keine_schmerzgrenze(self):
        # Einziges Profil im KI-Kader → Kernspieler-Zuschlag: Grenze 3 Mio
        # (±5 %); 2,4 Mio liegt deterministisch in der Gegenforderungs-Zone.
        self.client.force_login(self.user_b)
        r = self.client.post(reverse('transfer_place_bid'), {
            'player_id': self.ki_spieler.pk, 'betrag': '2400000',
        })
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data['ok'])
        self.assertEqual(data['ergebnis'], 'gegenforderung')
        text = r.content.decode('utf-8').lower()
        self.assertNotIn('schmerzgrenze', text)
        self.assertNotIn('noise_seed', text)
        self.assertNotIn('grenze_eff', text)

    def test_gebot_ohne_verein_verboten(self):
        ohne = User.objects.create_user('ohneclub', password='x')
        self.client.force_login(ohne)
        r = self.client.post(reverse('transfer_place_bid'), {
            'player_id': self.ki_spieler.pk, 'betrag': '1000000',
        })
        self.assertEqual(r.status_code, 403)
