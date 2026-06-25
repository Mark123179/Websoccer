"""Abschnitt 'Liveticker-Abdeckung' — Abgleich der Event-Familien.

Vergleicht die vom Ticker unterstützten Familien (EVENT_FAMILY_MAP) mit den in
der Stichprobe tatsächlich aufgetretenen Familien (aus report_data abgeleitet).
"""
from __future__ import annotations

from .constants import EVENT_FAMILY_MAP, EVENT_FAMILY_LABELS
from .utils import safe_dict, safe_list


def detect_occurred_families(report):
    """Welche Event-Familien sind in EINEM report_data nachweisbar?"""
    report = safe_dict(report)
    fams = set()
    goals = safe_list(report.get('goal_events'))
    if goals:
        fams.add('goal')
    for g in goals:
        if isinstance(g, dict) and g.get('goal_type') == 'corner':
            fams.add('corner')
    for nm in safe_list(report.get('sp_near_miss_events')):
        fams.add('chance')
        if isinstance(nm, dict):
            t = nm.get('type')
            if t == 'corner_miss':
                fams.add('corner')
            elif t == 'fk_saved':
                fams.add('save')
    if safe_list(report.get('card_events')) or safe_list(report.get('dismissal_events')):
        fams.add('card')
    if safe_list(report.get('injury_events')):
        fams.add('injury')
    if safe_list(report.get('home_substitutions')) or safe_list(report.get('away_substitutions')):
        fams.add('substitution')
    ms = safe_dict(report.get('match_stats'))
    if ms.get('home_fouls') or ms.get('away_fouls'):
        fams.add('foul')
    if ms.get('home_shots') or ms.get('away_shots'):
        fams.add('chance')
    # Nur Familien zurückgeben, die im EVENT_FAMILY_MAP definiert sind.
    return fams & set(EVENT_FAMILY_MAP)


def build_ticker_coverage(reports):
    reports = reports or []
    sample = [safe_dict(r.get('report')) for r in reports]
    n = len(sample)
    supported = sorted(EVENT_FAMILY_MAP)
    match_counts = {fam: 0 for fam in supported}
    for rd in sample:
        for fam in detect_occurred_families(rd):
            match_counts[fam] += 1
    occurred = {fam for fam, c in match_counts.items() if c > 0}
    coverage = (len(occurred) / len(supported)) if supported else None
    rows = []
    for fam in supported:
        rows.append({
            'family': fam,
            'label': EVENT_FAMILY_LABELS.get(fam, fam),
            'occurred': fam in occurred,
            'match_count': match_counts[fam],
            'evt_types': ', '.join(EVENT_FAMILY_MAP[fam]),
        })
    never = [EVENT_FAMILY_LABELS.get(f, f) for f in supported if f not in occurred]
    return {
        'title': 'Liveticker-Abdeckung',
        'available': n > 0,
        'note': '' if n > 0 else 'Leere Stichprobe: keine Ereignis-Familien nachweisbar.',
        'coverage_percent': (coverage * 100) if coverage is not None else None,
        'supported_count': len(supported),
        'occurred_count': len(occurred),
        'rows': rows,
        'never_triggered': never,
    }
