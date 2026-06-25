"""Gemeinsame, reine Helfer für die Simulation-Diagnose (keine DB-Writes)."""
from __future__ import annotations

NV = 'n/v'


def safe_dict(obj) -> dict:
    """Gibt obj zurück, falls es ein Dict ist, sonst ein leeres Dict."""
    return obj if isinstance(obj, dict) else {}


def safe_list(obj) -> list:
    """Gibt obj zurück, falls es eine Liste ist, sonst eine leere Liste."""
    return obj if isinstance(obj, list) else []


def mean(values):
    """Mittelwert über alle Nicht-None-Werte oder None bei leerer Liste."""
    vals = [v for v in values if v is not None]
    if not vals:
        return None
    return sum(vals) / len(vals)


def fmt_num(value, nd=2, suffix=''):
    if value is None:
        return NV
    try:
        return f'{float(value):.{nd}f}{suffix}'
    except (TypeError, ValueError):
        return NV


def fmt_pct(value, nd=1):
    """value als Anteil (0..1) → Prozentstring."""
    if value is None:
        return NV
    try:
        return f'{float(value) * 100:.{nd}f}%'
    except (TypeError, ValueError):
        return NV


def evaluate_corridor(value, corridor):
    """green/yellow/red/na anhand eines Korridor-Dicts {green:(lo,hi), yellow:(lo,hi)}."""
    if value is None or not corridor:
        return 'na'
    try:
        v = float(value)
    except (TypeError, ValueError):
        return 'na'
    green = corridor.get('green')
    yellow = corridor.get('yellow')
    if green and green[0] <= v <= green[1]:
        return 'green'
    if yellow and yellow[0] <= v <= yellow[1]:
        return 'yellow'
    return 'red'


def corridor_label(corridor):
    if not corridor:
        return NV
    g = corridor.get('green')
    if not g:
        return NV
    return f'grün {g[0]:g}–{g[1]:g}'
