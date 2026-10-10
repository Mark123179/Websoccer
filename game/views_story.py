"""Safe playback endpoints. Never serialize final report_data to a live client."""
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse, HttpResponseForbidden, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.decorators.clickjacking import xframe_options_sameorigin
from .models import MatchStory, MatchStoryRound, MatchEvent, SimulatedMatch, StoryAudit, StorySettings
from .story_release import round_is_released, release_enabled, refresh_barrier
from .stadium_scene_context import ticker_scene_context


def _score(events):
    home = away = 0
    for event in events:
        if event.cls == 'goal':
            home += event.team == 'home'
            away += event.team == 'away'
    return f'{home}:{away}'


def _event(event):
    # Full beats are stored for later 2D, not exposed early via the browser.
    return {
        'order': event.order, 'minute': event.minute, 'added': event.added,
        'team': event.team if event.cls not in ('analysis', 'phase') else None,
        'kind': event.kind, 'cls': event.cls, 'level': event.level,
        'text': event.text, 'offset_s': event.offset_s, 'duration_s': event.duration_s,
        'tally': event.payload.get('tally'),
    }


def _no_cache(data, status=200):
    response = JsonResponse(data, status=status)
    response['Cache-Control'] = 'private, no-store, max-age=0'
    response['Vary'] = 'Cookie'
    return response


def _pending_matches(round_, missing, released):
    """Include scheduled fixtures even while their story is being generated.

    Exactly one joined query for whichever competition owns this round.
    Never read their prematurely persisted score fields.
    """
    from .models import SeasonFixture, CupFixture, FriendlyFixture
    prefix = round_.key.split(':')[0]
    ids = [int(source) for source in missing if source.isdigit()]
    if prefix == 'league':
        rows = SeasonFixture.objects.filter(pk__in=ids).values(
            'pk', 'home_club__name', 'away_club__name', 'simulated_match_id')
    elif prefix == 'cup':
        rows = CupFixture.objects.filter(pk__in=ids).values(
            'pk', 'home_club__name', 'away_club__name', 'simulated_match_id')
    elif prefix in ('friendly', 'tournament'):
        rows = FriendlyFixture.objects.filter(pk__in=ids).values(
            'pk', 'sender_club__name', 'target_club__name', 'simulated_match_id')
    else:
        return []
    return [{
        'id': row['simulated_match_id'], 'fixture_id': row['pk'],
        'home': row.get('home_club__name', row.get('sender_club__name')) or 'Freilos',
        'away': row.get('away_club__name', row.get('target_club__name')) or 'Freilos',
        'score': '—' if released else '0:0', 'last_event': None,
        'ticker_url': reverse('story_ticker', args=[row['simulated_match_id']])
                      if row['simulated_match_id'] else None,
        'ended': released, 'status': 'terminal' if released else 'preparing',
    } for row in rows]


@login_required
@xframe_options_sameorigin
def ticker_page(request, sm_id):
    sm = get_object_or_404(SimulatedMatch.objects.select_related('home_club', 'away_club'), pk=sm_id)
    # No final score, report, ratings, state, issues or future event data in HTML.
    try:
        story = sm.story
    except MatchStory.DoesNotExist:
        story = None
    response = render(request, 'game/live_ticker.html', {
        'match_id': sm.pk, 'home_name': sm.home_club.name, 'away_name': sm.away_club.name,
        'api_url': reverse('story_ticker_api', args=[sm.pk]),
        'conference_url': reverse('story_conference', args=[story.round_id]) if story else '',
        'report_url': reverse('match_report_by_id', args=[sm.pk]),
        'is_admin': request.user.is_superuser,
        'admin_url': reverse('story_admin_action'),
        'ticker_stadium_environment': ticker_scene_context(sm.home_club),
    })
    response['Cache-Control'] = 'private, no-store'
    return response


@login_required
def ticker_api(request, sm_id):
    now = timezone.now()
    sm = get_object_or_404(SimulatedMatch.objects.select_related('story_round'), pk=sm_id)
    story = MatchStory.objects.filter(match=sm).select_related('round').first()
    if not story:
        released = sm.story_round_id is None or round_is_released(sm.story_round, now)
        return _no_cache({
            'status': 'historical' if released else 'preparing', 'events': [],
            'score': f'{sm.home_goals}:{sm.away_goals}' if released else '0:0',
            'released': released, 'server_now': now.isoformat(),
        })
    released = round_is_released(story.round, now)
    elapsed = max(0., (now - story.kickoff_at).total_seconds())
    events = list(story.events.filter(
        offset_s__lte=elapsed if not released else float('inf')).order_by('order'))
    return _no_cache({
        'status': 'released' if released else 'live', 'released': released,
        'score': _score(events), 'events': [_event(e) for e in events],
        'server_now': now.isoformat(), 'kickoff_at': story.kickoff_at.isoformat(),
        'elapsed_s': elapsed, 'duration_s': story.duration_s,
        'release_at': story.round.release_at.isoformat() if story.round.release_at else None,
        'round_complete': story.round.release_at is not None,
        'fallback': any(str(i).startswith('narrator_failed') for i in story.issues),
        'report_url': reverse('match_report_by_id', args=[sm.pk]) if released else None,
    })


@login_required
def conference_page(request, round_id):
    round_ = get_object_or_404(MatchStoryRound, pk=round_id)
    response = render(request, 'game/live_conference.html', {
        'round_label': round_.label, 'round_id': round_.pk,
        'api_url': reverse('story_conference_api', args=[round_.pk]),
        'is_admin': request.user.is_superuser,
        'admin_url': reverse('story_admin_action'),
    })
    response['Cache-Control'] = 'private, no-store'
    return response


@login_required
def conference_api(request, round_id):
    """One round request, four fixed queries, independent of match count."""
    now = timezone.now()
    round_ = get_object_or_404(MatchStoryRound, pk=round_id)
    released = round_is_released(round_, now)
    elapsed = max(0., (now - round_.kickoff_at).total_seconds())
    stories = list(round_.stories.select_related('match__home_club', 'match__away_club'))
    events = MatchEvent.objects.filter(story__round=round_)
    if not released:
        events = events.filter(offset_s__lte=elapsed)
    by_story = {s.pk: [] for s in stories}
    for event in events.order_by('order'):
        by_story[event.story_id].append(event)
    matches = []
    for story in stories:
        eligible = by_story[story.pk]
        matches.append({
            'id': story.match_id, 'home': story.match.home_club.name,
            'away': story.match.away_club.name, 'score': _score(eligible),
            'last_event': _event(eligible[-1]) if eligible else None,
            'ticker_url': reverse('story_ticker', args=[story.match_id]),
            'ended': released or elapsed >= story.duration_s,
        })
    missing = set(round_.expected_sources) - {s.source_key for s in stories}
    if missing:
        matches.extend(_pending_matches(round_, missing, released))
    return _no_cache({
        'round_id': round_.pk, 'label': round_.label, 'released': released,
        'complete': round_.release_at is not None,
        'pending_count': len(set(round_.expected_sources) - set(round_.terminal_sources)
                             - {s.source_key for s in stories}),
        'server_now': now.isoformat(), 'elapsed_s': elapsed,
        'release_at': round_.release_at.isoformat() if round_.release_at else None,
        'matches': matches,
    })


@login_required
@require_POST
@transaction.atomic
def admin_action(request):
    if not request.user.is_superuser:
        return HttpResponseForbidden('Nur Administratoren dürfen die Ergebnissperre ändern.')
    if request.POST.get('confirmed') != 'yes':
        return HttpResponseBadRequest('Explizite Bestätigung erforderlich.')
    action = request.POST.get('action')
    if action == 'rebuild':
        from .match_story.django_bridge import build_story_for
        sm = get_object_or_404(SimulatedMatch, pk=request.POST.get('match_id'))
        build_story_for(sm, force=True, actor=request.user)
        return redirect('story_ticker', sm_id=sm.pk)
    if request.POST.get('enabled') not in ('true', 'false'):
        return HttpResponseBadRequest('enabled muss true oder false sein.')
    enabled = request.POST['enabled'] == 'true'
    if action == 'global_override':
        obj, _ = StorySettings.objects.get_or_create(pk=1)
        obj.story_release_enabled = enabled
        obj.save(update_fields=['story_release_enabled'])
        target = 'global'
    elif action == 'round_override':
        obj = get_object_or_404(MatchStoryRound, pk=request.POST.get('round_id'))
        obj.release_enabled = enabled
        obj.save(update_fields=['release_enabled'])
        target = obj.key
    else:
        return HttpResponseBadRequest('Unbekannte Aktion.')
    StoryAudit.objects.create(actor=request.user, action=action, target=target,
                              details={'release_enabled': enabled})
    return redirect('story_conference', round_id=obj.pk) if action == 'round_override' else redirect('home')