"""Regressionstests: Sponsor-Torgeld bei Pokalspielen (Task-Bug: fixture.home_goals).

CupFixture hat KEIN Feld home_goals/away_goals — die Tore liegen in
home_goals_90/away_goals_90 (+ *_et bei Verlängerung). Die Buchung muss den
Endstand (90 min + Verlängerung, OHNE Elfmeterschießen) vergüten.
"""
from decimal import Decimal

from django.test import TestCase

from game.cup_service import _book_cup_torgeld_sponsor_bonus
from game.models import (
    Club, CupFixture, CupRound, CupSeason, FinanceTransaction, League,
    SponsorContract, SponsorOffer,
)


def _make_league(name='Testliga', competition_type='league'):
    return League.objects.create(
        name=name, country='Deutschland',
        competition_type=competition_type, max_teams=32,
    )


def _make_club(league, name='FC Test'):
    return Club.objects.create(
        name=name, short_name=name[:8], founded_year=2000,
        budget=1_000_000, league=league, fan_popularity=50,
    )


def _make_torgeld_contract(club, saison, betrag='10000'):
    offer = SponsorOffer.objects.create(
        club=club, saison=saison, slot='haupt', typ='torgeld',
        status='angenommen', fix_betrag=100_000, erwartungswert=100_000,
        sponsor_name='Torgeld AG', variable_json={'betrag': betrag},
    )
    return SponsorContract.objects.create(
        club=club, saison=saison, slot='haupt',
        offer=offer, fix_saison=100_000,
    )


class CupTorgeldSponsorTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.league = _make_league()
        cls.cup_league = _make_league('Testpokal', competition_type='cup')
        cls.home = _make_club(cls.league, 'FC Heim')
        cls.away = _make_club(cls.league, 'FC Gast')
        cls.cup_season = CupSeason.objects.create(
            competition=cls.cup_league, season='1',
            status=CupSeason.STATUS_SETUP,
        )
        cls.cup_round = CupRound.objects.create(
            cup_season=cls.cup_season, round_number=1,
            round_code='round_of_32', status=CupRound.STATUS_PENDING,
        )

    def _make_fixture(self, **kwargs):
        defaults = dict(
            cup_round=self.cup_round, bracket_position=1,
            home_club=self.home, away_club=self.away,
            status=CupFixture.STATUS_PLAYED,
        )
        defaults.update(kwargs)
        return CupFixture.objects.create(**defaults)

    def test_kein_attributeerror_und_buchung_nach_90_minuten(self):
        """Regressionsfall: fixture.home_goals existiert nicht — Buchung muss
        über home_goals_90 laufen und eine Torgeld-Transaktion erzeugen."""
        contract = _make_torgeld_contract(self.home, '1')
        fixture = self._make_fixture(
            home_goals_90=2, away_goals_90=0,
            decided_by='regular_time', winner_club=self.home,
        )

        _book_cup_torgeld_sponsor_bonus(fixture)

        tx = FinanceTransaction.objects.filter(
            club=self.home, typ='SPONSOR_VARIABEL',
            referenz_typ='sponsor_torgeld_v2', referenz_id=contract.pk,
        )
        self.assertEqual(tx.count(), 1)
        self.assertEqual(tx.first().betrag, Decimal('20000.00'))

    def test_verlaengerungstore_zaehlen_elfmeter_nicht(self):
        """Endstand = 90 min + Verlängerung; Elfmeterschießen zählt nicht."""
        contract = _make_torgeld_contract(self.away, '1')
        fixture = self._make_fixture(
            bracket_position=2,
            home_goals_90=1, away_goals_90=1,
            home_goals_et=0, away_goals_et=1,
            home_penalties=4, away_penalties=5,
            decided_by='penalties', winner_club=self.away,
        )

        _book_cup_torgeld_sponsor_bonus(fixture)

        tx = FinanceTransaction.objects.get(
            club=self.away, typ='SPONSOR_VARIABEL',
            referenz_typ='sponsor_torgeld_v2', referenz_id=contract.pk,
        )
        # 1 (90 min) + 1 (Verlängerung) = 2 Tore, Elfmeter zählen nicht
        self.assertEqual(tx.betrag, Decimal('20000.00'))

    def test_idempotent_pro_fixture(self):
        contract = _make_torgeld_contract(self.home, '1')
        fixture = self._make_fixture(
            bracket_position=3,
            home_goals_90=3, away_goals_90=0,
            decided_by='regular_time', winner_club=self.home,
        )

        _book_cup_torgeld_sponsor_bonus(fixture)
        _book_cup_torgeld_sponsor_bonus(fixture)

        self.assertEqual(
            FinanceTransaction.objects.filter(
                club=self.home, typ='SPONSOR_VARIABEL',
                referenz_typ='sponsor_torgeld_v2', referenz_id=contract.pk,
            ).count(),
            1,
        )

    def test_torlose_teams_buchen_nichts(self):
        _make_torgeld_contract(self.away, '1')
        fixture = self._make_fixture(
            bracket_position=4,
            home_goals_90=1, away_goals_90=0,
            decided_by='regular_time', winner_club=self.home,
        )

        _book_cup_torgeld_sponsor_bonus(fixture)

        self.assertFalse(
            FinanceTransaction.objects.filter(
                club=self.away, referenz_typ='sponsor_torgeld_v2',
            ).exists()
        )
