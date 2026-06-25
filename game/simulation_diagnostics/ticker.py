"""Abschnitt 'Liveticker-Abdeckung' — Abgleich der Event-Familien.

Vergleicht die vom Ticker unterstützten Familien (EVENT_FAMILY_MAP) mit den in
der Stichprobe tatsächlich aufgetretenen Familien (aus report_data abgeleitet).
"""
from __future__ import annotations

from .constants import (
    EVENT_FAMILY_MAP, EVENT_FAMILY_LABELS, EVENT_FAMILY_UNMEASURABLE,
)
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
    # Messbare Familien (Nicht-Auftreten = echtes Signal) von n/v-Familien
    # trennen. Die Abdeckungsquote zählt NUR messbare Familien — sonst würden
    # K.-o.-only- bzw. nicht persistierte Familien sie künstlich drücken.
    measurable = [f for f in supported if f not in EVENT_FAMILY_UNMEASURABLE]
    occurred = {f for f in measurable if match_counts[f] > 0}
    coverage = (len(occurred) / len(measurable)) if measurable else None
    rows = []
    for fam in supported:
        unmeasurable = fam in EVENT_FAMILY_UNMEASURABLE
        if unmeasurable:
            status = 'na'
        elif match_counts[fam] > 0:
            status = 'ok'
        elif n == 0:
            status = 'na'
        else:
            status = 'warn'
        rows.append({
            'family': fam,
            'label': EVENT_FAMILY_LABELS.get(fam, fam),
            'occurred': fam in occurred,
            'measurable': not unmeasurable,
            'status': status,
            'na_reason': EVENT_FAMILY_UNMEASURABLE.get(fam, ''),
            'match_count': match_counts[fam],
            'evt_types': ', '.join(EVENT_FAMILY_MAP[fam]),
        })
    # „Nie ausgelöst" nur für messbare Familien — n/v-Familien sind kein Fehler.
    never = [
        EVENT_FAMILY_LABELS.get(f, f)
        for f in measurable if f not in occurred
    ]
    return {
        'title': 'Liveticker-Abdeckung',
        'available': n > 0,
        'note': '' if n > 0 else 'Leere Stichprobe: keine Ereignis-Familien nachweisbar.',
        'coverage_percent': (coverage * 100) if coverage is not None else None,
        'supported_count': len(measurable),
        'occurred_count': len(occurred),
        'unmeasurable_count': len(EVENT_FAMILY_UNMEASURABLE),
        'rows': rows,
        'never_triggered': never,
    }
