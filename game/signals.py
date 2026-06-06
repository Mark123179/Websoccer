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


@receiver(post_save, sender='game.Club')
def reset_president_satisfaction_on_manager_change(sender, instance, created, **kwargs):
    """Setzt Präsident-Zufriedenheit auf 100, wenn managed_by neu gesetzt wird.

    Fängt alle Pfade ab, die einen Manager einem Verein zuweisen — nicht nur
    record_club_assignment(), sondern auch direkte Admin-Saves oder andere
    Update-Wege.  Die Funktion ist idempotent: Wenn bereits ein Eintrag mit
    value=100 existiert, ändert sie nichts.
    """
    if not instance.managed_by_id:
        return

    # Nur reagieren, wenn managed_by sich geändert hat
    try:
        previous = sender.objects.values_list('managed_by_id', flat=True).get(pk=instance.pk)
    except sender.DoesNotExist:
        previous = None

    # previous kommt aus der DB *nach* dem Save — wir prüfen daher via
    # update_fields ob managed_by im Diff war, oder ob es ein neuer Club ist.
    update_fields = kwargs.get('update_fields') or []
    is_managed_by_update = created or 'managed_by' in (update_fields or [])

    if not is_managed_by_update:
        return

    try:
        from .models import PresidentSatisfaction
        PresidentSatisfaction.objects.update_or_create(
            manager_id=instance.managed_by_id,
            club=instance,
            defaults={'value': 100},
        )
    except Exception:
        logger.warning(
            'reset_president_satisfaction_on_manager_change: '
            'Zufriedenheit für Club %s (manager_id=%s) nicht zurückgesetzt.',
            instance.pk, instance.managed_by_id, exc_info=True,
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
