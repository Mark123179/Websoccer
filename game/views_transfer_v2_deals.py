"""Views für das Transfersystem v2 — Kader anbieten, Meine Deals, Deal-Builder
(Task #821).

Kader anbieten (Reiter 4): Statusboard je Spieler (Profis/U21), Sale-Status-
Chips, Beobachter-Aufklappen, Wechselsperre-/Leih-Blockade, „Auf TL stellen"
mit Preisfindungs-Hilfe + Jugendabgabe-Vorschau, Forum-Post-Generator.

Meine Deals (Reiter 3): Meine Gebote, Anfragen erhalten/gesendet,
Kaufoptionen, laufende Leihen — mit Countdowns, Annehmen/Ablehnen/Zurückziehen.

Deal-Builder: Land→Liga→Verein-Kaskade, Profis/U21, max. 5 je Seite,
zweiseitiges Geld, Zeitpunkt-Chips, Live-Zusammenfassung mit Jugendabgabe.

Alle Geld-Mutationen laufen über die Service-Schicht (transfer_v2/services.py);
diese Views übersetzen nur Request → Service → Redirect/Render.
"""
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .economy.params import get_param
from .models import Club, League, Player, SquadOffer, WatchlistEntry
from .models import COUNTRY_FLAG_ASSETS
from .transfer_v2 import services
from .transfer_v2.calendar_dates import loan_deadline_date, loan_market_paused
from .transfer_v2.models import (
    ClubPartnership, DealRequest, DealRequestPlayer, Loan, LoanListing,
    PendingTransfer, TransferBid, TransferListing,
)
from .transfer_v2.services import TransferActionError
from .views import build_game_header, current_manager_club, YOUTH_AGE_LIMIT
from .views_transfer_v2 import (
    _euro, _levy_shares, _parse_amount, _positions, transfer_shell_context,
)
from .transfer_v2.youth_levy import calc_youth_levy

_LEVY_MIN = 'JUGENDABGABE_MIN_JE_VEREIN'
_LEVY_PCT = 'JUGENDABGABE_PCT'


# ── Helfer ────────────────────────────────────────────────────────────────

def _pct_de(value):
    s = f'{value:.2f}'.rstrip('0').rstrip('.')
    return s.replace('.', ',') + ' %'


def _is_youth(player):
    return player.age is not None and player.age <= YOUTH_AGE_LIMIT


def _player_card(player):
    """Schlankes Template-Dict für Spieler-Listen (Board, Builder, Popup)."""
    hp, np_ = _positions(player)
    return {
        'id': player.pk,
        'name': player.full_name,
        'age': player.age,
        'portrait': player.portrait_url,
        'flag': player.flag_url,
        'hp': hp,
        'np': np_,
        'mw_fmt': _euro(player.market_value),
        'mw_val': float(player.market_value or 0),
        'player_url': reverse('player_detail', args=[player.pk]),
        'locked': player.is_transfer_locked,
        'lock_days': player.transfer_lock_days_remaining,
        'loaned_out': player.is_loaned_out,
        'loaned_in': player.is_loaned_in,
    }


def _levy_sheet(player, seller):
    """Jugendabgabe-Vorschau-Daten für ein Modal (identisch zum Deal-Sheet)."""
    return {
        'levy': _levy_shares(player, seller),
        'levyMin': float(get_param(_LEVY_MIN)),
        'levyPctLabel': _pct_de(Decimal(str(get_param(_LEVY_PCT))) * 100),
    }


def _deal_title(deal, *, perspective_club):
    """„An/Von <Verein> · <Typ>" abhängig von der Perspektive."""
    typ_label = deal.get_typ_display()
    if deal.from_club_id == perspective_club.pk:
        return f'An {deal.to_club.name} · {typ_label}'
    return f'Von {deal.from_club.name} · {typ_label}'


def _deal_summary(deal):
    """Zusammenfassungs-Popup-Daten (§4.6) — ohne Differenz-/Paketwert."""
    from_players = []
    to_players = []
    p_obj_map = {}
    for e in deal.players.select_related('player'):
        p_obj_map[e.player_id] = e.player
        card = _player_card(e.player)
        if e.side == DealRequestPlayer.SIDE_FROM:
            from_players.append(card)
        else:
            to_players.append(card)

    is_swap = bool(from_players and to_players)

    # Jugendabgabe je Seite (wer zahlt an wen) — Single Source: calc_youth_levy.
    def _levy_side(players, zahler, gegen_geld):
        rows = []
        n = max(len(players), 1)
        for p in players:
            mw = Decimal(str(p['mw_val']))
            geld_anteil = Decimal(str(gegen_geld or 0)) / n
            basis = mw + geld_anteil if is_swap else geld_anteil
            res = calc_youth_levy(p_obj_map[p['id']], basis, zahler_club=zahler)
            for cid, betrag in res['betraege_je_ausbildungsverein'].items():
                rows.append({
                    'player': p['name'],
                    'club': club_names.get(cid, '—'),
                    'amt_fmt': _euro(betrag),
                })
        return rows

    club_names = {c.pk: c.name for c in Club.objects.all()}

    levy_from = _levy_side(from_players, deal.from_club, deal.cash_to)
    levy_to = _levy_side(to_players, deal.to_club, deal.cash_from)

    return {
        'id': deal.pk,
        'typ': deal.get_typ_display(),
        'timing': deal.get_timing_display(),
        'from_club': deal.from_club.name,
        'to_club': deal.to_club.name,
        'from_crest': deal.from_club.crest_static_path,
        'to_crest': deal.to_club.crest_static_path,
        'from_players': from_players,
        'to_players': to_players,
        'cash_from': int(deal.cash_from or 0),
        'cash_from_fmt': _euro(deal.cash_from) if deal.cash_from else '',
        'cash_to': int(deal.cash_to or 0),
        'cash_to_fmt': _euro(deal.cash_to) if deal.cash_to else '',
        'levy_from': levy_from,
        'levy_to': levy_to,
        'message': deal.message,
        'is_loan': deal.typ == DealRequest.TYP_LOAN,
        'loan_fee_fmt': _euro(deal.loan_fee) if deal.loan_fee else '',
        'loan_until': (deal.get_loan_until_display()
                       if deal.loan_until else ''),
        'loan_buy_fmt': (_euro(deal.loan_buy_option)
                         if deal.loan_buy_option else ''),
        'expires_ms': int(deal.expires_at.timestamp() * 1000),
    }


# ══════════════════════════════════════════════════════════════════════════
#  KADER ANBIETEN (Reiter 4)
# ══════════════════════════════════════════════════════════════════════════

@login_required
def transfer_offer_board(request):
    club = current_manager_club(user=request.user)
    if not club:
        return redirect('management_hub')

    seg = request.GET.get('seg', 'profis')
    if seg not in ('profis', 'u21'):
        seg = 'profis'

    squad = list(
        Player.objects.filter(club=club)
        .select_related('real_life_club')
        .order_by('-market_value', 'last_name')
    )
    offers = {
        o.player_id: o.status
        for o in SquadOffer.objects.filter(player__club=club)
    }

    # Beobachter je Spieler (Wappen + Vereinsname + Managername).
    watchers_by_player = {}
    watch_qs = (
        WatchlistEntry.objects
        .filter(player__in=squad)
        .select_related('manager', 'manager__managed_club')
    )
    for w in watch_qs:
        wclub = getattr(w.manager, 'managed_club', None)
        watchers_by_player.setdefault(w.player_id, []).append({
            'club': wclub.name if wclub else '—',
            'crest': wclub.crest_static_path if wclub else '',
            'club_url': (reverse('club_detail', args=[wclub.pk])
                         if wclub else ''),
            'manager': w.manager.name,
        })

    rows = []
    for p in squad:
        is_y = _is_youth(p)
        if seg == 'u21' and not is_y:
            continue
        if seg == 'profis' and is_y:
            continue
        card = _player_card(p)
        watchers = watchers_by_player.get(p.pk, [])
        card.update({
            'status': offers.get(p.pk, SquadOffer.STATUS_UVK),
            'watchers': watchers[:6],
            'watchers_extra': max(0, len(watchers) - 6),
            'watch_count': len(watchers),
            'listing_sheet': {
                'id': p.pk,
                'name': p.full_name,
                'sub': (f'{p.age} J. · {card["hp"]}'
                        + (f' · {card["np"]}' if card['np'] else '')
                        + ' · MW ' + _euro(p.market_value)),
                'mw': float(p.market_value or 0),
                'guidance': services.price_guidance(p),
                **_levy_sheet(p, club),
            },
        })
        rows.append(card)

    # Kaderstand-Zeile.
    from game.economy.kader import (effective_squad_limit, min_squad_size,
                                    squad_count)
    verliehen = Loan.objects.filter(owner_club=club, ended_at__isnull=True).count()
    ausgeliehen = Loan.objects.filter(loan_club=club, ended_at__isnull=True).count()

    status_choices = [
        {'code': c[0], 'label': c[1]} for c in SquadOffer.STATUS_CHOICES
    ]

    context = {
        'game_header': build_game_header(
            'Transfers', 'Kader anbieten · Kommunikation, kein Zwang',
            back_url='/'),
        'active_tab': 'anbieten',
        'club': club,
        'seg': seg,
        'rows': rows,
        'status_choices': status_choices,
        'squad_count': squad_count(club),
        'squad_min': min_squad_size(),
        'squad_max': effective_squad_limit(club),
        'verliehen': verliehen,
        'ausgeliehen': ausgeliehen,
        'min_bid_floor': int(get_param('TRANSFER_MIN_GEBOT')),
        'loan_min_fee': int(get_param('LEIHE_MIN_GEBUEHR')),
        'sheets_json': [r['listing_sheet'] for r in rows],
        **transfer_shell_context(club),
    }
    return render(request, 'game/transfer_v2/anbieten.html', context)


@login_required
@require_POST
def transfer_offer_status(request):
    club = current_manager_club(user=request.user)
    if not club:
        return redirect('management_hub')
    player = get_object_or_404(Player, pk=request.POST.get('player_id'))
    try:
        services.set_squad_offer_status(
            player, club, request.POST.get('status', ''))
    except TransferActionError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, f'Status für {player.full_name} gespeichert.')
    seg = request.POST.get('seg', 'profis')
    return redirect(f"{reverse('transfer_offer_board')}?seg={seg}")


@login_required
@require_POST
def transfer_offer_create_listing(request):
    club = current_manager_club(user=request.user)
    if not club:
        return redirect('management_hub')
    player = get_object_or_404(Player, pk=request.POST.get('player_id'))
    try:
        min_bid = _parse_amount(request.POST.get('min_bid'))
        buy_now_raw = (request.POST.get('buy_now') or '').strip()
        buy_now = _parse_amount(buy_now_raw) if buy_now_raw else None
        timing = request.POST.get('timing', 'SOFORT')
        duration_raw = request.POST.get('duration', '3')
        try:
            duration = int(duration_raw)
        except (TypeError, ValueError):
            raise TransferActionError('Ungültige Laufzeit.')
        services.create_listing(
            player, club, min_bid=min_bid, buy_now=buy_now,
            timing=timing, duration_days=duration)
    except TransferActionError as exc:
        messages.error(request, str(exc))
        return redirect(f"{reverse('transfer_offer_board')}?seg="
                        f"{request.POST.get('seg', 'profis')}")
    messages.success(
        request,
        f'{player.full_name} steht ab sofort auf dem Transfermarkt.')
    return redirect('transfer_market')


@login_required
def transfer_offer_forum(request):
    """Gibt den Forum-Post als reinen Text (JSON) für das Modal zurück."""
    from django.http import JsonResponse
    club = current_manager_club(user=request.user)
    if not club:
        return JsonResponse({'text': ''}, status=403)
    return JsonResponse({'text': services.build_forum_post(club)})


# ══════════════════════════════════════════════════════════════════════════
#  MEINE DEALS (Reiter 3)
# ══════════════════════════════════════════════════════════════════════════

@login_required
def transfer_my_deals(request):
    club = current_manager_club(user=request.user)
    if not club:
        return redirect('management_hub')
    now = timezone.now()

    # 4.1 Meine Gebote.
    my_bids = []
    bids = (
        TransferBid.objects
        .filter(club=club, listing__status=TransferListing.STATUS_ACTIVE)
        .select_related('listing__player', 'listing__seller')
        .order_by('-created_at')
    )
    for b in bids:
        listing = b.listing
        leading = (TransferBid.objects
                   .filter(listing=listing, is_leading=True).first())
        my_bids.append({
            'listing_id': listing.pk,
            'player': listing.player.full_name,
            'player_url': reverse('player_detail', args=[listing.player.pk]),
            'seller': listing.seller.name if listing.seller else 'Vereinslos',
            'my_bid_fmt': _euro(b.amount),
            'top_fmt': _euro(leading.amount) if leading else '—',
            'leading': bool(leading and leading.club_id == club.pk),
            'ends_ms': (int(listing.ends_at.timestamp() * 1000)
                        if listing.ends_at else ''),
            'over': bool(listing.ends_at and listing.ends_at <= now),
        })

    # 4.2/4.3 Anfragen erhalten / gesendet.
    recv = (
        DealRequest.objects
        .filter(to_club=club, status=DealRequest.STATUS_OPEN)
        .select_related('from_club').prefetch_related('players__player')
        .order_by('expires_at')
    )
    sent = (
        DealRequest.objects
        .filter(from_club=club, status=DealRequest.STATUS_OPEN)
        .select_related('to_club').prefetch_related('players__player')
        .order_by('expires_at')
    )

    def _deal_row(deal, *, received):
        other = deal.from_club if received else deal.to_club
        reserved = deal.cash_from if not received else Decimal('0')
        if deal.typ == DealRequest.TYP_LOAN and not received:
            reserved = deal.loan_fee or Decimal('0')
        return {
            'id': deal.pk,
            'title': _deal_title(deal, perspective_club=club),
            'crest': other.crest_static_path,
            'timing': deal.get_timing_display(),
            'reserved_fmt': _euro(reserved) if reserved else '',
            'expires_ms': int(deal.expires_at.timestamp() * 1000),
        }

    recv_rows = [_deal_row(d, received=True) for d in recv]
    sent_rows = [_deal_row(d, received=False) for d in sent]

    # 4.4 Kaufoptionen.
    own_options = []
    for loan in (Loan.objects
                 .filter(loan_club=club, ended_at__isnull=True,
                         buy_option__isnull=False)
                 .select_related('player', 'owner_club')):
        own_options.append({
            'loan_id': loan.pk,
            'player': loan.player.full_name,
            'player_url': reverse('player_detail', args=[loan.player.pk]),
            'flag': loan.player.flag_url,
            'hp': loan.player.main_position_1 or '—',
            'owner': loan.owner_club.name,
            'price_fmt': _euro(loan.buy_option),
        })
    foreign_options = []
    for loan in (Loan.objects
                 .filter(owner_club=club, ended_at__isnull=True,
                         buy_option__isnull=False)
                 .select_related('player', 'loan_club')):
        foreign_options.append({
            'player': loan.player.full_name,
            'loan_club': loan.loan_club.name,
            'price_fmt': _euro(loan.buy_option),
        })

    # 4.5 Laufende Leihen.
    def _loan_card(loan, *, outgoing):
        p = loan.player
        partner = loan.loan_club if outgoing else loan.owner_club
        hp, np_ = _positions(p)
        return {
            'id': loan.pk,
            'player': p.full_name,
            'player_url': reverse('player_detail', args=[p.pk]),
            'portrait': p.portrait_url,
            'flag': p.flag_url,
            'age': p.age,
            'hp': hp,
            'np': np_,
            'mw_fmt': _euro(p.market_value),
            'partner': partner.name,
            'partner_crest': partner.crest_static_path,
            'until': loan.get_until_display(),
            'fee_fmt': _euro(loan.fee),
            'buy_fmt': _euro(loan.buy_option) if loan.buy_option else '',
            'has_option': loan.buy_option is not None,
            'outgoing': outgoing,
            'recall_requested': loan.recall_requested,
        }

    loans_out = [_loan_card(l, outgoing=True) for l in
                 Loan.objects.filter(owner_club=club, ended_at__isnull=True)
                 .select_related('player', 'loan_club')]
    loans_in = [_loan_card(l, outgoing=False) for l in
                Loan.objects.filter(loan_club=club, ended_at__isnull=True)
                .select_related('player', 'owner_club')]

    # Zusammenfassungs-Popup-Daten (erhalten + gesendet).
    summaries = {}
    for d in list(recv) + list(sent):
        summaries[d.pk] = _deal_summary(d)

    seg = request.GET.get('seg', 'gebote')
    if seg not in ('gebote', 'erhalten', 'gesendet', 'optionen', 'leihen'):
        seg = 'gebote'

    context = {
        'game_header': build_game_header(
            'Transfers', 'Meine Deals · Gebote, Anfragen & Leihen',
            back_url='/'),
        'active_tab': 'deals',
        'club': club,
        'seg': seg,
        'my_bids': my_bids,
        'recv_rows': recv_rows,
        'sent_rows': sent_rows,
        'recv_count': len(recv_rows),
        'own_options': own_options,
        'foreign_options': foreign_options,
        'loans_out': loans_out,
        'loans_in': loans_in,
        'summaries_json': list(summaries.values()),
        **transfer_shell_context(club),
    }
    return render(request, 'game/transfer_v2/deals.html', context)


@login_required
@require_POST
def transfer_deal_accept(request):
    club = current_manager_club(user=request.user)
    if not club:
        return redirect('management_hub')
    deal = get_object_or_404(DealRequest, pk=request.POST.get('deal_id'))
    if deal.to_club_id != club.pk:
        messages.error(request, 'Diese Anfrage betrifft nicht deinen Verein.')
        return redirect('transfer_my_deals')
    try:
        services.accept_deal(deal)
    except TransferActionError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, 'Anfrage angenommen — Deal vollzogen.')
    return redirect(f"{reverse('transfer_my_deals')}?seg=erhalten")


@login_required
@require_POST
def transfer_deal_decline(request):
    club = current_manager_club(user=request.user)
    if not club:
        return redirect('management_hub')
    deal = get_object_or_404(DealRequest, pk=request.POST.get('deal_id'))
    if deal.to_club_id != club.pk:
        messages.error(request, 'Diese Anfrage betrifft nicht deinen Verein.')
        return redirect('transfer_my_deals')
    services.decline_deal(deal)
    messages.success(request, 'Anfrage abgelehnt.')
    return redirect(f"{reverse('transfer_my_deals')}?seg=erhalten")


@login_required
@require_POST
def transfer_deal_withdraw(request):
    club = current_manager_club(user=request.user)
    if not club:
        return redirect('management_hub')
    deal = get_object_or_404(DealRequest, pk=request.POST.get('deal_id'))
    if deal.from_club_id != club.pk:
        messages.error(request, 'Nur der Initiator kann zurückziehen.')
        return redirect('transfer_my_deals')
    services.withdraw_deal(deal)
    messages.success(request, 'Anfrage zurückgezogen — Reservierung frei.')
    return redirect(f"{reverse('transfer_my_deals')}?seg=gesendet")


@login_required
@require_POST
def transfer_deal_bid_remove(request):
    """Beendete Auktion aus „Meine Gebote" entfernen (nur Anzeige)."""
    # Es gibt keine eigene Tabelle für „entfernt"; wir leiten einfach zurück.
    # Nur beendete/nicht mehr aktive Listings verschwinden ohnehin aus der
    # Liste (Filter status=ACTIVE). Kein Datenmutations-Bedarf.
    return redirect(f"{reverse('transfer_my_deals')}?seg=gebote")


@login_required
@require_POST
def transfer_option_exercise(request):
    club = current_manager_club(user=request.user)
    if not club:
        return redirect('management_hub')
    loan = get_object_or_404(Loan, pk=request.POST.get('loan_id'))
    if loan.loan_club_id != club.pk:
        messages.error(request, 'Nur der Leihverein kann die Option ziehen.')
        return redirect('transfer_my_deals')
    try:
        services.exercise_buy_option(loan, club)
    except TransferActionError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(
            request,
            f'Kaufoption gezogen — {loan.player.full_name} gehört jetzt '
            f'{club.name}.')
    return redirect(f"{reverse('transfer_my_deals')}?seg=optionen")


# ══════════════════════════════════════════════════════════════════════════
#  LEIHMARKT (Reiter 2, Task #822)
# ══════════════════════════════════════════════════════════════════════════

@login_required
def transfer_loan_market(request):
    club = current_manager_club(user=request.user)
    if not club:
        return redirect('management_hub')

    fil = request.GET.get('f', '')
    if fil not in ('', 'WP', 'SE', 'opt'):
        fil = ''

    qs = (
        LoanListing.objects
        .filter(status=LoanListing.STATUS_ACTIVE)
        .select_related('player', 'owner_club')
        .order_by('-created_at')
    )
    if fil in ('WP', 'SE'):
        qs = qs.filter(until=fil)
    elif fil == 'opt':
        qs = qs.filter(buy_option_price__isnull=False)

    # Leih-Limits des eigenen Vereins (rein) — für Hinweis-Anzeige.
    rein_limit = int(get_param('LEIHE_LIMIT_REIN'))
    rein_aktiv = Loan.objects.filter(
        loan_club=club, ended_at__isnull=True).count()

    from .views_transfer_v2 import _tm_url
    rows = []
    for ll in qs:
        p = ll.player
        card = _player_card(p)
        paused = loan_market_paused(ll.until)
        partner = ClubPartnership.are_partners(ll.owner_club, club)
        fee = ll.fee_asking or Decimal('0')
        rows.append({
            **card,
            'listing_id': ll.pk,
            'owner': ll.owner_club.name,
            'owner_crest': ll.owner_club.crest_static_path,
            'owner_url': reverse('club_detail', args=[ll.owner_club.pk]),
            'own_listing': ll.owner_club_id == club.pk,
            'fee_fmt': ('0 €' if fee == 0 else _euro(fee)),
            'fee_zero': fee == 0,
            'partner': partner,
            'until': ll.get_until_display(),
            'until_code': ll.until,
            'opt_fmt': (_euro(ll.buy_option_price)
                        if ll.buy_option_price is not None else '—'),
            'tm_url': _tm_url(p.full_name),
            'paused': paused,
        })

    wp_deadline = loan_deadline_date('WP')
    se_deadline = loan_deadline_date('SE')
    wp_paused = loan_market_paused('WP')
    se_paused = loan_market_paused('SE')
    deadline_spieltage = int(get_param('LEIHE_DEADLINE_SPIELTAGE'))

    context = {
        'game_header': build_game_header(
            'Transfers', 'Leihmarkt · Leihen bis WP oder Saisonende',
            back_url='/'),
        'active_tab': 'leihmarkt',
        'club': club,
        'fil': fil,
        'rows': rows,
        'wp_deadline': wp_deadline,
        'se_deadline': se_deadline,
        'wp_paused': wp_paused,
        'se_paused': se_paused,
        'all_paused': wp_paused and se_paused,
        'deadline_spieltage': deadline_spieltage,
        'min_fee_fmt': _euro(get_param('LEIHE_MIN_GEBUEHR')),
        'rein_limit': rein_limit,
        'rein_aktiv': rein_aktiv,
        'rein_voll': rein_aktiv >= rein_limit,
        **transfer_shell_context(club),
    }
    return render(request, 'game/transfer_v2/leihmarkt.html', context)


@login_required
@require_POST
def transfer_loan_request(request):
    """Leihanfrage aus dem Leihmarkt (reserviert die Gebühr, 7 Tage offen)."""
    club = current_manager_club(user=request.user)
    if not club:
        return redirect('management_hub')
    listing = get_object_or_404(
        LoanListing, pk=request.POST.get('listing_id'))
    try:
        services.request_loan(listing, club)
    except TransferActionError as exc:
        messages.error(request, str(exc))
        return redirect('transfer_loan_market')
    fee = listing.fee_asking or Decimal('0')
    note = (f'Leihanfrage für {listing.player.full_name} gesendet'
            + (f' — {_euro(fee)} reserviert.' if fee > 0
               else ' — 0 € (Partnerverein).'))
    messages.success(request, note)
    return redirect(f"{reverse('transfer_my_deals')}?seg=gesendet")


@login_required
@require_POST
def transfer_loan_listing_create(request):
    """„Auf den Leihmarkt stellen" aus dem Kader-anbieten-Board."""
    club = current_manager_club(user=request.user)
    if not club:
        return redirect('management_hub')
    player = get_object_or_404(Player, pk=request.POST.get('player_id'))
    try:
        fee = _parse_amount(request.POST.get('loan_fee') or '0') \
            if (request.POST.get('loan_fee') or '').strip() else Decimal('0')
        buy_raw = (request.POST.get('loan_buy') or '').strip()
        buy = _parse_amount(buy_raw) if buy_raw else None
        until = request.POST.get('loan_until', 'SE')
        services.create_loan_listing(
            player, club, fee_asking=fee, until=until,
            buy_option_price=buy)
    except TransferActionError as exc:
        messages.error(request, str(exc))
        return redirect(f"{reverse('transfer_offer_board')}?seg="
                        f"{request.POST.get('seg', 'profis')}")
    messages.success(
        request, f'{player.full_name} steht ab sofort auf dem Leihmarkt.')
    return redirect('transfer_loan_market')


@login_required
@require_POST
def transfer_loan_listing_withdraw(request):
    club = current_manager_club(user=request.user)
    if not club:
        return redirect('management_hub')
    listing = get_object_or_404(
        LoanListing, pk=request.POST.get('listing_id'))
    try:
        services.withdraw_loan_listing(listing, club)
    except TransferActionError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(
            request,
            f'{listing.player.full_name} vom Leihmarkt zurückgezogen.')
    return redirect('transfer_loan_market')


@login_required
@require_POST
def transfer_loan_recall_request(request):
    """Stammverein fragt Rückruf an (nur einvernehmlich)."""
    club = current_manager_club(user=request.user)
    if not club:
        return redirect('management_hub')
    loan = get_object_or_404(Loan, pk=request.POST.get('loan_id'))
    try:
        services.request_recall(loan, club)
    except TransferActionError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(
            request,
            f'Rückruf angefragt — {loan.loan_club.name} muss zustimmen.')
    return redirect(f"{reverse('transfer_my_deals')}?seg=leihen")


@login_required
@require_POST
def transfer_loan_recall_respond(request):
    """Leihverein stimmt dem Rückruf zu oder lehnt ab."""
    club = current_manager_club(user=request.user)
    if not club:
        return redirect('management_hub')
    loan = get_object_or_404(Loan, pk=request.POST.get('loan_id'))
    accept = request.POST.get('antwort') == 'annehmen'
    try:
        services.respond_recall(loan, club, accept=accept)
    except TransferActionError as exc:
        messages.error(request, str(exc))
    else:
        if accept:
            messages.success(
                request,
                f'Rückruf angenommen — {loan.player.full_name} kehrt zu '
                f'{loan.owner_club.name} zurück.')
        else:
            messages.success(request, 'Rückruf abgelehnt — Leihe läuft weiter.')
    return redirect(f"{reverse('transfer_my_deals')}?seg=leihen")


# ══════════════════════════════════════════════════════════════════════════
#  DEAL-BUILDER
# ══════════════════════════════════════════════════════════════════════════

def _country_flag(country):
    asset = COUNTRY_FLAG_ASSETS.get(country, {})
    aid = asset.get('asset_id', '')
    if aid:
        from .asset_urls import flag_url
        return flag_url(aid)
    return ''


@login_required
def transfer_deal_builder(request):
    club = current_manager_club(user=request.user)
    if not club:
        return redirect('management_hub')

    # Ziel-Kaskade: Länder → Ligen → Vereine (mit Manager/KI-Label).
    leagues = (League.objects.exclude(country__in=['System', 'Unbekannt'])
               .order_by('country', 'level'))
    countries = {}
    for lg in leagues:
        clubs = [
            {
                'id': c.pk,
                'name': c.name,
                'crest': c.crest_static_path,
                'manager': (c.managed_by.name if c.managed_by_id else ''),
                'is_ki': not c.managed_by_id,
            }
            for c in Club.objects.filter(league=lg).exclude(pk=club.pk)
            .select_related('managed_by').order_by('name')
        ]
        entry = countries.setdefault(lg.country, {
            'name': lg.country,
            'flag': _country_flag(lg.country),
            'leagues': [],
        })
        entry['leagues'].append({
            'id': lg.pk,
            'name': lg.name,
            'clubs': clubs,
        })
    countries_list = sorted(countries.values(), key=lambda c: c['name'])

    # Eigenes Paket (Profis/U21) — nur wählbare (nicht gesperrt/verliehen).
    own_players = []
    for p in (Player.objects.filter(club=club)
              .order_by('-market_value', 'last_name')):
        card = _player_card(p)
        card['youth'] = _is_youth(p)
        card['selectable'] = not (p.is_transfer_locked or p.is_loaned_in
                                  or p.is_loaned_out)
        own_players.append(card)

    context = {
        'game_header': build_game_header(
            'Transfers', 'Deal-Builder · Neue Anfrage', back_url='/'),
        'active_tab': 'deals',
        'club': club,
        'countries_json': countries_list,
        'own_players_json': own_players,
        'levy_min': float(get_param(_LEVY_MIN)),
        'levy_pct_label': _pct_de(Decimal(str(get_param(_LEVY_PCT))) * 100),
        'max_per_side': int(get_param('TRANSFER_MAX_PAKET')),
        **transfer_shell_context(club),
    }
    return render(request, 'game/transfer_v2/builder.html', context)


@login_required
def transfer_builder_target_players(request):
    """AJAX: wählbare Spieler eines Ziel-Vereins (Profis/U21, Levy-Vorschau)."""
    from django.http import JsonResponse
    club = current_manager_club(user=request.user)
    if not club:
        return JsonResponse({'players': []}, status=403)
    target = get_object_or_404(Club, pk=request.GET.get('club_id'))
    players = []
    for p in (Player.objects.filter(club=target)
              .order_by('-market_value', 'last_name')):
        card = _player_card(p)
        card['youth'] = _is_youth(p)
        card['selectable'] = not (p.is_transfer_locked or p.is_loaned_in
                                  or p.is_loaned_out)
        players.append(card)
    return JsonResponse({'players': players})


@login_required
@require_POST
def transfer_builder_send(request):
    club = current_manager_club(user=request.user)
    if not club:
        return redirect('management_hub')
    to_club = get_object_or_404(Club, pk=request.POST.get('to_club_id'))

    def _ids(name):
        raw = request.POST.get(name, '')
        out = []
        for chunk in raw.split(','):
            chunk = chunk.strip()
            if chunk.isdigit():
                out.append(int(chunk))
        return out

    try:
        from_ids = _ids('from_players')
        to_ids = _ids('to_players')
        max_side = int(get_param('TRANSFER_MAX_PAKET'))
        if len(from_ids) > max_side or len(to_ids) > max_side:
            raise TransferActionError(f'Maximal {max_side} Spieler je Seite.')

        cash_from_raw = (request.POST.get('cash_from') or '').strip()
        cash_to_raw = (request.POST.get('cash_to') or '').strip()
        cash_from = _parse_amount(cash_from_raw) if cash_from_raw else Decimal('0')
        cash_to = _parse_amount(cash_to_raw) if cash_to_raw else Decimal('0')

        # Typ ableiten (Service erzwingt die Schemata erneut).
        if from_ids and to_ids:
            typ = (DealRequest.TYP_SWAP_CASH if (cash_from or cash_to)
                   else DealRequest.TYP_SWAP)
        elif to_ids or from_ids:
            # Kauf (Empfänger-Spieler gegen mein Geld) ODER Verkauf
            # (eigene Spieler gegen Empfänger-Geld) — beides TYP_CASH.
            typ = DealRequest.TYP_CASH
        else:
            raise TransferActionError(
                'Beide Seiten brauchen Inhalt (Spieler und/oder Geld).')

        from_players = list(Player.objects.filter(pk__in=from_ids, club=club))
        to_players = list(Player.objects.filter(pk__in=to_ids, club=to_club))
        if len(from_players) != len(from_ids) or len(to_players) != len(to_ids):
            raise TransferActionError('Ein Spieler passt nicht zum Verein.')

        services.create_deal_request(
            club, to_club, typ=typ,
            timing=request.POST.get('timing', 'SOFORT'),
            cash_from=cash_from, cash_to=cash_to,
            from_players=from_players, to_players=to_players,
            message=request.POST.get('message', ''),
        )
    except TransferActionError as exc:
        messages.error(request, str(exc))
        return redirect('transfer_deal_builder')
    messages.success(
        request, 'Anfrage gesendet — erscheint unter „Anfragen gesendet".')
    return redirect(f"{reverse('transfer_my_deals')}?seg=gesendet")
