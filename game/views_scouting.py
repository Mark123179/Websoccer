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
from django.db.models import F, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .views import build_game_header, current_manager_club
from .models import (
    CommunitySubmission,
    CountryNetwork,
    Player,
    ScoutingBid,
    ScoutingFind,
    WatchlistEntry,
)
from .scouting import coverage, department, geo, service


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
    rl_club = p.real_life_club if p.real_life_club_id else None
    return {
        'find_id': find.id,
        'player_id': p.id,
        'name': p.full_name,
        'age': p.age,
        'flag': _flag_emoji(iso2),
        'nat': primary_nat,
        'hp': hp,
        'np': ', '.join(np_list) if np_list else '—',
        'rl_club': rl_club.name if rl_club else '—',
        'rl_club_crest': rl_club.crest_static_path if rl_club else '',
        'rl_liga': (
            rl_club.league.name
            if (rl_club and rl_club.league_id) else '—'
        ),
        'market_value_fmt': _euro(p.market_value),
        'min_bid': int(find.min_bid),
        'min_bid_fmt': _euro(find.min_bid),
        'observer_count': find.observer_count,
        'portrait': p.profile_portrait_static_path,
        'watched': p.id in watched_ids,
    }


def _manager_of(club):
    return getattr(club, 'managed_by', None)


def _manager_of_user(request):
    """Manager-Profil direkt am User – funktioniert auch ohne Verein."""
    return getattr(getattr(request, 'user', None), 'manager_profile', None)


def _watchlist_redirect(request):
    nxt = request.POST.get('next') or ''
    if nxt.startswith('/transfers/beobachtungsliste/'):
        return redirect(nxt)
    return redirect('transfer_watchlist')


def _post_player(request):
    """Spieler aus POST['player_id'] – robust gegen fehlende/ungültige IDs (kein 500)."""
    try:
        pk = int(request.POST.get('player_id'))
    except (TypeError, ValueError):
        return None
    return Player.objects.filter(pk=pk).first()


def _search_players(search, watched_ids):
    """Öffentliche Spielersuche für die Beobachtungsliste.

    Liefert nur öffentliche Felder (Name/Alter/Position/Marktwert/Flagge),
    niemals base_strength/potential. Cappt auf 40 Treffer.
    """
    qs = Player.objects.select_related('real_life_club')
    if search['q']:
        qs = qs.filter(
            Q(first_name__icontains=search['q']) | Q(last_name__icontains=search['q'])
        )
    if search['pos']:
        qs = qs.filter(
            Q(main_position_1=search['pos'])
            | Q(main_position_2=search['pos'])
            | Q(main_position_3=search['pos'])
        )
    if watched_ids:
        qs = qs.exclude(id__in=watched_ids)

    if search['sort'] == 'name':
        qs = qs.order_by('last_name', 'first_name')
    elif search['sort'] == 'age':
        qs = qs.order_by('age')
    else:
        qs = qs.order_by(F('market_value').desc(nulls_last=True))

    land = search['land']
    results = []
    for p in qs.iterator():
        iso2 = geo.player_country_iso2(p) or ''
        if land and iso2.upper() != land:
            continue
        results.append({
            'player_id': p.id,
            'name': p.full_name,
            'age': p.age,
            'flag': _flag_emoji(iso2),
            'hp': p.main_position_1 or '—',
            'market_value_fmt': _euro(p.market_value),
        })
        if len(results) >= 40:
            break
    return results


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
    region_options = mapdata['regions']

    _DEMO_OVERRIDES = {
        'TR': ('scoutable', 'Demo: scoutbar'),
        'BE': ('scoutable', 'Demo: scoutbar'),
        'BG': ('scoutable', 'Demo: scoutbar'),
        'BR': ('scoutable', 'Demo: scoutbar'),
        'AR': ('building', 'Demo: im Aufbau'),
    }
    if not any(c['status'] in ('scoutable', 'building') for c in countries):
        countries = [
            dict(c, status=_DEMO_OVERRIDES[c['iso2']][0],
                 coverage_label=_DEMO_OVERRIDES[c['iso2']][1],
                 coverage_percent=50)
            if c['iso2'] in _DEMO_OVERRIDES else c
            for c in countries
        ]

    scope_tiles = []
    for c in countries:
        if c['status'] == 'unavailable':
            continue
        tile = dict(c)
        tile['flag'] = _flag_emoji(c['iso2'])
        scope_tiles.append(tile)

    watched_ids = set(
        WatchlistEntry.objects.filter(manager=manager).values_list('player_id', flat=True)
    ) if manager else set()

    finds = []
    if active and active.finds_generated:
        offered = active.finds.exclude(
            status=ScoutingFind.STATUS_EXPIRED
        ).select_related(
            'player', 'player__real_life_club', 'player__real_life_club__league'
        ).order_by('order')
        finds = [_find_card(f, watched_ids) for f in offered]

    today = date.today()
    bids = []
    for b in club.scouting_bids.filter(
        status=ScoutingBid.STATUS_ACTIVE
    ).select_related('player', 'player__real_life_club').order_by('window_date'):
        p = b.player
        rl_club = p.real_life_club if p.real_life_club_id else None
        bids.append({
            'id': b.id,
            'name': p.full_name,
            'portrait': p.profile_portrait_static_path,
            'rl_club': rl_club.name if rl_club else '—',
            'rl_club_crest': rl_club.crest_static_path if rl_club else '',
            'amount_fmt': _euro(b.amount),
            'min_bid_fmt': _euro(b.min_bid),
            'under_min': b.amount < b.min_bid,
            'window_label': _window_label(b.window_date),
            'days': max((b.window_date - today).days, 0),
        })

    pcts = [c['coverage_percent'] for c in countries]
    coverage_pct = round(sum(pcts) / len(pcts)) if pcts else 0
    scoutable_count = sum(1 for c in countries if c['status'] == 'scoutable')
    building_count = sum(1 for c in countries if c['status'] == 'building')

    context = {
        'game_header': build_game_header('Scouting', 'Transfers · Scoutingnetzwerk', back_url='/'),
        'active_tab': 'scouting',
        'club': club,
        'dept': dept_info,
        'scope_tiles': scope_tiles,
        'map_countries': countries,
        'region_options': region_options,
        'continents': mapdata['continents'],
        'selected_continent': selected_continent,
        'positions': POSITION_OPTIONS,
        'profiles': PROFILE_OPTIONS,
        'active_assignment': active,
        'finds': finds,
        'bids': bids,
        'coverage_pct': coverage_pct,
        'scoutable_count': scoutable_count,
        'building_count': building_count,
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


@login_required(login_url='/auth/login/')
@require_POST
def scouting_upgrade(request):
    club = current_manager_club(user=request.user)
    if not club:
        return redirect('management_hub')
    try:
        service.upgrade_department(club)
        messages.success(request, 'Scoutingbüro wurde ausgebaut.')
    except service.ScoutingError as exc:
        messages.error(request, str(exc))
    return redirect('transfer_scouting')


@login_required(login_url='/auth/login/')
@require_POST
def scouting_reject(request):
    club = current_manager_club(user=request.user)
    if not club:
        return redirect('management_hub')
    active = club.scouting_assignments.filter(
        status=club.scouting_assignments.model.STATUS_ACTIVE
    ).first()
    if active:
        try:
            service.reject_all_finds(active)
            messages.success(request, 'Alle Funde abgelehnt – der Auftrag wurde beendet.')
        except service.ScoutingError as exc:
            messages.error(request, str(exc))
    else:
        messages.error(request, 'Kein aktiver Scoutauftrag vorhanden.')
    return redirect('transfer_scouting')


# ── Beobachtungsliste + Community ─────────────────────────────────────────────
@login_required(login_url='/auth/login/')
def transfer_watchlist(request):
    # Die Beobachtungsliste ist managergebunden → auch ohne Verein voll nutzbar.
    manager = _manager_of_user(request)
    if manager is None:
        return redirect('management_hub')
    club = current_manager_club(user=request.user)

    entries = []
    watched_ids = set()
    qs = WatchlistEntry.objects.filter(manager=manager).select_related(
        'player', 'player__club'
    ).order_by('-updated_at')
    for w in qs:
        p = w.player
        watched_ids.add(p.id)
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

    # Spielersuche zum direkten Hinzufügen (mit Filter + Sortierung).
    search = {
        'q': (request.GET.get('q') or '').strip(),
        'pos': (request.GET.get('pos') or '').strip(),
        'land': (request.GET.get('land') or '').strip().upper(),
        'sort': (request.GET.get('sort') or 'market_value').strip(),
    }
    search_results = _search_players(search, watched_ids)

    mapdata = coverage.map_data()
    submit_countries = [
        {'iso2': c['iso2'], 'name': c['name'], 'flag': _flag_emoji(c['iso2'])}
        for c in mapdata['countries']
    ]
    my_subs = []
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
        'search': search,
        'search_results': search_results,
        'positions': POSITION_OPTIONS,
        'submit_countries': submit_countries,
        'my_subs': my_subs,
    }
    return render(request, 'game/management/scouting_watchlist.html', context)


@login_required(login_url='/auth/login/')
@require_POST
def scouting_watchlist_add(request):
    """Beliebigen Spieler zur (managergebundenen) Beobachtungsliste hinzufügen."""
    manager = _manager_of_user(request)
    if manager is None:
        return redirect('management_hub')
    player = _post_player(request)
    if player is None:
        messages.error(request, 'Spieler nicht gefunden.')
        return _watchlist_redirect(request)
    try:
        service.add_to_watchlist(manager, player)
        messages.success(request, f'{player.full_name} zur Beobachtungsliste hinzugefügt.')
    except service.ScoutingError as exc:
        messages.error(request, str(exc))
    return _watchlist_redirect(request)


@login_required(login_url='/auth/login/')
@require_POST
def scouting_watchlist_remove(request):
    """Spieler aus der Beobachtungsliste entfernen."""
    manager = _manager_of_user(request)
    if manager is None:
        return redirect('management_hub')
    player = _post_player(request)
    if player is None:
        messages.error(request, 'Spieler nicht gefunden.')
        return _watchlist_redirect(request)
    try:
        service.remove_from_watchlist(manager, player)
        messages.success(request, f'{player.full_name} von der Beobachtungsliste entfernt.')
    except service.ScoutingError as exc:
        messages.error(request, str(exc))
    return _watchlist_redirect(request)


@login_required(login_url='/auth/login/')
@require_POST
def scouting_community_submit(request):
    # Community-Einreichung ist managerseitig → auch ohne Verein möglich.
    manager = _manager_of_user(request)
    if manager is None:
        return redirect('management_hub')
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
