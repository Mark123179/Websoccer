"""Tests Finanzsystem Phase 2 — Einnahmen komplett (Spec Kap. 4, 6, 7, 8, 13, 15).

Deckt ab: TV-Töpfe/Sockel/Saisonausschüttung (tv.py), Pokalprämien
(events.py), Sponsorsystem inkl. Wahl-View (sponsors.py), Abfindungen
(severance.py), Saison-Jobs (season_jobs.py) und Genesis/Startbudget
(startbudget.py). Schwerpunkt überall: korrekte Beträge + Idempotenz.
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from game.economy.events import pokal_basis, sync_cup_premiums
from game.economy.params import get_decimal, get_param
from game.economy.season_jobs import finance_season_close, finance_season_open
from game.economy.severance import book_abfindung
from game.economy.sponsors import (
    SponsorChoiceError, book_sieg_bonus, book_zieljaeger_bonus,
    book_zuschauer_bonus, choose_offer, generate_offers, get_active_offer,
    sponsorwert,
)
from game.economy.startbudget import apply_genesis, startbudget
from game.economy.tv import (
    _linear_degressiv, distribute_season_tv, ensure_tv_pots, liga_topf,
    tv_sockel_rate, update_koeffizienten,
)
from game.models import (
    Club, CupFixture, CupRound, CupSeason, FinanceTransaction,
    GameSeasonState, LandKoeffizient, League, LeagueStandings, Player,
    SeasonFinanceState, SeasonFixture, SeasonGoal, SponsorOffer, TVPot,
    VereinKoeffizient,
)

LAND = 'Testonia'


def _mk_club(name, league, budget='0.00'):
    return Club.objects.create(
        name=name, short_name=name[:3].upper(), founded_year=1900,
        budget=Decimal(budget), league=league,
    )


def _mk_league_with_clubs(n=3, land=LAND, name='Testonia-Liga'):
    """Liga mit n Vereinen und Ringspielplan (jeder einmal Heimverein)."""
    league = League.objects.create(name=name, country=land)
    clubs = [_mk_club(f'FC Test {i + 1}', league) for i in range(n)]
    for md in range(1, n + 1):
        SeasonFixture.objects.create(
            league=league, season='0', matchday=md,
            home_club=clubs[md - 1], away_club=clubs[md % n], is_played=True,
        )
    return league, clubs


class TVMoneyTests(TestCase):
    def setUp(self):
        GameSeasonState.objects.create(current_season=0)
        # Kunstland mit höchster 5-Jahreswertung → Rang 1 → größter Topf.
        LandKoeffizient.objects.create(land=LAND, saison='0', punkte=99999)
        self.league, self.clubs = _mk_league_with_clubs(3)

    def test_pot_frozen_at_rank1(self):
        pots = ensure_tv_pots('0')
        self.assertIn(LAND, pots)
        self.assertEqual(pots[LAND].rang, 1)
        erwartet = Decimal(str(get_param('TV_TOEPFE', '0')['1']))
        self.assertEqual(Decimal(pots[LAND].gesamt), erwartet)
        # Idempotent: zweiter Aufruf erzeugt keine neuen Zeilen.
        anzahl = TVPot.objects.filter(saison='0').count()
        ensure_tv_pots('0')
        self.assertEqual(TVPot.objects.filter(saison='0').count(), anzahl)

    def test_sockel_rate_formula(self):
        topf = liga_topf(self.league, '0')
        sockel = Decimal(str(get_param('TV_VERTEILUNG', '0')['sockel']))
        erwartet = (topf * sockel / 3 / 3).quantize(Decimal('0.01'))
        self.assertEqual(tv_sockel_rate(self.league, '0'), erwartet)

    def test_linear_degressiv_sums_and_order(self):
        anteile = _linear_degressiv(Decimal('600'), 3)
        self.assertEqual(anteile, [Decimal('300'), Decimal('200'), Decimal('100')])

    def test_distribute_season_tv_amounts_and_idempotenz(self):
        for pos, club in enumerate(self.clubs, start=1):
            LeagueStandings.objects.create(
                league=self.league, club=club, season='0',
                position=pos, points=30 - pos,
            )
        # Verein 3 (Tabellenletzter) hat die höchste 5-Jahreswertung.
        VereinKoeffizient.objects.create(
            club=self.clubs[2], saison='0', punkte=100)

        res = distribute_season_tv(self.league, '0')
        self.assertEqual(res['errors'], [])
        self.assertEqual(len(res['booked']), 3)

        topf = liga_topf(self.league, '0')
        verteilung = get_param('TV_VERTEILUNG', '0')
        platz_summe = topf * Decimal(str(verteilung['platz']))
        koeff_summe = topf * Decimal(str(verteilung['koeff']))

        platz1 = FinanceTransaction.objects.get(
            club=self.clubs[0], typ='TV_PLATZ')
        self.assertEqual(
            platz1.betrag, (platz_summe * 3 / 6).quantize(Decimal('0.01')))
        letzter = FinanceTransaction.objects.get(
            club=self.clubs[2], typ='TV_PLATZ')
        self.assertEqual(
            letzter.betrag, (platz_summe * 1 / 6).quantize(Decimal('0.01')))

        # Koeffanteil: Verein 3 führt die 5-Jahreswertung an → größter Anteil.
        koeff3 = FinanceTransaction.objects.get(
            club=self.clubs[2], typ='TV_KOEFF')
        self.assertEqual(
            koeff3.betrag, (koeff_summe * 3 / 6).quantize(Decimal('0.01')))

        # Idempotenz: zweiter Lauf bucht nichts nach.
        anzahl = FinanceTransaction.objects.count()
        res2 = distribute_season_tv(self.league, '0')
        self.assertEqual(len(res2['skipped']), 3)
        self.assertEqual(FinanceTransaction.objects.count(), anzahl)

    def test_update_koeffizienten_carry_forward(self):
        VereinKoeffizient.objects.create(
            club=self.clubs[0], saison='0', punkte=50)
        res = update_koeffizienten('0')
        self.assertFalse(res['skipped'])

        zeile = LandKoeffizient.objects.get(land=LAND, saison='1')
        self.assertEqual(zeile.punkte, (Decimal('99999') / 5).quantize(Decimal('0.001')))
        vk = VereinKoeffizient.objects.get(club=self.clubs[0], saison='1')
        self.assertEqual(vk.punkte, Decimal('10.000'))

        # Idempotent: vorhandene Folgesaison-Zeilen werden nie überschrieben.
        res2 = update_koeffizienten('0')
        self.assertEqual(res2['laender'], 0)
        self.assertEqual(res2['vereine'], 0)


class CupPremiumTests(TestCase):
    def setUp(self):
        GameSeasonState.objects.create(current_season=0)
        LandKoeffizient.objects.create(land=LAND, saison='0', punkte=99999)
        self.liga = League.objects.create(name='Testonia-Liga', country=LAND)
        self.pokal = League.objects.create(name='Testonia-Pokal', country=LAND)
        self.clubs = [_mk_club(f'PC {i + 1}', self.liga) for i in range(4)]
        self.cup = CupSeason.objects.create(competition=self.pokal, season='0')
        r1 = CupRound.objects.create(
            cup_season=self.cup, round_number=1, round_code='R1')
        CupFixture.objects.create(
            cup_round=r1, bracket_position=1,
            home_club=self.clubs[0], away_club=self.clubs[1])
        CupFixture.objects.create(
            cup_round=r1, bracket_position=2,
            home_club=self.clubs[2], away_club=self.clubs[3])
        r2 = CupRound.objects.create(
            cup_season=self.cup, round_number=2, round_code='F')
        CupFixture.objects.create(
            cup_round=r2, bracket_position=1,
            home_club=self.clubs[0], away_club=self.clubs[2])

    def test_verdopplung_und_titelgeld(self):
        basis = pokal_basis(self.cup, '0')
        self.assertGreater(basis, 0)

        self.cup.status = CupSeason.STATUS_COMPLETED
        self.cup.winner_club = self.clubs[0]
        self.cup.save()

        res = sync_cup_premiums(self.cup)
        self.assertEqual(res['errors'], [])
        # 4 Teilnehmer R1 + 2 Teilnehmer R2 + Titelgeld = 7 Buchungen.
        self.assertEqual(res['booked'], 7)

        r1_tx = FinanceTransaction.objects.get(
            club=self.clubs[3], typ='PRAEMIE_POKAL')
        self.assertEqual(r1_tx.betrag, basis)

        r2_tx = FinanceTransaction.objects.get(
            club=self.clubs[2], typ='PRAEMIE_POKAL',
            referenz_typ='pokal_runde:2')
        self.assertEqual(r2_tx.betrag, (basis * 2).quantize(Decimal('0.01')))

        faktor = Decimal(str(get_param('POKAL_TITEL_FAKTOR', '0')))
        titel = FinanceTransaction.objects.get(
            club=self.clubs[0], typ='PRAEMIE_POKAL', referenz_typ='pokal_titel')
        self.assertEqual(titel.betrag, (basis * faktor).quantize(Decimal('0.01')))

    def test_sync_ist_idempotent(self):
        sync_cup_premiums(self.cup)
        anzahl = FinanceTransaction.objects.count()
        res2 = sync_cup_premiums(self.cup)
        self.assertEqual(res2['booked'], 0)
        self.assertEqual(FinanceTransaction.objects.count(), anzahl)


class SponsorSystemTests(TestCase):
    def setUp(self):
        GameSeasonState.objects.create(current_season=0)
        LandKoeffizient.objects.create(land=LAND, saison='0', punkte=99999)
        self.league, self.clubs = _mk_league_with_clubs(2)
        self.club = self.clubs[0]

    def test_generate_offers_idempotent_mit_sicherheit(self):
        offers = generate_offers(self.club, '0')
        self.assertGreaterEqual(len(offers), 3)
        self.assertLessEqual(len(offers), 5)
        self.assertIn('sicherheit', {o.typ for o in offers})

        wieder = generate_offers(self.club, '0')
        self.assertEqual({o.pk for o in offers}, {o.pk for o in wieder})

    def test_erwartungswert_kalibriert(self):
        wert = sponsorwert(self.club, '0')
        streuung = Decimal(str(get_param('SPONSOR_STREUUNG', '0')))
        toleranz = wert * (streuung + Decimal('0.001'))
        for offer in generate_offers(self.club, '0'):
            self.assertLessEqual(abs(offer.erwartungswert - wert), toleranz)
            if offer.typ == 'sicherheit':
                self.assertEqual(offer.fix_betrag, offer.erwartungswert)

    def test_choose_offer_bindend_je_saison(self):
        offers = generate_offers(self.club, '0')
        choose_offer(offers[0])
        self.assertTrue(SponsorOffer.objects.get(pk=offers[0].pk).gewaehlt)
        # Zweitwahl verboten, erneute Wahl desselben Angebots ist No-op.
        with self.assertRaises(SponsorChoiceError):
            choose_offer(offers[1])
        choose_offer(offers[0])
        self.assertEqual(SponsorOffer.objects.filter(
            club=self.club, saison='0', gewaehlt=True).count(), 1)

    def test_autopick_nimmt_sicherheit(self):
        self.assertIsNone(get_active_offer(self.club, '0', autopick=False))
        gewaehlt = get_active_offer(self.club, '0', autopick=True)
        self.assertEqual(gewaehlt.typ, 'sicherheit')
        # UI-Pfad sieht dieselbe Wahl.
        self.assertEqual(
            get_active_offer(self.club, '0', autopick=False).pk, gewaehlt.pk)

    def test_sieg_bonus_idempotent_je_referenz(self):
        offer = SponsorOffer.objects.create(
            club=self.club, saison='0', typ='sieggeld', sponsor_name='TestBet',
            fix_betrag=Decimal('1000000'), erwartungswert=Decimal('2000000'),
            variable_json={'einheit': 'sieg', 'betrag': '50000'}, gewaehlt=True,
        )
        tx = book_sieg_bonus(
            self.club, offer, '0', beschreibung='Sieggeld Test',
            referenz_typ='sponsor_sieg_liga', referenz_id=4711, spieltag=1)
        self.assertEqual(tx.betrag, Decimal('50000.00'))
        self.assertIsNone(book_sieg_bonus(
            self.club, offer, '0', beschreibung='Sieggeld Test',
            referenz_typ='sponsor_sieg_liga', referenz_id=4711, spieltag=1))
        self.assertEqual(FinanceTransaction.objects.filter(
            typ='SPONSOR_VARIABEL').count(), 1)

    def test_zuschauer_bonus_betrag(self):
        offer = SponsorOffer.objects.create(
            club=self.club, saison='0', typ='zuschauer', sponsor_name='ArenaCo',
            fix_betrag=Decimal('1000000'), erwartungswert=Decimal('2000000'),
            variable_json={'einheit': 'besucher', 'betrag': '0.5'}, gewaehlt=True,
        )
        tx = book_zuschauer_bonus(self.club, offer, 10000, '0', spieltag=1)
        self.assertEqual(tx.betrag, Decimal('5000.00'))

    def test_zieljaeger_bonus_nur_bei_erreichtem_ziel(self):
        offer = SponsorOffer.objects.create(
            club=self.club, saison='0', typ='zieljaeger', sponsor_name='Zenith',
            fix_betrag=Decimal('1200000'), erwartungswert=Decimal('2000000'),
            variable_json={'einheit': 'ziel', 'betrag': '800000',
                           'ziel_label': 'Klassenerhalt'},
            gewaehlt=True,
        )
        # Ohne ausgewertetes Ziel: nichts.
        self.assertIsNone(book_zieljaeger_bonus(self.club, '0'))

        SeasonGoal.objects.create(
            club=self.club, season_number=0, goal_tier='klassenerhalt',
            rank_in_league=1, achieved=True, evaluated_at=timezone.now(),
        )
        tx = book_zieljaeger_bonus(self.club, '0')
        self.assertEqual(tx.betrag, Decimal('800000.00'))
        self.assertEqual(tx.referenz_id, offer.pk)
        # Idempotent.
        self.assertIsNone(book_zieljaeger_bonus(self.club, '0'))


class SeveranceTests(TestCase):
    def setUp(self):
        GameSeasonState.objects.create(current_season=0)
        league = League.objects.create(name='Testonia-Liga', country=LAND)
        self.club = _mk_club('FC Trauer', league)
        self.player = Player.objects.create(
            club=self.club, first_name='Toni', last_name='Test', age=26,
            position='Sturm', main_position_1='ST',
            nationalities='Deutschland', market_value=Decimal('1000000'),
        )

    def test_karriereende_zahlt_nichts(self):
        self.assertIsNone(book_abfindung(self.player, 'karriereende', '0'))
        self.assertFalse(FinanceTransaction.objects.exists())

    def test_todesfall_altersfaktor_und_idempotenz(self):
        faktor = Decimal(str(get_param('ABFINDUNG_TOD', '0')['25-28']))
        tx = book_abfindung(self.player, 'tod', '0')
        self.assertEqual(
            tx.betrag, (faktor * Decimal('1000000')).quantize(Decimal('0.01')))
        self.assertIsNone(book_abfindung(self.player, 'tod', '0'))
        self.assertEqual(FinanceTransaction.objects.filter(
            typ='ABFINDUNG').count(), 1)

    def test_unbekannter_grund(self):
        with self.assertRaises(ValueError):
            book_abfindung(self.player, 'urlaub', '0')


class SeasonJobsTests(TestCase):
    def setUp(self):
        GameSeasonState.objects.create(current_season=0)
        LandKoeffizient.objects.create(land=LAND, saison='0', punkte=99999)
        self.league, self.clubs = _mk_league_with_clubs(2)

    def test_open_idempotent(self):
        res = finance_season_open('0')
        self.assertFalse(res['skipped'])
        self.assertGreater(res['sponsor_offers'], 0)
        self.assertTrue(SeasonFinanceState.objects.get(saison='0').opened_at)
        for club in self.clubs:
            self.assertTrue(SponsorOffer.objects.filter(
                club=club, saison='0').exists())

        self.assertTrue(finance_season_open('0')['skipped'])

    def test_close_teillauf_dann_abschluss(self):
        for pos, club in enumerate(self.clubs, start=1):
            LeagueStandings.objects.create(
                league=self.league, club=club, season='0',
                position=pos, points=10 - pos,
            )
        # Ein Spieltag offen → Teil-Lauf, closed_at bleibt leer.
        SeasonFixture.objects.filter(
            league=self.league, matchday=2).update(is_played=False)
        res = finance_season_close('0')
        self.assertIn('hinweis', res)
        self.assertIsNone(SeasonFinanceState.objects.get(saison='0').closed_at)
        self.assertFalse(FinanceTransaction.objects.filter(
            typ='TV_PLATZ').exists())

        # Alle Spiele durch → Ausschüttung + endgültiger Abschluss.
        SeasonFixture.objects.filter(league=self.league).update(is_played=True)
        res2 = finance_season_close('0')
        self.assertNotIn('hinweis', res2)
        state = SeasonFinanceState.objects.get(saison='0')
        self.assertTrue(state.closed_at)
        self.assertTrue(state.report_json)
        self.assertEqual(FinanceTransaction.objects.filter(
            typ='TV_PLATZ').count(), 2)

        self.assertTrue(finance_season_close('0')['skipped'])


class StartbudgetTests(TestCase):
    def setUp(self):
        GameSeasonState.objects.create(current_season=0)
        LandKoeffizient.objects.create(land=LAND, saison='0', punkte=99999)
        self.league, self.clubs = _mk_league_with_clubs(2)

    def test_startbudget_mindest_und_quote(self):
        minimum = get_decimal('STARTBUDGET_MIN', '0')
        wert = startbudget(self.clubs[0], '0')
        self.assertGreaterEqual(wert, minimum)

    def test_genesis_ersetzt_kontostand_idempotent(self):
        club = self.clubs[0]
        Club.objects.filter(pk=club.pk).update(budget=Decimal('123456789.00'))
        club.refresh_from_db()

        res = apply_genesis('0')
        self.assertEqual(res['errors'], [])
        club.refresh_from_db()
        self.assertEqual(club.budget, startbudget(club, '0'))
        self.assertTrue(FinanceTransaction.objects.filter(
            club=club, typ='KORREKTUR_ADMIN', referenz_typ='genesis').exists())

        res2 = apply_genesis('0')
        namen = {c.name for c in self.clubs}
        self.assertTrue(namen.issubset(set(res2['skipped'])))
        self.assertEqual(FinanceTransaction.objects.filter(
            typ='KORREKTUR_ADMIN', referenz_typ='genesis',
            club__in=self.clubs).count(), 2)

    def test_genesis_dry_run_bucht_nichts(self):
        res = apply_genesis('0', dry_run=True)
        namen = {e['club'] for e in res['clubs']}
        self.assertTrue({c.name for c in self.clubs}.issubset(namen))
        self.assertFalse(FinanceTransaction.objects.filter(
            club__in=self.clubs).exists())


class SponsorChooseViewTests(TestCase):
    def setUp(self):
        GameSeasonState.objects.create(current_season=0)
        LandKoeffizient.objects.create(land=LAND, saison='0', punkte=99999)
        self.league, self.clubs = _mk_league_with_clubs(2)
        self.club = self.clubs[0]

        User = get_user_model()
        self.user = User.objects.create_user('sponsor-tester', password='x')
        profile = self.user.manager_profile
        self.club.managed_by = profile
        self.club.save(update_fields=['managed_by'])

        self.offers = generate_offers(self.club, '0')
        self.url = reverse('management_sponsor_choose')

    def test_wahl_setzt_gewaehlt(self):
        self.client.force_login(self.user)
        resp = self.client.post(self.url, {'offer_id': self.offers[0].pk})
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(SponsorOffer.objects.get(pk=self.offers[0].pk).gewaehlt)

    def test_zweitwahl_wird_abgelehnt(self):
        self.client.force_login(self.user)
        self.client.post(self.url, {'offer_id': self.offers[0].pk})
        self.client.post(self.url, {'offer_id': self.offers[1].pk})
        self.assertFalse(SponsorOffer.objects.get(pk=self.offers[1].pk).gewaehlt)
        self.assertEqual(SponsorOffer.objects.filter(
            club=self.club, gewaehlt=True).count(), 1)

    def test_fremdes_angebot_nicht_waehlbar(self):
        fremd = generate_offers(self.clubs[1], '0')[0]
        self.client.force_login(self.user)
        resp = self.client.post(self.url, {'offer_id': fremd.pk})
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(SponsorOffer.objects.get(pk=fremd.pk).gewaehlt)

    def test_anonym_wird_umgeleitet(self):
        resp = self.client.post(self.url, {'offer_id': self.offers[0].pk})
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/auth/login/', resp['Location'])
        self.assertFalse(SponsorOffer.objects.filter(gewaehlt=True).exists())
