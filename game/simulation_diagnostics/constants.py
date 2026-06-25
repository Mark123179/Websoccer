"""Read-only Konstanten der Simulation-Diagnose.

WICHTIG: Dies sind EIGENE Diagnose-Korridore. Die Werte werden aus den
bestehenden Golden-Master-Tests / Regressionsläufen ÜBERNOMMEN und hier mit
Quelle dokumentiert. Es findet KEIN Import von Management Commands zur
Laufzeit statt (vgl. Architektur-Eckpfeiler der Aufgabe).
"""
from __future__ import annotations

# Stichprobengröße: die letzten N SimulatedMatch-Einträge.
RECENT_SAMPLE_SIZE = 50

# Mindest-Stichprobe je Position, bevor eine Position bewertet (geampelt) wird.
POSITION_MIN_SAMPLE = 3

# Quelle der Simulations-Spielerschnappschüsse (Liga-Simulation, season_service.py).
WS_SNAPSHOT_SOURCE = 'ws_liga'

# Regressions-Historie (nur LESEN; es wird KEIN neuer Lauf ausgelöst).
REGRESSION_HISTORY_DIR = '.local/regression_history'
REGRESSION_STABILITY_FILE = 'seeds_stability.json'

# ── Diagnose-Korridore ────────────────────────────────────────────────────────
# green/yellow = (untere, obere) Grenze. Liegt der Wert außerhalb von yellow,
# wird er als rot bewertet. None-Werte ergeben den Status 'na'.
DIAGNOSTIC_CORRIDORS = {
    # Quelle: validate_default_tactic_v1 (GPG-Korridor, eingefroren).
    'goals_per_game': {
        'green': (2.3, 3.2), 'yellow': (2.1, 3.4),
        'label': 'Tore/Spiel',
        'source': 'validate_default_tactic_v1 (GPG-Korridor)',
    },
    # Quelle: Regressions-Historie (Spielausgangsverteilung, Heimvorteil).
    'home_pct': {
        'green': (0.40, 0.52), 'yellow': (0.35, 0.58),
        'label': 'Heimsieg-Anteil',
        'source': 'Regression-Historie (home_pct)',
    },
    'draw_pct': {
        'green': (0.20, 0.30), 'yellow': (0.16, 0.34),
        'label': 'Unentschieden-Anteil',
        'source': 'Regression-Historie (draw_pct)',
    },
    'away_pct': {
        'green': (0.26, 0.38), 'yellow': (0.22, 0.42),
        'label': 'Auswärtssieg-Anteil',
        'source': 'Regression-Historie (away_pct)',
    },
    'yellow_per_game': {
        'green': (2.5, 4.5), 'yellow': (1.8, 5.5),
        'label': 'Gelbe Karten/Spiel',
        'source': 'Regression-Historie (yellow_per_game)',
    },
    'inj_per_game': {
        'green': (0.0, 1.2), 'yellow': (0.0, 1.8),
        'label': 'Verletzungen/Spiel',
        'source': 'Injury-Sim V1 (max. 2 Verletzungen/Team)',
    },
    # Korrelations-Gütemaße: nur die untere Grenze ist relevant (höher = besser).
    'spearman': {
        'green': (0.30, 1.0), 'yellow': (0.15, 1.0),
        'label': 'Spearman Stärke↔Punkte',
        'source': 'Regression-Historie (spearman)',
    },
    'pearson_xgd': {
        'green': (0.30, 1.0), 'yellow': (0.15, 1.0),
        'label': 'Pearson xGD↔Ergebnis',
        'source': 'Regression-Historie (pearson_xgd)',
    },
}

# ── Liveticker-Event-FAMILIEN ─────────────────────────────────────────────────
# ticker_commentary.py exportiert keine Familienliste, daher lokal definiert.
# Werte = die vom Ticker unterstützten evt_type-Signale (siehe build_ticker_text
# in game/ticker_commentary.py). Abgleich auf Familien-, nicht auf Satz-Ebene →
# stabil gegenüber Textänderungen.
EVENT_FAMILY_MAP = {
    'goal':         ('goal', 'corner_goal', 'freekick_goal', 'freekick_cross_goal',
                     'penalty_goal', 'penalty_scored'),
    'card':         ('card', 'gk_red_off'),
    'injury':       ('injury',),
    'substitution': ('sub',),
    'corner':       ('corner', 'corner_goal', 'corner_miss'),
    'foul':         ('foul', 'tackle_win', 'tackle_loss', 'pass_fail'),
    'chance':       ('shot', 'freekick_miss', 'penalty_miss'),
    'save':         ('fk_saved',),
    'kickoff':      ('extra_time_start', 'penalty_shootout_start'),
    'fulltime':     ('extra_time_end', 'penalty_shootout_end'),
}

EVENT_FAMILY_LABELS = {
    'goal': 'Tore',
    'card': 'Karten',
    'injury': 'Verletzungen',
    'substitution': 'Auswechslungen',
    'corner': 'Ecken',
    'foul': 'Fouls/Zweikämpfe',
    'chance': 'Chancen',
    'save': 'Paraden',
    'kickoff': 'Anstoß/Phasenstart',
    'fulltime': 'Abpfiff/Phasenende',
}
