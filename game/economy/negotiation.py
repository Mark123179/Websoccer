"""Reaktive KI-Verkäufer — Verhandlungs-Zustandsmaschine (Spec Kap. 9.2/9.3).

Manager bieten auf Spieler MANAGERLOSER Vereine (Club.managed_by IS NULL).
Die KI antwortet sofort nach Schmerzgrenze v2:

  Gebot ≥ Grenze_eff                → Deal (Abwicklung via execute_money_transfer)
  Gebot ≥ moderate_luecke_min×Grenze → Gegenforderung (Grenze×1,1;
                                        ab Runde 2 bei Finanzdruck ×1,0)
  sonst                              → Absage + Cooldown

Grenze_eff = Schmerzgrenze × (1 ± STREUUNG), deterministisch aus
noise_seed + Runde (SHA-256) — stabil je Verhandlungsrunde (kein
Reload-Exploit), ohne Seed nicht reverse-engineerbar. Max. 3 Runden,
danach Absage + Cooldown. Alle Kadenz-Werte in EconomyParameter
KI_VERKAEUFER ([KALIBRIERUNG]).

Locking-Regel (Scouting-V1-Lehre): Geld bewegt NUR die Transferabwicklung
(Club-Row-Locks in book_many-Reihenfolge). Lock-Ordnung ist überall
konsistent: erst die Verhandlungszeile, dann Club-Locks (in der
Transferabwicklung), zuletzt die Spielerzeile — kein Pfad läuft
andersherum, daher kein Deadlock-Zyklus.
"""
import hashlib
import secrets
from datetime import timedelta
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.utils import timezone

from .params import get_param
from .schmerzgrenze import bewertung
from .transfers import execute_money_transfer


class NegotiationError(Exception):
    """Fachlicher Verhandlungsfehler (deutsche Meldung für die UI)."""


def _params(saison=None):
    return get_param('KI_VERKAEUFER', saison)


def _streuung_faktor(seed: str, runde: int, streuung: float) -> Decimal:
    """Deterministischer Faktor in [1−streuung, 1+streuung]."""
    digest = hashlib.sha256(f'{seed}:{runde}'.encode()).hexdigest()
    anteil = int(digest[:12], 16) / float(0xFFFFFFFFFFFF)
    return Decimal(str(1 - streuung + 2 * streuung * anteil))


def _quantisiere(betrag: Decimal, schritt) -> Decimal:
    schritt = Decimal(str(schritt))
    if schritt <= 0:
        return betrag.quantize(Decimal('0.01'))
    return (betrag / schritt).to_integral_value(rounding='ROUND_HALF_UP') * schritt


def _finanzdruck(club) -> bool:
    """V1-Definition: Konto im Minus = Finanzdruck (Puffer-Regel folgt Phase 6)."""
    return (club.budget or Decimal('0')) < 0


def kann_bieten(player, bidder_club):
    """(ok, grund) — prüft Grundvoraussetzungen ohne Werte zu leaken."""
    from game.models import TransferNegotiation

    seller = player.club
    if seller is None:
        return False, 'Spieler ist vereinslos — kein KI-Verkäufer.'
    if seller.managed_by_id is not None:
        return False, 'Der Verein wird von einem Manager geführt.'
    if bidder_club is None or bidder_club.pk == seller.pk:
        return False, 'Ungültiger bietender Verein.'

    jetzt = timezone.now()
    gesperrt = TransferNegotiation.objects.filter(
        player=player, bidder_club=bidder_club,
        status=TransferNegotiation.STATUS_ABGELEHNT,
        cooldown_until__gt=jetzt,
    ).order_by('-cooldown_until').first()
    if gesperrt is not None:
        return False, (
            f'Abgelehnt — neues Angebot erst ab '
            f'{timezone.localtime(gesperrt.cooldown_until):%d.%m.%Y %H:%M} möglich.'
        )
    return True, ''


def place_bid(player, bidder_club, gebot, *, saison=None, spieltag=None):
    """Manager-Gebot abgeben; KI antwortet sofort.

    Returns dict: {'negotiation', 'ergebnis': 'deal'|'gegenforderung'|'abgelehnt',
                   'gegenforderung': Decimal|None, 'transfer': dict|None}.
    Die Schmerzgrenze selbst wird nie zurückgegeben.
    """
    gebot = Decimal(str(gebot)).quantize(Decimal('0.01'))
    if gebot <= 0:
        raise NegotiationError('Das Gebot muss größer als 0 sein.')

    ok, grund = kann_bieten(player, bidder_club)
    if not ok:
        raise NegotiationError(grund)

    seller = player.club
    p = _params(saison)
    max_runden = int(p['max_runden'])

    try:
        return _ki_antwort(player, bidder_club, seller, gebot, p,
                           max_runden, saison, spieltag)
    except IntegrityError:
        # Partieller Unique-Index auf offene Verhandlungen: zwei parallele
        # Erst-Gebote desselben Bieters → sauberer Fehler statt 500.
        raise NegotiationError(
            'Für diesen Spieler läuft bereits eine Verhandlung — '
            'bitte erneut versuchen.'
        )


def _ki_antwort(player, bidder_club, seller, gebot, p, max_runden,
                saison, spieltag):
    """KI-Antwortlogik in einer Transaktion (nur von place_bid gerufen)."""
    from game.models import TransferNegotiation

    with transaction.atomic():
        nego = (
            TransferNegotiation.objects
            .select_for_update()
            .filter(
                player=player, bidder_club=bidder_club,
                status=TransferNegotiation.STATUS_GEGENFORDERUNG,
            )
            .first()
        )
        if nego is None:
            nego = TransferNegotiation(
                player=player, bidder_club=bidder_club, seller_club=seller,
                runde=1, noise_seed=secrets.token_hex(16),
                status=TransferNegotiation.STATUS_GEGENFORDERUNG,
            )
        else:
            nego.runde += 1

        wertung = bewertung(player, saison=saison)
        if wertung is None:
            raise NegotiationError(
                'Für diesen Spieler ist keine Bewertung möglich.'
            )
        grenze = wertung['schmerzgrenze']
        faktor = _streuung_faktor(
            nego.noise_seed, nego.runde, float(p['streuung']),
        )
        grenze_eff = (grenze * faktor).quantize(Decimal('0.01'))

        nego.letztes_gebot = gebot

        if gebot >= grenze_eff:
            transfer = execute_money_transfer(
                player, bidder_club, gebot, saison=saison, spieltag=spieltag,
            )
            nego.status = TransferNegotiation.STATUS_DEAL
            nego.gegenforderung = None
            nego.save()
            return {'negotiation': nego, 'ergebnis': 'deal',
                    'gegenforderung': None, 'transfer': transfer}

        moderate = grenze_eff * Decimal(str(p['moderate_luecke_min']))
        if gebot >= moderate and nego.runde < max_runden:
            faktor_gf = Decimal(str(p['gegenforderung_faktor']))
            if nego.runde >= 2 and _finanzdruck(seller):
                faktor_gf = Decimal(str(p['finanzdruck_faktor']))
            forderung = _quantisiere(
                grenze_eff * faktor_gf, p['gebot_quantisierung'],
            )
            nego.status = TransferNegotiation.STATUS_GEGENFORDERUNG
            nego.gegenforderung = forderung
            nego.save()
            return {'negotiation': nego, 'ergebnis': 'gegenforderung',
                    'gegenforderung': forderung, 'transfer': None}

        nego.status = TransferNegotiation.STATUS_ABGELEHNT
        nego.gegenforderung = None
        nego.cooldown_until = timezone.now() + timedelta(
            days=int(p['cooldown_tage']),
        )
        nego.save()
        return {'negotiation': nego, 'ergebnis': 'abgelehnt',
                'gegenforderung': None, 'transfer': None}


def accept_counter(negotiation, *, saison=None, spieltag=None):
    """Gegenforderung annehmen → Deal zur Gegenforderung."""
    from game.models import TransferNegotiation

    with transaction.atomic():
        nego = (
            TransferNegotiation.objects
            .select_for_update()
            .get(pk=negotiation.pk)
        )
        if nego.status != TransferNegotiation.STATUS_GEGENFORDERUNG:
            raise NegotiationError('Diese Verhandlung ist nicht mehr offen.')
        if nego.gegenforderung is None:
            raise NegotiationError('Es liegt keine Gegenforderung vor.')
        player = nego.player
        if player.club_id != nego.seller_club_id:
            nego.status = TransferNegotiation.STATUS_ABGELEHNT
            nego.save(update_fields=['status', 'updated_at'])
            raise NegotiationError('Der Spieler hat den Verein bereits verlassen.')

        transfer = execute_money_transfer(
            player, nego.bidder_club, nego.gegenforderung,
            saison=saison, spieltag=spieltag,
        )
        nego.status = TransferNegotiation.STATUS_DEAL
        nego.letztes_gebot = nego.gegenforderung
        nego.save()
        return {'negotiation': nego, 'ergebnis': 'deal', 'transfer': transfer}


def cancel(negotiation, *, saison=None):
    """Verhandlung abbrechen (Manager-Seite) → Absage + Cooldown."""
    from game.models import TransferNegotiation

    p = _params(saison)
    with transaction.atomic():
        nego = (
            TransferNegotiation.objects
            .select_for_update()
            .get(pk=negotiation.pk)
        )
        if nego.status != TransferNegotiation.STATUS_GEGENFORDERUNG:
            raise NegotiationError('Diese Verhandlung ist nicht mehr offen.')
        nego.status = TransferNegotiation.STATUS_ABGELEHNT
        nego.cooldown_until = timezone.now() + timedelta(
            days=int(p['cooldown_tage']),
        )
        nego.save()
        return nego
