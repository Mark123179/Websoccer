"""Idempotenz-Regressionstests für das Sponsoring-V2-System.

Prüft:
  (a) Slot mit nur terminal-Status-Rows (abgesagt) regeneriert NICHT beim Page-Load.
  (b) Exclusivity-stornierte Offers bleiben nach erneutem generate_offers_v2-Aufruf
      unverändert — kein Re-Roll.
  (c) accept_offer_v2 wirft SponsorAcceptError wenn Sponsor in Liga bereits vergeben.
"""
from django.test import TestCase
from django.contrib.auth import get_user_model

from game.models import (
    League, Club, SponsorOffer, Sponsor,
)
from game.economy.sponsors import (
    SLOTS, generate_offers_v2, SponsorAcceptError,
)

User = get_user_model()


def _make_club(name='TestClub', league=None):
    c = Club.objects.create(
        name=name,
        short_name=name[:8],
        founded_year=2000,
        budget=1_000_000,
        fan_popularity=50,
        league=league,
    )
    return c


def _make_league(name='TestLiga'):
    return League.objects.create(name=name)


def _make_offer(club, saison, slot='haupt', status='abgesagt'):
    return SponsorOffer.objects.create(
        club=club,
        saison=saison,
        slot=slot,
        typ='sicherheit',
        status=status,
        fix_betrag=500_000,
        erwartungswert=500_000,
        sponsor_name='TestSponsor AG',
    )


class SponsoringV2IdempotenzTests(TestCase):
    """generate_offers_v2 darf nie re-rollen wenn bereits Non-Legacy-Rows vorhanden."""

    @classmethod
    def setUpTestData(cls):
        cls.league = _make_league()
        cls.club = _make_club('FC Idempotenz', league=cls.league)
        cls.saison = '1'

    def test_abgesagte_rows_blockieren_regenerierung(self):
        """Slot mit nur 'abgesagt'-Rows → generate_offers_v2 NICHT neu generieren."""
        # Vorbedingung: Slot 'haupt' hat eine abgesagte Row (z. B. aus Migration)
        o = _make_offer(self.club, self.saison, slot='haupt', status='abgesagt')
        offer_pk = o.pk

        # generate_offers_v2 aufrufen (wie View es täte)
        result = generate_offers_v2(self.club, self.saison)

        # Die Funktion soll den Slot als "vorhanden" betrachten und NICHT neu generieren
        haupt_offers = result.get('haupt', [])
        pks_in_result = [x.pk for x in haupt_offers]

        # Nur die eine ursprüngliche Row darf zurückkommen — kein neuer Offer
        self.assertIn(offer_pk, pks_in_result,
            'Die existierende abgesagte Row muss zurückgegeben werden.')
        # Kein zweiter Offer für diesen Slot darf erstellt worden sein
        db_count = SponsorOffer.objects.filter(
            club=self.club, saison=self.saison, slot='haupt',
        ).exclude(status='legacy').count()
        self.assertEqual(db_count, 1,
            'generate_offers_v2 darf bei abgesagten Rows NICHT neu generieren '
            f'(gefunden: {db_count}).')

    def test_abgesagte_rows_unveraendert_nach_wiederholtem_aufruf(self):
        """Mehrfacher Aufruf von generate_offers_v2 ändert abgesagte Rows nicht."""
        o = _make_offer(self.club, self.saison, slot='trikot', status='abgesagt')
        offer_pk_before = o.pk

        # Zwei Aufrufe
        generate_offers_v2(self.club, self.saison)
        generate_offers_v2(self.club, self.saison)

        # Exakt eine Row, Status unverändert
        rows = SponsorOffer.objects.filter(
            club=self.club, saison=self.saison, slot='trikot',
        ).exclude(status='legacy')
        self.assertEqual(rows.count(), 1)
        self.assertEqual(rows.first().pk, offer_pk_before)
        self.assertEqual(rows.first().status, 'abgesagt')

    def test_exclusivity_stornierte_offers_bleiben_abgesagt(self):
        """Exklusivitäts-stornierte Offers werden durch erneuten Aufruf nicht überschrieben."""
        # Slot 'ausruester': ein bereits abgesagter Offer (simuliert Exklusivitätsstornierung)
        o = _make_offer(self.club, self.saison, slot='ausruester', status='abgesagt')
        pks_before = {
            r.pk for r in SponsorOffer.objects.filter(
                club=self.club, saison=self.saison, slot='ausruester',
            ).exclude(status='legacy')
        }

        # Erneuter Aufruf
        generate_offers_v2(self.club, self.saison)

        pks_after = {
            r.pk for r in SponsorOffer.objects.filter(
                club=self.club, saison=self.saison, slot='ausruester',
            ).exclude(status='legacy')
        }
        self.assertEqual(pks_before, pks_after,
            'Exklusivitäts-stornierte Rows dürfen durch generate_offers_v2 nicht verändert werden.')


class SponsoringV2ExclusivityGuardTests(TestCase):
    """accept_offer_v2 Exklusivitäts-Guard: doppelter Vertragsabschluss wird verhindert."""

    @classmethod
    def setUpTestData(cls):
        cls.league = _make_league('GuardLiga')
        cls.club_a = _make_club('Club A', league=cls.league)
        cls.club_b = _make_club('Club B', league=cls.league)
        cls.saison = '1'
        cls.sponsor = Sponsor.objects.create(
            slug='test-hauptsponsor-guard',
            name='Guard Hauptsponsor GmbH',
            bereich='hauptsponsor',
        )

    def test_accept_offer_v2_wirft_bei_liga_exklusivitaet(self):
        """accept_offer_v2 muss SponsorAcceptError werfen wenn Sponsor bereits in Liga vergeben."""
        from game.models import SponsorContract
        from game.economy.sponsors import accept_offer_v2

        # Offer für Club A erstellen und Vertrag manuell anlegen (simuliert akzeptiert)
        offer_a = _make_offer(self.club_a, self.saison, slot='haupt', status='fixiert')
        SponsorOffer.objects.filter(pk=offer_a.pk).update(
            sponsor=self.sponsor, status='fixiert',
        )
        SponsorContract.objects.create(
            saison=self.saison,
            club=self.club_a,
            slot='haupt',
            sponsor=self.sponsor,
            offer=offer_a,
            fix_saison=500_000,
        )

        # Offer für Club B mit demselben Sponsor
        offer_b = _make_offer(self.club_b, self.saison, slot='haupt', status='offen')
        SponsorOffer.objects.filter(pk=offer_b.pk).update(
            sponsor=self.sponsor,
        )
        offer_b.refresh_from_db()

        # accept_offer_v2 muss SponsorAcceptError werfen (Exklusivitätskonflikt)
        with self.assertRaises(SponsorAcceptError, msg=(
            'accept_offer_v2 muss SponsorAcceptError werfen wenn derselbe Sponsor '
            'bereits in der Liga vergeben ist.'
        )):
            accept_offer_v2(offer_b)
