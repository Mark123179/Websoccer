from .models import Club, ManagerProfile

CURRENT_MANAGER_PROFILE_IMAGE = 'game/images/managers/default-manager.png'


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
            from django.templatetags.static import static as _static
            profile_image_url = _static(_raw or CURRENT_MANAGER_PROFILE_IMAGE)
        _flag_raw = manager_profile_obj.nationality_flag or ''
        nationality_flag_url = _flag_raw if _flag_raw.startswith('http') else ''
    else:
        manager_name = 'Manager'
        trainer_type_label = 'Laptoptrainer'
        from django.templatetags.static import static as _static
        profile_image_url = _static(CURRENT_MANAGER_PROFILE_IMAGE)
        nationality_flag_url = ''

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
        }
    }
