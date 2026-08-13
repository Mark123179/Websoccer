"""KI-Überführung: Automatische Antworten auf offene DealRequests für KI-Vereine.

KI-Vereine (managed_by_id IS NULL) beantworten offene DealRequest-Anfragen
(Typen: CASH-Kauf, SWAP, SWAP_CASH, LOAN), die an sie gerichtet sind, auf
Basis der Schmerzgrenzen-Bewertung.

Anfragen bekommen 24 Stunden Bedenkzeit; jüngere werden übersprungen.
Entscheidung per Schmerzgrenzen-Vergleich: angebotener Wert >= Schmerzgrenze
→ accept_deal, sonst → decline_deal.

dry_run=True (aus KI_KAEUFER-Parameter): kein Schreibzugriff, nur zählen/loggen.
"""
import logging
from decimal import Decimal

from django.utils import timezone

from game.economy.params import get_decimal, get_param
from game.economy.schmerzgrenze import bewertung

from .models import DealRequest, DealRequestPlayer
from .services import TransferActionError, accept_deal, decline_deal

logger = logging.getLogger(__name__)

ZERO = Decimal('0.00')
_24H = timezone.timedelta(hours=24)


def _schmerzgrenze_fuer(player, saison):
    """Gibt die Schmerzgrenze des Spielers zurück oder None bei fehlender Datenbasis."""
    ergebnis = bewertung(player, saison=saison)
    if ergebnis is None:
        return None
    return ergebnis['schmerzgrenze']


def _angebotener_wert_cash(deal, saison):
    """Angebotener Wert für CASH-Kauf: cash_from des Initiators."""
    return Decimal(str(deal.cash_from))


def _angebotener_wert_swap(deal, saison):
    """Angebotener Wert für SWAP / SWAP_CASH:
    Summe der Schmerzgrenzen der FROM-Spieler (die der Initiator anbietet)
    + cash_from - cash_to.
    Gibt None zurück, wenn eine Schmerzgrenze fehlt.
    """
    from_eintraege = list(
        deal.players.filter(side=DealRequestPlayer.SIDE_FROM)
        .select_related('player', 'player__strength_profile')
    )
    summe = ZERO
    for eintrag in from_eintraege:
        grenze = _schmerzgrenze_fuer(eintrag.player, saison)
        if grenze is None:
            return None
        summe += grenze
    summe += Decimal(str(deal.cash_from)) - Decimal(str(deal.cash_to))
    return summe


def _geforderter_wert_loan(deal, saison):
    """Geforderter Mindestwert für LOAN:
    max(LEIHE_MIN_GEBUEHR, 0.05 * Schmerzgrenze des Leihspielers).
    Gibt (None, None) bei fehlender Datenbasis zurück.
    """
    to_eintraege = list(
        deal.players.filter(side=DealRequestPlayer.SIDE_TO)
        .select_related('player', 'player__strength_profile')
    )
    if not to_eintraege:
        return None, None
    spieler = to_eintraege[0].player
    grenze = _schmerzgrenze_fuer(spieler, saison)
    if grenze is None:
        return None, None
    try:
        min_gebuehr = get_decimal('LEIHE_MIN_GEBUEHR', saison)
    except Exception:
        min_gebuehr = ZERO
    schwelle = max(min_gebuehr, Decimal('0.05') * grenze)
    return schwelle, grenze


def _bewerte_deal(deal, saison):
    """Bewertet einen Deal aus Sicht des KI-Empfängers (to_club).

    Returns:
        (annehmen: bool, grund: str)
    """
    typ = deal.typ

    # Spieler des KI-Vereins (die abgegeben werden sollen) sind SIDE_TO
    to_eintraege = list(
        deal.players.filter(side=DealRequestPlayer.SIDE_TO)
        .select_related('player', 'player__strength_profile')
    )

    if typ == DealRequest.TYP_LOAN:
        angeboten = Decimal(str(deal.loan_fee)) if deal.loan_fee is not None else ZERO
        gefordert, grenze = _geforderter_wert_loan(deal, saison)
        if gefordert is None:
            return False, 'Keine Schmerzgrenzen-Datenbasis für Leihspieler'
        if angeboten >= gefordert:
            return True, f'Leihgebühr {angeboten} >= Schwelle {gefordert}'
        return False, f'Leihgebühr {angeboten} < Schwelle {gefordert} (5% von {grenze})'

    # Für CASH, SWAP, SWAP_CASH: geforderter Wert = Summe Schmerzgrenzen TO-Spieler
    if not to_eintraege:
        return False, 'Keine Spieler auf TO-Seite (kein Abgabegegenstand)'

    gefordert = ZERO
    for eintrag in to_eintraege:
        grenze = _schmerzgrenze_fuer(eintrag.player, saison)
        if grenze is None:
            return False, (
                f'Keine Schmerzgrenzen-Datenbasis für Spieler '
                f'{eintrag.player_id} — KI verkauft nicht ohne Bewertung'
            )
        gefordert += grenze

    if typ == DealRequest.TYP_CASH:
        angeboten = _angebotener_wert_cash(deal, saison)
    elif typ in (DealRequest.TYP_SWAP, DealRequest.TYP_SWAP_CASH):
        angeboten = _angebotener_wert_swap(deal, saison)
        if angeboten is None:
            return False, 'Keine Schmerzgrenzen-Datenbasis für angebotene FROM-Spieler'
    else:
        return False, f'Unbekannter Deal-Typ: {typ}'

    if angeboten >= gefordert:
        return True, f'Angebot {angeboten} >= Schmerzgrenze {gefordert}'
    return False, f'Angebot {angeboten} < Schmerzgrenze {gefordert}'


def respond_open_deals(*, saison=None, now=None):
    """KI-Vereine beantworten offene DealRequests nach 24h Bedenkzeit.

    Idempotent — mehrfacher Aufruf schadet nicht. Robuster try/except je
    Anfrage: Fehler werden geloggt, der Job bricht nie ab.

    Args:
        saison: Sim-Saison (None → aktuelle).
        now: Referenzzeitpunkt (None → aktuell). Für Tests.

    Returns:
        dict mit Statistiken (und dry_run-Flag wenn active).
    """
    from .models import DealRequest

    now = now or timezone.now()
    cutoff = now - _24H

    # dry_run aus KI_KAEUFER-Parameter
    try:
        params = get_param('KI_KAEUFER', saison)
        if not isinstance(params, dict):
            params = {}
    except Exception:
        params = {}
    dry_run = bool(params.get('dry_run', True))

    # Offene Deals an KI-Vereine, die älter als 24h sind
    qs = (
        DealRequest.objects
        .filter(
            status=DealRequest.STATUS_OPEN,
            to_club__managed_by_id__isnull=True,
            created_at__lte=cutoff,
        )
        .select_related(
            'to_club', 'from_club',
        )
        .order_by('pk')
        .values_list('pk', flat=True)
    )

    pks = list(qs)
    angenommen = 0
    abgelehnt = 0
    fehler = 0
    uebersprungen = 0

    for pk in pks:
        try:
            deal = (
                DealRequest.objects
                .select_related('to_club', 'from_club')
                .get(pk=pk)
            )
            # Idempotenz: Status könnte sich zwischenzeitlich geändert haben
            if deal.status != DealRequest.STATUS_OPEN:
                uebersprungen += 1
                continue

            # Typ-Filter: nur CASH, SWAP, SWAP_CASH, LOAN
            if deal.typ not in (
                DealRequest.TYP_CASH,
                DealRequest.TYP_SWAP,
                DealRequest.TYP_SWAP_CASH,
                DealRequest.TYP_LOAN,
            ):
                logger.debug(
                    'ai_deals: Deal #%s übersprungen (Typ %s nicht unterstützt)',
                    pk, deal.typ,
                )
                uebersprungen += 1
                continue

            annehmen, grund = _bewerte_deal(deal, saison)

            if dry_run:
                entscheidung = 'ANGENOMMEN' if annehmen else 'ABGELEHNT'
                logger.info(
                    'ai_deals [dry_run] Deal #%s: %s — %s',
                    pk, entscheidung, grund,
                )
                if annehmen:
                    angenommen += 1
                else:
                    abgelehnt += 1
                continue

            if annehmen:
                try:
                    accept_deal(deal, saison=saison)
                    angenommen += 1
                    logger.info(
                        'ai_deals: Deal #%s ANGENOMMEN — %s', pk, grund)
                except (TransferActionError, Exception) as exc:
                    # Fallback: ablehnen (z.B. Kaderlimit, Deckung)
                    try:
                        decline_deal(deal)
                        abgelehnt += 1
                        logger.warning(
                            'ai_deals: Deal #%s accept_deal fehlgeschlagen '
                            '(%s) — als ABGELEHNT gebucht', pk, exc)
                    except Exception as exc2:
                        fehler += 1
                        logger.exception(
                            'ai_deals: Deal #%s Fallback-decline fehlgeschlagen: %s',
                            pk, exc2)
            else:
                try:
                    decline_deal(deal)
                    abgelehnt += 1
                    logger.info(
                        'ai_deals: Deal #%s ABGELEHNT — %s', pk, grund)
                except Exception as exc:
                    fehler += 1
                    logger.exception(
                        'ai_deals: Deal #%s decline fehlgeschlagen: %s',
                        pk, exc)

        except Exception:
            fehler += 1
            logger.exception('ai_deals: Fehler bei Deal #%s', pk)

    result = {
        'angenommen': angenommen,
        'abgelehnt': abgelehnt,
        'fehler': fehler,
        'uebersprungen': uebersprungen,
    }
    if dry_run:
        result['dry_run'] = True
    return result
