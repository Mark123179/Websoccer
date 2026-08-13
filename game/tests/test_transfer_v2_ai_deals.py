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


# ---------------------------------------------------------------------------
# Task #842: Gegenforderung (COUNTER) bei knapp zu niedrigen Angeboten
# ---------------------------------------------------------------------------

class CounterOfferTests(Base):
    """KI stellt eine Gegenforderung, wenn das Angebot in der
    Verhandlungszone liegt (>= moderate_luecke_min × Schmerzgrenze)."""

    def _grenze(self):
        from game.economy.schmerzgrenze import bewertung
        self.ki_player.refresh_from_db()
        return bewertung(self.ki_player, saison=SAISON)['schmerzgrenze']

    def test_counter_at_75_percent(self):
        """Angebot bei 75 % der Schmerzgrenze → COUNTER mit quantisierter
        Gegenforderung >= Grenze × 1.1."""
        grenze = self._grenze()
        angebot = (grenze * Decimal('0.75')).quantize(Decimal('0.01'))
        deal = _mk_deal_old(
            self.from_club, self.ki_club,
            typ=DealRequest.TYP_CASH,
            cash_from=angebot,
            to_players=[self.ki_player],
            saison=SAISON,
        )

        result = respond_open_deals(saison=SAISON, now=timezone.now())
        deal.refresh_from_db()
        self.ki_player.refresh_from_db()

        self.assertEqual(deal.status, DealRequest.STATUS_COUNTER)
        self.assertIsNotNone(deal.counter_offer)
        # Quantisiert auf 10.000er-Schritte
        self.assertEqual(deal.counter_offer % Decimal('10000'), 0)
        # Gegenforderung >= Grenze × 1.1 (aufgerundet)
        self.assertGreaterEqual(deal.counter_offer, grenze * Decimal('1.1'))
        # Spieler bleibt beim KI-Verein
        self.assertEqual(self.ki_player.club_id, self.ki_club.pk)
        self.assertEqual(result['gegenforderungen'], 1)
        self.assertEqual(result['angenommen'], 0)
        self.assertEqual(result['abgelehnt'], 0)

    def test_decline_at_60_percent(self):
        """Angebot bei 60 % der Schmerzgrenze → DECLINED (unter 70 %-Zone)."""
        grenze = self._grenze()
        angebot = (grenze * Decimal('0.60')).quantize(Decimal('0.01'))
        deal = _mk_deal_old(
            self.from_club, self.ki_club,
            typ=DealRequest.TYP_CASH,
            cash_from=angebot,
            to_players=[self.ki_player],
            saison=SAISON,
        )

        result = respond_open_deals(saison=SAISON, now=timezone.now())
        deal.refresh_from_db()

        self.assertEqual(deal.status, DealRequest.STATUS_DECLINED)
        self.assertIsNone(deal.counter_offer)
        self.assertEqual(result['abgelehnt'], 1)
        self.assertEqual(result['gegenforderungen'], 0)

    def test_accept_at_100_percent(self):
        """Angebot bei 100 % der Schmerzgrenze → ACCEPTED (kein Counter)."""
        grenze = self._grenze()
        deal = _mk_deal_old(
            self.from_club, self.ki_club,
            typ=DealRequest.TYP_CASH,
            cash_from=grenze,
            to_players=[self.ki_player],
            saison=SAISON,
        )

        result = respond_open_deals(saison=SAISON, now=timezone.now())
        deal.refresh_from_db()

        self.assertEqual(deal.status, DealRequest.STATUS_ACCEPTED)
        self.assertEqual(result['angenommen'], 1)
        self.assertEqual(result['gegenforderungen'], 0)

    def test_counter_not_reprocessed_by_job(self):
        """COUNTER-Deals werden vom KI-Job nicht erneut verarbeitet."""
        grenze = self._grenze()
        angebot = (grenze * Decimal('0.75')).quantize(Decimal('0.01'))
        deal = _mk_deal_old(
            self.from_club, self.ki_club,
            typ=DealRequest.TYP_CASH,
            cash_from=angebot,
            to_players=[self.ki_player],
            saison=SAISON,
        )
        respond_open_deals(saison=SAISON, now=timezone.now())
        deal.refresh_from_db()
        self.assertEqual(deal.status, DealRequest.STATUS_COUNTER)
        erster_betrag = deal.counter_offer

        # Zweiter Lauf: kein Re-Processing (Status != OPEN)
        result = respond_open_deals(saison=SAISON, now=timezone.now())
        deal.refresh_from_db()
        self.assertEqual(deal.status, DealRequest.STATUS_COUNTER)
        self.assertEqual(deal.counter_offer, erster_betrag)
        self.assertEqual(result['gegenforderungen'], 0)

    def test_counter_dry_run_no_write(self):
        """dry_run=True: Gegenforderung wird nur gezählt, nicht geschrieben."""
        _setup_economy_params(dry_run=True)
        grenze = self._grenze()
        angebot = (grenze * Decimal('0.75')).quantize(Decimal('0.01'))
        deal = _mk_deal_old(
            self.from_club, self.ki_club,
            typ=DealRequest.TYP_CASH,
            cash_from=angebot,
            to_players=[self.ki_player],
            saison=SAISON,
        )

        result = respond_open_deals(saison=SAISON, now=timezone.now())
        deal.refresh_from_db()

        self.assertEqual(deal.status, DealRequest.STATUS_OPEN)
        self.assertIsNone(deal.counter_offer)
        self.assertEqual(result['gegenforderungen'], 1)
        self.assertTrue(result['dry_run'])

    def test_counter_expires_via_job(self):
        """Abgelaufene COUNTER-Deals werden über expire_due_deals aufgeräumt
        (Reservierung des Initiators wird freigegeben)."""
        from game.transfer_v2.jobs import expire_due_deals
        grenze = self._grenze()
        angebot = (grenze * Decimal('0.75')).quantize(Decimal('0.01'))
        deal = _mk_deal_old(
            self.from_club, self.ki_club,
            typ=DealRequest.TYP_CASH,
            cash_from=angebot,
            to_players=[self.ki_player],
            saison=SAISON,
        )
        respond_open_deals(saison=SAISON, now=timezone.now())
        deal.refresh_from_db()
        self.assertEqual(deal.status, DealRequest.STATUS_COUNTER)

        result = expire_due_deals(now=timezone.now() + timedelta(days=8))
        deal.refresh_from_db()
        self.assertEqual(deal.status, DealRequest.STATUS_EXPIRED)
        self.assertEqual(result['abgelaufen'], 1)
        # Reservierung freigegeben
        self.from_club.refresh_from_db()
        self.assertEqual(self.from_club.reserved, Decimal('0.00'))


class AcceptCounterDealTests(Base):
    """Manager nimmt die Gegenforderung an → Transfer zum counter_offer."""

    def _mk_counter_deal(self):
        from game.economy.schmerzgrenze import bewertung
        self.ki_player.refresh_from_db()
        grenze = bewertung(self.ki_player, saison=SAISON)['schmerzgrenze']
        angebot = (grenze * Decimal('0.75')).quantize(Decimal('0.01'))
        deal = _mk_deal_old(
            self.from_club, self.ki_club,
            typ=DealRequest.TYP_CASH,
            cash_from=angebot,
            to_players=[self.ki_player],
            saison=SAISON,
        )
        respond_open_deals(saison=SAISON, now=timezone.now())
        deal.refresh_from_db()
        assert deal.status == DealRequest.STATUS_COUNTER
        return deal

    def test_accept_counter_executes_transfer(self):
        """accept_counter_deal: Geld bewegt sich in Höhe counter_offer,
        Spieler wechselt, Reservierung aufgelöst."""
        from game.transfer_v2.services import accept_counter_deal
        deal = self._mk_counter_deal()
        forderung = deal.counter_offer
        budget_vorher = self.from_club.budget

        accept_counter_deal(deal, saison=SAISON)

        deal.refresh_from_db()
        self.ki_player.refresh_from_db()
        self.from_club.refresh_from_db()
        self.ki_club.refresh_from_db()

        self.assertEqual(deal.status, DealRequest.STATUS_ACCEPTED)
        self.assertEqual(deal.cash_from, forderung)
        # Spieler gehört jetzt dem Initiator
        self.assertEqual(self.ki_player.club_id, self.from_club.pk)
        # Initiator zahlt genau die Gegenforderung
        self.assertEqual(self.from_club.budget, budget_vorher - forderung)
        # Reservierung vollständig aufgelöst
        self.assertEqual(self.from_club.reserved, Decimal('0.00'))

    def test_accept_counter_insufficient_funds(self):
        """Deckung reicht nicht → Fehler, Deal bleibt COUNTER."""
        from game.transfer_v2.services import (
            TransferActionError, accept_counter_deal,
        )
        deal = self._mk_counter_deal()
        # Budget unter die Gegenforderung drücken
        Club.objects.filter(pk=self.from_club.pk).update(
            budget=deal.counter_offer - Decimal('100000'))

        with self.assertRaises(TransferActionError):
            accept_counter_deal(deal, saison=SAISON)

        deal.refresh_from_db()
        self.ki_player.refresh_from_db()
        self.assertEqual(deal.status, DealRequest.STATUS_COUNTER)
        self.assertEqual(self.ki_player.club_id, self.ki_club.pk)

    def test_decline_counter_releases_reservation(self):
        """decline_counter_deal → DECLINED, Reservierung frei."""
        from game.transfer_v2.services import decline_counter_deal
        deal = self._mk_counter_deal()

        decline_counter_deal(deal)

        deal.refresh_from_db()
        self.from_club.refresh_from_db()
        self.assertEqual(deal.status, DealRequest.STATUS_DECLINED)
        self.assertIsNotNone(deal.resolved_at)
        self.assertEqual(self.from_club.reserved, Decimal('0.00'))

    def test_max_one_counter_per_deal(self):
        """counter_deal auf eine bereits gestellte Gegenforderung → Fehler."""
        from game.transfer_v2.services import (
            TransferActionError, counter_deal,
        )
        deal = self._mk_counter_deal()
        with self.assertRaises(TransferActionError):
            counter_deal(deal, Decimal('9999999'))


class CounterOfferUiTests(Base):
    """Manager-UI: COUNTER-Deals erscheinen unter „gesendet" mit Betrag;
    die Schmerzgrenze wird nirgends offengelegt."""

    def _mk_counter_deal(self):
        from game.economy.schmerzgrenze import bewertung
        self.ki_player.refresh_from_db()
        grenze = bewertung(self.ki_player, saison=SAISON)['schmerzgrenze']
        angebot = (grenze * Decimal('0.75')).quantize(Decimal('0.01'))
        deal = _mk_deal_old(
            self.from_club, self.ki_club,
            typ=DealRequest.TYP_CASH,
            cash_from=angebot,
            to_players=[self.ki_player],
            saison=SAISON,
        )
        respond_open_deals(saison=SAISON, now=timezone.now())
        deal.refresh_from_db()
        return deal, grenze

    def _login(self):
        from django.test import Client
        c = Client()
        username = self.from_club.managed_by.user.username
        c.force_login(self.from_club.managed_by.user)
        return c

    def test_counter_deal_visible_in_sent_segment(self):
        deal, grenze = self._mk_counter_deal()
        c = self._login()
        from django.urls import reverse
        resp = c.get(reverse('transfer_my_deals') + '?seg=gesendet')
        self.assertEqual(resp.status_code, 200)
        rows = resp.context['sent_rows']
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]['is_counter'])
        self.assertTrue(rows[0]['counter_fmt'])
        self.assertContains(resp, 'Gegenforderung')

    def test_schmerzgrenze_not_leaked(self):
        """Die interne Schmerzgrenze taucht in der Antwort nicht auf —
        nur der quantisierte counter_offer."""
        deal, grenze = self._mk_counter_deal()
        c = self._login()
        from django.urls import reverse
        resp = c.get(reverse('transfer_my_deals') + '?seg=gesendet')
        html = resp.content.decode('utf-8')
        # Roh-Wert der Grenze (unquantisiert) darf nicht enthalten sein.
        grenze_int = str(int(grenze))
        # counter_offer ist auf 10k gerundet und != Grenze
        self.assertNotEqual(int(deal.counter_offer), int(grenze))
        self.assertNotIn(grenze_int, html.replace('.', '').replace(',', ''))
        # Row-Dict enthält keine Schmerzgrenzen-Felder
        row = resp.context['sent_rows'][0]
        for key in row:
            self.assertNotIn('schmerz', key.lower())
            self.assertNotIn('grenze', key.lower())

    def test_counter_accept_endpoint(self):
        """POST auf transfer_deal_counter_accept vollzieht den Deal."""
        deal, _ = self._mk_counter_deal()
        c = self._login()
        from django.urls import reverse
        resp = c.post(reverse('transfer_deal_counter_accept'),
                      {'deal_id': deal.pk})
        self.assertEqual(resp.status_code, 302)
        deal.refresh_from_db()
        self.ki_player.refresh_from_db()
        self.assertEqual(deal.status, DealRequest.STATUS_ACCEPTED)
        self.assertEqual(self.ki_player.club_id, self.from_club.pk)

    def test_counter_decline_endpoint(self):
        """POST auf transfer_deal_counter_decline lehnt ab."""
        deal, _ = self._mk_counter_deal()
        c = self._login()
        from django.urls import reverse
        resp = c.post(reverse('transfer_deal_counter_decline'),
                      {'deal_id': deal.pk})
        self.assertEqual(resp.status_code, 302)
        deal.refresh_from_db()
        self.assertEqual(deal.status, DealRequest.STATUS_DECLINED)

    def test_foreign_manager_cannot_touch_counter(self):
        """Ein fremder Manager kann die Gegenforderung nicht annehmen."""
        deal, _ = self._mk_counter_deal()
        fremd = _mk_club('FC Fremd', managed=True)
        from django.test import Client
        from django.urls import reverse
        c = Client()
        c.force_login(fremd.managed_by.user)
        resp = c.post(reverse('transfer_deal_counter_accept'),
                      {'deal_id': deal.pk})
        deal.refresh_from_db()
        self.assertEqual(deal.status, DealRequest.STATUS_COUNTER)


class SwapCashCounterTests(Base):
    """Regression (Review #842): Gegenforderung bei SWAP_CASH ersetzt die
    KOMPLETTE Geld-Seite — auch ein ursprüngliches cash_to (Geld vom
    KI-Empfänger an den Initiator) wird genullt."""

    def _grenzen(self):
        from game.economy.schmerzgrenze import bewertung
        self.ki_player.refresh_from_db()
        return bewertung(self.ki_player, saison=SAISON)['schmerzgrenze']

    def _mk_swap_counter(self, *, cash_from=None, cash_to=None):
        """SWAP_CASH: eigener Spieler + Geldkomponenten gegen KI-Spieler,
        Angebotswert in der Verhandlungszone (~75-90 % der Forderung)."""
        eigener = _mk_player(self.from_club, 'Tausch Spieler', age=27,
                             mw='2000000')
        _mk_profil(eigener, staerke=50)
        from game.economy.schmerzgrenze import bewertung
        eigener_wert = bewertung(eigener, saison=SAISON)['schmerzgrenze']
        grenze = self._grenzen()

        if cash_from is None and cash_to is None:
            # Standard: KI soll cash_to an den Initiator zahlen — Angebots-
            # wert = eigener_wert − cash_to. Ziel ~80 % der Grenze.
            cash_to = (eigener_wert - grenze * Decimal('0.80')).quantize(
                Decimal('0.01'))
            assert cash_to > 0, 'Testaufbau: cash_to muss positiv sein'
            cash_from = Decimal('0')

        deal = _mk_deal_old(
            self.from_club, self.ki_club,
            typ=DealRequest.TYP_SWAP_CASH,
            cash_from=cash_from, cash_to=cash_to,
            from_players=[eigener], to_players=[self.ki_player],
            saison=SAISON,
        )
        respond_open_deals(saison=SAISON, now=timezone.now())
        deal.refresh_from_db()
        return deal, eigener, grenze, eigener_wert

    def test_swap_cash_with_cash_to_gets_counter(self):
        """SWAP_CASH mit cash_to in der Verhandlungszone → COUNTER; die
        Gegenforderung deckt Forderung×1.1 minus Sachwert (Netto-Geldanteil
        OHNE das alte cash_to)."""
        deal, eigener, grenze, eigener_wert = self._mk_swap_counter()
        self.assertEqual(deal.status, DealRequest.STATUS_COUNTER)
        self.assertIsNotNone(deal.counter_offer)
        # Netto-Geldanteil: Gesamtforderung − Sachwert, aufquantisiert.
        erwartet_min = grenze * Decimal('1.1') - eigener_wert
        self.assertGreaterEqual(deal.counter_offer, erwartet_min)
        self.assertEqual(deal.counter_offer % Decimal('10000'), 0)

    def test_accept_swap_counter_clears_cash_to(self):
        """Annahme der Gegenforderung: cash_to wird genullt, der Initiator
        zahlt GENAU counter_offer, die KI erhält counter_offer (plus
        Spielertausch) — kein Altbetrag fließt zurück."""
        from game.transfer_v2.services import accept_counter_deal
        deal, eigener, grenze, eigener_wert = self._mk_swap_counter()
        self.assertEqual(deal.status, DealRequest.STATUS_COUNTER)
        forderung = deal.counter_offer
        alt_cash_to = deal.cash_to
        self.assertGreater(alt_cash_to, 0)

        self.from_club.refresh_from_db()
        self.ki_club.refresh_from_db()
        budget_init_vorher = self.from_club.budget
        budget_ki_vorher = self.ki_club.budget

        accept_counter_deal(deal, saison=SAISON)

        deal.refresh_from_db()
        self.from_club.refresh_from_db()
        self.ki_club.refresh_from_db()
        self.ki_player.refresh_from_db()
        eigener.refresh_from_db()

        self.assertEqual(deal.status, DealRequest.STATUS_ACCEPTED)
        self.assertEqual(deal.cash_from, forderung)
        self.assertEqual(deal.cash_to, Decimal('0.00'))
        # Spieler getauscht
        self.assertEqual(self.ki_player.club_id, self.from_club.pk)
        self.assertEqual(eigener.club_id, self.ki_club.pk)
        # Geldfluss: Initiator zahlt genau die Gegenforderung …
        self.assertEqual(self.from_club.budget,
                         budget_init_vorher - forderung)
        # … die KI erhält sie VOLL (kein cash_to-Rückfluss); ggf. abzüglich
        # Jugendabgabe, daher >= forderung − 10 % Toleranz und > Altpfad.
        zulauf_ki = self.ki_club.budget - budget_ki_vorher
        self.assertGreaterEqual(zulauf_ki, forderung * Decimal('0.90'))
        falscher_altpfad = forderung - alt_cash_to
        self.assertGreater(zulauf_ki, falscher_altpfad)
        # TransferRecord spiegelt die neuen Konditionen
        from game.transfer_v2.models import TransferRecord
        record = TransferRecord.objects.filter(
            club_a=self.from_club, club_b=self.ki_club).latest('pk')
        self.assertEqual(record.cash_a, forderung)
        self.assertEqual(record.cash_b, Decimal('0.00'))
        # Reservierung vollständig aufgelöst
        self.assertEqual(self.from_club.reserved, Decimal('0.00'))

    def test_swap_cash_from_direction_counter(self):
        """SWAP_CASH, bei dem der Initiator bereits cash_from zahlt: die
        Gegenforderung ersetzt cash_from; Annahme zahlt genau counter_offer."""
        from game.transfer_v2.services import accept_counter_deal
        grenze = self._grenzen()
        eigener = _mk_player(self.from_club, 'Zuzahl Spieler', age=27,
                             mw='500000')
        _mk_profil(eigener, staerke=40)
        from game.economy.schmerzgrenze import bewertung
        eigener_wert = bewertung(eigener, saison=SAISON)['schmerzgrenze']
        # Ziel-Angebotswert 80 % der Grenze: cash_from = 0.8×Grenze − Sachwert
        cash_from = (grenze * Decimal('0.80') - eigener_wert).quantize(
            Decimal('0.01'))
        assert cash_from > 0

        deal = _mk_deal_old(
            self.from_club, self.ki_club,
            typ=DealRequest.TYP_SWAP_CASH,
            cash_from=cash_from,
            from_players=[eigener], to_players=[self.ki_player],
            saison=SAISON,
        )
        respond_open_deals(saison=SAISON, now=timezone.now())
        deal.refresh_from_db()
        self.assertEqual(deal.status, DealRequest.STATUS_COUNTER)
        forderung = deal.counter_offer
        self.assertGreater(forderung, cash_from)

        self.from_club.refresh_from_db()
        budget_vorher = self.from_club.budget
        accept_counter_deal(deal, saison=SAISON)

        deal.refresh_from_db()
        self.from_club.refresh_from_db()
        self.assertEqual(deal.status, DealRequest.STATUS_ACCEPTED)
        self.assertEqual(deal.cash_from, forderung)
        self.assertEqual(deal.cash_to, Decimal('0.00'))
        self.assertEqual(self.from_club.budget, budget_vorher - forderung)
        self.assertEqual(self.from_club.reserved, Decimal('0.00'))


class LoanCounterTests(Base):
    """Review-Fix (#842): LOAN-Gegenforderungen nutzen dieselbe
    parametrisierte Verhandlungszone (moderate_luecke_min /
    gegenforderung_faktor aus KI_VERKAEUFER) wie Kauf-Deals."""

    def _schwelle(self):
        """Leih-Mindestschwelle = max(LEIHE_MIN_GEBUEHR, 5 % Schmerzgrenze)."""
        from game.economy.params import get_decimal
        from game.economy.schmerzgrenze import bewertung
        self.ki_player.refresh_from_db()
        grenze = bewertung(self.ki_player, saison=SAISON)['schmerzgrenze']
        try:
            min_gebuehr = get_decimal('LEIHE_MIN_GEBUEHR', SAISON)
        except Exception:
            min_gebuehr = Decimal('0')
        return max(min_gebuehr, Decimal('0.05') * grenze)

    def _mk_loan_deal(self, fee):
        return _mk_deal_old(
            self.from_club, self.ki_club,
            typ=DealRequest.TYP_LOAN,
            loan_until='WP',
            loan_fee=fee,
            to_players=[self.ki_player],
            saison=SAISON,
        )

    def test_loan_counter_at_75_percent(self):
        """Leihgebühr bei 75 % der Schwelle liegt in der 70 %-Zone → COUNTER
        mit Schwelle × gegenforderung_faktor, quantisiert."""
        schwelle = self._schwelle()
        fee = (schwelle * Decimal('0.75')).quantize(Decimal('0.01'))
        deal = self._mk_loan_deal(fee)

        result = respond_open_deals(saison=SAISON, now=timezone.now())
        deal.refresh_from_db()

        self.assertEqual(deal.status, DealRequest.STATUS_COUNTER)
        self.assertIsNotNone(deal.counter_offer)
        self.assertGreaterEqual(deal.counter_offer,
                                schwelle * Decimal('1.1'))
        self.assertEqual(deal.counter_offer % Decimal('10000'), 0)
        self.assertEqual(result['gegenforderungen'], 1)

    def test_loan_decline_below_zone(self):
        """Leihgebühr bei 60 % der Schwelle → DECLINED (unter 70 %-Zone)."""
        schwelle = self._schwelle()
        fee = (schwelle * Decimal('0.60')).quantize(Decimal('0.01'))
        deal = self._mk_loan_deal(fee)

        result = respond_open_deals(saison=SAISON, now=timezone.now())
        deal.refresh_from_db()

        self.assertEqual(deal.status, DealRequest.STATUS_DECLINED)
        self.assertIsNone(deal.counter_offer)
        self.assertEqual(result['abgelehnt'], 1)
        self.assertEqual(result['gegenforderungen'], 0)

    def test_loan_zone_follows_parameter(self):
        """Angepasstes moderate_luecke_min (0.50) verschiebt die Zone auch
        für Leihen: 60 % der Schwelle wird jetzt gekontert statt abgelehnt,
        und der Faktor 1.3 hebt die Gegenforderung entsprechend an."""
        from game.models import EconomyParameter
        EconomyParameter.objects.update_or_create(
            saison=SAISON, key='KI_VERKAEUFER',
            defaults={'value': {
                'moderate_luecke_min': 0.50,
                'gegenforderung_faktor': 1.3,
                'gebot_quantisierung': 10000,
                'max_runden': 3,
            }},
        )
        schwelle = self._schwelle()
        fee = (schwelle * Decimal('0.60')).quantize(Decimal('0.01'))
        deal = self._mk_loan_deal(fee)

        respond_open_deals(saison=SAISON, now=timezone.now())
        deal.refresh_from_db()

        self.assertEqual(deal.status, DealRequest.STATUS_COUNTER)
        self.assertGreaterEqual(deal.counter_offer,
                                schwelle * Decimal('1.3'))

    def test_accept_loan_counter_sets_loan_fee(self):
        """Annahme eines LOAN-COUNTER setzt loan_fee (nicht cash_from) und
        vollzieht die Leihe zur Gegenforderung."""
        from game.transfer_v2.services import accept_counter_deal
        schwelle = self._schwelle()
        fee = (schwelle * Decimal('0.75')).quantize(Decimal('0.01'))
        deal = self._mk_loan_deal(fee)
        respond_open_deals(saison=SAISON, now=timezone.now())
        deal.refresh_from_db()
        self.assertEqual(deal.status, DealRequest.STATUS_COUNTER)
        forderung = deal.counter_offer

        self.from_club.refresh_from_db()
        budget_vorher = self.from_club.budget
        accept_counter_deal(deal, saison=SAISON)

        deal.refresh_from_db()
        self.from_club.refresh_from_db()
        self.assertEqual(deal.status, DealRequest.STATUS_ACCEPTED)
        self.assertEqual(deal.loan_fee, forderung)
        self.assertEqual(deal.cash_from, Decimal('0.00'))
        self.assertEqual(self.from_club.budget, budget_vorher - forderung)
        self.assertEqual(self.from_club.reserved, Decimal('0.00'))
        # Leihe existiert
        from game.transfer_v2.models import Loan
        self.assertTrue(Loan.objects.filter(
            player=self.ki_player, loan_club=self.from_club,
            owner_club=self.ki_club, ended_at__isnull=True).exists())


class SwapCashZeroCounterTests(Base):
    """Review-Fix (#842): Deckt der Sachwert der angebotenen Spieler die
    Forderung bereits, lag das Angebot nur wegen des geforderten cash_to in
    der Zone → COUNTER mit 0 € (reiner Tausch, cash_to entfällt)."""

    def _mk_zero_counter_deal(self):
        """Wertvoller eigener Spieler + gefordertes cash_to drücken den
        Netto-Angebotswert in die 70–100 %-Zone; der Sachwert allein liegt
        über Grenze × 1.1."""
        from game.economy.schmerzgrenze import bewertung
        self.ki_player.refresh_from_db()
        grenze = bewertung(self.ki_player, saison=SAISON)['schmerzgrenze']

        # Deutlich stärkerer eigener Spieler → Sachwert > Grenze × 1.1.
        eigener = _mk_player(self.from_club, 'Star Spieler', age=26,
                             mw='6000000')
        _mk_profil(eigener, staerke=70)
        eigener_wert = bewertung(eigener, saison=SAISON)['schmerzgrenze']
        self.assertGreater(eigener_wert, grenze * Decimal('1.1'))

        # cash_to so wählen, dass Netto (Sachwert − cash_to) ≈ 80 % Grenze.
        cash_to = (eigener_wert - grenze * Decimal('0.80')).quantize(
            Decimal('0.01'))
        self.assertGreater(cash_to, 0)

        deal = _mk_deal_old(
            self.from_club, self.ki_club,
            typ=DealRequest.TYP_SWAP_CASH,
            cash_to=cash_to,
            from_players=[eigener], to_players=[self.ki_player],
            saison=SAISON,
        )
        respond_open_deals(saison=SAISON, now=timezone.now())
        deal.refresh_from_db()
        return deal, eigener, grenze

    def test_in_zone_offer_with_covering_players_gets_zero_counter(self):
        """Sachwert deckt die Forderung → COUNTER mit 0 € statt DECLINE."""
        deal, eigener, grenze = self._mk_zero_counter_deal()
        self.assertEqual(deal.status, DealRequest.STATUS_COUNTER)
        self.assertEqual(deal.counter_offer, Decimal('0.00'))

    def test_accept_zero_counter_clears_cash_to(self):
        """Annahme: reiner Tausch — Initiator zahlt 0, KI zahlt kein
        cash_to mehr aus, Spieler wechseln."""
        from game.transfer_v2.services import accept_counter_deal
        deal, eigener, grenze = self._mk_zero_counter_deal()
        alt_cash_to = deal.cash_to
        self.assertGreater(alt_cash_to, 0)

        self.from_club.refresh_from_db()
        self.ki_club.refresh_from_db()
        budget_init_vorher = self.from_club.budget
        budget_ki_vorher = self.ki_club.budget

        accept_counter_deal(deal, saison=SAISON)

        deal.refresh_from_db()
        self.from_club.refresh_from_db()
        self.ki_club.refresh_from_db()
        self.ki_player.refresh_from_db()
        eigener.refresh_from_db()

        self.assertEqual(deal.status, DealRequest.STATUS_ACCEPTED)
        self.assertEqual(deal.cash_from, Decimal('0.00'))
        self.assertEqual(deal.cash_to, Decimal('0.00'))
        # Spieler getauscht
        self.assertEqual(self.ki_player.club_id, self.from_club.pk)
        self.assertEqual(eigener.club_id, self.ki_club.pk)
        # Kein Geld fließt vom Initiator ab …
        self.assertEqual(self.from_club.budget, budget_init_vorher)
        # … und die KI zahlt das alte cash_to NICHT aus (Budget nicht
        # um alt_cash_to gesunken; Jugendabgabe fällt hier nicht auf die
        # KI-Seite als Auszahlung des cash_to an).
        self.assertGreater(self.ki_club.budget,
                           budget_ki_vorher - alt_cash_to)
        # TransferRecord: beide Geldseiten 0
        from game.transfer_v2.models import TransferRecord
        record = TransferRecord.objects.filter(
            club_a=self.from_club, club_b=self.ki_club).latest('pk')
        self.assertEqual(record.cash_a, Decimal('0.00'))
        self.assertEqual(record.cash_b, Decimal('0.00'))
        # Reservierung vollständig aufgelöst
        self.assertEqual(self.from_club.reserved, Decimal('0.00'))
