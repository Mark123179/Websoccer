"""Read-only, simulation-wide referee comparison from persisted match reports."""
from collections import defaultdict

from .models import GameSeasonState, SimulatedMatch


def _card_count(stats, kind):
    if not isinstance(stats, dict):
        return None
    values = [stats.get(f'{side}_{kind}') for side in ('home', 'away')]
    if any(type(value) is not int or value < 0 for value in values):
        return None
    return sum(values)


def _highlight(rate, average, games, referee_count):
    # Do not classify a single match or compare someone only with themselves.
    if games < 5 or referee_count < 2 or average is None or average <= 0:
        return '', 'Noch keine belastbare Vergleichsbasis.'
    ratio = rate / average
    if ratio >= 1.5:
        return 'is-high', 'Stark erhöht (mindestens 50 % über dem Sim-Durchschnitt).'
    if ratio >= 1.25:
        return 'is-elevated', 'Erhöht (mindestens 25 % über dem Sim-Durchschnitt).'
    if ratio <= .75:
        return 'is-low', 'Selten (mindestens 25 % unter dem Sim-Durchschnitt).'
    return '', 'Im üblichen Bereich.'


def current_referee_stats(referee_id):
    season = GameSeasonState.objects.values_list('current_season', flat=True).first()
    if season is None:
        return {'available': False, 'message': 'Aktuelle Saison noch nicht festgelegt.'}
    totals = defaultdict(lambda: {
        'games': 0, 'yellow': 0, 'red': 0, 'penalty': 0,
        'yellow_games': 0, 'red_games': 0, 'penalty_games': 0,
    })
    # Project only the small report sections needed here, not full player reports.
    matches = SimulatedMatch.objects.filter(
        season=str(season), referee__isnull=False,
    ).exclude(report_data={}).order_by().values_list(
        'referee_id', 'report_data__match_stats', 'report_data__goal_events',
    )
    for ref_id, stats, goals in matches.iterator(chunk_size=500):
        row = totals[ref_id]
        row['games'] += 1
        for kind in ('yellow', 'red'):
            count = _card_count(stats, kind)
            if count is not None:
                row[kind] += count
                row[f'{kind}_games'] += 1
        if isinstance(goals, list) and all(
            isinstance(goal, dict) and isinstance(goal.get('goal_type'), str)
            for goal in goals
        ):
            row['penalty'] += sum(
                isinstance(goal, dict) and goal.get('goal_type') == 'penalty_sp'
                for goal in goals
            )
            row['penalty_games'] += 1
    own = totals[referee_id]
    result = {
        'available': True, 'season': season, 'games': own['games'],
        'message': 'Noch keine Einsätze in dieser Saison.' if not own['games'] else '',
        'metrics': [],
    }
    if not own['games']:
        return result
    result['metrics'].append({
        'label': 'Spiele', 'value': str(own['games']), 'class_name': '',
        'detail': 'Geleitete Spiele der aktuellen Saison, alle Wettbewerbe.',
    })
    for kind, label, average_display in (
        ('yellow', 'Ø Gelb', True), ('red', 'Rot', False),
        ('penalty', 'Elfmeter-Tore', False),
    ):
        measured = own[f'{kind}_games']
        peers = [row for row in totals.values() if row[f'{kind}_games']]
        denominator = sum(row[f'{kind}_games'] for row in peers)
        average = sum(row[kind] for row in peers) / denominator if denominator else None
        complete = measured == own['games']
        rate = own[kind] / measured if measured else 0
        css, interpretation = _highlight(rate, average, measured, len(peers)) if complete else (
            '', 'Nicht in allen Spielberichten erfasst.',
        )
        value = (f'{rate:.1f}'.replace('.', ',') if average_display else str(own[kind])) if complete else '—'
        detail = interpretation
        if complete and average is not None:
            detail += f' Pro Spiel: {rate:.2f}; gesamte Sim: {average:.2f}.'
        if kind == 'penalty':
            detail += ' Nur verwandelte Elfmeter im Spiel; kein Elfmeterschießen.'
        result['metrics'].append({
            'label': label, 'value': value, 'class_name': css, 'detail': detail,
        })
    result['metrics'].append({
        'label': 'Umstritten', 'value': '—', 'class_name': '',
        'detail': 'Umstrittene Entscheidungen werden in der Simulation nicht erfasst.',
    })
    return result
