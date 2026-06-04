"""
game.signals — Django signal receivers.

Connected in GameConfig.ready() (game/apps.py).
"""
import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(post_save, sender='game.MatchResult')
def auto_record_matchday_revenue(sender, instance, created, **kwargs):
    """
    Bucht Stadioneinnahmen automatisch nach dem Speichern eines Heimspiel-
    MatchResult, sofern:
      - ein home_club gesetzt ist
      - home_club ein Stadion hat
      - noch kein MatchdayRevenue-Eintrag für dieses Spiel existiert (idempotent)
    """
    if not instance.home_club_id:
        return

    try:
        _ = instance.matchday_revenue
        return
    except Exception:
        pass

    try:
        home_club = instance.home_club
        _ = home_club.stadium
    except Exception:
        return

    try:
        from .stadium_revenue import record_matchday_revenue
        record_matchday_revenue(
            club=home_club,
            match_result=instance,
        )
    except Exception as exc:
        logger.warning(
            'auto_record_matchday_revenue: Einnahmen für %s nicht verbucht: %s',
            instance,
            exc,
        )


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
