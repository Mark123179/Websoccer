import os
from datetime import date, timedelta

from django.db.models import Q
from django.templatetags.static import static as _static

from .asset_urls import resolve_stadium_url
from .models import Club, CupFixture, ManagerProfile, SeasonFixture
from .competition_assets import competition_logo_static_path

_CUP_ROUND_LABELS: dict[str, str] = {
    'round_of_64': '1. Runde',
    'round_of_32': '1. Runde',
    'round_of_18': '1. Runde',
    'round_of_16': '2. Runde',
    'quarter_final': 'Viertelfinale',
    'semi_final': 'Halbfinale',
    'final': 'Finale',
}

CURRENT_MANAGER_PROFILE_IMAGE = 'game/images/managers/default-manager.png'

_STADIUM_ASSETS = {
    901:      'game/images/stadiums/germany/b-leverkusen.jpg',
    905:      'game/images/stadiums/germany/bochum.jpg',
    907:      'game/images/stadiums/germany/b-dortmund.jpg',
    908:      'game/images/stadiums/germany/b-gladbach.jpg',
    912:      'game/images/stadiums/germany/e-frankfurt.jpg',
    915:      'game/images/stadiums/germany/fc-bayern.jpg',
    918:      'game/images/stadiums/germany/mainz.jpg',
    944:      'game/images/stadiums/germany/freiburg.jpg',
    948:      'game/images/stadiums/germany/werder.jpg',
    960:      'game/images/stadiums/germany/stuttgart.jpg',
    961:      'game/images/stadiums/germany/wolfsburg.jpg',
    2238:     'game/images/stadiums/germany/augsburg.jpg',
    2245:     'game/images/stadiums/germany/holstein kiel.jpg',
    121182:   'game/images/stadiums/germany/union berlin.jpg',
    879226:   'game/images/stadiums/germany/hoffenheim.jpg',
    880295:   'game/images/stadiums/germany/heidenheim.jpg',
    3604375:  'game/images/stadiums/germany/st pauli.jpg',
    91013388: 'game/images/stadiums/germany/redbull-leipzig.jpg',
}

_WEEKDAY_LABELS = ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So']


def _stadium_asset_url(club):
    if not club:
        return ''
    profile = club._state.fields_cache.get('public_profile')
    profile_path = getattr(profile, 'stadium_image_static_path', '')
    if profile_path:
        return resolve_stadium_url(profile_path)
    return resolve_stadium_url(_STADIUM_ASSETS.get(club.fm_inside_id, ''))


def _build_global_calendar(club, calendar_offset, live_rounds=None, read_only=False):
    today = date.today()
    game_date = today + timedelta(days=calendar_offset)
    window_start = game_date - timedelta(days=3)
    window_end   = game_date + timedelta(days=3)

    fixtures_by_date = {}
    from .story_release import active_rounds
    if live_rounds is None:
        live_rounds = list(active_rounds())
    locked_league_keys = {r.key for r in live_rounds if r.key.startswith('league:')}
    locked_cup_keys = {r.key for r in live_rounds if r.key.startswith('cup:')}

    if club is not None:
        # Alle Partien des Vereins im 7-Tage-Fenster, ohne U21-Ligen
        qs = (
            SeasonFixture.objects
            .filter(
                scheduled_date__range=(window_start, window_end),
            )
            .filter(Q(home_club=club) | Q(away_club=club))
            .exclude(league__name__icontains='U21')
            .select_related(
                'home_club', 'away_club', 'league',
                'home_club__public_profile',
            )
        )

        for f in qs:
            is_home = (f.home_club_id == club.pk)
            opponent = f.away_club if is_home else f.home_club
            venue = 'H' if is_home else 'A'
            lineup_saved = f.home_lineup_set if is_home else f.away_lineup_set

            # Stadionbild immer vom Heimverein des Fixtures
            home_club_of_fixture = f.home_club
            fixture_stadium = _stadium_asset_url(home_club_of_fixture)

            if (f.is_played and f.home_goals is not None and f.away_goals is not None
                    and f'league:{f.league_id}:{f.season}:{f.matchday}' not in locked_league_keys):
                result = f'{f.home_goals}:{f.away_goals}'
            else:
                result = ''

            match_time = (
                f.scheduled_time.strftime('%H:%M') if f.scheduled_time else ''
            )
            meta = f'{f.matchday}. Spieltag ({venue})'

            opp_crest = opponent.crest_static_path if opponent else ''
            opp_url   = f'/clubs/{opponent.pk}/' if opponent else ''

            comp_logo = competition_logo_static_path(f.league)

            fixtures_by_date[f.scheduled_date] = {
                'opponent_name':    opponent.name if opponent else '',
                'opponent_crest':   opp_crest,
                'opponent_url':     opp_url,
                'stadium':          fixture_stadium,
                'competition_logo': comp_logo,
                'lineup_saved':     lineup_saved,
                'result':           result,
                'venue':            venue,
                'meta':             meta,
                'match_time':       match_time,
            }

        # Pokalbegegnungen im Fenster einbeziehen (kein Freilos)
        cup_qs = (
            CupFixture.objects
            .filter(
                Q(home_club=club) | Q(away_club=club),
                is_bye=False,
                cup_round__scheduled_date__range=(window_start, window_end),
            )
            .select_related(
                'home_club', 'away_club',
                'cup_round__cup_season__competition',
                'home_club__public_profile',
            )
        )
        for cf in cup_qs:
            scheduled_date = cf.cup_round.scheduled_date
            if not scheduled_date:
                continue
            # Liga-Spieltag hat Vorrang bei gleichem Datum
            if scheduled_date in fixtures_by_date:
                continue
            is_home = (cf.home_club_id == club.pk)
            cup_opponent = cf.away_club if is_home else cf.home_club
            cup_venue = 'H' if is_home else 'A'
            cup_comp   = cf.cup_round.cup_season.competition
            comp_name  = cup_comp.name

            if (cf.status == CupFixture.STATUS_PLAYED and cf.home_goals_90 is not None
                    and f'cup:{cf.cup_round_id}' not in locked_cup_keys):
                h = (cf.home_goals_90 or 0) + (cf.home_goals_et or 0)
                a = (cf.away_goals_90 or 0) + (cf.away_goals_et or 0)
                suffix = ''
                if cf.decided_by == CupFixture.DECIDED_BY_ET:
                    suffix = ' n.V.'
                elif cf.decided_by == CupFixture.DECIDED_BY_PENALTIES:
                    suffix = ' n.E.'
                cup_result = f'{h}:{a}{suffix}'
            else:
                cup_result = ''

            round_label = _CUP_ROUND_LABELS.get(
                cf.cup_round.round_code,
                cf.cup_round.round_code.replace('_', ' ').title(),
            )

            cup_stadium = _stadium_asset_url(cf.home_club)
            cup_comp_logo = competition_logo_static_path(cup_comp)
            fixtures_by_date[scheduled_date] = {
                'opponent_name':    cup_opponent.name if cup_opponent else 'Freilos',
                'opponent_crest':   cup_opponent.crest_static_path if cup_opponent else '',
                'opponent_url':     f'/clubs/{cup_opponent.pk}/' if cup_opponent else '',
                'stadium':          cup_stadium,
                'competition_logo': cup_comp_logo,
                'lineup_saved':     False,
                'result':           cup_result,
                'venue':            cup_venue,
                'meta':             f'{comp_name} · {round_label} ({cup_venue})',
                'match_time':       '18:30',
            }

    # Tageswetter: Vergangenheit gedimmt, heute..+7 voll, ab +8 kein Icon
    from .weather_service import ensure_weather_for_day, get_weather_for_date, weather_context
    _wx_horizon = today + timedelta(days=7)

    calendar_days = []
    for offset in range(-3, 4):
        day = game_date + timedelta(days=offset)
        day_weather = None
        weather_dimmed = False
        if day <= _wx_horizon:
            try:
                if read_only:
                    dw = get_weather_for_date(day)
                else:
                    dw, _ = ensure_weather_for_day(day)
                day_weather = weather_context(dw) if dw is not None else None
            except Exception:
                day_weather = None
            weather_dimmed = day < today
        calendar_days.append({
            'date': day,
            'weekday': _WEEKDAY_LABELS[day.weekday()],
            'day_number': day.day,
            'is_today': day == today,
            'fixture': fixtures_by_date.get(day),
            'weather': day_weather,
            'weather_dimmed': weather_dimmed,
        })

    return {
        'calendar_days': calendar_days,
        'previous_offset': calendar_offset - 1,
        'next_offset': calendar_offset + 1,
    }


def current_manager(request):
    read_only = getattr(request, 'creator_read_only', False)
    if request.user.is_authenticated:
        if read_only:
            manager_profile_obj = ManagerProfile.objects.filter(user=request.user).first()
        else:
            manager_profile_obj, _ = ManagerProfile.objects.get_or_create(
                user=request.user,
                defaults={'name': request.user.username},
            )
        try:
            club = (
                Club.objects.select_related('league').get(managed_by=manager_profile_obj)
                if manager_profile_obj is not None else None
            )
        except Club.DoesNotExist:
            club = None
    else:
        manager_profile_obj = None
        club = None

    club_url    = f'/clubs/{club.id}/'                    if club else ''
    squad_url   = f'/clubs/{club.id}/squad/'              if club else ''
    tactics_url = f'/clubs/{club.id}/tactics/?squad=pro'  if club else ''
    club_crest = club.crest_static_path if club else _static('game/images/brand/favicon-32.png')
    club_name = club.name if club else 'Kein Verein'

    if manager_profile_obj:
        manager_name = manager_profile_obj.name
        from .manager_profile import current_title
        active_title_label = current_title(manager_profile_obj)
        trainer_type_label = active_title_label or manager_profile_obj.trainer_type_label
        _raw = manager_profile_obj.profile_image or ''
        if _raw and not _raw.startswith('game/'):
            from django.conf import settings as _settings
            profile_image_url = _settings.MEDIA_URL + _raw
        else:
            profile_image_url = _static(_raw or CURRENT_MANAGER_PROFILE_IMAGE)
        _flag_raw = manager_profile_obj.nationality_flag or ''
        nationality_flag_url = _flag_raw if _flag_raw.startswith('http') else ''
    else:
        manager_name = 'Manager'
        trainer_type_label = 'Laptoptrainer'
        profile_image_url = _static(CURRENT_MANAGER_PROFILE_IMAGE)
        nationality_flag_url = ''

    try:
        calendar_offset = int(request.GET.get('calendar_offset', 0))
    except (TypeError, ValueError):
        calendar_offset = 0

    if manager_profile_obj is not None:
        from .notifications import unread_count as _unread_count
        unread_notifications = _unread_count(manager_profile_obj)
    else:
        unread_notifications = 0

    from .asset_urls import default_player_url as _dp_url
    from django.conf import settings as _cfg
    return {
        'assets_base_url': _cfg.ASSETS_BASE_URL,
        'unread_notifications_count': unread_notifications,
        'current_manager': {
            'name': manager_name,
            'role': trainer_type_label,
            'title': active_title_label if manager_profile_obj else '',
            'club': club,
            'club_name': club_name,
            'club_url': club_url,
            'squad_url': squad_url,
            'tactics_url': tactics_url,
            'club_crest': club_crest,
            'profile_image': profile_image_url,
            'nationality_flag': nationality_flag_url,
        },
        'global_calendar': _build_global_calendar(
            club, calendar_offset, getattr(request, '_story_active_rounds', None),
            read_only=read_only),
        'default_player_url': _dp_url(),
    }


def posthog_settings(request):
    return {
        'POSTHOG_API_KEY': os.environ.get('POSTHOG_API_KEY', ''),
        'POSTHOG_HOST':    os.environ.get('POSTHOG_HOST', 'https://eu.i.posthog.com'),
    }
