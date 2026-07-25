"""Regressionstests: Sponsor-Sieggeld bei Pokalspielen.

`_book_cup_win_sponsor_bonus` bucht das Sponsor-Sieggeld für den Pokalsieger.
Tests decken ab:
- Sieggeld wird für winner_club gebucht (V2-Pfad, reguläre Spielzeit)
- Siege nach Verlängerung (decided_by='extra_time') werden korrekt gebucht
- Siege nach Elfmeterschießen (decided_by='penalties') werden korrekt gebucht
- Verlierer bekommt kein Sieggeld
- Doppelter Aufruf bucht nicht doppelt (Idempotenz je Fixture × Contract)
- V1-Fallback (gewaehlt=True SponsorOffer) greift nur ohne V2-Contracts
"""
from decimal import Decimal

from django.test import TestCase

from game.cup_service import _book_cup_win_sponsor_bonus
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


def _make_sieggeld_contract(club, saison, betrag='50000'):
    """V2-SponsorContract mit typ=sieggeld (abgelaufen=False per Default)."""
    offer = SponsorOffer.objects.create(
        club=club, saison=saison, slot='haupt', typ='sieggeld',
        status='angenommen', fix_betrag=100_000, erwartungswert=100_000,
        sponsor_name='Sieggeld AG', variable_json={'betrag': betrag},
    )
    return SponsorContract.objects.create(
        club=club, saison=saison, slot='haupt',
        offer=offer, fix_saison=100_000,
    )


def _make_v1_sieggeld_offer(club, saison, betrag='30000'):
    """V1-SponsorOffer mit gewaehlt=True und typ=sieggeld.

    variable_json muss 'einheit': 'sieg' enthalten, weil _variable() (V1)
    die Einheit aus variable_json liest (V2 leitet sie aus offer.typ ab).
    """
    return SponsorOffer.objects.create(
        club=club, saison=saison, slot='haupt', typ='sieggeld',
        status='angenommen', fix_betrag=100_000, erwartungswert=100_000,
        sponsor_name='V1 Sieggeld AG',
        variable_json={'einheit': 'sieg', 'betrag': betrag},
        gewaehlt=True,
    )


class CupSieggeldSponsorTests(TestCase):

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

    def test_sieggeld_fuer_sieger_regulaere_spielzeit(self):
        """Grundfall V2: Sieggeld wird nach Sieg in regulärer Spielzeit gebucht."""
        contract = _make_sieggeld_contract(self.home, '1', betrag='50000')
        fixture = self._make_fixture(
            bracket_position=1,
            home_goals_90=2, away_goals_90=0,
            decided_by='regular_time', winner_club=self.home,
        )

        _book_cup_win_sponsor_bonus(fixture)

        tx = FinanceTransaction.objects.filter(
            club=self.home, typ='SPONSOR_VARIABEL',
            referenz_typ='sponsor_sieg_pokal_v2', referenz_id=contract.pk,
        )
        self.assertEqual(tx.count(), 1)
        self.assertEqual(tx.first().betrag, Decimal('50000.00'))

    def test_sieggeld_nach_verlaengerung(self):
        """V2: Sieggeld wird auch nach Verlängerungssieg korrekt gebucht."""
        contract = _make_sieggeld_contract(self.away, '1', betrag='50000')
        fixture = self._make_fixture(
            bracket_position=2,
            home_goals_90=1, away_goals_90=1,
            home_goals_et=0, away_goals_et=1,
            decided_by='extra_time', winner_club=self.away,
        )

        _book_cup_win_sponsor_bonus(fixture)

        tx = FinanceTransaction.objects.filter(
            club=self.away, typ='SPONSOR_VARIABEL',
            referenz_typ='sponsor_sieg_pokal_v2', referenz_id=contract.pk,
        )
        self.assertEqual(tx.count(), 1)
        self.assertEqual(tx.first().betrag, Decimal('50000.00'))

    def test_sieggeld_nach_elfmeterschiessen(self):
        """V2: Sieggeld wird bei decided_by='penalties' korrekt gebucht.

        Das Elfmeterschießen entscheidet das Spiel, zählt aber nicht als
        regulärer Sieg — das Sieggeld wird trotzdem für den winner_club gebucht.
        """
        contract = _make_sieggeld_contract(self.home, '1', betrag='50000')
        fixture = self._make_fixture(
            bracket_position=3,
            home_goals_90=1, away_goals_90=1,
            home_goals_et=0, away_goals_et=0,
            home_penalties=4, away_penalties=3,
            decided_by='penalties', winner_club=self.home,
        )

        _book_cup_win_sponsor_bonus(fixture)

        tx = FinanceTransaction.objects.filter(
            club=self.home, typ='SPONSOR_VARIABEL',
            referenz_typ='sponsor_sieg_pokal_v2', referenz_id=contract.pk,
        )
        self.assertEqual(tx.count(), 1)
        self.assertEqual(tx.first().betrag, Decimal('50000.00'))

    def test_verlierer_bekommt_kein_sieggeld(self):
        """Der unterlegene Verein wird nicht gebucht, auch bei aktivem Contract."""
        _make_sieggeld_contract(self.away, '1')
        fixture = self._make_fixture(
            bracket_position=4,
            home_goals_90=2, away_goals_90=0,
            decided_by='regular_time', winner_club=self.home,
        )

        _book_cup_win_sponsor_bonus(fixture)

        self.assertFalse(
            FinanceTransaction.objects.filter(
                club=self.away,
                referenz_typ__startswith='sponsor_sieg_pokal',
            ).exists()
        )

    def test_idempotent_doppelter_aufruf(self):
        """Doppelter Aufruf bucht das Sieggeld nicht zweimal (Idempotenz)."""
        contract = _make_sieggeld_contract(self.home, '1', betrag='50000')
        fixture = self._make_fixture(
            bracket_position=5,
            home_goals_90=2, away_goals_90=1,
            decided_by='regular_time', winner_club=self.home,
        )

        _book_cup_win_sponsor_bonus(fixture)
        _book_cup_win_sponsor_bonus(fixture)

        self.assertEqual(
            FinanceTransaction.objects.filter(
                club=self.home, typ='SPONSOR_VARIABEL',
                referenz_typ='sponsor_sieg_pokal_v2', referenz_id=contract.pk,
            ).count(),
            1,
        )

    def test_idempotent_nach_elfmeterschiessen(self):
        """Idempotenz gilt auch bei decided_by='penalties'."""
        contract = _make_sieggeld_contract(self.away, '1', betrag='50000')
        fixture = self._make_fixture(
            bracket_position=6,
            home_goals_90=0, away_goals_90=0,
            home_goals_et=0, away_goals_et=0,
            home_penalties=2, away_penalties=3,
            decided_by='penalties', winner_club=self.away,
        )

        _book_cup_win_sponsor_bonus(fixture)
        _book_cup_win_sponsor_bonus(fixture)

        self.assertEqual(
            FinanceTransaction.objects.filter(
                club=self.away, typ='SPONSOR_VARIABEL',
                referenz_typ='sponsor_sieg_pokal_v2', referenz_id=contract.pk,
            ).count(),
            1,
        )

    def test_v1_fallback_ohne_v2_contract(self):
        """V1-Fallback greift wenn kein V2-SponsorContract mit typ=sieggeld vorhanden."""
        _make_v1_sieggeld_offer(self.home, '1', betrag='30000')
        fixture = self._make_fixture(
            bracket_position=7,
            home_goals_90=1, away_goals_90=0,
            decided_by='regular_time', winner_club=self.home,
        )

        _book_cup_win_sponsor_bonus(fixture)

        tx = FinanceTransaction.objects.filter(
            club=self.home, typ='SPONSOR_VARIABEL',
            referenz_typ='sponsor_sieg_pokal',
        )
        self.assertEqual(tx.count(), 1)

    def test_v1_fallback_nicht_wenn_v2_contract_aktiv(self):
        """V1-Fallback wird NICHT ausgeführt wenn V2-Contract für denselben Sieger vorhanden.

        Beide Contracts (V2 und V1-Offer) gehören zum winner_club self.home.
        Die Funktion darf NUR den V2-Pfad buchen — kein zusätzlicher V1-Pfad.
        """
        contract = _make_sieggeld_contract(self.home, '1', betrag='50000')
        _make_v1_sieggeld_offer(self.home, '1', betrag='30000')
        fixture = self._make_fixture(
            bracket_position=8,
            home_goals_90=1, away_goals_90=0,
            decided_by='regular_time', winner_club=self.home,
        )

        _book_cup_win_sponsor_bonus(fixture)

        self.assertEqual(
            FinanceTransaction.objects.filter(
                club=self.home, typ='SPONSOR_VARIABEL',
                referenz_typ='sponsor_sieg_pokal_v2', referenz_id=contract.pk,
            ).count(),
            1,
            'V2-Buchung fehlt',
        )
        self.assertFalse(
            FinanceTransaction.objects.filter(
                club=self.home, referenz_typ='sponsor_sieg_pokal',
            ).exists(),
            'V1-Fallback darf nicht zusätzlich buchen wenn V2-Contract aktiv',
        )

    def test_kein_winner_keine_buchung(self):
        """Wenn winner_club=None, wird gar nichts gebucht."""
        _make_sieggeld_contract(self.home, '1')
        fixture = self._make_fixture(
            bracket_position=9,
            home_goals_90=0, away_goals_90=0,
        )

        _book_cup_win_sponsor_bonus(fixture)

        self.assertFalse(
            FinanceTransaction.objects.filter(
                referenz_typ__startswith='sponsor_sieg_pokal',
            ).exists()
        )
