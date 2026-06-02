from .models import Club, ManagerProfile

CURRENT_MANAGER_PROFILE_IMAGE = 'game/images/managers/kirschgutzje-test.png'


def current_manager(request):
    club = (
        Club.objects.filter(fm_inside_id=915).first()
        or Club.objects.filter(name__icontains='Bayern').first()
    )
    club_name = club.name if club else 'FC Bayern Muenchen'

    if request.user.is_authenticated:
        manager_profile_obj, _ = ManagerProfile.objects.get_or_create(
            user=request.user,
            defaults={'name': request.user.username},
        )
    else:
        manager_profile_obj = None

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
            'club_name': club_name,
            'club_url': f'/clubs/{club.id}/' if club else '/clubs/',
            'tactics_url': f'/clubs/{club.id}/tactics/?squad=pro' if club else '/clubs/',
            'club_crest': club.crest_static_path if club else 'game/images/crests/915.png',
            'profile_image': profile_image_url,
            'nationality_flag': nationality_flag_url,
        }
    }
