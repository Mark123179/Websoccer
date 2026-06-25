"""Orchestrator der Simulation-Diagnose.

``build_simulation_diagnostics_report()`` führt alle Abschnitts-Dicts zum
Kontext zusammen und liefert IMMER genau acht Abschnitts-Keys (auch wenn ein
Abschnitt keine Datenbasis hat — dann mit n/v-Inhalt statt fehlendem Key).
"""
from __future__ import annotations

from .season_status import build_season_status
from .recent_matches import (
    fetch_recent_reports, build_recent_matches, compute_recent_metrics,
)
from .balance import build_balance
from .features import build_features
from .positions import build_positions
from .tactics import build_tactics
from .ticker import build_ticker_coverage
from .regression import build_regression

SECTION_KEYS = (
    'season_status', 'recent_matches', 'balance', 'features',
    'positions', 'tactics', 'ticker', 'regression',
)


def build_simulation_diagnostics_report():
    reports = fetch_recent_reports()
    metrics = compute_recent_metrics(reports)
    report = {
        'season_status':  build_season_status(),
        'recent_matches': build_recent_matches(reports),
        'balance':        build_balance(metrics),
        'features':       build_features(reports),
        'positions':      build_positions(),
        'tactics':        build_tactics(reports),
        'ticker':         build_ticker_coverage(reports),
        'regression':     build_regression(),
    }
    # Invariante: exakt die acht definierten Abschnitts-Keys.
    assert set(report) == set(SECTION_KEYS)
    return report
