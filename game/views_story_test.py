"""Isolated playback routes. Never call production rebuild or release actions."""
from datetime import datetime
from functools import wraps
import logging

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseForbidden, Http404
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .live_story_test import SESSION_KEY, generate_run
from .views_story import _no_cache

logger = logging.getLogger(__name__)


def _stadium_preview_environment(club_id=None):
    """Current club-keyed spatial scene; never a photograph fallback."""
    if club_id is not None:
        from .models import Club
        from .stadium_scene_context import ticker_scene_context
        try:
            club = Club.objects.select_related("stadium").get(pk=int(club_id))
        except (ValueError, TypeError, Club.DoesNotExist):
            raise ValueError("Ungültiger Stadionverein.")
        context = ticker_scene_context(club)
        if context is None:
            raise ValueError("Für diesen Verein gibt es keine freigegebene räumliche Laufzeitszene.")
        return context
    from .models import Club
    from .stadium_scene_context import ticker_scene_context
    club = Club.objects.filter(fm_inside_id=907).select_related("stadium").first()
    context = ticker_scene_context(club)
    if context is None:
        raise ValueError("Für den BVB fehlt die gemeinsame räumliche Stadion-Scene.")
    return context


def admin_only(view):
    @login_required
    @wraps(view)
    def protected(request, *args, **kwargs):
        if not request.user.is_superuser:
            return HttpResponseForbidden('Live-Ticker-Test: nur für Administratoren.')
        return view(request, *args, **kwargs)
    return protected


def _run(request):
    run = request.session.get(SESSION_KEY)
    if not run:
        run = generate_run()
        request.session[SESSION_KEY] = run
    return run


def _sample(run):
    now = timezone.now()
    elapsed = max(0, (now - datetime.fromisoformat(run['kickoff_at'])).total_seconds())
    return now, elapsed, elapsed >= run['duration_s']


def _eligible(story, elapsed):
    return sorted((e for e in story['events'] if e['offset_s'] <= elapsed),
                  key=lambda e: e['order'])


def _score(events):
    return '{}:{}'.format(
        sum(e['cls'] == 'goal' and e['team'] == 'home' for e in events),
        sum(e['cls'] == 'goal' and e['team'] == 'away' for e in events),
    )


def _story(run, slot):
    if slot not in (1, 2, 3):
        raise Http404
    return run['stories'][slot - 1]


def _context(run):
    return {
        'is_test': True, 'test_kickoff': datetime.fromisoformat(run['kickoff_at']),
        'test_reset_url': reverse('story_test_reset'),
        'test_conference_url': reverse('story_test_conference'),
        'test_games': [{
            'id': s['id'], 'url': reverse('story_test_ticker', args=[s['id']]),
        } for s in run['stories']],
    }


@admin_only
def ticker_page(request, slot=1):
    try:
        run = _run(request)
    except Exception:
        logger.exception('Admin ticker test generation failed')
        return HttpResponse('Testspiel konnte nicht erzeugt werden. Bitte erneut öffnen.', status=503)
    story = _story(run, slot)
    context = _context(run)
    context.update({
        'match_id': slot, 'home_name': story['home'], 'away_name': story['away'],
        'api_url': reverse('story_test_ticker_api', args=[slot]),
        'conference_url': reverse('story_test_conference'),
        'is_admin': False,
    })
    try:
        context['ticker_stadium_environment'] = _stadium_preview_environment(
            request.GET.get("stadium_club"),
        )
    except (OSError, ValueError, KeyError):
        # A missing preview must not stop the original sandbox match playback.
        logger.exception('Ticker stadium preview reference unavailable')
        context['ticker_stadium_environment'] = {'unavailable': True}
    response = render(request, 'game/live_ticker.html', context)
    response['Cache-Control'] = 'private, no-store'
    return response


@admin_only
def conference_page(request):
    run = request.session.get(SESSION_KEY)
    if not run:
        return redirect('story_test_start')
    response = render(request, 'game/live_conference.html', {
        **_context(run), 'round_label': 'Admin-Test · drei parallele Partien',
        'api_url': reverse('story_test_conference_api'), 'is_admin': False,
    })
    response['Cache-Control'] = 'private, no-store'
    return response


@admin_only
def ticker_api(request, slot):
    run = request.session.get(SESSION_KEY)
    if not run:
        return _no_cache({'error': 'Testlauf fehlt. Testnavigation erneut öffnen.'}, status=409)
    story = _story(run, slot)
    now, elapsed, released = _sample(run)
    events = _eligible(story, elapsed)
    return _no_cache({
        'run_id': run['run_id'], 'kickoff_at': run['kickoff_at'],
        'server_now': now.isoformat(), 'elapsed_s': elapsed,
        'duration_s': story['duration_s'], 'released': released,
        'status': 'released' if released else 'live', 'events': events,
        'score': _score(events), 'report_url': None,
    })


@admin_only
def conference_api(request):
    run = request.session.get(SESSION_KEY)
    if not run:
        return _no_cache({'error': 'Testlauf fehlt. Testnavigation erneut öffnen.'}, status=409)
    now, elapsed, released = _sample(run)
    matches = []
    for story in run['stories']:
        events = _eligible(story, elapsed)
        matches.append({
            'id': story['id'], 'home': story['home'], 'away': story['away'],
            'score': _score(events), 'last_event': events[-1] if events else None,
            'ended': elapsed >= story['duration_s'],
            'ticker_url': reverse('story_test_ticker', args=[story['id']]),
        })
    return _no_cache({
        'run_id': run['run_id'], 'server_now': now.isoformat(), 'elapsed_s': elapsed,
        'released': released, 'complete': True, 'pending_count': 0, 'matches': matches,
    })


@admin_only
@require_POST
def reset(request):
    try:
        run = generate_run()
    except Exception:
        logger.exception('Admin ticker test reset failed')
        return HttpResponse('Neues Testspiel konnte nicht erzeugt werden. Der alte Lauf bleibt erhalten.', status=503)
    request.session[SESSION_KEY] = run
    return redirect('story_test_start')