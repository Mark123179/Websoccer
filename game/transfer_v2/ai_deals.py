"""KI-Überführung: Automatische Antworten auf offene DealRequests für KI-Vereine.

KI-Vereine (managed_by_id IS NULL) beantworten offene DealRequest-Anfragen
(Typen: CASH-Kauf, SWAP, SWAP_CASH, LOAN), die an sie gerichtet sind, auf
Basis der Schmerzgrenzen-Bewertung.

Anfragen bekommen 24 Stunden Bedenkzeit; jüngere werden übersprungen.
Entscheidung per Schmerzgrenzen-Vergleich mit Verhandlungszone:
- angebotener Wert >= Schmerzgrenze → accept_deal
- angebotener Wert >= Schmerzgrenze × moderate_luecke_min → counter_deal
  (Gegenforderung = Schmerzgrenze × gegenforderung_faktor, quantisiert;
  die interne Schmerzgrenze wird NIE offengelegt)
- sonst → decline_deal

dry_run=True (aus KI_KAEUFER-Parameter): kein Schreibzugriff, nur zählen/loggen.
"""
import logging
from decimal import Decimal

from django.utils import timezone

from game.economy.params import get_decimal, get_param
from game.economy.schmerzgrenze import bewertung

from .models import DealRequest, DealRequestPlayer
from .services import (
    TransferActionError, accept_deal, counter_deal, decline_deal,
)

logger = logging.getLogger(__name__)

ZERO = Decimal('0.00')
_24H = timezone.timedelta(hours=24)

# Entscheidungs-Codes von _bewerte_deal
ACCEPT = 'accept'
COUNTER = 'counter'
DECLINE = 'decline'


def _verkaeufer_params(saison):
    """KI_VERKAEUFER-Parameter mit robusten Fallbacks (Seed 0129)."""
    try:
        p = get_param('KI_VERKAEUFER', saison)
        if not isinstance(p, dict):
            p = {}
    except Exception:
        p = {}
    return {
        'moderate_luecke_min': Decimal(str(p.get('moderate_luecke_min', 0.70))),
        'gegenforderung_faktor': Decimal(str(p.get('gegenforderung_faktor', 1.1))),
        'gebot_quantisierung': Decimal(str(p.get('gebot_quantisierung', 10000))),
    }


def _quantisiere_auf(betrag, schritt):
    """Rundet auf den nächsten Quantisierungs-Schritt AUF (nie unter Forderung)."""
    schritt = Decimal(str(schritt))
    if schritt <= 0:
        return betrag.quantize(Decimal('0.01'))
    import math
    return Decimal(math.ceil(betrag / schritt)) * schritt


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
        (entscheidung: 'accept'|'counter'|'decline',
         gegenforderung: Decimal|None,  # nur bei 'counter' gesetzt
         grund: str)
    Die interne Schmerzgrenze taucht nur im Log-Grund auf, nie in
    Manager-sichtbaren Daten.
    """
    typ = deal.typ

    # Spieler des KI-Vereins (die abgegeben werden sollen) sind SIDE_TO
    to_eintraege = list(
        deal.players.filter(side=DealRequestPlayer.SIDE_TO)
        .select_related('player', 'player__strength_profile')
    )

    p = _verkaeufer_params(saison)

    if typ == DealRequest.TYP_LOAN:
        angeboten = Decimal(str(deal.loan_fee)) if deal.loan_fee is not None else ZERO
        gefordert, grenze = _geforderter_wert_loan(deal, saison)
        if gefordert is None:
            return DECLINE, None, 'Keine Schmerzgrenzen-Datenbasis für Leihspieler'
        if angeboten >= gefordert:
            return ACCEPT, None, f'Leihgebühr {angeboten} >= Schwelle {gefordert}'
        # Leih-Gegenforderung: gleiche Verhandlungszone wie Kauf-Deals
        # (moderate_luecke_min/gegenforderung_faktor aus KI_VERKAEUFER),
        # max. 1 Runde pro Anfrage.
        if (angeboten >= gefordert * p['moderate_luecke_min']
                and deal.counter_offer is None):
            forderung = _quantisiere_auf(
                gefordert * p['gegenforderung_faktor'],
                p['gebot_quantisierung'])
            return COUNTER, forderung, (
                f'Leihgebühr {angeboten} in Verhandlungszone '
                f'(>= {p["moderate_luecke_min"]}×{gefordert}) '
                f'— Gegenforderung {forderung}')
        return DECLINE, None, (
            f'Leihgebühr {angeboten} < Schwelle {gefordert} (5% von {grenze})')

    # Für CASH, SWAP, SWAP_CASH: geforderter Wert = Summe Schmerzgrenzen TO-Spieler
    if not to_eintraege:
        return DECLINE, None, 'Keine Spieler auf TO-Seite (kein Abgabegegenstand)'

    gefordert = ZERO
    for eintrag in to_eintraege:
        grenze = _schmerzgrenze_fuer(eintrag.player, saison)
        if grenze is None:
            return DECLINE, None, (
                f'Keine Schmerzgrenzen-Datenbasis für Spieler '
                f'{eintrag.player_id} — KI verkauft nicht ohne Bewertung'
            )
        gefordert += grenze

    if typ == DealRequest.TYP_CASH:
        angeboten = _angebotener_wert_cash(deal, saison)
    elif typ in (DealRequest.TYP_SWAP, DealRequest.TYP_SWAP_CASH):
        angeboten = _angebotener_wert_swap(deal, saison)
        if angeboten is None:
            return DECLINE, None, (
                'Keine Schmerzgrenzen-Datenbasis für angebotene FROM-Spieler')
    else:
        return DECLINE, None, f'Unbekannter Deal-Typ: {typ}'

    if angeboten >= gefordert:
        return ACCEPT, None, f'Angebot {angeboten} >= Schmerzgrenze {gefordert}'

    # Verhandlungszone: Angebot knapp unter der Grenze → Gegenforderung.
    # Nur wenn noch keine Gegenforderung gestellt wurde (max. 1 Runde).
    if (angeboten >= gefordert * p['moderate_luecke_min']
            and deal.counter_offer is None):
        # Gegenforderung bezieht sich auf den GELDANTEIL des Initiators:
        # Gesamtforderung × Faktor minus Wert der angebotenen FROM-Spieler.
        # Sie ersetzt die KOMPLETTE Geld-Seite des Deals (cash_to entfällt).
        gesamt = gefordert * p['gegenforderung_faktor']
        sachwert = angeboten - Decimal(str(deal.cash_from)) + Decimal(str(deal.cash_to))
        geldanteil = gesamt - sachwert
        # geldanteil <= 0: Der Sachwert allein deckt die Forderung bereits —
        # das Angebot lag nur wegen des geforderten cash_to in der Zone.
        # Gegenforderung = 0 € (reiner Tausch, cash_to entfällt bei Annahme).
        forderung = (_quantisiere_auf(geldanteil, p['gebot_quantisierung'])
                     if geldanteil > 0 else ZERO)
        return COUNTER, forderung, (
            f'Angebot {angeboten} in Verhandlungszone '
            f'(>= {p["moderate_luecke_min"]}×{gefordert}) '
            f'— Gegenforderung {forderung}')
    return DECLINE, None, f'Angebot {angeboten} < Schmerzgrenze {gefordert}'


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
    gegenforderungen = 0
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

            entscheidung, forderung, grund = _bewerte_deal(deal, saison)

            if dry_run:
                label = {ACCEPT: 'ANGENOMMEN', COUNTER: 'GEGENFORDERUNG',
                         DECLINE: 'ABGELEHNT'}[entscheidung]
                logger.info(
                    'ai_deals [dry_run] Deal #%s: %s — %s',
                    pk, label, grund,
                )
                if entscheidung == ACCEPT:
                    angenommen += 1
                elif entscheidung == COUNTER:
                    gegenforderungen += 1
                else:
                    abgelehnt += 1
                continue

            if entscheidung == ACCEPT:
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
            elif entscheidung == COUNTER:
                try:
                    counter_deal(deal, forderung)
                    gegenforderungen += 1
                    logger.info(
                        'ai_deals: Deal #%s GEGENFORDERUNG — %s', pk, grund)
                except (TransferActionError, Exception) as exc:
                    # Fallback: ablehnen (z.B. Race auf Status)
                    try:
                        decline_deal(deal)
                        abgelehnt += 1
                        logger.warning(
                            'ai_deals: Deal #%s counter_deal fehlgeschlagen '
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
        'gegenforderungen': gegenforderungen,
        'fehler': fehler,
        'uebersprungen': uebersprungen,
    }
    if dry_run:
        result['dry_run'] = True
    return result
