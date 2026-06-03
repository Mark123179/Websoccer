from datetime import date, timedelta

from django.templatetags.static import static as _static

from .models import Club, ManagerProfile
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
    league_name = (
        club.league.name if club and club.league else '1. Bundesliga'
    )
    stadium = _STADIUM_ASSETS.get(club.fm_inside_id, '') if club else ''

    def _fixture(lineup_saved, result, venue, meta, match_time=''):
        return {
            'opponent_name': '',
            'opponent_crest': '',
            'opponent_url': '',
            'stadium': stadium,
            'competition_logo': competition_logo_static_path(league_name),
            'lineup_saved': lineup_saved,
            'result': result,
            'venue': venue,
            'meta': meta,
            'match_time': match_time,
        }

    fixtures_by_date = (
        {
            today - timedelta(days=3): _fixture(False, '1:1', 'A', '33. Spieltag (A)'),
            today - timedelta(days=1): _fixture(True, '5:0', 'H', 'Testspiel (H)'),
            today + timedelta(days=2): _fixture(False, '', 'H', '27. Spieltag (H)', match_time='18:00'),
        }
        if club is not None
        else {}
    )

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

    club_url = f'/clubs/{club.id}/' if club else '/clubs/'
    tactics_url = f'/clubs/{club.id}/tactics/?squad=pro' if club else '/clubs/'
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
            'tactics_url': tactics_url,
            'club_crest': club_crest,
            'profile_image': profile_image_url,
            'nationality_flag': nationality_flag_url,
        },
        'global_calendar': _build_global_calendar(club, calendar_offset),
    }
