"""Abschnitt 'Letzte Spiele' — Mittelwerte der letzten N SimulatedMatch."""
from __future__ import annotations

from .constants import RECENT_SAMPLE_SIZE
from .utils import safe_dict, mean, fmt_num, fmt_pct


def fetch_recent_reports(limit=RECENT_SAMPLE_SIZE):
    """Liest die letzten `limit` SimulatedMatch read-only aus."""
    from game.models import SimulatedMatch
    reports = []
    qs = (
        SimulatedMatch.objects
        .select_related('home_club', 'away_club')
        .order_by('-simulated_at')[:limit]
    )
    for sm in qs:
        reports.append({
            'id': sm.id,
            'home_goals': sm.home_goals,
            'away_goals': sm.away_goals,
            'home_club': sm.home_club.short_name or sm.home_club.name,
            'away_club': sm.away_club.short_name or sm.away_club.name,
            'report': safe_dict(sm.report_data),
        })
    return reports


def compute_recent_metrics(reports):
    """Reine Aggregation der Kennzahlen aus einer Report-Liste."""
    n = len(reports)
    if n == 0:
        return {
            'goals_per_game': None, 'home_pct': None,
            'draw_pct': None, 'away_pct': None, 'avg_xg': None,
        }
    total_goals = sum((r['home_goals'] or 0) + (r['away_goals'] or 0) for r in reports)
    home_w = draw = away_w = 0
    xg_vals = []
    for r in reports:
        hg, ag = r['home_goals'] or 0, r['away_goals'] or 0
        if hg > ag:
            home_w += 1
        elif hg == ag:
            draw += 1
        else:
            away_w += 1
        rd = safe_dict(r.get('report'))
        hx, ax = rd.get('home_xg'), rd.get('away_xg')
        if hx is not None and ax is not None:
            try:
                xg_vals.append(float(hx) + float(ax))
            except (TypeError, ValueError):
                pass
    return {
        'goals_per_game': total_goals / n,
        'home_pct': home_w / n,
        'draw_pct': draw / n,
        'away_pct': away_w / n,
        'avg_xg': mean(xg_vals),
    }


def build_recent_matches(reports):
    n = len(reports)
    metrics = compute_recent_metrics(reports)
    rows = []
    for r in reports[:12]:
        rd = safe_dict(r.get('report'))
        hx, ax = rd.get('home_xg'), rd.get('away_xg')
        xg = None
        if hx is not None and ax is not None:
            try:
                xg = float(hx) + float(ax)
            except (TypeError, ValueError):
                xg = None
        rows.append({
            'home': r['home_club'], 'away': r['away_club'],
            'hg': r['home_goals'], 'ag': r['away_goals'],
            'xg': fmt_num(xg),
        })
    return {
        'title': 'Letzte Spiele',
        'available': n > 0,
        'note': '' if n > 0 else 'Leere Stichprobe: keine SimulatedMatch-Einträge vorhanden.',
        'sample_size': n,
        'metrics': metrics,
        'xg_available': metrics['avg_xg'] is not None,
        'display': {
            'goals_per_game': fmt_num(metrics['goals_per_game']),
            'home_pct': fmt_pct(metrics['home_pct']),
            'draw_pct': fmt_pct(metrics['draw_pct']),
            'away_pct': fmt_pct(metrics['away_pct']),
            'avg_xg': fmt_num(metrics['avg_xg']),
        },
        'rows': rows,
    }
