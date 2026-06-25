"""Abschnitt 'Positionsmatrix' — baseline-relative Ampel je Position.

Die Ampel bewertet ausschließlich die Abweichung der Durchschnitts-NOTE einer
Position von der Liga-Baseline (die Note sollte positionsunabhängig ähnlich
liegen). Tore/Vorlagen/Minuten werden nur informativ ausgewiesen, da sie
positionsbedingt stark schwanken. Fehlt die Datenbasis, wird n/v gezeigt.
"""
from __future__ import annotations

from .constants import WS_SNAPSHOT_SOURCE, POSITION_MIN_SAMPLE
from .utils import mean

# Ampel-Schwellen für die Note-Abweichung von der Liga-Baseline.
_NOTE_GREEN = 0.4
_NOTE_YELLOW = 0.8


def fetch_position_snapshots():
    from game.models import PlayerFormSnapshot
    rows = []
    qs = (
        PlayerFormSnapshot.objects
        .filter(source=WS_SNAPSHOT_SOURCE)
        .values('position', 'rating', 'goals', 'assists', 'minutes_played')
    )
    for s in qs:
        rows.append({
            'position': (s['position'] or '').strip() or '?',
            'rating': float(s['rating']) if s['rating'] is not None else None,
            'goals': int(s['goals'] or 0),
            'assists': int(s['assists'] or 0),
            'minutes': int(s['minutes_played'] or 0),
        })
    return rows


def aggregate_positions(snapshots):
    """Reine Aggregation: liefert baseline_note, sample_size und Positionszeilen."""
    snapshots = snapshots or []
    n = len(snapshots)
    baseline_note = mean([s['rating'] for s in snapshots if s['rating'] is not None])
    groups = {}
    for s in snapshots:
        groups.setdefault(s['position'], []).append(s)
    rows = []
    for pos in sorted(groups):
        items = groups[pos]
        cnt = len(items)
        avg_note = mean([s['rating'] for s in items if s['rating'] is not None])
        goals_pm = (sum(s['goals'] for s in items) / cnt) if cnt else None
        assists_pm = (sum(s['assists'] for s in items) / cnt) if cnt else None
        avg_min = mean([s['minutes'] for s in items])
        if avg_note is None or baseline_note is None or cnt < POSITION_MIN_SAMPLE:
            note_status, delta = 'na', None
        else:
            delta = avg_note - baseline_note
            ad = abs(delta)
            note_status = 'green' if ad <= _NOTE_GREEN else (
                'yellow' if ad <= _NOTE_YELLOW else 'red'
            )
        rows.append({
            'position': pos,
            'sample': cnt,
            'avg_note': avg_note,
            'note_status': note_status,
            'note_delta': delta,
            'goals_per_match': goals_pm,
            'assists_per_match': assists_pm,
            'avg_minutes': avg_min,
        })
    return {'baseline_note': baseline_note, 'sample_size': n, 'rows': rows}


def build_positions(snapshots=None):
    if snapshots is None:
        snapshots = fetch_position_snapshots()
    agg = aggregate_positions(snapshots)
    available = agg['sample_size'] > 0
    return {
        'title': 'Positionsmatrix',
        'available': available,
        'note': '' if available else (
            'Keine ws_liga-Spielerschnappschüsse vorhanden — Positionsmatrix n/v.'
        ),
        'baseline_note': agg['baseline_note'],
        'rows': agg['rows'],
    }
