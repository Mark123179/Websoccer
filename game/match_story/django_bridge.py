"""The only Django-dependent addition to the frozen v4.1 narrator.

Timing and narration are never rewritten. Full beat payloads are persisted.
Historical snapshots are explicitly unknown unless supplied by an export.
"""
import logging
from copy import deepcopy
from django.db import transaction
from django.utils import timezone
from game.models import MatchStory, MatchEvent, SimulatedMatch, StoryAudit, TacticSetup
from game.story_release import ensure_round, refresh_barrier
from . import narrate

logger = logging.getLogger(__name__)
TACTIC_FIELDS = (
    'formation', 'lineup', 'bench', 'standards', 'substitutions',
    'first_half', 'second_half', 'instructions', 'conditions', 'is_confirmed',
)


def tactic_snapshot(home, away, *, context='pflicht', squad_scope='pro'):
    tactics = {t.club_id: t for t in TacticSetup.objects.filter(
        club_id__in=[home.pk, away.pk], context=context, squad_scope=squad_scope)}
    def dump(club):
        tactic = tactics.get(club.pk)
        return deepcopy({key: getattr(tactic, key) for key in TACTIC_FIELDS}) if tactic else None
    return {'home': dump(home), 'away': dump(away), 'provenance': 'simulation'}


def export_for(sm, snapshot):
    return {
        'match': {
            'id': sm.pk, 'match_type': sm.match_type,
            'home_club': {'id': sm.home_club_id, 'name': sm.home_club.name},
            'away_club': {'id': sm.away_club_id, 'name': sm.away_club.name},
            'home_goals': sm.home_goals, 'away_goals': sm.away_goals,
            'referee': str(sm.referee) if sm.referee_id else None,
        },
        'report_data': deepcopy(sm.report_data),
        'home_tactic': snapshot.get('home'), 'away_tactic': snapshot.get('away'),
    }


def expected_duration(rd):
    kicks = sum(bool(e.get('team') and e.get('round')) for e in rd.get('penalty_events', []))
    return 900.0 + (300 if rd.get('decided_by') in ('extra_time', 'penalties') else 0) + (
        kicks * 8 + 14 if kicks else 0)


def _fallback_events(story, rd):
    """Real legacy incidents only, subject to the same timed release."""
    incidents = []
    for key, cls, kind in (('goal_events', 'goal', 'tor'), ('card_events', 'card', 'karte'),
                           ('injury_events', 'injury', 'verletzung')):
        for event in rd.get(key, []) or []:
            side = event.get('team') or event.get('club_side')
            text = (
                f"Tor: {event.get('scorer_name') or 'Spieler'}" if cls == 'goal'
                else f"{'Karte' if cls == 'card' else 'Verletzung'}: {event.get('player_name') or 'Spieler'}"
            )
            incidents.append((event.get('minute', 0), side, cls, kind, text, event))
    for side in ('home', 'away'):
        for event in rd.get(f'{side}_substitutions', []) or []:
            incidents.append((event['minute'], side, 'sub', 'wechsel', 'Spielerwechsel', event))
    score = {'home': 0, 'away': 0}
    events = []
    final_minute = 120 if rd.get('decided_by') in ('extra_time', 'penalties') else 90
    for i, (minute, side, cls, kind, text, raw) in enumerate(sorted(incidents, key=lambda e: e[0])):
        payload = {'legacy': deepcopy(raw), 'beats': []}
        if cls == 'goal' and side in score:
            score[side] += 1
            payload['score'] = f"{score['home']}:{score['away']}"
        events.append(MatchEvent(
            story=story, order=i, seq=i, beat=1, minute=minute, team=side,
            cls=cls, kind=kind, level=5 if cls == 'goal' else 3, text=text,
            offset_s=min(story.duration_s, minute / final_minute * (
                1200 if final_minute == 120 else 900)),
            duration_s=0, payload=payload,
        ))
    return events


def _core_issues(sm, events):
    issues = []
    rd = sm.report_data
    for side in ('home', 'away'):
        beats = [b for event in events for b in event.payload.get('beats', [])
                 if b.get('team', event.team) == side]
        got = {
            'goals': sum(b['cls'] == 'goal' for b in beats),
            'shots': sum(b['cls'] in ('goal', 'shot') for b in beats),
            'shots_on_target': sum(b['cls'] == 'goal' or (
                b['cls'] == 'shot' and bool(b['payload'].get('on_target'))) for b in beats),
            'corners': sum(b['cls'] == 'corner' for b in beats),
            'cards': sum(b['cls'] == 'card' for b in beats),
        }
        stats = rd.get('match_stats') or {}
        expected = {k: stats.get(f'{side}_{k}', 0) for k in ('shots', 'shots_on_target', 'corners')}
        expected['goals'] = rd.get(f'{side}_goals', getattr(sm, f'{side}_goals'))
        expected['cards'] = stats.get(f'{side}_yellow', 0) + stats.get(f'{side}_red', 0)
        if got != expected:
            issues.append(f'Kernzahlen {side}: erwartet {expected}, gespeichert {got}')
    return issues


@transaction.atomic
def build_story_for(sm, kickoff_at=None, *, round_=None, source_key=None,
                    snapshot=None, force=False, actor=None):
    """Serialize on match row; force is an actual fresh narrator run."""
    sm = SimulatedMatch.objects.select_for_update(of=('self',)).select_related(
        'home_club', 'away_club', 'referee').get(pk=sm.pk)
    old = MatchStory.objects.filter(match=sm).first()
    if old and not force:
        return old
    if old:
        round_ = old.round
        snapshot = deepcopy(old.tactic_snapshot)
        source_key = old.source_key
        StoryAudit.objects.create(
            actor=actor, action='rebuild_backup', target=str(sm.pk),
            details={'story': {key: getattr(old, key) for key in (
                'version', 'duration_s', 'final_score', 'tactic_snapshot', 'segments', 'state', 'issues')},
                'events': list(old.events.values(
                    'order', 'seq', 'beat', 'minute', 'added', 'team', 'kind', 'cls',
                    'level', 'visible', 'text', 'actors', 'offset_s', 'duration_s', 'payload'))},
        )
    if round_ is None and sm.story_round_id:
        round_ = sm.story_round
        source_key = sm.story_source_key or source_key
        if snapshot is None:
            snapshot = sm.story_tactic_snapshot or None
    if round_ is None:
        round_ = ensure_round(
            f'historical:{sm.pk}' if kickoff_at is None else f'probe:{sm.pk}',
            [str(sm.pk)], [sm.home_club_id, sm.away_club_id], 'Spiel',
            kickoff_at=kickoff_at or sm.simulated_at,
        )
        if kickoff_at is None:
            round_.historical = True
            round_.save(update_fields=['historical'])
    snapshot = deepcopy(snapshot if snapshot is not None else {
        'home': None, 'away': None, 'provenance': 'historical_unknown'})
    if not round_.historical and sm.story_round_id != round_.pk:
        sm.story_round = round_
        sm.story_source_key = str(source_key or sm.pk)
        sm.story_tactic_snapshot = snapshot
        sm.save(update_fields=['story_round', 'story_source_key', 'story_tactic_snapshot'])
    if old:
        old.delete()
    story = MatchStory.objects.create(
        match=sm, round=round_, source_key=str(source_key or sm.pk),
        kickoff_at=round_.kickoff_at, duration_s=expected_duration(sm.report_data),
        final_score=f'{sm.home_goals}:{sm.away_goals}', tactic_snapshot=snapshot,
    )
    try:
        result = narrate(export_for(sm, snapshot))
        lines = result['lines']
        if not lines:
            raise ValueError('Narrator returned no lines')
        story.duration_s = lines[-1].offset_s + lines[-1].duration_s
        story.final_score = f"{result['score']['home']}:{result['score']['away']}"
        story.segments = result['segments']
        story.state = result['state']
        story.issues = list(result['issues'])
        events = [MatchEvent(
            story=story, order=i, seq=line.seq, beat=line.beat, minute=line.minute,
            added=line.added, team=line.team, kind=line.kind, cls=line.cls,
            level=line.payload.get('level', 2), visible=line.visible, text=line.text,
            actors={k: p.id if p else None for k, p in line.actors.items()},
            offset_s=line.offset_s, duration_s=line.duration_s, payload=deepcopy(line.payload),
        ) for i, line in enumerate(lines)]
        # A composed foul/card line can contain beats belonging to opposite
        # teams. v4's display-line team is not the card recipient's team.
        # Preserve each original beat's identity/side, without changing text,
        # composition, offsets, or any narrator logic.
        original = {}
        for beat in result['beats']:
            fingerprint = (beat.seq, beat.kind, beat.cls, tuple(sorted(
                (k, p.id if p else None) for k, p in beat.actors.items())))
            original.setdefault(fingerprint, []).append(beat)
        for event in events:
            for raw in event.payload.get('beats', []):
                fingerprint = (event.seq, raw['kind'], raw['cls'],
                               tuple(sorted(raw.get('actors', {}).items())))
                candidates = original.get(fingerprint, [])
                if not candidates:
                    raise ValueError('Original beat identity missing')
                beat = candidates.pop(0)
                raw.update({
                    'team': beat.team, 'seq': beat.seq, 'beat': beat.beat,
                    'minute': beat.minute, 'added': beat.added,
                    'visible': beat.visible, 'tags': list(beat.tags),
                })
        story.issues.extend(_core_issues(sm, events))
        if abs(story.duration_s - expected_duration(sm.report_data)) > .02:
            story.issues.append(
                f'planner_duration: {story.duration_s} != {expected_duration(sm.report_data)}')
    except Exception as exc:
        logger.exception('Narrator failed for match %s', sm.pk)
        story.issues = [f'narrator_failed: {type(exc).__name__}: {str(exc)[:300]}']
        story.duration_s = expected_duration(sm.report_data)
        events = _fallback_events(story, sm.report_data)
    story.save()
    MatchEvent.objects.bulk_create(events)
    refresh_barrier(round_.pk)
    return story


def simulation_story(sm, *, round_=None, source_key=None, snapshot=None):
    """Savepoint isolates storyteller errors from the simulation transaction."""
    try:
        return build_story_for(
            sm, kickoff_at=timezone.now(), round_=round_ or sm.story_round,
            source_key=source_key or sm.story_source_key,
            snapshot=snapshot if snapshot is not None else sm.story_tactic_snapshot)
    except Exception as exc:
        logger.exception('Story persistence failed for match %s; round stays locked', sm.pk)
        try:
            with transaction.atomic():
                StoryAudit.objects.create(
                    action='persistence_error', target=str(sm.pk),
                    details={'error': type(exc).__name__, 'source': source_key or sm.story_source_key})
        except Exception:
            logger.exception('Could not persist storyteller failure audit for match %s', sm.pk)
        return None