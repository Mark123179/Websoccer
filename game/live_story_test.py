"""Admin-only simulations; no domain data may survive this sandbox."""
import uuid

from django.db import transaction
from django.utils import timezone

from .match_engine import simulate_match
from .match_story import narrate
from .match_story.django_bridge import export_for, tactic_snapshot
from .models import Club, SimulatedMatch

SESSION_KEY = 'admin_live_story_test'
TEST_CLUB_IDS = (915, 907)  # FM IDs, not Django primary keys.


def generate_run():
    clubs = {c.fm_inside_id: c for c in Club.objects.filter(
        fm_inside_id__in=TEST_CLUB_IDS)}
    if len(clubs) != 2:
        raise ValueError('Für den Test müssen Bayern München und Borussia Dortmund vorhanden sein.')
    home, away = [clubs[i] for i in TEST_CLUB_IDS]
    run_id = uuid.uuid4().hex
    stories = []
    # The real engine may repair/default tactics. Roll back ALL such writes
    # and discard on_commit hooks, even though generation itself succeeds.
    with transaction.atomic():
        for slot in range(1, 4):
            report = simulate_match(home, away)
            match = SimulatedMatch(
                pk=int(run_id[:12], 16) + slot, home_club=home, away_club=away,
                home_goals=report['home_goals'], away_goals=report['away_goals'],
                report_data=report, match_type='league',
            )
            result = narrate(export_for(match, tactic_snapshot(home, away)))
            events = [{
                'order': order, 'minute': line.minute, 'added': line.added,
                'team': line.team if line.cls not in ('analysis', 'phase') else None,
                'kind': line.kind, 'cls': line.cls, 'level': line.payload.get('level', 2),
                'text': line.text, 'offset_s': line.offset_s,
                'duration_s': line.duration_s,
            } for order, line in enumerate(result['lines'])]
            if not events:
                raise ValueError('Der Erzähler hat keine Testgeschichte erzeugt.')
            stories.append({
                'id': slot, 'home': home.name, 'away': away.name,
                'events': events, 'issues': result['issues'],
                'duration_s': events[-1]['offset_s'] + events[-1]['duration_s'],
            })
        transaction.set_rollback(True)
    return {
        'run_id': run_id, 'kickoff_at': timezone.now().isoformat(),
        'duration_s': max(s['duration_s'] for s in stories), 'stories': stories,
    }