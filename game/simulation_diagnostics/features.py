"""Abschnitt 'Feature-Ampel' — Code-Vorhandensein UND messbare Nutzung.

Status:
  ok   — Feature im Code vorhanden UND in der Stichprobe messbar aufgetreten.
  warn — Code vorhanden, in der (nicht leeren) Stichprobe aber nicht aufgetreten.
  bad  — Code/Struktur fehlt.
  na   — aus den Daten nicht prüfbar (z. B. leere Stichprobe).

Es wird KEINE Simulation und KEIN Management Command ausgelöst — nur sichere
Imports/Attributprüfungen ohne Seiteneffekte.
"""
from __future__ import annotations

import importlib

from .utils import safe_dict, safe_list


def _module_attr(modname, attr):
    try:
        m = importlib.import_module(modname)
    except Exception:
        return False
    return hasattr(m, attr)


def _model_attr(model_name, attr):
    try:
        from game import models
    except Exception:
        return False
    model = getattr(models, model_name, None)
    return model is not None and hasattr(model, attr)


# ── Nutzungs-Detektoren (rein, je ein report_data) ────────────────────────────

def _has_set_piece(report):
    for g in safe_list(report.get('goal_events')):
        if isinstance(g, dict) and g.get('goal_type') in (
            'corner', 'fk_direct', 'fk_cross', 'penalty_sp'
        ):
            return True
    return bool(safe_list(report.get('sp_near_miss_events')))


def _has_injury(report):
    return bool(safe_list(report.get('injury_events')))


def _has_cards(report):
    return bool(
        safe_list(report.get('card_events'))
        or safe_list(report.get('dismissal_events'))
    )


def _has_subs(report):
    return bool(
        safe_list(report.get('home_substitutions'))
        or safe_list(report.get('away_substitutions'))
    )


def _has_compiled_tactic(report):
    return bool(
        safe_dict(report.get('home_compiled_tactic'))
        or safe_dict(report.get('away_compiled_tactic'))
    )


def _has_freshness(report):
    for key in ('home_fatigue_cost', 'away_fatigue_cost'):
        v = report.get(key)
        if v is None:
            continue
        try:
            if float(v) != 1.0:
                return True
        except (TypeError, ValueError):
            continue
    return False


def _has_ticker_event(report):
    # Der Liveticker greift, sobald irgendein narrierbares Ereignis auftritt.
    return (
        bool(safe_list(report.get('goal_events')))
        or _has_set_piece(report)
        or _has_injury(report)
        or _has_cards(report)
        or _has_subs(report)
    )


_FEATURES = [
    {
        'label': 'Set-Pieces (Ecken/Freistöße/Elfmeter)',
        'code': lambda: _module_attr('game.match_engine', '_set_piece_xg'),
        'detect': _has_set_piece,
        'hint': 'Standardsituationen als eigene xG-Pfade.',
    },
    {
        'label': 'Verletzungen',
        'code': lambda: _model_attr('Player', 'is_ws_injured'),
        'detect': _has_injury,
        'hint': 'Max. 2 pro Team; seltenes Ereignis (warn statt rot, wenn nicht in Stichprobe).',
    },
    {
        'label': 'Karten & Platzverweise',
        'code': lambda: _module_attr('game.match_engine', '_resolve_dismissal'),
        'detect': _has_cards,
        'hint': 'Gelb/Gelb-Rot/Rot inkl. TW-Sonderlogik.',
    },
    {
        'label': 'Auswechslungen',
        'code': lambda: _module_attr('game.match_engine', 'ActiveLineupState'),
        'detect': _has_subs,
        'hint': 'Mid-Match-Substitution-Engine.',
    },
    {
        'label': 'Taktik-Kompilierung',
        'code': lambda: _module_attr('game.tactic_compiler', 'compile_tactic'),
        'detect': _has_compiled_tactic,
        'hint': 'Kompilierte Taktik je Spiel im Report hinterlegt.',
    },
    {
        'label': 'Frische / Ermüdung',
        'code': lambda: _model_attr('PlayerStrengthProfile', 'freshness'),
        'detect': _has_freshness,
        'hint': 'Frische wirkt als Ermüdungskosten (fatigue_cost).',
    },
    {
        'label': 'Liveticker-Kommentar',
        'code': lambda: _module_attr('game.ticker_commentary', 'build_ticker_text'),
        'detect': _has_ticker_event,
        'hint': 'Deterministischer Radio-Kommentar je Ereignis.',
    },
]


def build_features(reports):
    reports = reports or []
    sample = [safe_dict(r.get('report')) for r in reports]
    n = len(sample)
    rows = []
    for feat in _FEATURES:
        try:
            code_present = bool(feat['code']())
        except Exception:
            code_present = False
        match_count = sum(1 for rd in sample if feat['detect'](rd)) if n else 0
        if not code_present:
            status, evidence = 'bad', 'Code/Struktur nicht gefunden'
        elif n == 0:
            status, evidence = 'na', 'Leere Stichprobe — Nutzung nicht prüfbar'
        elif match_count > 0:
            status, evidence = 'ok', f'in {match_count}/{n} Spielen aufgetreten'
        else:
            status, evidence = 'warn', f'Code vorhanden, in {n} Spielen nicht aufgetreten'
        rows.append({
            'feature': feat['label'],
            'status': status,
            'evidence': evidence,
            'hint': feat['hint'],
        })
    return {
        'title': 'Feature-Ampel',
        'available': n > 0,
        'note': '' if n > 0 else 'Leere Stichprobe: nur Code-Vorhandensein prüfbar (Status na).',
        'rows': rows,
    }
