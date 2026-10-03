"""One server-side release policy for all result consumers.

No story on a newly registered round is never a release bypass. Old matches
without a registered round remain historical, including after backfill.
"""
from datetime import timedelta
from django.db import transaction
from django.db.models import Exists, Q
from django.utils import timezone
from .models import MatchStoryRound, MatchStory, StorySettings


def release_enabled():
    return StorySettings.objects.filter(pk=1, story_release_enabled=False).exists() is False


def round_is_released(round_, now=None, enabled=None):
    if round_.historical or not round_.release_enabled:
        return True
    if enabled is None:
        enabled = release_enabled()
    return not enabled or (
        round_.release_at is not None and round_.release_at <= (now or timezone.now())
    )


def round_release_time(sm):
    if sm.story_round_id:
        return sm.story_round.release_at
    try:
        return sm.story.round.release_at
    except MatchStory.DoesNotExist:
        return None


def is_released(sm, now=None):
    if sm is None:
        return True
    if sm.story_round_id:
        return round_is_released(MatchStoryRound.objects.get(pk=sm.story_round_id), now)
    return True  # no registered playback: pre-feature historical record


def active_rounds(now=None):
    return MatchStoryRound.objects.filter(historical=False, release_enabled=True).filter(
        Q(release_at__isnull=True) | Q(release_at__gt=now or timezone.now())
    ).filter(
        ~Exists(StorySettings.objects.filter(pk=1, story_release_enabled=False))
    )


@transaction.atomic
def ensure_round(key, sources, clubs, label, *, league_id=None, tournament_id=None,
                 kickoff_at=None, terminal_sources=()):
    round_, _ = MatchStoryRound.objects.get_or_create(
        key=key, defaults={
            'kickoff_at': kickoff_at or timezone.now(), 'label': label,
            'expected_sources': list(map(str, sources)),
            'terminal_sources': list(map(str, terminal_sources)),
            'club_ids': sorted(set(clubs)), 'league_id': league_id,
            'tournament_id': tournament_id,
        },
    )
    # Repeated simulation must not reset the persisted clock.
    return round_


@transaction.atomic
def refresh_barrier(round_id, terminal_source=None):
    round_ = MatchStoryRound.objects.select_for_update().get(pk=round_id)
    if terminal_source is not None and str(terminal_source) not in round_.terminal_sources:
        round_.terminal_sources.append(str(terminal_source))
    stories = list(round_.stories.values_list('source_key', 'duration_s'))
    resolved = set(round_.terminal_sources) | {key for key, _ in stories}
    if set(round_.expected_sources) <= resolved:
        round_.release_at = round_.kickoff_at + timedelta(
            seconds=max((d for _, d in stories), default=0))
    else:
        round_.release_at = None
    round_.save(update_fields=['terminal_sources', 'release_at'])
    return round_


def league_round(league, season, matchday):
    from .models import SeasonFixture
    fixtures = list(SeasonFixture.objects.filter(
        league=league, season=season, matchday=matchday
    ).values_list('pk', 'home_club_id', 'away_club_id'))
    return ensure_round(
        f'league:{league.pk}:{season}:{matchday}',
        [str(pk) for pk, _, _ in fixtures],
        [club for _, h, a in fixtures for club in (h, a)],
        f'{league.name} · Spieltag {matchday}', league_id=league.pk,
    )


def cup_round(fixture):
    from .models import CupFixture
    fixtures = list(CupFixture.objects.filter(cup_round_id=fixture.cup_round_id).values(
        'pk', 'home_club_id', 'away_club_id', 'is_bye'))
    return ensure_round(
        f'cup:{fixture.cup_round_id}', [str(f['pk']) for f in fixtures],
        [c for f in fixtures for c in (f['home_club_id'], f['away_club_id']) if c],
        f'Pokal · Runde {fixture.cup_round.round_number}',
        league_id=fixture.cup_round.cup_season.competition_id,
        terminal_sources=[str(f['pk']) for f in fixtures if f['is_bye']],
    )


def friendly_round(fixture):
    from .models import CommunityTournamentMatch, FriendlyFixture
    tm = CommunityTournamentMatch.objects.filter(friendly_fixture=fixture).select_related(
        'round__phase__tournament').first()
    if tm:
        matches = list(CommunityTournamentMatch.objects.filter(round=tm.round).values(
            'pk', 'friendly_fixture_id', 'home_entry__club_id', 'away_entry__club_id',
            'friendly_fixture__status'))
        t = tm.round.phase.tournament
        return ensure_round(
            f'tournament:{tm.round_id}', [str(m['friendly_fixture_id'] or f"bye:{m['pk']}") for m in matches],
            [c for m in matches for c in (m['home_entry__club_id'], m['away_entry__club_id']) if c],
            f'{t.name} · {tm.round.name or tm.round.number}', tournament_id=t.pk,
            terminal_sources=[
                str(m['friendly_fixture_id']) if m['friendly_fixture_id'] else f"bye:{m['pk']}"
                for m in matches if not m['friendly_fixture_id']
                or m['friendly_fixture__status'] == FriendlyFixture.STATUS_NOT_PLAYED
            ],
        )
    return ensure_round(
        f'friendly:{fixture.pk}', [str(fixture.pk)],
        [fixture.sender_club_id, fixture.target_club_id], 'Freundschaftsspiel',
    )