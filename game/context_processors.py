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
        manager_profile_obj = ManagerProfile.objects.filter(name='Kirschgutzje').first()

    if manager_profile_obj:
        manager_name = manager_profile_obj.name
        trainer_type_label = manager_profile_obj.trainer_type_label
        profile_image = manager_profile_obj.profile_image or CURRENT_MANAGER_PROFILE_IMAGE
    else:
        manager_name = 'Manager'
        trainer_type_label = 'Laptoptrainer'
        profile_image = CURRENT_MANAGER_PROFILE_IMAGE

    return {
        'current_manager': {
            'name': manager_name,
            'role': trainer_type_label,
            'club_name': club_name,
            'club_url': f'/clubs/{club.id}/' if club else '/clubs/',
            'tactics_url': f'/clubs/{club.id}/tactics/?squad=pro' if club else '/clubs/',
            'club_crest': club.crest_static_path if club else 'game/images/crests/915.png',
            'profile_image': profile_image,
        }
    }
