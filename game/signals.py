"""
game.signals — Django signal receivers.

Connected in GameConfig.ready() (game/apps.py).
"""

from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender='auth.User')
def create_manager_profile_on_user_create(sender, instance, created, **kwargs):
    """Auto-create a ManagerProfile whenever a new User account is created.

    This ensures every player always has a profile row from day one — no need
    for get_or_create scattered across views.  No CareerStation is created
    here; that happens when the manager is first assigned to a club via
    record_club_assignment().
    """
    if not created:
        return
    from .models import ManagerProfile
    member_since = None
    if instance.date_joined:
        try:
            member_since = instance.date_joined.date()
        except Exception:
            pass
    ManagerProfile.objects.get_or_create(
        user=instance,
        defaults={
            'name': instance.username,
            'member_since': member_since,
        },
    )
