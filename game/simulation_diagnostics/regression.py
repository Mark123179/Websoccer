"""Abschnitt 'Regression gegen Golden-Master' — liest vorhandene Historie.

Liest NUR die jüngste seeds_stability.json aus .local/regression_history/ und
vergleicht die Mediane gegen die Diagnose-Korridore. Es wird KEIN neuer
Regressionslauf ausgelöst. Fehlt/defekt die Historie → Hinweiszeile.
"""
from __future__ import annotations

import json
import os

from .constants import (
    REGRESSION_HISTORY_DIR, REGRESSION_STABILITY_FILE, DIAGNOSTIC_CORRIDORS,
)
from .utils import evaluate_corridor, corridor_label, fmt_num

_REGRESSION_METRICS = [
    'goals_per_game', 'home_pct', 'draw_pct', 'away_pct',
    'yellow_per_game', 'inj_per_game', 'spearman', 'pearson_xgd',
]


def _median(values):
    vals = sorted(float(v) for v in values if v is not None)
    if not vals:
        return None
    m = len(vals) // 2
    if len(vals) % 2:
        return vals[m]
    return (vals[m - 1] + vals[m]) / 2


def find_latest_run(base_dir=REGRESSION_HISTORY_DIR):
    if not os.path.isdir(base_dir):
        return None
    candidates = []
    for name in os.listdir(base_dir):
        path = os.path.join(base_dir, name, REGRESSION_STABILITY_FILE)
        if os.path.isfile(path):
            candidates.append((name, path))
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0]  # (label, path)


def load_latest_regression(base_dir=REGRESSION_HISTORY_DIR):
    latest = find_latest_run(base_dir)
    if not latest:
        return None, None, 'Keine Regressions-Historie gefunden.'
    label, path = latest
    try:
        with open(path) as f:
            data = json.load(f)
    except Exception as exc:
        return label, None, f'Historie nicht lesbar: {exc}'
    if not isinstance(data, dict):
        return label, None, 'Historie hat unerwartetes Format.'
    return label, data, ''


def evaluate_regression(data):
    metrics = (data or {}).get('metrics') or {}
    stability = (data or {}).get('stability') or {}
    rows = []
    for key in _REGRESSION_METRICS:
        series = metrics.get(key)
        corridor = DIAGNOSTIC_CORRIDORS.get(key)
        med = _median(series) if isinstance(series, list) and series else None
        nd = 4 if key in ('spearman', 'pearson_xgd') else 3
        rows.append({
            'key': key,
            'label': corridor.get('label', key) if corridor else key,
            'median': fmt_num(med, nd),
            'corridor_label': corridor_label(corridor),
            'status': evaluate_corridor(med, corridor),
        })
    flags = []
    for key, val in stability.items():
        ok = bool(val.get('ok', True)) if isinstance(val, dict) else True
        flags.append({'key': key, 'ok': ok})
    return rows, flags


def build_regression():
    label, data, note = load_latest_regression()
    if data is None:
        return {
            'title': 'Regression vs. Golden-Master',
            'available': False,
            'note': note,
            'run_label': label or '',
            'rows': [],
            'stability_flags': [],
        }
    rows, flags = evaluate_regression(data)
    return {
        'title': 'Regression vs. Golden-Master',
        'available': True,
        'note': '',
        'run_label': label,
        'rows': rows,
        'stability_flags': flags,
    }
