from datetime import date, timedelta

from django.db.models import Q
from django.templatetags.static import static as _static

from .models import Club, ManagerProfile, SeasonFixture
from .competition_assets import competition_logo_static_path

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


def _build_global_calendar(club, calendar_offset):
    today = date.today()
    game_date = today + timedelta(days=calendar_offset)
    window_start = game_date - timedelta(days=3)
    window_end   = game_date + timedelta(days=3)

    fixtures_by_date = {}

    if club is not None:
        stadium = _STADIUM_ASSETS.get(club.fm_inside_id, '')

        # Alle Partien des Vereins im 7-Tage-Fenster, ohne U21-Ligen
        qs = (
            SeasonFixture.objects
            .filter(
                scheduled_date__range=(window_start, window_end),
            )
            .filter(Q(home_club=club) | Q(away_club=club))
            .exclude(league__name__icontains='U21')
            .select_related('home_club', 'away_club', 'league')
        )

        for f in qs:
            is_home = (f.home_club_id == club.pk)
            opponent = f.away_club if is_home else f.home_club
            venue = 'H' if is_home else 'A'
            lineup_saved = f.home_lineup_set if is_home else f.away_lineup_set

            if f.is_played and f.home_goals is not None and f.away_goals is not None:
                result = f'{f.home_goals}:{f.away_goals}'
            else:
                result = ''

            match_time = (
                f.scheduled_time.strftime('%H:%M') if f.scheduled_time else ''
            )
            meta = f'{f.matchday}. Spieltag ({venue})'

            opp_crest = opponent.crest_static_path if opponent else ''
            opp_url   = f'/clubs/{opponent.pk}/' if opponent else ''

            fixtures_by_date[f.scheduled_date] = {
                'opponent_name':    opponent.name if opponent else '',
                'opponent_crest':   opp_crest,
                'opponent_url':     opp_url,
                'stadium':          stadium,
                'competition_logo': competition_logo_static_path(f.league.name),
                'lineup_saved':     lineup_saved,
                'result':           result,
                'venue':            venue,
                'meta':             meta,
                'match_time':       match_time,
            }

    calendar_days = []
    for offset in range(-3, 4):
        day = game_date + timedelta(days=offset)
        calendar_days.append({
            'date': day,
            'weekday': _WEEKDAY_LABELS[day.weekday()],
            'day_number': day.day,
            'is_today': day == today,
            'fixture': fixtures_by_date.get(day),
        })

    return {
        'calendar_days': calendar_days,
        'previous_offset': calendar_offset - 1,
        'next_offset': calendar_offset + 1,
    }


def current_manager(request):
    if request.user.is_authenticated:
        manager_profile_obj, _ = ManagerProfile.objects.get_or_create(
            user=request.user,
            defaults={'name': request.user.username},
        )
        try:
            club = Club.objects.select_related('league').get(managed_by=manager_profile_obj)
        except Club.DoesNotExist:
            club = None
    else:
        manager_profile_obj = None
        club = None

    club_url    = f'/clubs/{club.id}/'                    if club else ''
    squad_url   = f'/clubs/{club.id}/squad/'              if club else ''
    tactics_url = f'/clubs/{club.id}/tactics/?squad=pro'  if club else ''
    club_crest = club.crest_static_path if club else 'game/images/brand/favicon-32.png'
    club_name = club.name if club else 'Kein Verein'

    if manager_profile_obj:
        manager_name = manager_profile_obj.name
        trainer_type_label = manager_profile_obj.trainer_type_label
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

    return {
        'current_manager': {
            'name': manager_name,
            'role': trainer_type_label,
            'club': club,
            'club_name': club_name,
            'club_url': club_url,
            'squad_url': squad_url,
            'tactics_url': tactics_url,
            'club_crest': club_crest,
            'profile_image': profile_image_url,
            'nationality_flag': nationality_flag_url,
        },
        'global_calendar': _build_global_calendar(club, calendar_offset),
    }
