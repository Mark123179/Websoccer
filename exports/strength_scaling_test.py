"""
strength_scaling_test.py — Websoccer Stärke-Skalierungs-Experiment
==================================================================
Testet 4 Exponenten für das Stärkeverhältnis in der xG-Formel:
    base_xg = 1.36 * (own_off / opp_def) ** EXP

Gleichstarke Teams bleiben bei jedem Exponenten symmetrisch (ratio=1.0).
Je höher EXP, desto stärker kippen asymmetrische Partien zugunsten des
Favoriten.

Usage:
    python strength_scaling_test.py [n_sims] [fixture]
    python strength_scaling_test.py 5000
    python strength_scaling_test.py 5000 bayern_fixture.json

Ausgabe:
    strength_scaling_results.json
    strength_scaling_results.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from copy import deepcopy
from pathlib import Path
from typing import Optional

# ── Imports aus dem Sim-Paket ─────────────────────────────────────────────────
import run_match
from run_match import simulate_match_minutes, _clamp, _zone_factor
from batch_tactic_tests import run_batch, _without_conditions, _conditions, _with_conditions
from balance_matrix import (
    make_team,
    neutral_tactic,
    compact_tactic,
    build_scenarios,
)


# ══════════════════════════════════════════════════════════════════════════════
# Exponenten-Konfiguration
# ══════════════════════════════════════════════════════════════════════════════

EXPONENTS: list[tuple[str, float]] = [
    ("exp_1.00 (current)",  1.00),
    ("exp_1.15",            1.15),
    ("exp_1.25",            1.25),
    ("exp_1.35",            1.35),
]


# ══════════════════════════════════════════════════════════════════════════════
# Monkey-Patch-Fabrik
# ══════════════════════════════════════════════════════════════════════════════

def _make_expected_goals(exp: float):
    """
    Gibt eine patched _expected_goals-Funktion zurück, die das
    Stärkeverhältnis mit dem angegebenen Exponenten skaliert.
    Alle anderen Faktoren (Taktik-Multiplikatoren, Zone-Faktor, Clamp)
    bleiben identisch zur Originalformel.
    """
    def _patched(
        own_strength: dict,
        opp_strength: dict,
        own_compiled: Optional[dict] = None,
        opp_compiled: Optional[dict] = None,
        own_zone_strengths: Optional[dict] = None,
        opp_zone_strengths: Optional[dict] = None,
    ) -> float:
        own_off = (
            own_strength['overall'] * 0.45
            + own_strength['attack'] * 0.32
            + own_strength['midfield'] * 0.23
        )
        opp_def = (
            opp_strength['overall'] * 0.35
            + opp_strength['defense'] * 0.42
            + opp_strength['goalkeeper'] * 0.23
        )
        ratio = own_off / max(opp_def, 1.0)
        base_xg = 1.36 * (ratio ** exp)

        if own_compiled:
            base_xg *= own_compiled.get('xg_for', 1.0)
            base_xg *= own_compiled.get('shot_quality', 1.0)
            base_xg *= 0.85 + 0.15 * own_compiled.get('shot_volume', 1.0)
        if opp_compiled:
            base_xg *= opp_compiled.get('xg_against', 1.0)
        if own_compiled and own_zone_strengths and opp_zone_strengths:
            base_xg *= _zone_factor(own_compiled, own_zone_strengths, opp_zone_strengths)

        return _clamp(base_xg, 0.2, 4.5)

    _patched.__name__ = f"_expected_goals_exp{exp:.2f}"
    return _patched


def _patch(exp: float):
    """Setzt run_match._expected_goals auf den Patch mit dem Exponenten."""
    run_match._expected_goals = _make_expected_goals(exp)


def _restore_original():
    """Stellt die originale _expected_goals-Funktion wieder her."""
    run_match._expected_goals = _make_expected_goals(1.0)


# ══════════════════════════════════════════════════════════════════════════════
# Ausgewählte Test-Szenarien (die relevanten asymmetrischen + Sanity-Checks)
# ══════════════════════════════════════════════════════════════════════════════

SCENARIO_IDS = [
    "equal_top_vs_equal_top",       # Symmetrie-Sanity: beide ~50%
    "equal_mid_vs_equal_mid",       # Symmetrie-Sanity: Mid
    "top_vs_mid",                   # Favorit heim vs. Mittelfeld
    "mid_vs_top",                   # Außenseiter heim vs. Favorit
    "top_vs_low",                   # Favorit heim vs. Schwach
    "low_vs_top_defensive",         # Außenseiter heim vs. Favorit
    "top_attacking_vs_low_compact", # Favorit vs. kompaktes Low-Team
]


# ══════════════════════════════════════════════════════════════════════════════
# Ausgabe-Hilfsfunktionen
# ══════════════════════════════════════════════════════════════════════════════

def _scenario_short(sid: str) -> str:
    return {
        "equal_top_vs_equal_top":       "EQ_Top   ",
        "equal_mid_vs_equal_mid":       "EQ_Mid   ",
        "top_vs_mid":                   "Top→Mid  ",
        "mid_vs_top":                   "Mid→Top  ",
        "top_vs_low":                   "Top→Low  ",
        "low_vs_top_defensive":         "Low→Top  ",
        "top_attacking_vs_low_compact": "Top→LoCmpt",
    }.get(sid, sid[:10])


def print_comparison_table(all_results: list[dict]) -> None:
    """
    Gibt eine Vergleichstabelle aus:
    Zeilen = Szenarien, Spalten = Exponenten.
    Pro Zelle: H% / D% / A%  xGF xGA
    """
    # Gruppiere: {scenario_id: {exp_label: result}}
    by_scenario: dict[str, dict[str, dict]] = {}
    for entry in all_results:
        sid = entry["scenario_id"]
        exp = entry["exp_label"]
        if sid not in by_scenario:
            by_scenario[sid] = {}
        by_scenario[sid][exp] = entry["result"]

    exp_labels = [lbl for lbl, _ in EXPONENTS]
    col_w = 36

    # Header
    print()
    print("═" * (12 + col_w * len(exp_labels)))
    print(f"{'Szenario':<12}", end="")
    for lbl in exp_labels:
        print(f"  {lbl:<{col_w - 2}}", end="")
    print()
    print(f"{'':12}", end="")
    for _ in exp_labels:
        print(f"  {'H%    D%    A%    xGF   xGA':<{col_w - 2}}", end="")
    print()
    print("─" * (12 + col_w * len(exp_labels)))

    for sid in SCENARIO_IDS:
        if sid not in by_scenario:
            continue
        row_data = by_scenario[sid]
        short = _scenario_short(sid)
        print(f"{short:<12}", end="")
        for lbl in exp_labels:
            r = row_data.get(lbl)
            if r is None:
                print(f"  {'—':<{col_w - 2}}", end="")
            else:
                cell = (
                    f"{r['home_win_pct']:5.1f} "
                    f"{r['draw_pct']:5.1f} "
                    f"{r['away_win_pct']:5.1f}  "
                    f"{r['avg_home_xg']:.3f} "
                    f"{r['avg_away_xg']:.3f}"
                )
                print(f"  {cell:<{col_w - 2}}", end="")
        print()

    print("═" * (12 + col_w * len(exp_labels)))
    print()

    # Delta-Tabelle: wie verändert sich H% gegenüber exp_1.00?
    baseline_lbl = exp_labels[0]
    print("Delta H%-Gewinn gegenüber exp_1.00 (current):")
    print(f"{'Szenario':<12}", end="")
    for lbl in exp_labels[1:]:
        print(f"  {lbl:>{col_w - 2}}", end="")
    print()
    print("─" * (12 + (col_w) * (len(exp_labels) - 1)))
    for sid in SCENARIO_IDS:
        if sid not in by_scenario:
            continue
        row_data = by_scenario[sid]
        base = row_data.get(baseline_lbl)
        if not base:
            continue
        short = _scenario_short(sid)
        print(f"{short:<12}", end="")
        for lbl in exp_labels[1:]:
            r = row_data.get(lbl)
            if r is None:
                print(f"  {'—':>{col_w - 2}}", end="")
            else:
                delta = r['home_win_pct'] - base['home_win_pct']
                sign = "+" if delta >= 0 else ""
                print(f"  {sign}{delta:+.1f}%{'':{col_w - 8}}", end="")
        print()
    print()


# ══════════════════════════════════════════════════════════════════════════════
# CSV-Export
# ══════════════════════════════════════════════════════════════════════════════

def write_csv(all_results: list[dict], out_path: Path) -> None:
    if not all_results:
        return
    fieldnames = [
        "exp_label", "exp_value",
        "scenario_id", "scenario_label",
        "home_team", "away_team",
        "n",
        "home_win_pct", "draw_pct", "away_win_pct",
        "avg_home_goals", "avg_away_goals", "avg_total_goals",
        "avg_home_xg", "avg_away_xg",
        "avg_home_shots", "avg_away_shots",
        "avg_home_possession", "avg_away_possession",
        "avg_home_fouls", "avg_away_fouls",
        "avg_home_yellow", "avg_away_yellow",
        "avg_home_fatigue_cost",
        "lead_after_80_count", "leads_protected_after_80", "leads_lost_after_80",
        "lead_protected_pct", "lead_lost_pct",
        "trailed_at_60_count", "comeback_wins", "comeback_draws",
        "comeback_win_pct",
    ]

    rows = []
    for entry in all_results:
        r = entry["result"]
        la80 = r.get("lead_after_80_count", 0)
        t60  = r.get("trailed_at_60_count", 0)
        rows.append({
            "exp_label":        entry["exp_label"],
            "exp_value":        entry["exp_value"],
            "scenario_id":      entry["scenario_id"],
            "scenario_label":   entry["scenario_label"],
            "home_team":        entry["home_team"],
            "away_team":        entry["away_team"],
            "n":                r["n"],
            "home_win_pct":     round(r["home_win_pct"], 2),
            "draw_pct":         round(r["draw_pct"], 2),
            "away_win_pct":     round(r["away_win_pct"], 2),
            "avg_home_goals":   round(r["avg_home_goals"], 3),
            "avg_away_goals":   round(r["avg_away_goals"], 3),
            "avg_total_goals":  round(r["avg_total_goals"], 3),
            "avg_home_xg":      round(r["avg_home_xg"], 4),
            "avg_away_xg":      round(r["avg_away_xg"], 4),
            "avg_home_shots":   round(r["avg_home_shots"], 2),
            "avg_away_shots":   round(r["avg_away_shots"], 2),
            "avg_home_possession": round(r["avg_home_possession"], 1),
            "avg_away_possession": round(r["avg_away_possession"], 1),
            "avg_home_fouls":   round(r["avg_home_fouls"], 2),
            "avg_away_fouls":   round(r["avg_away_fouls"], 2),
            "avg_home_yellow":  round(r["avg_home_yellow"], 3),
            "avg_away_yellow":  round(r["avg_away_yellow"], 3),
            "avg_home_fatigue_cost": round(r["avg_home_fatigue_cost"], 4),
            "lead_after_80_count":      la80,
            "leads_protected_after_80": r.get("leads_protected_after_80", 0),
            "leads_lost_after_80":      r.get("leads_lost_after_80", 0),
            "lead_protected_pct": round(
                r.get("leads_protected_after_80", 0) / la80 * 100 if la80 else 0, 2),
            "lead_lost_pct": round(
                r.get("leads_lost_after_80", 0) / la80 * 100 if la80 else 0, 2),
            "trailed_at_60_count": t60,
            "comeback_wins":   r.get("comeback_wins", 0),
            "comeback_draws":  r.get("comeback_draws", 0),
            "comeback_win_pct": round(
                r.get("comeback_wins", 0) / t60 * 100 if t60 else 0, 2),
        })

    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"CSV gespeichert: {out_path}  ({len(rows)} Zeilen)")


# ══════════════════════════════════════════════════════════════════════════════
# Hauptprogramm
# ══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Stärke-Skalierungs-Experiment: 4 Exponenten × 7 Szenarien"
    )
    parser.add_argument("n_sims", nargs="?", type=int, default=1000,
                        help="Simulationen pro Batch (default: 1000, empfohlen: 5000)")
    parser.add_argument("fixture", nargs="?", default="bayern_fixture.json",
                        help="Pfad zur Fixture-JSON (default: bayern_fixture.json)")
    args = parser.parse_args()

    N      = args.n_sims
    fx_path = Path(args.fixture)
    if not fx_path.exists():
        sys.exit(f"Fixture nicht gefunden: {fx_path}")

    fixture = json.loads(fx_path.read_text())
    mid_team    = make_team("Mid-Team (150)",    avg_str=150.0, team_id=10)
    low_team    = make_team("Low-Team (130)",    avg_str=130.0, team_id=11)
    low_compact = make_team("Low-Kompakt (130)", avg_str=130.0, team_id=12, tactic=compact_tactic())
    all_scenarios = build_scenarios(fixture, mid_team, low_team, low_compact)

    # Nur die relevanten Szenarien
    scenarios = [s for s in all_scenarios if s["id"] in SCENARIO_IDS]

    total_batches = len(EXPONENTS) * len(scenarios)
    print(f"\nStärke-Skalierungs-Test")
    print(f"  Exponenten:  {[lbl for lbl, _ in EXPONENTS]}")
    print(f"  Szenarien:   {len(scenarios)}")
    print(f"  Sims/Batch:  {N:,}")
    print(f"  Batches ges: {total_batches}  ({total_batches * N:,} Sims)")
    print()

    all_results: list[dict] = []
    t0 = time.perf_counter()
    done = 0

    for exp_label, exp_val in EXPONENTS:
        _patch(exp_val)
        print(f"── {exp_label} ──────────────────────────────────────────")
        for scen in scenarios:
            home = scen["home"]
            away = scen["away"]
            # Taktik: baseline_no_conditions (kein Condition-Rauschen)
            ht = _without_conditions(deepcopy(home["tactic"]))
            at = scen["away_tactic"]

            r = run_batch(home, away, ht, at, N, "baseline_no_conditions", simulate_match_minutes)
            all_results.append({
                "exp_label":      exp_label,
                "exp_value":      exp_val,
                "scenario_id":    scen["id"],
                "scenario_label": scen["label"],
                "home_team":      home["team"]["name"],
                "away_team":      away["team"]["name"],
                "result":         r,
            })
            done += 1
            elapsed = time.perf_counter() - t0
            eta = elapsed / done * (total_batches - done) if done else 0
            print(
                f"  [{done:2d}/{total_batches}] {scen['id']:<35}  "
                f"H:{r['home_win_pct']:5.1f}% D:{r['draw_pct']:5.1f}% A:{r['away_win_pct']:5.1f}%  "
                f"xGF:{r['avg_home_xg']:.3f} xGA:{r['avg_away_xg']:.3f}  "
                f"ETA {eta:.0f}s"
            )
        print()

    _restore_original()

    total_elapsed = time.perf_counter() - t0
    print(f"Fertig in {total_elapsed:.1f}s  ({total_batches * N:,} Sims)")

    # Vergleichstabelle
    print_comparison_table(all_results)

    # JSON
    json_path = Path("strength_scaling_results.json")
    json_path.write_text(json.dumps({
        "exponents":       [{"label": lbl, "value": v} for lbl, v in EXPONENTS],
        "scenario_ids":    SCENARIO_IDS,
        "n_per_batch":     N,
        "total_sims":      total_batches * N,
        "elapsed_seconds": round(total_elapsed, 3),
        "results":         all_results,
    }, ensure_ascii=False, indent=2))
    print(f"JSON gespeichert: {json_path}")

    # CSV
    csv_path = Path("strength_scaling_results.csv")
    write_csv(all_results, csv_path)


if __name__ == "__main__":
    main()
