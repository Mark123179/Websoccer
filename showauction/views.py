"""Show-Auktion — Manager-Views: Bühne, Detailseite, JSON-Aktionen.

Sichtbarkeit (Achse 2) wird HIER durchgesetzt: Der Server rendert nur,
was die Konfiguration erlaubt — das eigene Gebot sieht man immer.
Preise entscheidet ausschließlich der Server (Spec §4.3).
"""
import json
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from game.views import build_game_header, current_manager_club, pitch_position_slots

from . import pricing, service
from .models import ShowAuction, ShowAuctionWatch

LOGIN_URL = '/auth/login/'


def _viewer(request):
    club = current_manager_club(request.user)
    manager = getattr(request.user, 'manager_profile', None)
    return club, manager


def _fmt_eur(value):
    if value is None:
        return None
    return f'{int(Decimal(str(value))):,}'.replace(',', '.') + ' €'


def _color_bundle(hex_color):
    """Farbwelt einer Auktion aus color_hex ableiten (Vorlage Auktionen.dc):
    accent = Typfarbe, ink = fast-schwarze Tönung der Typfarbe (Flächen),
    chip_ink = Textfarbe AUF der Typfarbe, rgb = 'r,g,b' für Glow-Alphas."""
    raw = (hex_color or '#ffd400').lstrip('#')
    if len(raw) == 3:
        raw = ''.join(ch * 2 for ch in raw)
    try:
        r, g, b = int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16)
    except (ValueError, IndexError):
        r, g, b = 255, 212, 0
    luminanz = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return {
        'accent': f'#{r:02x}{g:02x}{b:02x}',
        'ink': f'#{12 + r // 18:02x}{12 + g // 18:02x}{12 + b // 18:02x}',
        'chip_ink': '#101010' if luminanz > 0.55 else '#ffffff',
        'rgb': f'{r},{g},{b}',
    }


def _sichtbar(cfg):
    return cfg.get('sichtbarkeit', 'nichts')


def _auction_state(a, club, manager, now):
    """Alle anzeigbaren Fakten einer Auktion — sichtbarkeitsgefiltert."""
    cfg = a.cfg
    richtung = cfg.get('gebotsrichtung')
    sicht = _sichtbar(cfg)
    aktive = [b for b in a.bids.all() if b.is_active]
    bid_count = len(aktive)
    bieter = len({b.club_id for b in aktive})
    last_at = max((b.updated_at for b in aktive), default=None)
    heat, heat_label = pricing.heat_score(bid_count, bieter, last_at, now)
    heat_verdeckt = sicht in ('nur_gebotsanzahl', 'nichts')

    top = None
    if aktive:
        top = max(aktive, key=lambda b: (b.amount, -b.pk))

    zeig_betrag = sicht in ('hoechstgebot_und_bieter', 'nur_hoechstgebot')
    zeig_bieter = sicht == 'hoechstgebot_und_bieter'
    zeig_anzahl = sicht in ('hoechstgebot_und_bieter', 'nur_hoechstgebot',
                            'nur_gebotsanzahl')

    preis_aktuell = None
    naechster_schritt_at = None
    if richtung == 'fallend' and a.status == ShowAuction.STATUS_RUNNING:
        preis_aktuell = pricing.dutch_price(
            cfg, a.start_price, a.market_value_snapshot, a.starts_at, now,
        )
        intervall = int(cfg['preisverfall']['intervall_minuten'])
        vergangene = max(0, int((now - a.starts_at).total_seconds() // (intervall * 60)))
        naechster_schritt_at = a.starts_at + timedelta(minutes=(vergangene + 1) * intervall)
        if a.ends_at and naechster_schritt_at > a.ends_at:
            naechster_schritt_at = a.ends_at
    elif richtung == 'fest':
        preis_aktuell = a.start_price
    elif richtung == 'aufsteigend' and top is not None and zeig_betrag:
        preis_aktuell = top.amount
    elif richtung == 'aufsteigend' and top is None:
        preis_aktuell = a.start_price

    mein_gebot = None
    mein_fuehrend = False
    ticket_bezahlt = False
    beobachtet = False
    if club is not None:
        meine = [b for b in aktive if b.club_id == club.pk]
        if meine:
            eigenes = max(meine, key=lambda b: b.updated_at)
            mein_gebot = eigenes.amount
            mein_fuehrend = any(b.is_leading for b in meine)
        ticket_bezahlt = any(
            b.club_id == club.pk and b.coin_charged for b in a.bids.all()
        )
        beobachtet = any(w.club_id == club.pk for w in a.watches.all())

    # Mindestgebot (aufsteigend) für Feld-Placeholder
    naechstes_min = None
    if richtung == 'aufsteigend':
        if top is None:
            naechstes_min = a.start_price or Decimal('1')
        else:
            naechstes_min = top.amount + pricing.min_increment(cfg, top.amount)
            if a.start_price:
                naechstes_min = max(naechstes_min, a.start_price)
    elif richtung == 'verdeckt':
        naechstes_min = a.start_price

    restzeit_s = None
    if a.ends_at and a.status == ShowAuction.STATUS_RUNNING:
        restzeit_s = max(0, int((a.ends_at - now).total_seconds()))
    start_in_s = None
    if a.status == ShowAuction.STATUS_SCHEDULED and a.starts_at:
        start_in_s = max(0, int((a.starts_at - now).total_seconds()))

    grund = None
    if a.status == ShowAuction.STATUS_RUNNING:
        grund = service.check_participation(a, club, manager)

    coin_bedarf = 0
    for cond in (a.conditions or []):
        if cond.get('art') == 'coins':
            coin_bedarf = int(cond.get('anzahl') or 1)

    return {
        'auction': a,
        'cfg': cfg,
        'richtung': richtung,
        'sicht': sicht,
        'status': a.status,
        'bid_count': bid_count if zeig_anzahl else None,
        'bieter_count': bieter if zeig_bieter else None,
        'heat': heat,
        'heat_label': None if heat_verdeckt else heat_label,
        'heat_verdeckt': heat_verdeckt,
        'preis_aktuell': preis_aktuell,
        'preis_aktuell_fmt': _fmt_eur(preis_aktuell),
        'naechster_schritt_at': naechster_schritt_at,
        'top_club': (top.club if (top is not None and zeig_bieter) else None),
        'mein_gebot': mein_gebot,
        'mein_gebot_fmt': _fmt_eur(mein_gebot),
        'mein_fuehrend': mein_fuehrend,
        'ticket_bezahlt': ticket_bezahlt,
        'coin_bedarf': coin_bedarf,
        'beobachtet': beobachtet,
        'naechstes_min': naechstes_min,
        'naechstes_min_fmt': _fmt_eur(naechstes_min),
        'restzeit_s': restzeit_s,
        'start_in_s': start_in_s,
        'teilnahme_grund': grund,
        'mw_fmt': _fmt_eur(a.market_value_snapshot),
        'boden_fmt': (_fmt_eur(pricing.dutch_floor(cfg, a.market_value_snapshot))
                      if richtung == 'fallend' and a.market_value_snapshot else None),
        'farbe': _color_bundle(a.color_hex),
        'hot': bool(restzeit_s is not None and restzeit_s < 3600),
    }


def _cond_rows(conditions):
    """Teilnahmebedingungen als deutsche Klartext-Zeilen (Spec §11)."""
    rows = []
    for c in (conditions or []):
        art = c.get('art')
        if art == 'coins':
            n = int(c.get('anzahl') or 1)
            plural = 's' if n != 1 else ''
            rows.append(f'Eintritt: {n} Hoeneß-Coin{plural} — fällig mit deinem ersten Gebot, kein Refund')
        elif art == 'max_mw_schnitt':
            rows.append(f'Nur für Kader mit Ø Marktwert bis {_fmt_eur(c.get("betrag"))}')
        elif art == 'freie_kaderplaetze':
            n = int(c.get('anzahl') or 1)
            rows.append(f'Mindestens {n} freie{"r" if n == 1 else ""} Kaderplatz{"" if n == 1 else "plätze"} nötig'.replace('Kaderplatzplätze', 'Kaderplätze'))
        elif art == 'mindestkontostand':
            rows.append(f'Kontostand mindestens {_fmt_eur(c.get("betrag"))}')
        elif art == 'liga':
            rows.append('Nur für Vereine bestimmter Ligen zugelassen')
    return rows


def _center_out(items):
    """Dringlichste Auktion in die Mitte: [4,2,1,3,5]-Anordnung (Spec §9)."""
    arranged = [None] * len(items)
    mitte = (len(items) - 1) // 2
    for i, item in enumerate(items):
        if i == 0:
            arranged[mitte] = item
        else:
            offset = (i + 1) // 2
            pos = mitte - offset if i % 2 else mitte + offset
            arranged[pos] = item
    return [x for x in arranged if x is not None]


@login_required(login_url=LOGIN_URL)
def stage(request):
    service.resolve_due()  # Lazy-Abwicklung (E26) — billig, wenn nichts fällig
    now = timezone.now()
    club, manager = _viewer(request)

    qs = (ShowAuction.objects
          .filter(status__in=[ShowAuction.STATUS_RUNNING, ShowAuction.STATUS_SCHEDULED])
          .select_related('player', 'preset', 'player__club')
          .prefetch_related('bids', 'watches'))
    live, geplant = [], []
    for a in qs:
        state = _auction_state(a, club, manager, now)
        if a.status == ShowAuction.STATUS_RUNNING:
            live.append(state)
        else:
            geplant.append(state)
    live.sort(key=lambda s: (s['restzeit_s'] is None, s['restzeit_s'] or 0))
    geplant.sort(key=lambda s: s['auction'].starts_at or now)

    beendete = (ShowAuction.objects
                .filter(status__in=[ShowAuction.STATUS_SETTLED, ShowAuction.STATUS_FAILED])
                .select_related('player', 'winner_club')
                .order_by('-ends_at')[:8])
    finished_rows = [{
        'a': b,
        'preis_fmt': _fmt_eur(b.winning_amount),
        'farbe': _color_bundle(b.color_hex),
    } for b in beendete]

    arranged = _center_out(live)
    mitte = (len(arranged) - 1) / 2 if arranged else 0
    for i, s in enumerate(arranged):
        s['dist'] = min(2, int(round(abs(i - mitte))))
    return render(request, 'showauction/stage.html', {
        'game_header': build_game_header(
            'Auktionshaus', 'Transfers · Show-Auktionen', back_url='/'),
        'live_auctions': arranged,
        'planned_auctions': geplant,
        'finished_rows': finished_rows,
        'now': now,
    })


@login_required(login_url=LOGIN_URL)
def detail(request, pk):
    service.resolve_due()
    now = timezone.now()
    club, manager = _viewer(request)
    a = get_object_or_404(
        ShowAuction.objects.select_related('player', 'preset', 'winner_club',
                                           'player__club'),
        pk=pk,
    )
    if a.status == ShowAuction.STATUS_DRAFT and not request.user.is_staff:
        from django.http import Http404
        raise Http404
    state = _auction_state(a, club, manager, now)

    # Gebotsliste — nur was die Sichtbarkeit erlaubt (eigene immer)
    aktive = [b for b in a.bids.all() if b.is_active]
    aktive.sort(key=lambda b: (-b.amount, b.updated_at))
    zeig_liste = state['sicht'] == 'hoechstgebot_und_bieter'
    gebots_liste = aktive[:10] if zeig_liste else []
    meine_gebote = ([b for b in a.bids.all() if club and b.club_id == club.pk]
                    if club else [])
    meine_gebote.sort(key=lambda b: b.updated_at, reverse=True)

    # Mindesterhöhung (nur offen aufsteigend mit konfigurierter Erhöhung)
    min_inc_fmt = None
    if (state['richtung'] == 'aufsteigend'
            and (a.cfg.get('mindesterhoehung', 'keine') or 'keine') != 'keine'):
        basis = state['preis_aktuell'] or a.start_price or Decimal('0')
        min_inc_fmt = _fmt_eur(pricing.min_increment(a.cfg, basis))

    # Verfügbares Guthaben fürs Gebots-Modal (Budget minus aktive Reservierungen)
    verfuegbar_int = None
    if club is not None:
        from game.economy.reservations import reserved_money
        verfuegbar_int = int(Decimal(str(club.budget or 0)) - reserved_money(club))

    # Vorherige/Nächste laufende Auktion (Studio-Navigation)
    prev_auction = next_auction = None
    if a.status == ShowAuction.STATUS_RUNNING:
        running = list(ShowAuction.objects
                       .filter(status=ShowAuction.STATUS_RUNNING)
                       .select_related('player')
                       .order_by('ends_at', 'pk'))
        pks = [x.pk for x in running]
        if a.pk in pks and len(running) > 1:
            idx = pks.index(a.pk)
            next_auction = running[(idx + 1) % len(running)]
            prev_auction = running[(idx - 1) % len(running)]

    groesse_fmt = None
    if getattr(a.player, 'height_cm', None):
        groesse_fmt = f'{a.player.height_cm / 100:.2f}'.replace('.', ',') + ' m'

    return render(request, 'showauction/detail.html', {
        'game_header': build_game_header(
            a.player.full_name, 'Transfers · Auktionshaus',
            back_url=reverse('showauction_stage')),
        's': state,
        'a': a,
        'player': a.player,
        'groesse_fmt': groesse_fmt,
        'position_slots': pitch_position_slots(a.player),
        'gebots_rows': [{
            'club': b.club,
            'fmt': _fmt_eur(b.amount),
            'at': b.updated_at,
            'leading': b.is_leading,
        } for b in gebots_liste],
        'meine_gebote': [{
            'fmt': _fmt_eur(b.amount),
            'at': b.updated_at,
            'leading': b.is_leading,
            'aktiv': b.is_active,
        } for b in meine_gebote[:5]],
        'cond_rows': _cond_rows(a.conditions),
        'start_fmt': _fmt_eur(a.start_price) if a.start_price is not None else 'Frei',
        'now': now,
        'min_inc_fmt': min_inc_fmt,
        'verfuegbar_int': verfuegbar_int,
        'verfuegbar_fmt': _fmt_eur(verfuegbar_int) if verfuegbar_int is not None else None,
        'naechstes_min_int': (int(state['naechstes_min'])
                              if state['naechstes_min'] is not None else ''),
        'prev_auction': prev_auction,
        'next_auction': next_auction,
        'my_club': club,
    })


@login_required(login_url=LOGIN_URL)
def status_json(request, pk):
    """Polling-Endpunkt der Detailseite/Bühne (15-s-Takt im JS)."""
    service.resolve_due()
    now = timezone.now()
    club, manager = _viewer(request)
    try:
        a = (ShowAuction.objects
             .select_related('player', 'winner_club')
             .prefetch_related('bids', 'watches').get(pk=pk))
    except ShowAuction.DoesNotExist:
        return JsonResponse({'ok': False, 'fehler': 'Auktion nicht gefunden.'}, status=404)
    s = _auction_state(a, club, manager, now)
    return JsonResponse({
        'ok': True,
        'status': a.status,
        'status_label': a.get_status_display(),
        'restzeit_s': s['restzeit_s'],
        'start_in_s': s['start_in_s'],
        'preis_aktuell': (str(s['preis_aktuell']) if s['preis_aktuell'] is not None else None),
        'preis_aktuell_fmt': s['preis_aktuell_fmt'],
        'naechstes_min_fmt': s['naechstes_min_fmt'],
        'bid_count': s['bid_count'],
        'heat': s['heat'],
        'heat_label': s['heat_label'],
        'mein_fuehrend': s['mein_fuehrend'],
        'extension_count': a.extension_count,
        'hold_step_index': a.hold_step_index,
        'winner': (a.winner_club.name if a.winner_club_id else None),
        'winning_amount_fmt': _fmt_eur(a.winning_amount),
        'fail_reason': a.fail_reason or None,
    })


def _json_body(request):
    try:
        return json.loads(request.body.decode('utf-8') or '{}')
    except (ValueError, UnicodeDecodeError):
        return {}


@login_required(login_url=LOGIN_URL)
@require_POST
def bid(request, pk):
    club, manager = _viewer(request)
    if club is None:
        return JsonResponse({'ok': False, 'fehler': 'Du brauchst einen Verein, um zu bieten.'}, status=400)
    data = _json_body(request)
    amount = data.get('amount') or request.POST.get('amount')
    if amount in (None, ''):
        return JsonResponse({'ok': False, 'fehler': 'Gebotsbetrag fehlt.'}, status=400)
    try:
        service.place_bid(pk, club, manager, amount)
    except service.AuctionError as exc:
        return JsonResponse({'ok': False, 'fehler': str(exc)}, status=400)
    return JsonResponse({'ok': True})


@login_required(login_url=LOGIN_URL)
@require_POST
def buy(request, pk):
    club, manager = _viewer(request)
    if club is None:
        return JsonResponse({'ok': False, 'fehler': 'Du brauchst einen Verein, um zuzuschlagen.'}, status=400)
    try:
        service.buy_now(pk, club, manager)
    except service.AuctionError as exc:
        return JsonResponse({'ok': False, 'fehler': str(exc)}, status=400)
    return JsonResponse({'ok': True})


@login_required(login_url=LOGIN_URL)
@require_POST
def watch(request, pk):
    club, manager = _viewer(request)
    a = get_object_or_404(ShowAuction, pk=pk)
    try:
        aktiv = service.toggle_watch(a, club)
    except service.AuctionError as exc:
        return JsonResponse({'ok': False, 'fehler': str(exc)}, status=400)
    return JsonResponse({'ok': True, 'beobachtet': aktiv})
