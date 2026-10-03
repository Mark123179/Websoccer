"""Deferred result notifications: once, atomically, after the round barrier."""
from django.db import transaction
from django.utils import timezone
from .models import MatchStory
from .story_release import round_is_released, release_enabled


def publish_due_results(now=None):
    now = now or timezone.now()
    enabled = release_enabled()
    candidates = MatchStory.objects.filter(
        notification_sent=False, match__match_type='freundschaft', round__historical=False,
    ).select_related('round', 'match__home_club', 'match__away_club')
    sent = 0
    for story in candidates:
        if not round_is_released(story.round, now, enabled):
            continue
        with transaction.atomic():
            locked = MatchStory.objects.select_for_update().get(pk=story.pk)
            if locked.notification_sent:
                continue
            from .notifications import notify_club
            sm = story.match
            for club in (sm.home_club, sm.away_club):
                notify_club(club, 'Freundschaftsspiel beendet',
                            f'{sm.home_club.name} {sm.home_goals}:{sm.away_goals} {sm.away_club.name}')
            locked.notification_sent = True
            locked.save(update_fields=['notification_sent'])
            sent += 1
    return sent