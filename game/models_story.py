"""Durable narration and fail-closed competition playback barriers."""
from django.db import models
from django.conf import settings


class StorySettings(models.Model):
    """Singleton; override is explicit, global, and audited."""
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    story_release_enabled = models.BooleanField(default=True)


class MatchStoryRound(models.Model):
    key = models.CharField(max_length=160, unique=True)
    label = models.CharField(max_length=160)
    kickoff_at = models.DateTimeField()
    expected_sources = models.JSONField(default=list)
    terminal_sources = models.JSONField(default=list)
    club_ids = models.JSONField(default=list)
    league_id = models.PositiveIntegerField(null=True, blank=True)
    tournament_id = models.PositiveIntegerField(null=True, blank=True)
    release_enabled = models.BooleanField(default=True)
    historical = models.BooleanField(default=False)
    # Materialized only after every expected source has a story/terminal outcome.
    release_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)


class MatchStory(models.Model):
    match = models.OneToOneField('game.SimulatedMatch', on_delete=models.CASCADE,
                                 related_name='story')
    round = models.ForeignKey(MatchStoryRound, on_delete=models.PROTECT,
                               related_name='stories')
    source_key = models.CharField(max_length=80)
    version = models.CharField(max_length=16, default='v4.1')
    kickoff_at = models.DateTimeField()
    duration_s = models.FloatField()
    final_score = models.CharField(max_length=16)
    tactic_snapshot = models.JSONField(default=dict)
    segments = models.JSONField(default=list)
    state = models.JSONField(default=dict)
    issues = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    notification_sent = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['round', 'source_key'], name='story_round_source_unique'),
        ]


class MatchEvent(models.Model):
    story = models.ForeignKey(MatchStory, on_delete=models.CASCADE, related_name='events')
    order = models.PositiveIntegerField()
    seq = models.FloatField()
    beat = models.PositiveSmallIntegerField()
    minute = models.PositiveSmallIntegerField()
    added = models.PositiveSmallIntegerField(default=0)
    team = models.CharField(max_length=4, null=True)
    kind = models.CharField(max_length=40)
    cls = models.CharField(max_length=24)
    level = models.PositiveSmallIntegerField(default=2)
    visible = models.BooleanField(default=True)
    text = models.TextField()
    actors = models.JSONField(default=dict)
    offset_s = models.FloatField()
    duration_s = models.FloatField()
    payload = models.JSONField(default=dict)

    class Meta:
        ordering = ['order']
        constraints = [
            models.UniqueConstraint(fields=['story', 'order'], name='story_event_order_unique'),
        ]
        indexes = [
            models.Index(fields=['story', 'offset_s'], name='story_offset_idx'),
            models.Index(fields=['story', 'cls'], name='story_cls_idx'),
        ]


class StoryAudit(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=40)
    target = models.CharField(max_length=160)
    details = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)