"""Transfermarkt-Endpunkte (Finanzsystem Phase 4, Spec Kap. 9).

Verkaufskategorien (eigener Kader) + Angebots-Dialog gegen KI-Verkäufer
(reaktive Verhandlungen). Alle Antworten sind JSON für die Kaderseite.
Schmerzgrenzen oder Streuungsdetails werden NIE ausgeliefert — nur das
Verhandlungsergebnis (Deal / Gegenforderung / Absage).
"""
from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST

from .economy.booking import InsufficientFunds
from .economy.negotiation import (
    NegotiationError, accept_counter, cancel, place_bid,
)
from .economy.transfers import TransferError
from .models import Club, Player, TransferNegotiation

SALE_CATEGORIES = {code for code, _ in Player.SALE_CATEGORY_CHOICES}


def _viewer_club(request):
    from .views import current_manager_club
    return current_manager_club(user=request.user)


def _fmt_euro(value):
    return f'{int(Decimal(value)):,}'.replace(',', '.') + ' €'


def _fehler(text, status=400):
    return JsonResponse({'ok': False, 'error': text}, status=status)


@login_required
@require_POST
def squad_set_sale_status(request, club_id):
    """Verkaufskategorie + KI-Sichtbarkeit für eigene Spieler setzen (bulk)."""
    club = get_object_or_404(Club, id=club_id)
    if _viewer_club(request) != club:
        return _fehler('Keine Berechtigung für diesen Verein.', 403)

    raw_ids = request.POST.getlist('player_ids') or [request.POST.get('player_id')]
    try:
        player_ids = [int(pid) for pid in raw_ids if pid]
    except (TypeError, ValueError):
        return _fehler('Ungültige Spielerauswahl.')
    if not player_ids:
        return _fehler('Keine Spieler ausgewählt.')

    category = (request.POST.get('sale_category') or '').strip()
    if category not in SALE_CATEGORIES:
        return _fehler('Ungültige Verkaufskategorie.')
    visible = request.POST.get('sale_visible_to_ai') == '1'
    if category == 'UVK':
        visible = False  # Unverkäuflich ist nie KI-sichtbar (Postfach-Hygiene).

    updated = Player.objects.filter(club=club, id__in=player_ids).update(
        sale_category=category, sale_visible_to_ai=visible,
    )
    if updated == 0:
        return _fehler('Keine passenden Spieler in deinem Kader.', 404)
    return JsonResponse({
        'ok': True, 'updated': updated,
        'sale_category': category, 'sale_visible_to_ai': visible,
    })


def _nego_payload(nego):
    return {
        'id': nego.pk,
        'runde': nego.runde,
        'status': nego.status,
        'gegenforderung': (
            float(nego.gegenforderung) if nego.gegenforderung is not None else None
        ),
        'gegenforderung_fmt': (
            _fmt_euro(nego.gegenforderung) if nego.gegenforderung is not None else None
        ),
    }


@login_required
@require_POST
def transfer_place_bid(request):
    """Manager-Gebot auf einen Spieler eines managerlosen Vereins."""
    bidder = _viewer_club(request)
    if bidder is None:
        return _fehler('Du führst aktuell keinen Verein.', 403)

    try:
        player = get_object_or_404(Player, id=int(request.POST.get('player_id', '')))
    except (TypeError, ValueError):
        return _fehler('Ungültiger Spieler.')

    raw = (request.POST.get('betrag') or '').replace('.', '').replace(',', '.')
    try:
        betrag = Decimal(raw)
    except InvalidOperation:
        return _fehler('Bitte einen gültigen Betrag eingeben.')

    try:
        ergebnis = place_bid(player, bidder, betrag)
    except (NegotiationError, TransferError) as exc:
        return _fehler(str(exc))
    except InsufficientFunds:
        return _fehler('Dein Budget deckt dieses Gebot nicht (Grundregel: '
                       'keine aktiven Ausgaben ohne Deckung).')

    nego = ergebnis['negotiation']
    if ergebnis['ergebnis'] == 'deal':
        message = (f'Transfer perfekt! {player.full_name} wechselt für '
                   f'{_fmt_euro(nego.letztes_gebot)} zu {bidder.name}.')
    elif ergebnis['ergebnis'] == 'gegenforderung':
        message = (f'{nego.seller_club.name} lehnt ab, fordert aber '
                   f'{_fmt_euro(nego.gegenforderung)} '
                   f'(Runde {nego.runde}).')
    else:
        bis = timezone.localtime(nego.cooldown_until)
        message = (f'{nego.seller_club.name} lehnt das Angebot ab. '
                   f'Neuer Versuch ab {bis:%d.%m.%Y %H:%M}.')

    return JsonResponse({
        'ok': True,
        'ergebnis': ergebnis['ergebnis'],
        'message': message,
        'negotiation': _nego_payload(nego),
    })


def _own_negotiation(request, bidder):
    try:
        nego_id = int(request.POST.get('negotiation_id', ''))
    except (TypeError, ValueError):
        return None
    return TransferNegotiation.objects.filter(
        pk=nego_id, bidder_club=bidder,
    ).select_related('player', 'seller_club').first()


@login_required
@require_POST
def transfer_accept_counter(request):
    """Gegenforderung der KI annehmen → Deal zur Gegenforderung."""
    bidder = _viewer_club(request)
    if bidder is None:
        return _fehler('Du führst aktuell keinen Verein.', 403)
    nego = _own_negotiation(request, bidder)
    if nego is None:
        return _fehler('Verhandlung nicht gefunden.', 404)

    try:
        ergebnis = accept_counter(nego)
    except (NegotiationError, TransferError) as exc:
        return _fehler(str(exc))
    except InsufficientFunds:
        return _fehler('Dein Budget deckt die Gegenforderung nicht.')

    nego = ergebnis['negotiation']
    return JsonResponse({
        'ok': True,
        'ergebnis': 'deal',
        'message': (f'Transfer perfekt! {nego.player.full_name} wechselt für '
                    f'{_fmt_euro(nego.letztes_gebot)} zu {bidder.name}.'),
        'negotiation': _nego_payload(nego),
    })


@login_required
@require_POST
def transfer_cancel_negotiation(request):
    """Laufende Verhandlung abbrechen (Absage + Cooldown)."""
    bidder = _viewer_club(request)
    if bidder is None:
        return _fehler('Du führst aktuell keinen Verein.', 403)
    nego = _own_negotiation(request, bidder)
    if nego is None:
        return _fehler('Verhandlung nicht gefunden.', 404)

    try:
        nego = cancel(nego)
    except NegotiationError as exc:
        return _fehler(str(exc))

    bis = timezone.localtime(nego.cooldown_until)
    return JsonResponse({
        'ok': True,
        'ergebnis': 'abgebrochen',
        'message': (f'Verhandlung beendet. Neues Angebot ab '
                    f'{bis:%d.%m.%Y %H:%M} möglich.'),
        'negotiation': _nego_payload(nego),
    })
