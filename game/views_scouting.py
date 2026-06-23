"""Views für das Scouting-System (Task #594).

Transfers → Scouting-Screen, Beobachtungsliste, Gebots-/Auftrags-Endpunkte,
Community-Einreichung sowie die Creator-Moderation. Die Service-Schicht
(game/scouting/service.py) kapselt alle Geld-/Status-Mutationen; diese Views
übersetzen nur Request → Service → Redirect/Render und leaken niemals
base_strength/potential an das Template.
"""

from datetime import date
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .views import build_game_header, current_manager_club
from .models import (
    CommunitySubmission,
    CountryNetwork,
    ScoutingBid,
    ScoutingFind,
    WatchlistEntry,
)
from .scouting import coverage, department, geo, service


# Ungefähre Weltkoordinaten (x%, y%) auf der stilisierten Karte (1000×460).
MARKER_COORDS = {
    'DE': (53.7, 20.8), 'FR': (50.6, 22.8), 'ES': (49.0, 27.6), 'IT': (53.5, 26.7),
    'GB': (50.0, 21.4), 'PT': (47.5, 28.5), 'NL': (51.4, 20.9), 'BE': (51.2, 21.8),
    'AT': (54.5, 23.2), 'CH': (52.1, 23.9), 'TR': (59.1, 27.8), 'BG': (56.5, 26.3),
    'HR': (54.4, 24.5), 'RS': (55.7, 25.1), 'PL': (55.8, 21.0), 'CZ': (54.0, 22.2),
    'GR': (56.6, 28.9), 'UA': (58.5, 22.0), 'RO': (57.2, 25.3), 'DK': (53.5, 19.1),
    'SE': (55.0, 17.0), 'NO': (53.0, 16.7),
    'BR': (36.7, 58.8), 'AR': (33.8, 69.2), 'UY': (34.4, 69.4), 'CO': (29.4, 47.4),
    'CL': (30.4, 68.6), 'PE': (28.6, 56.7), 'EC': (28.2, 50.1), 'PY': (34.0, 64.0),
    'NG': (52.1, 45.0), 'GH': (49.9, 46.9), 'SN': (45.2, 41.8), 'CI': (48.9, 47.0),
    'MA': (48.1, 31.1), 'EG': (58.7, 33.3), 'DZ': (50.9, 29.6), 'CM': (53.2, 47.9),
    'TN': (52.8, 29.6),
    'JP': (88.8, 30.2), 'KR': (85.3, 29.1), 'SA': (63.0, 36.3), 'QA': (64.3, 36.0),
    'IR': (64.3, 30.2), 'CN': (82.3, 27.8), 'AU': (91.4, 69.6),
}

POSITION_OPTIONS = ['IV', 'RV', 'LV', 'DM', 'ZM', 'OM', 'RF', 'LF', 'ST']
PROFILE_OPTIONS = [
    ('backup', 'Back-up'),
    ('ergaenzung', 'Ergänzung'),
    ('rotation', 'Rotation'),
    ('stammkraft', 'Stammkraft'),
    ('talent', 'Jugendspieler'),
]


# ── Helfer ────────────────────────────────────────────────────────────────────
def _euro(value):
    if value is None:
        return '—'
    try:
        v = int(round(float(value)))
    except (TypeError, ValueError):
        return '—'
    return f'{v:,}'.replace(',', '.') + ' €'


def _flag_emoji(iso2):
    if not iso2 or len(iso2) != 2 or not iso2.isalpha():
        return ''
    return ''.join(chr(0x1F1E6 + ord(c) - 65) for c in iso2.upper())


def _window_label(window_date):
    return 'SP' if window_date.month == 7 else 'WP'


def _parse_amount(raw):
    cleaned = (raw or '').replace('.', '').replace(' ', '').replace('€', '').replace(',', '.').strip()
    try:
        return Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return None


def _find_card(find, watched_ids):
    """Öffentliche Sicht auf einen Fund — ohne Stärke/Potential/Attribute."""
    p = find.player
    mains = [x for x in p.main_positions if x]
    hp = mains[0] if mains else (p.main_position_1 or '—')
    np_list = [x for x in (mains[1:] + p.secondary_positions) if x]
    iso2 = geo.player_country_iso2(p) or ''
    primary_nat = p.nationalities.split(',')[0].strip() if p.nationalities else ''
    return {
        'find_id': find.id,
        'player_id': p.id,
        'name': p.full_name,
        'age': p.age,
        'flag': _flag_emoji(iso2),
        'nat': primary_nat,
        'hp': hp,
        'np': ', '.join(np_list) if np_list else '—',
        'rl_club': p.club.name if p.club_id else '—',
        'rl_liga': (p.club.league.name if (p.club_id and p.club.league_id) else '—'),
        'market_value_fmt': _euro(p.market_value),
        'min_bid': int(find.min_bid),
        'min_bid_fmt': _euro(find.min_bid),
        'observer_count': find.observer_count,
        'portrait': p.profile_portrait_static_path,
        'watched': p.id in watched_ids,
    }


def _manager_of(club):
    return getattr(club, 'managed_by', None)


# ── Hauptscreen ───────────────────────────────────────────────────────────────
@login_required(login_url='/auth/login/')
def transfer_scouting(request):
    club = current_manager_club(user=request.user)
    if not club:
        return redirect('management_hub')
    manager = _manager_of(club)

    dept = department.get_or_create_department(club)
    level = dept.level
    dept_info = {
        'level': level,
        'duration': department.order_duration(level),
        'cost_fmt': _euro(department.order_cost(level)),
        'can_upgrade': department.can_upgrade(level),
        'upgrade_cost_fmt': _euro(department.upgrade_cost(level)) if department.can_upgrade(level) else None,
    }

    # Funde erzeugen, sobald ein Auftrag fällig ist (Lazy-Resolve beim Aufruf).
    active = club.scouting_assignments.filter(
        status=club.scouting_assignments.model.STATUS_ACTIVE
    ).first()
    if active and active.is_ready and not active.finds_generated:
        try:
            service.generate_finds(active)
        except service.ScoutingError:
            pass
        active.refresh_from_db()

    mapdata = coverage.map_data()
    countries = mapdata['countries']
    selected_continent = request.GET.get('kontinent', 'europa')
    cont_countries = [c for c in countries if c['continent'] == selected_continent]
    scope_tiles = cont_countries or countries
    region_options = [r for r in mapdata['regions'] if r['continent'] == selected_continent]

    for c in scope_tiles:
        c['flag'] = _flag_emoji(c['iso2'])

    map_markers = []
    for c in countries:
        coord = MARKER_COORDS.get(c['iso2'])
        if not coord:
            continue
        map_markers.append({
            'iso2': c['iso2'],
            'name': c['name'],
            'status': c['status'],
            'x': coord[0],
            'y': coord[1],
            'in_continent': c['continent'] == selected_continent,
        })

    watched_ids = set(
        WatchlistEntry.objects.filter(manager=manager).values_list('player_id', flat=True)
    ) if manager else set()

    finds = []
    if active and active.finds_generated:
        offered = active.finds.exclude(
            status=ScoutingFind.STATUS_EXPIRED
        ).select_related('player', 'player__club', 'player__club__league').order_by('order')
        finds = [_find_card(f, watched_ids) for f in offered]

    today = date.today()
    bids = []
    for b in club.scouting_bids.filter(
        status=ScoutingBid.STATUS_ACTIVE
    ).select_related('player').order_by('window_date'):
        bids.append({
            'id': b.id,
            'name': b.player.full_name,
            'amount_fmt': _euro(b.amount),
            'min_bid_fmt': _euro(b.min_bid),
            'under_min': b.amount < b.min_bid,
            'window_label': _window_label(b.window_date),
            'days': max((b.window_date - today).days, 0),
        })

    pcts = [c['coverage_percent'] for c in cont_countries] or [c['coverage_percent'] for c in countries]
    coverage_pct = round(sum(pcts) / len(pcts)) if pcts else 0

    context = {
        'game_header': build_game_header('Scouting', 'Transfers · Scoutingnetzwerk', back_url='/'),
        'active_tab': 'scouting',
        'club': club,
        'dept': dept_info,
        'scope_tiles': scope_tiles,
        'map_markers': map_markers,
        'region_options': region_options,
        'continents': mapdata['continents'],
        'selected_continent': selected_continent,
        'positions': POSITION_OPTIONS,
        'profiles': PROFILE_OPTIONS,
        'active_assignment': active,
        'finds': finds,
        'bids': bids,
        'coverage_pct': coverage_pct,
        'available_budget_fmt': _euro(service.available_budget(club)),
        'reserved_budget_fmt': _euro(service.reserved_budget(club)),
    }
    return render(request, 'game/management/scouting.html', context)


# ── Aktionen ──────────────────────────────────────────────────────────────────
@login_required(login_url='/auth/login/')
@require_POST
def scouting_start(request):
    club = current_manager_club(user=request.user)
    if not club:
        return redirect('management_hub')
    manager = _manager_of(club)
    scope_type = request.POST.get('scope_type', 'country')
    scope_key = (request.POST.get('scope_key') or '').strip()
    position = (request.POST.get('position') or '').strip()
    profile = (request.POST.get('profile') or 'ergaenzung').strip()
    try:
        service.start_assignment(club, manager, scope_type, scope_key, profile, position)
        messages.success(request, 'Scout wurde losgeschickt.')
    except service.ScoutingError as exc:
        messages.error(request, str(exc))
    return redirect('transfer_scouting')


@login_required(login_url='/auth/login/')
@require_POST
def scouting_bid(request):
    club = current_manager_club(user=request.user)
    if not club:
        return redirect('management_hub')
    manager = _manager_of(club)
    find = get_object_or_404(ScoutingFind, pk=request.POST.get('find_id'))
    amount = _parse_amount(request.POST.get('amount'))
    if amount is None:
        messages.error(request, 'Ungültiger Gebotsbetrag.')
        return redirect('transfer_scouting')
    try:
        service.place_bid(club, manager, find, amount)
        messages.success(request, 'Gebot abgegeben.')
    except service.ScoutingError as exc:
        messages.error(request, str(exc))
    return redirect('transfer_scouting')


@login_required(login_url='/auth/login/')
@require_POST
def scouting_watch(request):
    club = current_manager_club(user=request.user)
    if not club:
        return redirect('management_hub')
    manager = _manager_of(club)
    find = get_object_or_404(ScoutingFind, pk=request.POST.get('find_id'))
    try:
        service.watch_find(club, manager, find)
        messages.success(request, 'Spieler zur Beobachtungsliste hinzugefügt.')
    except service.ScoutingError as exc:
        messages.error(request, str(exc))
    return redirect(request.POST.get('next') or 'transfer_scouting')


@login_required(login_url='/auth/login/')
@require_POST
def scouting_withdraw(request):
    club = current_manager_club(user=request.user)
    if not club:
        return redirect('management_hub')
    bid = get_object_or_404(ScoutingBid, pk=request.POST.get('bid_id'), club=club)
    try:
        service.withdraw_bid(bid)
        messages.success(request, 'Gebot zurückgezogen.')
    except service.ScoutingError as exc:
        messages.error(request, str(exc))
    return redirect('transfer_scouting')


# ── Beobachtungsliste + Community ─────────────────────────────────────────────
@login_required(login_url='/auth/login/')
def transfer_watchlist(request):
    club = current_manager_club(user=request.user)
    if not club:
        return redirect('management_hub')
    manager = _manager_of(club)

    entries = []
    qs = WatchlistEntry.objects.filter(manager=manager).select_related(
        'player', 'player__club'
    ).order_by('-updated_at') if manager else []
    for w in qs:
        p = w.player
        iso2 = geo.player_country_iso2(p) or ''
        entries.append({
            'player_id': p.id,
            'name': p.full_name,
            'age': p.age,
            'flag': _flag_emoji(iso2),
            'hp': p.main_position_1 or '—',
            'market_value_fmt': _euro(p.market_value),
            'status': w.status,
            'status_label': w.get_status_display(),
        })

    mapdata = coverage.map_data()
    submit_countries = [
        {'iso2': c['iso2'], 'name': c['name'], 'flag': _flag_emoji(c['iso2'])}
        for c in mapdata['countries']
    ]
    my_subs = []
    if manager:
        for s in manager.community_submissions.order_by('-created_at')[:20]:
            my_subs.append({
                'iso2': s.iso2,
                'flag': _flag_emoji(s.iso2),
                'player_name': s.player_name or '—',
                'status_label': s.get_status_display(),
                'created': s.created_at,
            })

    context = {
        'game_header': build_game_header('Beobachtungsliste', 'Transfers · Scouting', back_url='/'),
        'active_tab': 'watchlist',
        'club': club,
        'entries': entries,
        'submit_countries': submit_countries,
        'my_subs': my_subs,
    }
    return render(request, 'game/management/scouting_watchlist.html', context)


@login_required(login_url='/auth/login/')
@require_POST
def scouting_community_submit(request):
    club = current_manager_club(user=request.user)
    if not club:
        return redirect('management_hub')
    manager = _manager_of(club)
    iso2 = (request.POST.get('iso2') or '').strip().upper()
    tm_url = (request.POST.get('tm_url') or '').strip()
    player_name = (request.POST.get('player_name') or '').strip()
    try:
        service.submit_community_profile(manager, iso2, tm_url, player_name)
        messages.success(request, 'Profil eingereicht. Danke für deinen Beitrag!')
    except service.ScoutingError as exc:
        messages.error(request, str(exc))
    return redirect('transfer_watchlist')


# ── Creator-Moderation ────────────────────────────────────────────────────────
@login_required(login_url='/auth/login/')
def creator_scouting_overview(request):
    pending = CommunitySubmission.objects.filter(
        status=CommunitySubmission.STATUS_PENDING
    ).select_related('manager').order_by('created_at')
    networks = CountryNetwork.objects.order_by('-community_points', 'name')
    context = {
        'pending': pending,
        'networks': networks,
    }
    return render(request, 'creator/scouting_overview.html', context)


@login_required(login_url='/auth/login/')
@require_POST
def creator_moderate_submission(request, submission_id):
    sub = get_object_or_404(CommunitySubmission, pk=submission_id)
    approve = request.POST.get('action') == 'approve'
    service.moderate_submission(sub, approve=approve)
    messages.success(request, 'Einreichung bearbeitet.')
    return redirect('creator_scouting_overview')
