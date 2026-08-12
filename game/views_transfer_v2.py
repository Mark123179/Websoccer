"""Views für das Transfersystem v2 — Reiter Transfermarkt (Task #820).

Rendert Ticker, Headliner, Filter, Gepinnt/Alle Listings, Gebotsverlauf,
Deal-Sheet-Daten und Transfergerüchte exakt nach Prototyp/Spec. Alle
Geld-Mutationen laufen über die Service-Schicht (game/transfer_v2/services.py);
diese Views übersetzen nur Request → Service → Redirect/Render.
"""
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from datetime import timedelta

from django.utils import timezone
from django.views.decorators.http import require_POST

from .economy.params import get_param
from .economy.reservations import reserved_money
from .models import Club, PlayerMarketValueSnapshot
from .transfer_v2 import services
from .transfer_v2.models import (
    DealRequest, ListingPin, RumorNews, TransferBid, TransferListing,
)
from .transfer_v2.services import TransferActionError
from .transfer_v2.youth_levy import calc_youth_levy
from .views import build_game_header, current_manager_club

POSITION_OPTIONS = [
    'TW', 'IV', 'LV', 'RV', 'DM', 'ZM', 'LM', 'RM', 'OM', 'LF', 'RF', 'ST',
]


# ── Helfer ────────────────────────────────────────────────────────────────

def _euro(value):
    """Deutsche Geldformatierung: 21.500.000 €. None → —."""
    if value is None:
        return '—'
    try:
        v = int(round(float(value)))
    except (TypeError, ValueError):
        return '—'
    return f'{v:,}'.replace(',', '.') + ' €'


def _num_de(value):
    try:
        v = int(round(float(value)))
    except (TypeError, ValueError):
        return ''
    return f'{v:,}'.replace(',', '.')


def _tm_url(name):
    from urllib.parse import quote
    return ('https://www.transfermarkt.de/schnellsuche/ergebnis/'
            'schnellsuche?query=' + quote(name))


def _bid_time_fmt(dt):
    """„heute 11:42" / „gestern 21:04" / „14.07. 18:20" (lokale Zeit)."""
    local = timezone.localtime(dt)
    today = timezone.localdate()
    d = local.date()
    if d == today:
        return f'heute {local:%H:%M}'
    if (today - d).days == 1:
        return f'gestern {local:%H:%M}'
    return f'{local.day:02d}.{local.month:02d}. {local:%H:%M}'


def _date_de_short(dt):
    local = timezone.localtime(dt) if timezone.is_aware(dt) else dt
    return f'{local.day:02d}.{local.month:02d}.'


def _pct_de(value):
    """Prozent deutsch, ohne überflüssige Nullen: 8 % / 2,7 %."""
    s = f'{value:.2f}'.rstrip('0').rstrip('.')
    return s.replace('.', ',') + ' %'


def _positions(player):
    hp = ','.join(player.main_positions[:3])
    np_ = ','.join(player.secondary_positions[:3])
    return hp, np_


def _mw_trend(player_ids):
    """MW-Trend je Spieler aus den letzten zwei Snapshots (0 wenn < 2)."""
    trends = {}
    snaps = (
        PlayerMarketValueSnapshot.objects
        .filter(player_id__in=player_ids)
        .order_by('player_id', '-recorded_at', '-id')
        .values_list('player_id', 'value_eur')
    )
    seen = {}
    for pid, val in snaps:
        seen.setdefault(pid, []).append(val)
    for pid, vals in seen.items():
        if len(vals) >= 2:
            trends[pid] = vals[0] - vals[1]
    return trends


# Referenz-Basis für die Anteils-Ableitung: so groß, dass die konfigurierte
# Mindestabgabe je Verein nie greift → betrag/REF ist der reine Prozentsatz.
_LEVY_REF_BASIS = Decimal('1000000000000')


def _levy_shares(player, seller):
    """Prozent-Anteile der Jugendabgabe je Ausbildungsverein.

    Single Source of Truth ist calc_youth_levy() (identisch zur Buchung):
    Mit einer Referenz-Basis, bei der die Mindestabgabe nicht bindet, ergibt
    betrag/basis exakt den Prozentanteil jedes Ausbildungsvereins. Das
    Frontend rechnet live: max(konfigurierte Mindestabgabe, Summe × Anteil).
    """
    if seller is None:
        return []
    res = calc_youth_levy(player, _LEVY_REF_BASIS, zahler_club=seller)
    betraege = res['betraege_je_ausbildungsverein']
    if not betraege:
        return []
    clubs = {c.pk: c.name for c in Club.objects.filter(pk__in=betraege)}
    shares = []
    for cid, betrag in sorted(betraege.items(), key=lambda kv: -kv[1]):
        anteil = betrag / _LEVY_REF_BASIS
        shares.append({
            'club': clubs.get(cid, '—'),
            'pct_raw': float(anteil),
            'pct_label': _pct_de(anteil * 100),
        })
    return shares


def _countdown_label(ends_at, now):
    """Server-seitiger Initialtext (JS übernimmt sekündlich)."""
    if ends_at is None:
        return '24h ab 1. Gebot', 'none'
    rest = (ends_at - now).total_seconds()
    if rest <= 0:
        return 'beendet', 'over'
    s = int(rest)
    if s < 3600:
        return f'{s // 60:02d}:{s % 60:02d} min', 'red'
    if s < 86400:
        return f'{s // 3600}h {s % 3600 // 60}m', ('gold' if s < 43200 else 'white')
    return f'{s // 86400} T {s % 86400 // 3600} h', 'white'


def _listing_row(listing, *, club, trends, pinned_ids, pin_counts, now):
    """Ein Listing → Template-Dict (Tabelle, Headliner UND Deal-Sheet)."""
    p = listing.player
    seller = listing.seller
    hp, np_ = _positions(p)
    trend = trends.get(p.pk, Decimal('0'))
    leading = None
    bids = []
    for b in listing.bid_list:
        bids.append({
            'club': b.club.name,
            'amt_fmt': _euro(b.amount),
            'time_fmt': _bid_time_fmt(b.created_at),
        })
        if b.is_leading:
            leading = b
    next_min = services.min_next_bid(listing)
    cd_label, cd_kind = _countdown_label(listing.ends_at, now)

    top_club_txt = ''
    top_own = False
    if leading is not None:
        if club is not None and leading.club_id == club.pk:
            top_club_txt = 'Du führst!'
            top_own = True
        else:
            top_club_txt = leading.club.name
    elif not bids:
        top_club_txt = 'kein Gebot'

    is_own = club is not None and listing.seller_id == club.pk
    buy_now = listing.buy_now
    mw = p.market_value

    return {
        'id': listing.pk,
        'name': p.full_name,
        'age': p.age,
        'portrait': p.portrait_url,
        'flag': p.flag_url,
        'player_url': reverse('player_detail', args=[p.pk]),
        'hp': hp,
        'np': np_,
        'seller_name': seller.name if seller else 'Vereinslos',
        'seller_crest': seller.crest_static_path if seller else '',
        'seller_url': (reverse('club_detail', args=[seller.pk])
                       if seller else ''),
        'rl': (p.real_life_club.name if p.real_life_club_id else '—'),
        'mw_fmt': _euro(mw),
        'mw_val': float(mw or 0),
        'tm_url': _tm_url(p.full_name),
        'trend_up': trend > 0,
        'trend_zero': trend == 0,
        'trend_txt': ('—' if trend == 0 else
                      ('▲ +' if trend > 0 else '▼ −') + _num_de(abs(trend))),
        'timing': listing.get_timing_display(),
        'timing_code': listing.timing,
        'timing_sofort': listing.timing == TransferListing.TIMING_SOFORT,
        'since': _date_de_short(listing.listed_at),
        'min_fmt': _euro(listing.min_bid),
        'top_fmt': _euro(leading.amount) if leading else '—',
        'top_club_txt': top_club_txt,
        'top_own': top_own,
        'buy_fmt': _euro(buy_now) if buy_now is not None else '—',
        'has_buy': buy_now is not None,
        'cd_label': cd_label,
        'cd_kind': cd_kind,
        'ends_at_ms': (int(listing.ends_at.timestamp() * 1000)
                       if listing.ends_at else ''),
        'ext': listing.extensions,
        'pins': pin_counts.get(listing.pk, 0),
        'pinned': listing.pk in pinned_ids,
        'own': is_own,
        'is_fa': listing.is_free_agent,
        'bids': bids,
        'has_bids': bool(bids),
        # Deal-Sheet-Daten (JSON via json_script):
        'sheet': {
            'id': listing.pk,
            'name': p.full_name,
            'sub': (f'{p.age} J. · {hp}' + (f' · {np_}' if np_ else '')
                    + ' · ' + (seller.name if seller else 'Vereinslos')),
            'img': p.portrait_url,
            'nextMin': float(next_min),
            'buyNow': float(buy_now) if buy_now is not None else None,
            'fa': listing.is_free_agent,
            'timing': listing.get_timing_display(),
            'levy': _levy_shares(p, seller),
            'levyMin': float(get_param('JUGENDABGABE_MIN_JE_VEREIN')),
            'levyPctLabel': _pct_de(
                Decimal(str(get_param('JUGENDABGABE_PCT'))) * 100),
        },
    }


# ── Gemeinsamer Kontext (Budget-Kopf + Tabs) ──────────────────────────────

def transfer_shell_context(club):
    reserviert = reserved_money(club)
    verfuegbar = (club.budget or Decimal('0')) - reserviert
    open_deals = DealRequest.objects.filter(
        to_club=club, status=DealRequest.STATUS_OPEN).count()
    return {
        'konto_fmt': _euro(club.budget),
        'reserviert_fmt': _euro(reserviert),
        'verfuegbar_fmt': _euro(verfuegbar),
        'open_deal_count': open_deals,
    }


# ── Ticker ────────────────────────────────────────────────────────────────

def _ticker_parts(listings, now):
    """Laufband-Segmente aus vorhandenen Daten (KEINE neuen Inhalte)."""
    parts = []

    def plain(t):
        parts.append({'t': t, 'kind': 'plain', 'url': ''})

    def player(p):
        parts.append({'t': p.full_name, 'kind': 'player',
                      'url': reverse('player_detail', args=[p.pk])})

    def clubpart(c):
        parts.append({'t': c.name.upper(), 'kind': 'club',
                      'url': reverse('club_detail', args=[c.pk])})

    def gold(t):
        parts.append({'t': t, 'kind': 'deadline', 'url': ''})

    # Jüngste Gebots-Erhöhungen (führende Gebote, neueste zuerst).
    recent = (TransferBid.objects
              .filter(listing__in=[l for l in listings], is_leading=True)
              .select_related('club', 'listing__player', 'listing__seller')
              .order_by('-created_at')[:3])
    for b in recent:
        clubpart(b.club)
        plain(f' erhöht auf {_euro(b.amount)} für ')
        player(b.listing.player)
        if b.listing.seller:
            plain(' (')
            clubpart(b.listing.seller)
            plain(') +++ ')
        else:
            plain(' +++ ')

    # Endspurt: Auktionen, die in < 2 h enden.
    for l in listings:
        if l.ends_at and timedelta() < (l.ends_at - now) <= timedelta(hours=2):
            plain('ENDSPURT: ')
            player(l.player)
            plain(' — ')
            gold('Auktion endet in unter 2 Stunden')
            plain(' +++ ')
            break

    # Anti-Sniping-Verlängerungen.
    ext = [l for l in listings if l.extensions > 0]
    if ext:
        l = max(ext, key=lambda x: x.extensions)
        plain('ANTI-SNIPING: Die ')
        player(l.player)
        plain(f'-Auktion bereits {l.extensions}× verlängert +++ ')

    # Vereinslose.
    fa = [l for l in listings if l.is_free_agent]
    if fa:
        l = fa[0]
        plain('VEREINSLOS: ')
        player(l.player)
        plain(f' ab {_euro(l.min_bid)} — 24h-Auktion ab erstem Gebot +++ ')

    # Neue Listings (< 24 h).
    new = [l for l in listings
           if not l.is_free_agent
           and (now - l.listed_at) <= timedelta(hours=24)]
    if new:
        l = new[0]
        plain('NEU AUF DER LISTE: ')
        player(l.player)
        plain(f' ab {_euro(l.min_bid)} +++ ')

    # Leih-Deadline.
    from .transfer_v2.calendar_dates import loan_deadline_date
    try:
        dl = loan_deadline_date('WP')
        plain('LEIH-DEADLINE zur Winterpause: ')
        gold(f'{dl.day:02d}.{dl.month:02d}.{dl.year}')
        plain(' +++ ')
    except Exception:
        pass
    return parts


# ── Seiten-View ───────────────────────────────────────────────────────────

@login_required
def transfer_market(request):
    club = current_manager_club(user=request.user)
    if not club:
        return redirect('management_hub')
    now = timezone.now()

    listings = list(
        TransferListing.objects
        .filter(status=TransferListing.STATUS_ACTIVE)
        .select_related('player', 'player__real_life_club', 'seller')
        .prefetch_related('bids__club')
    )
    for l in listings:
        l.bid_list = sorted(l.bids.all(), key=lambda b: b.created_at,
                            reverse=True)

    player_ids = [l.player_id for l in listings]
    trends = _mw_trend(player_ids)
    pinned_ids = set(
        ListingPin.objects.filter(club=club, listing__in=listings)
        .values_list('listing_id', flat=True)
    )
    pin_counts = {}
    for pin in ListingPin.objects.filter(listing__in=listings):
        pin_counts[pin.listing_id] = pin_counts.get(pin.listing_id, 0) + 1

    rows = {
        l.pk: _listing_row(l, club=club, trends=trends,
                           pinned_ids=pinned_ids, pin_counts=pin_counts,
                           now=now)
        for l in listings
    }

    # Headliner: die 3 zeitlich nächsten Auktionsenden.
    dated = sorted((l for l in listings if l.ends_at and l.ends_at > now),
                   key=lambda l: l.ends_at)
    headliners = [rows[l.pk] for l in dated[:3]]

    pinned_rows = [rows[l.pk] for l in listings if l.pk in pinned_ids]
    # Alle Listings: endend zuerst, Vereinslose ohne ends_at hinten.
    ordered = sorted(
        listings,
        key=lambda l: (l.ends_at is None, l.ends_at or now, l.pk),
    )
    all_rows = [rows[l.pk] for l in ordered]

    ticker_enabled = bool(get_param('TRANSFER_TICKER_ENABLED'))
    ticker = _ticker_parts(listings, now) if ticker_enabled else []

    rumors = []
    for r in RumorNews.objects.select_related('player')[:8]:
        rumors.append({
            'id': r.pk,
            'outlet': r.outlet,
            'headline': r.headline,
            'img': (r.player.portrait_url if r.player_id else ''),
            'can_react': (r.affected_club_id == club.pk and not r.reaction),
            'reaction': r.reaction,
        })

    sheets = [rows[l.pk]['sheet'] for l in ordered]

    context = {
        'game_header': build_game_header(
            'Transfers', 'Transfermarkt · Jeder Tag ist Deadline Day',
            back_url='/'),
        'active_tab': 'markt',
        'club': club,
        'ticker_enabled': ticker_enabled and bool(ticker),
        'ticker': ticker,
        'headliners': headliners,
        'pinned_rows': pinned_rows,
        'all_rows': all_rows,
        'listing_total': len(all_rows),
        'position_options': POSITION_OPTIONS,
        'rumors': rumors,
        'sheets_json': sheets,
        **transfer_shell_context(club),
    }
    return render(request, 'game/transfer_v2/transfermarkt.html', context)


# ── POST-Endpunkte ────────────────────────────────────────────────────────

def _parse_amount(raw):
    digits = ''.join(ch for ch in str(raw or '') if ch.isdigit())
    if not digits:
        raise TransferActionError('Bitte einen gültigen Betrag eingeben.')
    try:
        return Decimal(digits)
    except InvalidOperation:
        raise TransferActionError('Bitte einen gültigen Betrag eingeben.')


@login_required
@require_POST
def transfer_market_bid(request):
    club = current_manager_club(user=request.user)
    if not club:
        return redirect('management_hub')
    listing = get_object_or_404(
        TransferListing, pk=request.POST.get('listing_id'))
    try:
        amount = _parse_amount(request.POST.get('amount'))
        services.place_bid(listing, club, amount)
    except TransferActionError as exc:
        messages.error(request, str(exc))
    else:
        listing.refresh_from_db()
        note = f'Gebot platziert — {_euro(amount)} reserviert. Gebot ist bindend.'
        if listing.extensions > 0 and listing.ends_at and (
                listing.ends_at - timezone.now()) > timedelta(hours=23):
            note += ' Anti-Sniping: Auktion +24 h verlängert.'
        messages.success(request, note)
    return redirect('transfer_market')


@login_required
@require_POST
def transfer_market_buy_now(request):
    club = current_manager_club(user=request.user)
    if not club:
        return redirect('management_hub')
    listing = get_object_or_404(
        TransferListing, pk=request.POST.get('listing_id'))
    try:
        services.buy_now(listing, club)
    except TransferActionError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(
            request,
            f'Sofortkauf abgeschlossen — {listing.player.full_name} '
            f'wechselt zu {club.name}.')
    return redirect('transfer_market')


@login_required
@require_POST
def transfer_market_pin(request):
    club = current_manager_club(user=request.user)
    if not club:
        return redirect('management_hub')
    listing = get_object_or_404(
        TransferListing, pk=request.POST.get('listing_id'),
        status=TransferListing.STATUS_ACTIVE)
    pin = ListingPin.objects.filter(listing=listing, club=club).first()
    if pin:
        pin.delete()
        messages.success(request, 'Pin entfernt.')
    else:
        ListingPin.objects.create(listing=listing, club=club)
        messages.success(
            request, 'Angepinnt — du erhältst alle Ereignisse dieses Listings.')
    return redirect('transfer_market')


@login_required
@require_POST
def transfer_rumor_react(request):
    club = current_manager_club(user=request.user)
    if not club:
        return redirect('management_hub')
    rumor = get_object_or_404(RumorNews, pk=request.POST.get('rumor_id'))
    reaction = request.POST.get('reaction')
    valid = {
        'denied': RumorNews.REACTION_DENIED,
        'nc': RumorNews.REACTION_NO_COMMENT,
        'confirmed': RumorNews.REACTION_CONFIRMED,
    }
    if reaction not in valid:
        messages.error(request, 'Ungültige Reaktion.')
    elif rumor.affected_club_id != club.pk:
        messages.error(request, 'Dieses Gerücht betrifft nicht deinen Verein.')
    else:
        # Atomarer Compare-and-Set: nur die EINE Anfrage, die die noch
        # leere Reaktion setzt, gewinnt — parallele Requests verlieren
        # deterministisch (updated == 0) und überschreiben nichts.
        updated = RumorNews.objects.filter(
            pk=rumor.pk, reaction='',
        ).update(reaction=valid[reaction], reaction_at=timezone.now())
        if not updated:
            messages.error(request, 'Bereits reagiert — Reaktion ist einmalig.')
        else:
            texte = {
                'denied': 'Dementi veröffentlicht.',
                'nc': '„Kein Kommentar" veröffentlicht.',
                'confirmed': 'Bestätigung veröffentlicht.',
            }
            messages.success(request, texte[reaction])
    return redirect('transfer_market')
