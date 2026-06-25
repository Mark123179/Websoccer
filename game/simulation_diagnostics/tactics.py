"""Abschnitt 'Taktik-Wirkung' — Spielausgänge je Formation (soweit Daten vorhanden).

V1 gruppiert nach der real im report_data vorhandenen Formation. Fehlt diese
Information, wird der Abschnitt als n/v ausgewiesen statt geraten.
"""
from __future__ import annotations

from .utils import safe_dict


def build_tactics(reports):
    reports = reports or []
    groups = {}  # formation -> {n, gf, ga, wins}
    have_data = False
    for r in reports:
        rd = safe_dict(r.get('report'))
        hg = r.get('home_goals') or 0
        ag = r.get('away_goals') or 0
        for formation_key, gf, ga in (
            ('home_formation', hg, ag),
            ('away_formation', ag, hg),
        ):
            formation = (rd.get(formation_key) or '').strip()
            if not formation:
                continue
            have_data = True
            g = groups.setdefault(formation, {'n': 0, 'gf': 0, 'ga': 0, 'wins': 0})
            g['n'] += 1
            g['gf'] += gf
            g['ga'] += ga
            if gf > ga:
                g['wins'] += 1
    rows = []
    for formation in sorted(groups, key=lambda f: -groups[f]['n']):
        g = groups[formation]
        n = g['n']
        rows.append({
            'formation': formation,
            'sample': n,
            'goals_for': g['gf'] / n,
            'goals_against': g['ga'] / n,
            'win_pct': g['wins'] / n * 100,
        })
    return {
        'title': 'Taktik-Wirkung',
        'available': have_data,
        'note': '' if have_data else (
            'Keine Formations-/Taktikmerkmale in report_data — Gruppierung n/v.'
        ),
        'dimension': 'Formation',
        'rows': rows,
    }
