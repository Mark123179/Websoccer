"""Read-only, de-duplicated core-stat audit of persisted historical stories."""
import json
import os
from pathlib import Path
import sys
from collections import Counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
import django
django.setup()
from game.models import MatchStory


def analyze():
    fields = ('shots', 'shots_on_target', 'corners', 'cards', 'goals')
    affected = {field: set() for field in fields}
    affected_sides = Counter()
    missing = {field: set() for field in fields}
    source_counts = Counter()
    examples = {field: [] for field in fields}
    rows = []
    stories = MatchStory.objects.filter(round__historical=True).select_related('match').prefetch_related('events')
    for story in stories.iterator(chunk_size=50):
        rd = story.match.report_data
        stats = rd.get('match_stats') or {}
        events = list(story.events.all())
        for issue in story.issues:
            if str(issue).startswith('Kernzahlen'):
                source_counts['bridge' if 'gespeichert' in issue else 'original'] += 1
        for side in ('home', 'away'):
            beats = [beat for event in events for beat in event.payload.get('beats', [])
                     if beat.get('team', event.team) == side]
            got = {
                'shots': sum(b['cls'] in ('goal', 'shot') for b in beats),
                'shots_on_target': sum(b['cls'] == 'goal' or
                                      (b['cls'] == 'shot' and bool(b['payload'].get('on_target'))) for b in beats),
                'corners': sum(b['cls'] == 'corner' for b in beats),
                'cards': sum(b['cls'] == 'card' for b in beats),
                'goals': sum(b['cls'] == 'goal' for b in beats),
            }
            expected = {field: stats.get(f'{side}_{field}', 0)
                        for field in ('shots', 'shots_on_target', 'corners')}
            expected['cards'] = stats.get(f'{side}_yellow', 0) + stats.get(f'{side}_red', 0)
            expected['goals'] = rd.get(f'{side}_goals', getattr(story.match, f'{side}_goals'))
            for field in fields:
                keys = ([f'{side}_yellow', f'{side}_red'] if field == 'cards' else
                        [f'{side}_goals'] if field == 'goals' else [f'{side}_{field}'])
                source = rd if field == 'goals' else stats
                absent = [key for key in keys if key not in source or source[key] is None]
                if absent:
                    missing[field].add(story.match_id)
                if expected[field] != got[field]:
                    affected[field].add(story.match_id)
                    affected_sides[field] += 1
                    row = {
                        'match_id': story.match_id, 'side': side, 'field': field,
                        'expected': expected[field], 'narrated': got[field],
                        'missing_input_keys': absent,
                        'input_goals': expected['goals'],
                        'input_shots': expected['shots'],
                        'input_shots_on_target': expected['shots_on_target'],
                        'issues': [issue for issue in story.issues
                                   if str(issue).startswith(f'Kernzahlen {side}:')],
                    }
                    rows.append(row)
                    if len(examples[field]) < 3:
                        examples[field].append(row)
    games = set().union(*affected.values())
    return {
        'matches_scanned': stories.count(), 'core_messages': sum(source_counts.values()),
        'message_sources': dict(source_counts), 'affected_matches': len(games),
        'affected_match_sides': len({(r['match_id'], r['side']) for r in rows}),
        'by_field': {
            field: {'affected_matches': len(affected[field]), 'affected_sides': affected_sides[field],
                    'matches_with_missing_input': len(missing[field]),
                    'affected_matches_with_missing_input': len(affected[field] & missing[field])}
            for field in fields},
        'examples': examples, 'differences': rows,
    }


if __name__ == '__main__':
    result = json.dumps(analyze(), ensure_ascii=False, indent=2)
    if len(sys.argv) > 1:
        Path(sys.argv[1]).write_text(result + '\n')
    else:
        print(result)