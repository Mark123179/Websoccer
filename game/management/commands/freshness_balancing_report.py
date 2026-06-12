"""Frische-Balancing-Report — Monte-Carlo-Simulation der V1-Belastungsszenarien.

Keine DB-Schreibzugriffe. Nur reine Berechnungsfunktionen aus freshness_service.py.

Szenarien:
  S1  Ein Wettbewerb    — Spiel alle 3 Tage (30 Spiele/90d)
  S2  Zwei Wettbewerbe  — Liga·Frei·Pokal·Liga·Frei·Frei (6-Tage-Zyklus, ~45 Sp.)
  S3  Drei Wettbewerbe  — Liga·Frei·Pokal·Liga·Frei·CL   (6-Tage-Zyklus, ~60 Sp.)
  T   Trainingsgelände  — Szenario S2 mit Training S0–S3 verglichen
  M   Medizin           — Szenario S2 mit Medizin S0–S3 verglichen
"""
from __future__ import annotations

import csv
import io
import json
import random
import statistics
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Optional

from django.core.management.base import BaseCommand

from game.freshness_service import (
    BASE_INJURY_RISK_PER_90,
    MEDIZIN_INJURY_FACTOR,
    compute_single_player_loss,
    daily_recovery_amount,
    freshness_injury_multiplier,
)

# ── Verletzungs-Tier-Tabelle (identisch zu match_engine._INJURY_TIERS) ────────
_INJURY_TIERS = [
    ('Leicht',  3,  7, 0.70),
    ('Mittel', 10, 21, 0.25),
    ('Schwer', 28, 56, 0.05),
]
_MAX_INJURIES_PER_TEAM = 2

# ── Virtueller Kader (22 Spieler) ─────────────────────────────────────────────
#  (id, Name, Position, Ausdauer, is_starter)
_SQUAD_TEMPLATE = [
    (1,  'TW1',  'TW', 72, True),
    (2,  'TW2',  'TW', 70, False),
    (3,  'IV1',  'IV', 79, True),
    (4,  'IV2',  'IV', 78, True),
    (5,  'IV3',  'IV', 76, False),
    (6,  'IV4',  'IV', 75, False),
    (7,  'LV1',  'LV', 76, True),
    (8,  'LV2',  'LV', 73, False),
    (9,  'RV1',  'RV', 75, True),
    (10, 'RV2',  'RV', 74, False),
    (11, 'DM1',  'DM', 82, True),
    (12, 'DM2',  'DM', 80, False),
    (13, 'ZM1',  'ZM', 75, True),
    (14, 'ZM2',  'ZM', 74, True),
    (15, 'ZM3',  'ZM', 73, False),
    (16, 'LM1',  'LM', 78, True),
    (17, 'LM2',  'LM', 76, False),
    (18, 'RM1',  'RM', 77, True),
    (19, 'RM2',  'RM', 75, False),
    (20, 'ST1',  'ST', 71, True),
    (21, 'ST2',  'ST', 70, True),
    (22, 'ST3',  'ST', 72, False),
]

# Ersatz-Priorität pro Position
_BACKUP_POSITIONS: dict[str, list[str]] = {
    'TW': ['TW'],
    'IV': ['IV', 'LV', 'RV'],
    'LV': ['LV', 'IV', 'RV'],
    'RV': ['RV', 'IV', 'LV'],
    'DM': ['DM', 'ZM'],
    'ZM': ['ZM', 'DM', 'LM', 'RM'],
    'LM': ['LM', 'ZM', 'RM'],
    'RM': ['RM', 'ZM', 'LM'],
    'ST': ['ST', 'LM', 'RM'],
}

# Tage für tägliche Snapshots (Frische am Tagesende)
_SNAPSHOT_DAYS = [10, 20, 30, 60, 90]


# ── Datenstrukturen ────────────────────────────────────────────────────────────

@dataclass
class SimPlayer:
    pid:          int
    name:         str
    position:     str
    ausdauer:     int
    is_starter:   bool
    freshness:    float = 100.0
    injury_days:  int   = 0
    total_injuries: int = 0
    total_injury_days: int = 0
    inj_by_type:  dict  = field(default_factory=lambda: {'Leicht': 0, 'Mittel': 0, 'Schwer': 0})
    matches_played: int = 0
    minutes_played: int = 0
    per_match_losses: list = field(default_factory=list)
    pre_match_freshness: list = field(default_factory=list)   # Frische VOR jedem Spiel
    daily_freshness: list = field(default_factory=list)       # Tägliche Frische (für Min/Avg)
    snapshots:    dict  = field(default_factory=dict)


@dataclass
class ScenarioResult:
    name:               str
    description:        str
    total_matches:      int
    training_level:     int
    medizin_level:      int
    # Pre-match freshness (key insight)
    pre_match_starter:  list   # alle pre-match Frische-Werte aller Starter aller Runs
    pre_match_bench:    list
    # Tages-Snapshots (Endtag)
    starter_snap:       dict   # {day: [values]}
    bench_snap:         dict
    # Minimum-Frische (worst case)
    min_freshness_starter: list  # min pro Run
    # Schwellenwerte (gezählt über alle match-Zeitpunkte)
    below80_at_match:   list   # [count per run, avg über alle Spieltage]
    below70_at_match:   list
    below60_at_match:   list
    # Verletzungen
    injury_total:       list
    injury_days_total:  list
    inj_by_type:        dict   # {'Leicht': [...], ...}
    avg_days_by_type:   dict
    # Position
    pos_loss:           dict   # {pos: [avg_loss_per_match per run]}


# ── Spielpläne ────────────────────────────────────────────────────────────────

def _build_schedule(days: int, scenario_id: int) -> list[int]:
    """Gibt sortierte, eindeutige Spieltage zurück.

    Reale Spielpläne:
    S1 — Ein Wettbewerb: Spiel alle 3 Tage.
    S2 — Zwei Wettbewerbe (6-Tage-Zyklus, 3 Spiele):
         Liga · Frei · Pokal · Liga · Frei · Frei  →  Spieltage 0, 2, 3
    S3 — Drei Wettbewerbe (6-Tage-Zyklus, 4 Spiele):
         Liga · Frei · Pokal · Liga · Frei · CL    →  Spieltage 0, 2, 3, 5
    """
    if scenario_id == 1:
        return list(range(0, days, 3))

    elif scenario_id == 2:
        # 6-Tage-Zyklus: 0, 2, 3 (= Liga, Pokal, Liga) → ~45 Spiele/90 Tage
        matches = []
        cycle_start = 0
        while cycle_start < days:
            for offset in (0, 2, 3):
                d = cycle_start + offset
                if d < days:
                    matches.append(d)
            cycle_start += 6
        return sorted(set(matches))

    else:
        # 6-Tage-Zyklus: 0, 2, 3, 5 (= Liga, Pokal, Liga, CL) → ~60 Spiele/90 Tage
        matches = []
        cycle_start = 0
        while cycle_start < days:
            for offset in (0, 2, 3, 5):
                d = cycle_start + offset
                if d < days:
                    matches.append(d)
            cycle_start += 6
        return sorted(set(matches))


def _match_stats(schedule: list[int]) -> str:
    """Gibt Spiele-Dichte-Info zurück."""
    if len(schedule) < 2:
        return f'{len(schedule)} Spiele'
    gaps = [b - a for a, b in zip(schedule, schedule[1:])]
    avg_gap = sum(gaps) / len(gaps)
    min_gap = min(gaps)
    return f'{len(schedule)} Spiele  │  Ø {avg_gap:.1f} Tage/Spiel  │  min. {min_gap} Tag(e) Abstand'


# ── Simulation ────────────────────────────────────────────────────────────────

def _fresh_squad() -> list[SimPlayer]:
    return [SimPlayer(pid=t[0], name=t[1], position=t[2],
                      ausdauer=t[3], is_starter=t[4])
            for t in _SQUAD_TEMPLATE]


def _find_replacement(position: str, bench_healthy: list) -> Optional[SimPlayer]:
    for pref_pos in _BACKUP_POSITIONS.get(position, [position]):
        for p in bench_healthy:
            if p.position == pref_pos and p not in bench_healthy:  # already filtered
                return p
        for p in bench_healthy:
            if p.position == pref_pos:
                return p
    return None


def _roll_injuries(players: list, medizin_factor: float,
                   rng: random.Random) -> list[tuple]:
    candidates = []
    for p in players:
        fresh = int(p.freshness)
        prob = BASE_INJURY_RISK_PER_90 * freshness_injury_multiplier(fresh) * medizin_factor
        if rng.random() >= prob:
            continue
        r = rng.random()
        cum = 0.0
        itype, idays = 'Leicht', rng.randint(3, 7)
        for t_type, d_min, d_max, weight in _INJURY_TIERS:
            cum += weight
            if r < cum:
                itype = t_type
                idays = rng.randint(d_min, d_max)
                break
        candidates.append((p, itype, idays))
    if len(candidates) > _MAX_INJURIES_PER_TEAM:
        candidates = rng.sample(candidates, _MAX_INJURIES_PER_TEAM)
    return candidates


def _simulate_once(
    match_days: set,
    training_level: int,
    medizin_level: int,
    days: int,
    fatigue_cost: float,
    rng: random.Random,
) -> list[SimPlayer]:
    squad = _fresh_squad()
    medizin_factor = MEDIZIN_INJURY_FACTOR.get(medizin_level, 1.0)

    for day in range(days):
        is_match_day = day in match_days

        # ── Tägliche Regeneration (läuft jeden Tag, auch am Spieltag) ────────
        # Reihenfolge: Regeneration ZUERST, dann Spielbelastung.
        # Gedämpfte Regeneration bei hoher Frische (daily_recovery_amount):
        #   90–100 → 50 %  │  80–89 → 75 %  │  < 80 → 100 %
        for p in squad:
            if p.injury_days > 0:
                continue  # Verletzte erholen sich nicht
            if p.freshness >= 100.0:
                continue
            recovery = daily_recovery_amount(p.freshness, training_level)
            p.freshness = min(100.0, p.freshness + recovery)

        # ── Spieltag ─────────────────────────────────────────────────────────
        if is_match_day:
            healthy_bench = [p for p in squad if not p.is_starter and p.injury_days == 0]

            # Lineup: Starter oder Ersatz
            lineup: list[SimPlayer] = []
            used_bench: set[int] = set()
            for p in squad:
                if not p.is_starter:
                    continue
                if p.injury_days == 0:
                    lineup.append(p)
                else:
                    # Ersatz suchen
                    available = [b for b in healthy_bench if b.pid not in used_bench]
                    sub = _find_replacement(p.position, available)
                    if sub:
                        lineup.append(sub)
                        used_bench.add(sub.pid)

            # Frische vor dem Spiel aufzeichnen (PRE-MATCH — der entscheidende Wert)
            for p in lineup:
                p.pre_match_freshness.append(p.freshness)

            # Frischeverlust anwenden
            for p in lineup:
                loss = compute_single_player_loss(
                    position=p.position,
                    ausdauer=p.ausdauer,
                    fatigue_cost=fatigue_cost,
                    training_level=training_level,
                    minutes=90,
                )
                p.freshness = max(0.0, p.freshness - loss)
                p.matches_played += 1
                p.minutes_played += 90
                p.per_match_losses.append(loss)

            # Verletzungen auswürfeln (nach dem Spiel)
            injuries = _roll_injuries(lineup, medizin_factor, rng)
            for p, itype, idays in injuries:
                p.injury_days = idays
                p.total_injuries += 1
                p.total_injury_days += idays
                p.inj_by_type[itype] += 1

        # ── Verletzungs-Countdown ────────────────────────────────────────────
        for p in squad:
            if p.injury_days > 0:
                p.injury_days -= 1

        # ── Tages-Snapshot & tägliche Frische-Aufzeichnung ──────────────────
        for p in squad:
            p.daily_freshness.append(p.freshness)
        if (day + 1) in _SNAPSHOT_DAYS:
            for p in squad:
                p.snapshots[day + 1] = p.freshness

    return squad


# ── Multi-Run-Aggregation ──────────────────────────────────────────────────────

def _run_scenario(
    name: str,
    description: str,
    scenario_id: int,
    training_level: int,
    medizin_level: int,
    days: int,
    fatigue_cost: float,
    runs: int,
    seed: int,
) -> ScenarioResult:
    schedule     = _build_schedule(days, scenario_id)
    match_set    = set(schedule)
    total_matches = len(schedule)

    # Aggregatoren
    pre_match_starter_all: list[float] = []
    pre_match_bench_all:   list[float] = []
    starter_snap:  dict[int, list[float]] = {d: [] for d in _SNAPSHOT_DAYS}
    bench_snap:    dict[int, list[float]] = {d: [] for d in _SNAPSHOT_DAYS}
    min_fresh_runs: list[float] = []
    below80_runs, below70_runs, below60_runs = [], [], []
    inj_total, inj_days_total = [], []
    inj_by_type: dict[str, list[int]] = {'Leicht': [], 'Mittel': [], 'Schwer': []}
    avg_days_by_type: dict[str, list[float]] = {'Leicht': [], 'Mittel': [], 'Schwer': []}
    pos_losses: dict[str, list[float]] = {}

    rng = random.Random(seed)

    for _ in range(runs):
        squad = _simulate_once(
            match_days=match_set,
            training_level=training_level,
            medizin_level=medizin_level,
            days=days,
            fatigue_cost=fatigue_cost,
            rng=rng,
        )

        # Pre-match Frische
        for p in squad:
            if p.is_starter:
                pre_match_starter_all.extend(p.pre_match_freshness)
            else:
                pre_match_bench_all.extend(p.pre_match_freshness)

        # Tages-Snapshots
        for d in _SNAPSHOT_DAYS:
            starter_snap[d].extend(p.snapshots.get(d, 100.0) for p in squad if p.is_starter)
            bench_snap[d].extend(p.snapshots.get(d, 100.0)   for p in squad if not p.is_starter)

        # Minimum-Frische (Starter)
        starters = [p for p in squad if p.is_starter]
        if starters:
            min_fresh_this = min(
                min(p.daily_freshness) if p.daily_freshness else 100.0
                for p in starters
            )
            min_fresh_runs.append(min_fresh_this)

        # Schwellenwerte: zähle pro Pre-Match-Zeitpunkt
        total_matches_run = sum(len(p.pre_match_freshness) for p in starters)
        if total_matches_run > 0:
            b80 = sum(1 for p in starters for f in p.pre_match_freshness if f < 80)
            b70 = sum(1 for p in starters for f in p.pre_match_freshness if f < 70)
            b60 = sum(1 for p in starters for f in p.pre_match_freshness if f < 60)
            below80_runs.append(b80 / total_matches_run * 11)  # Spieler pro Spiel im Schnitt
            below70_runs.append(b70 / total_matches_run * 11)
            below60_runs.append(b60 / total_matches_run * 11)
        else:
            below80_runs.append(0.0)
            below70_runs.append(0.0)
            below60_runs.append(0.0)

        # Verletzungen
        inj_total.append(sum(p.total_injuries for p in squad))
        inj_days_total.append(sum(p.total_injury_days for p in squad))
        for itype in ('Leicht', 'Mittel', 'Schwer'):
            cnt = sum(p.inj_by_type[itype] for p in squad)
            inj_by_type[itype].append(cnt)
            if cnt > 0:
                total_idays = sum(p.total_injury_days for p in squad if p.inj_by_type[itype] > 0)
                avg_days_by_type[itype].append(total_idays / cnt)

        # Position
        for p in squad:
            if p.per_match_losses:
                pos_losses.setdefault(p.position, [])
                pos_losses[p.position].append(statistics.mean(p.per_match_losses))

    return ScenarioResult(
        name=name,
        description=description,
        total_matches=total_matches,
        training_level=training_level,
        medizin_level=medizin_level,
        pre_match_starter=pre_match_starter_all,
        pre_match_bench=pre_match_bench_all,
        starter_snap=starter_snap,
        bench_snap=bench_snap,
        min_freshness_starter=min_fresh_runs,
        below80_at_match=below80_runs,
        below70_at_match=below70_runs,
        below60_at_match=below60_runs,
        injury_total=inj_total,
        injury_days_total=inj_days_total,
        inj_by_type=inj_by_type,
        avg_days_by_type=avg_days_by_type,
        pos_loss=pos_losses,
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _avg(lst: list) -> float:
    return statistics.mean(lst) if lst else 0.0


def _std(lst: list) -> float:
    return statistics.stdev(lst) if len(lst) > 1 else 0.0


def _fmt(v: float, dec: int = 1) -> str:
    return f'{v:.{dec}f}'


def _row(cols: list, widths: list, sep: str = '  ') -> str:
    return sep.join(str(c).ljust(w) for c, w in zip(cols, widths))


def _sep(widths: list, ch: str = '─', joiner: str = '  ') -> str:
    return joiner.join(ch * w for w in widths)


def _perf_note(loss: float) -> str:
    if loss >= 12:  return '⚠ KRITISCH'
    if loss >= 9:   return '▲ Hoch'
    if loss >= 6:   return '● Mittel'
    return            '▼ Niedrig'


def _tier_rng(t: str) -> str:
    return {'Leicht': ' 3– 7d', 'Mittel': '10–21d', 'Schwer': '28–56d'}[t]


# ── Report-Ausgabe ─────────────────────────────────────────────────────────────

def _print_scenario(res: ScenarioResult, schedule: list[int], stdout) -> None:
    W = 74
    stdout.write(f'\n{"━" * W}')
    stdout.write(f'  {res.name} — {res.description}')
    stdout.write(f'  Training S{res.training_level}  │  Medizin S{res.medizin_level}  '
                 f'│  {_match_stats(schedule)}')
    stdout.write(f'{"━" * W}')

    # [A] Pre-match Frische (Kernmetrik)
    stdout.write('\n  [A] FRISCHE BEIM SPIELBEGINN (Ø aller Starters aller Spiele)')
    stdout.write('      ← Dieser Wert bestimmt Leistung und Verletzungsrisiko')
    wA = [10, 10, 12]
    stdout.write('  ' + _row(['Gruppe', 'Ø Frische', 'Min. Frische'], wA))
    stdout.write('  ' + _sep(wA))
    pm_s = _avg(res.pre_match_starter)
    pm_b = _avg(res.pre_match_bench)
    mn_s = _avg(res.min_freshness_starter)
    stdout.write('  ' + _row(['Startelf', _fmt(pm_s), _fmt(mn_s)], wA))
    if res.pre_match_bench:
        stdout.write('  ' + _row(['Bank', _fmt(pm_b), '─'], wA))

    # Frische-Warnung
    if pm_s < 80:
        stdout.write(f'  ⚠  Startelf tritt im Schnitt mit < 80 Frische an → Leistungsmalus aktiv')
    elif pm_s < 90:
        stdout.write(f'  ℹ  Startelf im leicht erschöpften Bereich (80–90), noch kein Malus')
    else:
        stdout.write(f'  ✓  Startelf tritt erholt an (≥ 90 Frische)')

    # [B] Tages-Snapshots
    stdout.write('\n  [B] FRISCHE-VERLAUF (Ø Startelf am Tagesende)')
    stdout.write('      Achtung: Ruhetage zeigen höhere Werte als echte Spielbelastung.')
    wB = [10] + [8] * len(_SNAPSHOT_DAYS)
    stdout.write('  ' + _row([''] + [f'Tag {d}' for d in _SNAPSHOT_DAYS], wB))
    stdout.write('  ' + _sep(wB))
    stdout.write('  ' + _row(['Startelf'] + [_fmt(_avg(res.starter_snap[d])) for d in _SNAPSHOT_DAYS], wB))
    stdout.write('  ' + _row(['Bank']     + [_fmt(_avg(res.bench_snap[d]))   for d in _SNAPSHOT_DAYS], wB))

    # [C] Schwellenwerte beim Spielbeginn
    stdout.write('\n  [C] SPIELER MIT FRISCHE-DEFIZIT BEIM SPIELBEGINN (Ø Spieler/Spiel)')
    b80 = _avg(res.below80_at_match)
    b70 = _avg(res.below70_at_match)
    b60 = _avg(res.below60_at_match)
    stdout.write(f'      < 80 Frische:  {_fmt(b80)} Spieler/Spiel  '
                 f'│  < 70:  {_fmt(b70)}  │  < 60:  {_fmt(b60)}')

    # [D] Frischeverlust nach Position
    stdout.write('\n  [D] FRISCHEVERLUST NACH POSITION (Ø pro Spiel)')
    wD = [6, 16, 12]
    stdout.write('  ' + _row(['Pos.', 'Ø Verlust/Spiel', 'Einordnung'], wD))
    stdout.write('  ' + _sep(wD))
    for pos in ['TW', 'IV', 'LV', 'RV', 'DM', 'ZM', 'LM', 'RM', 'ST']:
        losses = res.pos_loss.get(pos)
        if not losses:
            continue
        avg_l = _avg(losses)
        stdout.write('  ' + _row([pos, _fmt(avg_l, 2), _perf_note(avg_l)], wD))

    # [E] Verletzungsstatistik
    stdout.write('\n  [E] VERLETZUNGSSTATISTIK (Ø ± Stdabw. über alle Simulationen)')
    t_m = _avg(res.injury_total)
    t_s = _std(res.injury_total)
    d_m = _avg(res.injury_days_total)
    stdout.write(f'      Verletzungen gesamt:  {_fmt(t_m)} (±{_fmt(t_s)})   '
                 f'│  Ausfalltage gesamt: {_fmt(d_m)}')
    wE = [20, 10, 12, 8]
    stdout.write('  ' + _row(['Typ', 'Anz. (Ø)', 'Ø Ausfall', '%'], wE))
    stdout.write('  ' + _sep(wE))
    for itype in ('Leicht', 'Mittel', 'Schwer'):
        cnt  = _avg(res.inj_by_type[itype])
        days_avg = _avg(res.avg_days_by_type[itype]) if res.avg_days_by_type[itype] else 0.0
        pct  = cnt / t_m * 100 if t_m > 0 else 0
        stdout.write('  ' + _row(
            [f'{itype} ({_tier_rng(itype)})', _fmt(cnt), _fmt(days_avg), f'{_fmt(pct)}%'],
            wE,
        ))


def _print_comparison_table(
    label: str,
    results: list[ScenarioResult],
    vary_attr: str,
    schedules: list[list[int]],
    stdout,
) -> None:
    W = 74
    stdout.write(f'\n{"═" * W}')
    stdout.write(f'  {label}')
    stdout.write(f'{"═" * W}')
    wC = [6, 13, 8, 8, 8, 8, 10, 12]
    stdout.write('  ' + _row(
        ['Stufe', 'Ø Frische\n  (Spielbeginn)', 'b80/Sp', 'b70/Sp', 'b60/Sp',
         'Verletz.', 'Ausfallt.', 'Min Frische'],
        wC,
    ))
    stdout.write('  ' + _sep(wC, '─'))
    for res in results:
        lvl  = getattr(res, vary_attr)
        pm   = _fmt(_avg(res.pre_match_starter))
        b80  = _fmt(_avg(res.below80_at_match))
        b70  = _fmt(_avg(res.below70_at_match))
        b60  = _fmt(_avg(res.below60_at_match))
        inj  = _fmt(_avg(res.injury_total))
        injd = _fmt(_avg(res.injury_days_total))
        mn   = _fmt(_avg(res.min_freshness_starter))
        stdout.write('  ' + _row([f'S{lvl}', pm, b80, b70, b60, inj, injd, mn], wC))
    stdout.write('═' * W)


def _print_training_display_legend(stdout) -> None:
    W = 74
    stdout.write(f'\n{"─" * W}')
    stdout.write('  HINWEIS: Frische-ANZEIGE im UI nach Trainingsgelände')
    stdout.write('  (Simulationswerte sind immer exakt — nur die UI-Darstellung variiert)')
    stdout.write(f'{"─" * W}')
    stdout.write('  S0  →  gerundet auf 5er-Schritte  z.B. 73 → "75"')
    stdout.write('  S1  →  ca. ±1–2 Punkte ungenau    z.B. 73 → "72" oder "74"')
    stdout.write('  S2  →  exakter Wert                z.B. 73 → "73"')
    stdout.write('  S3  →  exakter Wert + +1.5 Regen/Tag')
    stdout.write(f'{"─" * W}')


# ── Fazit ─────────────────────────────────────────────────────────────────────

def _print_summary(results_s123: list[ScenarioResult], stdout) -> None:
    stdout.write('\n' + '═' * 74)
    stdout.write('  FAZIT — WICHTIGSTE ERKENNTNISSE')
    stdout.write('═' * 74)
    for res in results_s123:
        pm = _avg(res.pre_match_starter)
        inj = _avg(res.injury_total)
        b80 = _avg(res.below80_at_match)
        emoji = '✓' if pm >= 90 else ('ℹ' if pm >= 80 else '⚠')
        stdout.write(f'  {emoji}  {res.name}: Ø {_fmt(pm)} Frische/Spiel  │  '
                     f'{_fmt(b80)} Sp. < 80  │  {_fmt(inj)} Verletz./90 Tage')
    stdout.write('')
    stdout.write('  Empfehlung V1: Keine Konstantenänderung ohne echte Saisondaten.')
    stdout.write('  Bei Saisonläufen prüfen:')
    stdout.write('    • Frische-Ø < 75 → BASE_MATCH_FITNESS_LOSS ggf. reduzieren')
    stdout.write('    • Frische-Ø > 95 → BASE_DAILY_RECOVERY ggf. reduzieren')
    stdout.write('    • > 0.5 Verletzungen/Spieler/Saison → BASE_INJURY_RISK prüfen')
    stdout.write('═' * 74)


# ── Export ────────────────────────────────────────────────────────────────────

def _to_dict(results: list[ScenarioResult]) -> list[dict]:
    out = []
    for res in results:
        out.append({
            'szenario':       res.name,
            'beschreibung':   res.description,
            'spiele_gesamt':  res.total_matches,
            'training_stufe': res.training_level,
            'medizin_stufe':  res.medizin_level,
            'frische_spielbeginn': {
                'starter_avg': round(_avg(res.pre_match_starter), 2),
                'bench_avg':   round(_avg(res.pre_match_bench), 2) if res.pre_match_bench else None,
                'starter_min': round(_avg(res.min_freshness_starter), 2),
            },
            'tages_snapshots_startelf': {
                f'tag_{d}': round(_avg(res.starter_snap[d]), 2) for d in _SNAPSHOT_DAYS
            },
            'schwellenwerte_pro_spiel': {
                'unter_80': round(_avg(res.below80_at_match), 2),
                'unter_70': round(_avg(res.below70_at_match), 2),
                'unter_60': round(_avg(res.below60_at_match), 2),
            },
            'verletzungen': {
                'gesamt':       round(_avg(res.injury_total), 2),
                'std':          round(_std(res.injury_total), 2),
                'ausfalltage':  round(_avg(res.injury_days_total), 2),
                'leicht':       round(_avg(res.inj_by_type['Leicht']), 2),
                'mittel':       round(_avg(res.inj_by_type['Mittel']), 2),
                'schwer':       round(_avg(res.inj_by_type['Schwer']), 2),
            },
            'verlust_pro_spiel': {
                pos: round(_avg(ls), 2) for pos, ls in res.pos_loss.items()
            },
        })
    return out


def _to_csv(results: list[ScenarioResult]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([
        'Szenario', 'Spiele', 'Training', 'Medizin',
        'PreMatch_Avg', 'PreMatch_Min',
        'Snap_T10', 'Snap_T20', 'Snap_T30', 'Snap_T60', 'Snap_T90',
        'b80_pro_Spiel', 'b70_pro_Spiel', 'b60_pro_Spiel',
        'Verletz_Avg', 'Verletz_Std', 'Ausfallt',
        'Leicht', 'Mittel', 'Schwer',
        'Loss_TW', 'Loss_IV', 'Loss_LV', 'Loss_RV',
        'Loss_DM', 'Loss_ZM', 'Loss_LM', 'Loss_RM', 'Loss_ST',
    ])
    for res in results:
        pos_l = {p: round(_avg(ls), 2) for p, ls in res.pos_loss.items()}
        w.writerow([
            res.name, res.total_matches, res.training_level, res.medizin_level,
            round(_avg(res.pre_match_starter), 2),
            round(_avg(res.min_freshness_starter), 2),
            *[round(_avg(res.starter_snap[d]), 2) for d in _SNAPSHOT_DAYS],
            round(_avg(res.below80_at_match), 2),
            round(_avg(res.below70_at_match), 2),
            round(_avg(res.below60_at_match), 2),
            round(_avg(res.injury_total), 2),
            round(_std(res.injury_total), 2),
            round(_avg(res.injury_days_total), 2),
            round(_avg(res.inj_by_type['Leicht']), 2),
            round(_avg(res.inj_by_type['Mittel']), 2),
            round(_avg(res.inj_by_type['Schwer']), 2),
            pos_l.get('TW', ''), pos_l.get('IV', ''), pos_l.get('LV', ''),
            pos_l.get('RV', ''), pos_l.get('DM', ''), pos_l.get('ZM', ''),
            pos_l.get('LM', ''), pos_l.get('RM', ''), pos_l.get('ST', ''),
        ])
    return buf.getvalue()


# ── Django-Command ─────────────────────────────────────────────────────────────

class Command(BaseCommand):
    help = 'Frische-Balancing-Report: V1-Belastungsszenarien simulieren (keine DB-Writes)'

    def add_arguments(self, parser):
        parser.add_argument('--days',   type=int,   default=90,
                            help='Simulationsdauer in Tagen (Standard: 90)')
        parser.add_argument('--runs',   type=int,   default=300,
                            help='Monte-Carlo-Läufe pro Szenario (Standard: 300)')
        parser.add_argument('--seed',   type=int,   default=42,
                            help='Zufalls-Seed (Standard: 42)')
        parser.add_argument('--fatigue', type=float, default=1.0,
                            help='Taktik-fatigue_cost (Standard: 1.0 = neutral)')
        parser.add_argument('--export', choices=['json', 'csv'], default=None,
                            help='Export-Format: json oder csv')
        parser.add_argument('--output', type=str, default=None,
                            help='Ausgabedatei (Standard: freshness_report.{json|csv})')

    def handle(self, *args, **options):
        days    = options['days']
        runs    = options['runs']
        seed    = options['seed']
        fatigue = options['fatigue']
        exp_fmt = options['export']
        out_f   = options['output']

        self.stdout.write(self.style.SUCCESS(
            f'\n{"═" * 74}\n'
            f'  FRISCHE-BALANCING-REPORT  V1\n'
            f'  {runs} Simulationen  │  Seed={seed}  │  {days} Tage  │  fatigue={fatigue}\n'
            f'{"═" * 74}'
        ))

        all_results: list[ScenarioResult] = []
        all_schedules: dict[str, list[int]] = {}

        # ── Szenarien 1–3 ──────────────────────────────────────────────────────
        scenarios = [
            (1, 'S1', 'Ein Wettbewerb   — Spiel alle 3 Tage (30 Sp./90d)'),
            (2, 'S2', 'Zwei Wettbewerbe — Liga·Frei·Pokal·Liga·Frei·Frei (6-Tage-Zyklus, ~45 Sp.)'),
            (3, 'S3', 'Drei Wettbewerbe — Liga·Frei·Pokal·Liga·Frei·CL  (6-Tage-Zyklus, ~60 Sp.)'),
        ]
        results_s123 = []
        for sid, sname, sdesc in scenarios:
            self.stdout.write(f'  Simuliere {sname} ({runs}×) …')
            sched = _build_schedule(days, sid)
            all_schedules[sname] = sched
            res = _run_scenario(
                name=sname, description=sdesc, scenario_id=sid,
                training_level=1, medizin_level=1,
                days=days, fatigue_cost=fatigue, runs=runs, seed=seed,
            )
            results_s123.append(res)
            all_results.append(res)
            _print_scenario(res, sched, self.stdout)

        # ── Szenario 4: Trainingsgelände S0–S3 ────────────────────────────────
        self.stdout.write(f'\n  Simuliere Training-Kontrollgruppe S0–S3 ({runs}× je) …')
        t_results = []
        for t_lvl in range(4):
            sched = _build_schedule(days, 2)   # Basis = S2 (realistischer Stress)
            res = _run_scenario(
                name=f'T-S{t_lvl}',
                description=f'Trainingsgelände S{t_lvl}, Medizin S1',
                scenario_id=2, training_level=t_lvl, medizin_level=1,
                days=days, fatigue_cost=fatigue, runs=runs, seed=seed,
            )
            t_results.append(res)
            all_results.append(res)
        _print_comparison_table(
            'SZENARIO 4 — Trainingsgelände S0–S3  (Basis: S2, Zwei Wettbewerbe)',
            t_results, 'training_level',
            [_build_schedule(days, 2)] * 4, self.stdout,
        )

        # ── Szenario 5: Medizin S0–S3 ─────────────────────────────────────────
        self.stdout.write(f'\n  Simuliere Medizin-Kontrollgruppe S0–S3 ({runs}× je) …')
        m_results = []
        for m_lvl in range(4):
            res = _run_scenario(
                name=f'M-S{m_lvl}',
                description=f'Training S1, Medizin S{m_lvl}',
                scenario_id=2, training_level=1, medizin_level=m_lvl,
                days=days, fatigue_cost=fatigue, runs=runs, seed=seed,
            )
            m_results.append(res)
            all_results.append(res)
        _print_comparison_table(
            'SZENARIO 5 — Medizin S0–S3  (Basis: S2, Zwei Wettbewerbe)',
            m_results, 'medizin_level',
            [_build_schedule(days, 2)] * 4, self.stdout,
        )

        _print_training_display_legend(self.stdout)
        _print_summary(results_s123, self.stdout)

        # ── Export ─────────────────────────────────────────────────────────────
        if exp_fmt:
            fname = out_f or f'freshness_report.{exp_fmt}'
            if exp_fmt == 'json':
                with open(fname, 'w', encoding='utf-8') as f:
                    json.dump(_to_dict(all_results), f, ensure_ascii=False, indent=2)
            else:
                with open(fname, 'w', encoding='utf-8', newline='') as f:
                    f.write(_to_csv(all_results))
            self.stdout.write(self.style.SUCCESS(f'\n  → Export: {fname}'))

        self.stdout.write(self.style.SUCCESS('\n  Fertig.\n'))
