"""Tests Finanzsystem Phase 3 — Stadionökonomie + Stadionumfeld (Spec Kap. 5).

Deckt ab: Nachfrageformel (Basis/Beliebtheit/Gegner/Preis, kategorieweise
Kappung), Ausbau-Kostenbänder inkl. Splitting + Kategorie-Faktoren, Bauzeit
und Fertigstellung (resolve_due_expansions), laufende Stadionkosten
(Unterhalt + Spieltagskosten), Umfeld-Zusatzeinnahme sowie den Split des
Stadionumfeld-Zustands (Layout global / Ambiente per Verein).
"""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from game.economy.params import get_decimal, get_param
from game.economy.stadium import (
    basisnachfrage, beliebtheitsfaktor, compute_demand, expansion_bauzeit_tage,
    gegnerfaktor, pending_expansion_seats, preisfaktor, resolve_due_expansions,
    spieltagskosten, umfeld_einnahme, umfeld_stufen, unterhalt_rate,
)
from game.models import (
    Club, ClubStadionumfeldState, FinanceTransaction, GameSeasonState, League,
    MatchdayRevenue, Player, Stadium, StadionumfeldConfig, StadiumExpansion,
)
from game.stadium_costs import (
    get_expansion_cost, get_kostenmatrix, get_preis_pro_platz, max_kapazitaet,
)
from game.stadium_revenue import record_matchday_revenue


def _mk_club(name='FC Test', budget='0.00', league=None, fan_popularity=60):
    if league is None:
        league, _ = League.objects.get_or_create(name='Phase3-Liga', country='DE')
    return Club.objects.create(
        name=name, short_name=name[:3].upper(), founded_year=1900,
        budget=Decimal(budget), league=league, fan_popularity=fan_popularity,
    )


def _mk_stadium(club, steh=8000, sitz=10000, vip=500, city='Teststadt', **extra):
    return Stadium.objects.create(
        club=club, name=f'{club.short_name}-Arena', city=city,
        nord_standing=steh, ost_seating=sitz, west_vip=vip, **extra,
    )


def _mk_squad(club, mw_mio=50, n=20):
    """n Spieler mit gleichem Marktwert → Kader-MW = mw_mio Mio €."""
    einzel = Decimal(mw_mio) * Decimal('1000000') / n
    for i in range(n):
        Player.objects.create(
            club=club, first_name='P', last_name=f'{club.short_name}{i}',
            position='MID', market_value=einzel, age=25,
        )


class KostenbandTests(TestCase):
    """Ausbau: Bänder nach Zielkapazität × Kategorie-Faktor (Kap. 5.3)."""

    def test_elversberg_referenzbeispiel(self):
        # 10.000 → 25.000 Sitzplätze = 10.000×1.500 + 5.000×2.500 = 27,5 Mio.
        self.assertEqual(
            get_expansion_cost(10_000, 'SITZ', 15_000),
            Decimal('27500000'),
        )

    def test_kategorie_faktoren(self):
        faktoren = get_param('AUSBAU_FAKTOR_KATEGORIE')
        basis = get_expansion_cost(10_000, 'SITZ', 1_000)
        self.assertEqual(
            get_expansion_cost(10_000, 'STEH', 1_000),
            basis * Decimal(str(faktoren['steh'])),
        )
        self.assertEqual(
            get_expansion_cost(10_000, 'VIP', 1_000),
            basis * Decimal(str(faktoren['vip'])),
        )

    def test_splitting_ueber_bandgrenze(self):
        baender = {int(g): Decimal(str(p)) for g, p in get_param('AUSBAU_BAENDER')}
        grenzen = sorted(baender)
        g1, g2 = grenzen[0], grenzen[1]
        # 500 unterhalb der ersten Grenze + 500 darüber.
        erwartet = baender[g1] * 500 + baender[g2] * 500
        self.assertEqual(
            get_expansion_cost(g1 - 500, 'SITZ', 1_000), erwartet)

    def test_kostenmatrix_und_preis_pro_platz(self):
        matrix = get_kostenmatrix(10_000)
        self.assertEqual(set(matrix), {'STEH', 'SITZ', 'VIP'})
        self.assertEqual(
            Decimal(str(matrix['SITZ'])), get_preis_pro_platz(10_000, 'SITZ'))
        self.assertLess(matrix['STEH'], matrix['SITZ'])
        self.assertLess(matrix['SITZ'], matrix['VIP'])

    def test_max_kapazitaet_aus_parameter(self):
        self.assertEqual(max_kapazitaet(), int(get_param('STADION_MAX')))


class BauzeitTests(TestCase):
    """Bauzeit 1 Saison (7 Bautage) pro 15.000 Plätze; Fertigstellung."""

    def setUp(self):
        GameSeasonState.objects.create(current_season=0)
        self.club = _mk_club()
        self.stadium = _mk_stadium(self.club)

    def test_bauzeit_raster(self):
        self.assertEqual(expansion_bauzeit_tage(0), 0)
        self.assertEqual(expansion_bauzeit_tage(1_000), 1)
        self.assertEqual(expansion_bauzeit_tage(15_000), 7)
        self.assertEqual(expansion_bauzeit_tage(45_000), 21)

    def _mk_expansion(self, delta_tage, seats=1_000, applied=False):
        return StadiumExpansion.objects.create(
            stadium=self.stadium, stand='NORD', seat_type='STEH',
            seats_added=seats, cost=Decimal('1'),
            completes_at=timezone.now() + timedelta(days=delta_tage),
            applied=applied,
        )

    def test_faellige_erweiterung_wird_angewendet(self):
        vorher = self.stadium.nord_standing
        e = self._mk_expansion(-1, seats=2_000)
        self.assertEqual(resolve_due_expansions(self.stadium), 1)
        self.stadium.refresh_from_db()
        e.refresh_from_db()
        self.assertTrue(e.applied)
        self.assertEqual(self.stadium.nord_standing, vorher + 2_000)
        # Idempotent: zweiter Lauf ändert nichts mehr.
        self.assertEqual(resolve_due_expansions(self.stadium), 0)
        self.stadium.refresh_from_db()
        self.assertEqual(self.stadium.nord_standing, vorher + 2_000)

    def test_zukuenftige_erweiterung_bleibt_offen(self):
        vorher = self.stadium.nord_standing
        e = self._mk_expansion(+3, seats=2_000)
        self.assertEqual(resolve_due_expansions(self.stadium), 0)
        self.stadium.refresh_from_db()
        e.refresh_from_db()
        self.assertFalse(e.applied)
        self.assertEqual(self.stadium.nord_standing, vorher)
        self.assertEqual(pending_expansion_seats(self.stadium), 2_000)

    def test_pending_zaehlt_nur_offene(self):
        self._mk_expansion(+3, seats=1_500)
        self._mk_expansion(-1, seats=999, applied=True)
        self.assertEqual(pending_expansion_seats(self.stadium), 1_500)


class NachfrageTests(TestCase):
    """Nachfrageformel Kap. 5.1: Faktoren + kategorieweise Kappung."""

    def setUp(self):
        GameSeasonState.objects.create(current_season=0)
        self.club = _mk_club(fan_popularity=60)
        self.stadium = _mk_stadium(self.club)
        _mk_squad(self.club, mw_mio=50)

    def test_basisnachfrage_referenzwerte(self):
        # Spec-Referenz: 50 Mio → ~13.400; 1.440 Mio → ~92.600.
        self.assertAlmostEqual(
            basisnachfrage(50_000_000), 13_400, delta=700)
        self.assertAlmostEqual(
            basisnachfrage(1_440_000_000), 92_600, delta=4_000)
        self.assertEqual(basisnachfrage(0), 0.0)

    def test_beliebtheitsfaktor_grenzen(self):
        self.assertAlmostEqual(beliebtheitsfaktor(1), 0.705)
        self.assertAlmostEqual(beliebtheitsfaktor(100), 1.2)
        self.assertAlmostEqual(beliebtheitsfaktor(60), 1.0)

    def test_preisfaktor_klemmen(self):
        referenz = get_param('PREIS_REFERENZ')['sitz']
        self.assertAlmostEqual(preisfaktor(referenz, referenz), 1.0)
        self.assertEqual(preisfaktor(0, referenz), 1.3)       # Freikarten
        self.assertEqual(preisfaktor(referenz * 100, referenz), 0.5)
        self.assertEqual(preisfaktor(0.01, referenz), 1.3)

    def test_gegnerfaktor_fallbacks(self):
        p = get_param('GEGNERFAKTOR')
        self.assertEqual(gegnerfaktor(self.club), 1.0)
        self.assertAlmostEqual(
            gegnerfaktor(self.club, opponent_strength=0), float(p['mw_min']))
        self.assertAlmostEqual(
            gegnerfaktor(self.club, opponent_strength=100), float(p['mw_max']))

    def test_gegnerfaktor_derby_gleiche_stadt(self):
        gegner = _mk_club(name='Stadtrivale', league=self.club.league)
        _mk_stadium(gegner, city='Teststadt')
        _mk_squad(gegner, mw_mio=50)
        p = get_param('GEGNERFAKTOR')
        ohne = gegnerfaktor(self.club, opponent_club=gegner)
        # Gleicher MW → Basis 1,0 + Derby-Zuschlag.
        self.assertAlmostEqual(ohne, 1.0 + float(p['derby']), places=6)

    def test_compute_demand_kappung_und_summen(self):
        demand = compute_demand(self.club, self.stadium)
        kat = demand['kategorien']
        gesamt_z = sum(kat[k]['zuschauer'] for k in kat)
        gesamt_e = sum(kat[k]['einnahmen'] for k in kat)
        self.assertEqual(demand['zuschauer_gesamt'], gesamt_z)
        self.assertEqual(demand['einnahmen_gesamt'], gesamt_e)
        for k in kat:
            self.assertLessEqual(kat[k]['zuschauer'], kat[k]['kapazitaet'])
        self.assertGreater(demand['zuschauer_gesamt'], 0)
        self.assertLessEqual(demand['auslastung_pct'], 100.0)

    def test_record_matchday_revenue_bucht_ticket(self):
        vorher = self.club.budget
        entry = record_matchday_revenue(self.club, competition_name='Bundesliga')
        self.club.refresh_from_db()
        self.assertEqual(self.club.budget, vorher + entry.revenue_total)
        self.assertEqual(
            entry.attendance,
            entry.attendance_standing + entry.attendance_seating
            + entry.attendance_vip,
        )
        tx = FinanceTransaction.objects.get(club=self.club, typ='TICKET')
        self.assertEqual(tx.betrag, entry.revenue_total)


class StadionkostenTests(TestCase):
    """Unterhalt (jeder Spieltag) + Spieltagskosten (Heimspiel), Kap. 5.4."""

    def setUp(self):
        GameSeasonState.objects.create(current_season=0)
        self.club = _mk_club()
        self.stadium = _mk_stadium(self.club, steh=10_000, sitz=9_000, vip=1_000)

    def test_unterhalt_formel(self):
        platz = get_decimal('UNTERHALT_PLATZ')
        divisor = get_decimal('GEHALT_DIVISOR')
        erwartet = (Decimal(20_000) * platz / divisor).quantize(Decimal('0.01'))
        self.assertEqual(unterhalt_rate(self.stadium), erwartet)

    def test_spieltagskosten_formel(self):
        satz = get_decimal('KOSTEN_BESUCHER')
        self.assertEqual(
            spieltagskosten(12_345),
            (Decimal(12_345) * satz).quantize(Decimal('0.01')),
        )
        self.assertEqual(spieltagskosten(0), Decimal('0.00'))

    def test_umfeld_einnahme(self):
        satz = get_decimal('UMFELD_EURO_BESUCHER_JE_STUFE')
        self.assertEqual(umfeld_stufen(self.stadium), 0)
        self.assertEqual(umfeld_einnahme(self.stadium, 30_000), Decimal('0.00'))
        self.stadium.nlz_level = 2
        self.stadium.training_level = 1
        self.stadium.save(update_fields=['nlz_level', 'training_level'])
        self.assertEqual(umfeld_stufen(self.stadium), 3)
        self.assertEqual(
            umfeld_einnahme(self.stadium, 30_000),
            (Decimal(3) * satz * Decimal(30_000)).quantize(Decimal('0.01')),
        )


class StadionumfeldSplitTests(TestCase):
    """Layout global (Singleton) vs. Ambiente per Verein (Kap. 5 / Task)."""

    def setUp(self):
        self.admin = User.objects.create_superuser('admin', password='x')

    def test_save_trennt_layout_und_ambiente(self):
        self.client.force_login(self.admin)
        resp = self.client.post(
            reverse('stadionumfeld_save'),
            data='{"positions": {"a": 1}, "selected": "nlz", "day": false, "wetter": "regen", "hack": 1}',
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        config = StadionumfeldConfig.get_solo()
        self.assertEqual(config.state.get('positions'), {'a': 1})
        self.assertEqual(config.state.get('selected'), 'nlz')
        # Ambiente-Keys + unbekannte Keys landen NICHT im Singleton.
        self.assertNotIn('day', config.state)
        self.assertNotIn('wetter', config.state)
        self.assertNotIn('hack', config.state)

    def test_save_verlangt_superuser(self):
        user = User.objects.create_user('normalo', password='x')
        self.client.force_login(user)
        resp = self.client.post(
            reverse('stadionumfeld_save'), data='{}',
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 403)

    def test_club_state_for_club_erzeugt_zeile(self):
        club = _mk_club(name='Umfeld-Club')
        row = ClubStadionumfeldState.for_club(club)
        self.assertEqual(row.club, club)
        row.state = {'day': True}
        row.save(update_fields=['state', 'updated_at'])
        self.assertEqual(
            ClubStadionumfeldState.for_club(club).state, {'day': True})
