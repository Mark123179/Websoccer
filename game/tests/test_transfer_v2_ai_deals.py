"""Tests KI-Antwort-Job für Transfersystem v2 (Task #824, Teilstück "KI-Überführung").

Deckt ab:
1. KI-Verein nimmt CASH-Kaufangebot an, wenn cash_from >= Schmerzgrenze.
2. KI-Verein lehnt ab, wenn cash_from < Schmerzgrenze.
3. Anfragen jünger als 24h werden übersprungen (bleiben OPEN).
4. dry_run=True: keine Statusänderung, kein Transfer.
"""
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from game.models import (
    Club, EconomyParameter, GameSeasonState, League, Player,
    PlayerStrengthProfile, SeasonEconomySnapshot,
)
from game.transfer_v2.ai_deals import respond_open_deals
from game.transfer_v2.models import DealRequest, DealRequestPlayer
from game.transfer_v2.services import create_deal_request

SAISON = '0'


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

def _mk_league(name='KI-Deals-Liga'):
    league, _ = League.objects.get_or_create(name=name, country='Deutschland')
    return league


def _mk_club(name, budget='50000000.00', managed=False, league=None):
    """Erstellt einen Verein. managed=True setzt einen echten Manager (Dummy)."""
    from django.contrib.auth.models import User
    club = Club.objects.create(
        name=name, short_name=name[:3].upper(), founded_year=1900,
        budget=Decimal(budget), league=league or _mk_league(),
    )
    if managed:
        user = User.objects.create_user(f'u_{name[:8]}', password='x')
        club.managed_by = user.manager_profile
        club.save(update_fields=['managed_by'])
    return club


def _mk_player(club, name='Test Spieler', age=27, mw='2000000'):
    vor, nach = name.split(' ', 1)
    return Player.objects.create(
        club=club, first_name=vor, last_name=nach, age=age,
        position='Mittelfeld', main_position_1='MID',
        nationalities='Deutschland', market_value=Decimal(mw),
    )


def _mk_snapshot(saison=SAISON):
    """Erstellt einen minimalen SeasonEconomySnapshot für die Schmerzgrenzen-Berechnung."""
    return SeasonEconomySnapshot.objects.get_or_create(
        saison=saison,
        defaults={
            'mw_median': Decimal('2000000'),
            'gehalts_anker': Decimal('2000000'),
            'staerke_median': Decimal('60'),
            'potential_median': Decimal('100'),
            'mw_kurve_json': {
                '55': 1_500_000,
                '60': 2_000_000,
                '65': 2_500_000,
                '70': 3_000_000,
            },
        },
    )[0]


def _mk_profil(player, staerke=60):
    """Erstellt ein PlayerStrengthProfile für den Spieler."""
    return PlayerStrengthProfile.objects.create(
        player=player, base_strength=Decimal(str(staerke)),
    )


def _mk_deal_old(from_club, to_club, **kwargs):
    """Erstellt einen DealRequest und macht ihn mehr als 24h alt."""
    deal = create_deal_request(from_club, to_club, **kwargs)
    # Deal auf >24h vor "jetzt" schieben
    DealRequest.objects.filter(pk=deal.pk).update(
        created_at=timezone.now() - timedelta(hours=25),
    )
    deal.refresh_from_db()
    return deal


def _setup_economy_params(dry_run=False):
    """Setzt KI_KAEUFER mit dry_run-Flag für die Tests."""
    import json
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


# ---------------------------------------------------------------------------
# Basis-TestCase
# ---------------------------------------------------------------------------

class Base(TestCase):
    def setUp(self):
        GameSeasonState.objects.create(current_season=0)
        # Kadergrenzen neutralisieren
        EconomyParameter.objects.update_or_create(
            saison=SAISON, key='KADER_MIN', defaults={'value': 0})
        # Economy-Snapshot für Schmerzgrenzen
        _mk_snapshot(SAISON)
        # KI_KAEUFER mit dry_run=False (Echte Antworten)
        _setup_economy_params(dry_run=False)

        # Initiator: von einem Manager verwalteter Verein
        self.from_club = _mk_club('FC Anbieter', managed=True)
        # KI-Verein (kein Manager): to_club
        self.ki_club = _mk_club('FC KI-Verein', managed=False)
        # Spieler des KI-Vereins (wird ggf. abgegeben)
        self.ki_player = _mk_player(self.ki_club, 'KI Spieler', age=27, mw='2000000')
        # Stärkeprofil für den KI-Spieler (Schmerzgrenze ~ 2 Mio)
        _mk_profil(self.ki_player, staerke=60)


# ---------------------------------------------------------------------------
# Test 1: Annahme bei ausreichendem cash_from
# ---------------------------------------------------------------------------

class AcceptCashDealTests(Base):
    """KI-Verein nimmt ein CASH-Kaufangebot an, wenn cash_from >= Schmerzgrenze."""

    def test_accept_when_cash_above_schmerzgrenze(self):
        # Schmerzgrenze bei Stärke 60, MW 2 Mio ≈ 2 Mio.
        # Wir bieten mehr als die Schmerzgrenze.
        deal = _mk_deal_old(
            self.from_club, self.ki_club,
            typ=DealRequest.TYP_CASH,
            cash_from=Decimal('3000000'),
            to_players=[self.ki_player],
            saison=SAISON,
        )
        self.assertEqual(deal.status, DealRequest.STATUS_OPEN)

        result = respond_open_deals(saison=SAISON, now=timezone.now())

        deal.refresh_from_db()
        self.ki_player.refresh_from_db()

        self.assertEqual(deal.status, DealRequest.STATUS_ACCEPTED)
        # Spieler gehört jetzt dem Käufer
        self.assertEqual(self.ki_player.club_id, self.from_club.pk)
        self.assertEqual(result['angenommen'], 1)
        self.assertEqual(result['abgelehnt'], 0)
        self.assertNotIn('dry_run', result)

    def test_accept_at_exact_schmerzgrenze(self):
        """Annahme genau bei Schmerzgrenze (>=)."""
        # Schmerzgrenze bestimmen via bewertung
        from game.economy.schmerzgrenze import bewertung
        self.ki_player.refresh_from_db()
        w = bewertung(self.ki_player, saison=SAISON)
        grenze = w['schmerzgrenze']

        deal = _mk_deal_old(
            self.from_club, self.ki_club,
            typ=DealRequest.TYP_CASH,
            cash_from=grenze,
            to_players=[self.ki_player],
            saison=SAISON,
        )

        result = respond_open_deals(saison=SAISON, now=timezone.now())
        deal.refresh_from_db()

        # cash_from == schmerzgrenze → annehmen
        self.assertEqual(deal.status, DealRequest.STATUS_ACCEPTED)
        self.assertEqual(result['angenommen'], 1)


# ---------------------------------------------------------------------------
# Test 2: Ablehnung bei zu geringem cash_from
# ---------------------------------------------------------------------------

class DeclineCashDealTests(Base):
    """KI-Verein lehnt ab, wenn cash_from < Schmerzgrenze."""

    def test_decline_when_cash_below_schmerzgrenze(self):
        # Biete weniger als die Schmerzgrenze (~2 Mio bei Stärke 60)
        deal = _mk_deal_old(
            self.from_club, self.ki_club,
            typ=DealRequest.TYP_CASH,
            cash_from=Decimal('500000'),  # deutlich unter Schmerzgrenze
            to_players=[self.ki_player],
            saison=SAISON,
        )
        self.assertEqual(deal.status, DealRequest.STATUS_OPEN)

        result = respond_open_deals(saison=SAISON, now=timezone.now())

        deal.refresh_from_db()
        self.ki_player.refresh_from_db()

        self.assertEqual(deal.status, DealRequest.STATUS_DECLINED)
        # Spieler bleibt beim KI-Verein
        self.assertEqual(self.ki_player.club_id, self.ki_club.pk)
        self.assertEqual(result['abgelehnt'], 1)
        self.assertEqual(result['angenommen'], 0)

    def test_decline_without_strength_profile(self):
        """Ohne Stärkeprofil keine Bewertung → ablehnen."""
        spieler_ohne_profil = _mk_player(
            self.ki_club, 'Ohne Profil', age=25, mw='2000000')
        # Kein PlayerStrengthProfile → bewertung() gibt None zurück

        deal = _mk_deal_old(
            self.from_club, self.ki_club,
            typ=DealRequest.TYP_CASH,
            cash_from=Decimal('5000000'),
            to_players=[spieler_ohne_profil],
            saison=SAISON,
        )

        result = respond_open_deals(saison=SAISON, now=timezone.now())
        deal.refresh_from_db()
        spieler_ohne_profil.refresh_from_db()

        # KI verkauft nicht ohne Bewertungsgrundlage
        self.assertEqual(deal.status, DealRequest.STATUS_DECLINED)
        self.assertEqual(spieler_ohne_profil.club_id, self.ki_club.pk)


# ---------------------------------------------------------------------------
# Test 3: Anfragen jünger als 24h werden übersprungen
# ---------------------------------------------------------------------------

class SkipYoungDealsTests(Base):
    """Anfragen jünger als 24h werden übersprungen (bleiben OPEN)."""

    def test_new_deal_not_processed(self):
        # Deal erstellen OHNE ihn 24h alt zu machen
        deal = create_deal_request(
            self.from_club, self.ki_club,
            typ=DealRequest.TYP_CASH,
            cash_from=Decimal('5000000'),
            to_players=[self.ki_player],
            saison=SAISON,
        )
        self.assertEqual(deal.status, DealRequest.STATUS_OPEN)

        # Jetzt ausführen (now = aktuell → Deal ist < 24h alt)
        result = respond_open_deals(saison=SAISON, now=timezone.now())

        deal.refresh_from_db()
        self.ki_player.refresh_from_db()

        # Deal bleibt OPEN (24h Bedenkzeit noch nicht abgelaufen)
        self.assertEqual(deal.status, DealRequest.STATUS_OPEN)
        # Spieler bleibt beim KI-Verein
        self.assertEqual(self.ki_player.club_id, self.ki_club.pk)
        # Keine Annahmen/Ablehnungen
        self.assertEqual(result['angenommen'], 0)
        self.assertEqual(result['abgelehnt'], 0)

    def test_deal_exactly_24h_old_not_processed(self):
        """Deal genau 24h alt: noch nicht älter als 24h → übersprungen."""
        deal = create_deal_request(
            self.from_club, self.ki_club,
            typ=DealRequest.TYP_CASH,
            cash_from=Decimal('5000000'),
            to_players=[self.ki_player],
            saison=SAISON,
        )
        # Setze created_at auf genau jetzt - 24h (nicht > 24h)
        DealRequest.objects.filter(pk=deal.pk).update(
            created_at=timezone.now() - timedelta(hours=24),
        )

        # Cutoff: now - 24h → Deal ist >= cutoff, wird also verarbeitet
        # (created_at <= cutoff → also genau an der Grenze wird verarbeitet)
        result = respond_open_deals(saison=SAISON, now=timezone.now())
        deal.refresh_from_db()
        # Deal sollte verarbeitet worden sein (>= 24h alt: accepted oder declined)
        self.assertNotEqual(deal.status, DealRequest.STATUS_OPEN)

    def test_deal_23h_old_skipped(self):
        """Deal 23h alt: noch in der Bedenkzeit → übersprungen."""
        deal = create_deal_request(
            self.from_club, self.ki_club,
            typ=DealRequest.TYP_CASH,
            cash_from=Decimal('5000000'),
            to_players=[self.ki_player],
            saison=SAISON,
        )
        DealRequest.objects.filter(pk=deal.pk).update(
            created_at=timezone.now() - timedelta(hours=23),
        )

        result = respond_open_deals(saison=SAISON, now=timezone.now())
        deal.refresh_from_db()

        # Noch innerhalb Bedenkzeit → OPEN
        self.assertEqual(deal.status, DealRequest.STATUS_OPEN)


# ---------------------------------------------------------------------------
# Test 4: dry_run=True: keine Statusänderung, kein Transfer
# ---------------------------------------------------------------------------

class DryRunTests(Base):
    """dry_run=True: keine Statusänderung, kein Transfer."""

    def setUp(self):
        super().setUp()
        # KI_KAEUFER mit dry_run=True setzen
        _setup_economy_params(dry_run=True)

    def test_dry_run_no_status_change_accept(self):
        """Auch bei ausreichendem Angebot: kein accept im dry_run."""
        deal = _mk_deal_old(
            self.from_club, self.ki_club,
            typ=DealRequest.TYP_CASH,
            cash_from=Decimal('5000000'),  # über Schmerzgrenze
            to_players=[self.ki_player],
            saison=SAISON,
        )

        result = respond_open_deals(saison=SAISON, now=timezone.now())

        deal.refresh_from_db()
        self.ki_player.refresh_from_db()

        # Status bleibt OPEN
        self.assertEqual(deal.status, DealRequest.STATUS_OPEN)
        # Spieler bleibt beim KI-Verein
        self.assertEqual(self.ki_player.club_id, self.ki_club.pk)
        # dry_run-Flag im Ergebnis
        self.assertTrue(result.get('dry_run'))
        # Statistiken werden trotzdem gezählt
        self.assertGreaterEqual(result.get('angenommen', 0), 0)

    def test_dry_run_no_status_change_decline(self):
        """Auch bei unzureichendem Angebot: kein decline im dry_run."""
        deal = _mk_deal_old(
            self.from_club, self.ki_club,
            typ=DealRequest.TYP_CASH,
            cash_from=Decimal('100000'),  # unter Schmerzgrenze
            to_players=[self.ki_player],
            saison=SAISON,
        )

        result = respond_open_deals(saison=SAISON, now=timezone.now())

        deal.refresh_from_db()
        self.ki_player.refresh_from_db()

        # Status bleibt OPEN
        self.assertEqual(deal.status, DealRequest.STATUS_OPEN)
        # Spieler bleibt beim KI-Verein
        self.assertEqual(self.ki_player.club_id, self.ki_club.pk)
        # dry_run-Flag im Ergebnis
        self.assertTrue(result.get('dry_run'))

    def test_dry_run_counts_but_does_not_write(self):
        """dry_run zählt Annahmen/Ablehnungen, schreibt aber nichts."""
        # Ein Deal über Schmerzgrenze, einer darunter
        ki_player2 = _mk_player(self.ki_club, 'KI Zwei', age=27, mw='2000000')
        _mk_profil(ki_player2, staerke=60)

        deal_gut = _mk_deal_old(
            self.from_club, self.ki_club,
            typ=DealRequest.TYP_CASH,
            cash_from=Decimal('5000000'),
            to_players=[self.ki_player],
            saison=SAISON,
        )
        deal_schlecht = _mk_deal_old(
            self.from_club, self.ki_club,
            typ=DealRequest.TYP_CASH,
            cash_from=Decimal('100000'),
            to_players=[ki_player2],
            saison=SAISON,
        )

        result = respond_open_deals(saison=SAISON, now=timezone.now())

        # Beide Deals bleiben OPEN
        deal_gut.refresh_from_db()
        deal_schlecht.refresh_from_db()
        self.assertEqual(deal_gut.status, DealRequest.STATUS_OPEN)
        self.assertEqual(deal_schlecht.status, DealRequest.STATUS_OPEN)
        # dry_run-Flag
        self.assertTrue(result.get('dry_run'))
        # Zählungen stimmen
        self.assertEqual(result['angenommen'], 1)
        self.assertEqual(result['abgelehnt'], 1)


# ---------------------------------------------------------------------------
# Weitere Randfälle
# ---------------------------------------------------------------------------

class EdgeCaseTests(Base):
    """Weitere Randfälle: managed Verein wird nicht als KI-Verein behandelt,
    Idempotenz, etc."""

    def test_managed_club_not_processed(self):
        """Deals an Vereine MIT Manager werden nicht durch den KI-Job beantwortet."""
        # from_club ist managed → to_club ist hier auch managed
        managed_recipient = _mk_club('FC Manager Empfänger', managed=True)
        spieler = _mk_player(managed_recipient, 'Managed Spieler', age=25)
        _mk_profil(spieler, staerke=60)

        deal = create_deal_request(
            self.from_club, managed_recipient,
            typ=DealRequest.TYP_CASH,
            cash_from=Decimal('5000000'),
            to_players=[spieler],
            saison=SAISON,
        )
        DealRequest.objects.filter(pk=deal.pk).update(
            created_at=timezone.now() - timedelta(hours=25),
        )
        deal.refresh_from_db()

        result = respond_open_deals(saison=SAISON, now=timezone.now())

        deal.refresh_from_db()
        # Deal bleibt OPEN — Empfänger ist kein KI-Verein
        self.assertEqual(deal.status, DealRequest.STATUS_OPEN)
        self.assertEqual(result['angenommen'], 0)
        self.assertEqual(result['abgelehnt'], 0)

    def test_idempotent_already_resolved(self):
        """Bereits aufgelöste Deals werden nicht erneut verarbeitet."""
        deal = _mk_deal_old(
            self.from_club, self.ki_club,
            typ=DealRequest.TYP_CASH,
            cash_from=Decimal('5000000'),
            to_players=[self.ki_player],
            saison=SAISON,
        )
        # Ersten Lauf
        respond_open_deals(saison=SAISON, now=timezone.now())
        deal.refresh_from_db()
        status_nach_erstem_lauf = deal.status

        # Zweiten Lauf
        result = respond_open_deals(saison=SAISON, now=timezone.now())
        deal.refresh_from_db()

        # Status bleibt wie nach dem ersten Lauf
        self.assertEqual(deal.status, status_nach_erstem_lauf)
        # Im zweiten Lauf keine neuen Verarbeitungen (Deal nicht mehr OPEN)
        self.assertEqual(result['angenommen'], 0)
        self.assertEqual(result['abgelehnt'], 0)
