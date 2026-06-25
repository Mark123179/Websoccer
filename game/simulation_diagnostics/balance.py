"""Abschnitt 'Balance-KPIs' — Kennzahlen gegen DIAGNOSTIC_CORRIDORS."""
from __future__ import annotations

from .constants import DIAGNOSTIC_CORRIDORS
from .utils import evaluate_corridor, corridor_label, fmt_num, fmt_pct

# (metric-key, Darstellungsart)
_BALANCE_KEYS = [
    ('goals_per_game', 'num'),
    ('home_pct', 'pct'),
    ('draw_pct', 'pct'),
    ('away_pct', 'pct'),
]


def build_balance(metrics):
    metrics = metrics or {}
    rows = []
    any_value = False
    for key, kind in _BALANCE_KEYS:
        corridor = DIAGNOSTIC_CORRIDORS.get(key)
        value = metrics.get(key)
        if value is not None:
            any_value = True
        status = evaluate_corridor(value, corridor)
        disp = fmt_pct(value) if kind == 'pct' else fmt_num(value)
        rows.append({
            'key': key,
            'label': corridor.get('label', key) if corridor else key,
            'value': disp,
            'status': status,
            'corridor_label': corridor_label(corridor),
            'reason': '' if value is not None else 'Kennzahl nicht aus Stichprobe ableitbar',
        })
    return {
        'title': 'Balance-KPIs',
        'available': any_value,
        'note': '' if any_value else 'Leere Stichprobe: keine Kennzahlen berechenbar.',
        'rows': rows,
    }
