"""
balance_matrix.py — Websoccer Multi-Szenario Balancing-Matrix
=============================================================
Standalone, Django-frei.
Testet 8 Teamstärke-Szenarien × 8 Taktik-Varianten = 64 Batches.

Usage:
    python balance_matrix.py [n_sims] [fixture]
    python balance_matrix.py 5000
    python balance_matrix.py 10000
"""
from __future__ import annotations

import argparse
import csv
import json
import time
from copy import deepcopy
from pathlib import Path

from batch_tactic_tests import (
    run_batch,
    _without_conditions,
    _with_conditions,
    _conditions,
    print_result,
)
from run_match import simulate_match_minutes
from tactic_compiler import compile_tactic


# ══════════════════════════════════════════════════════════════════════════════
# Taktik-Hilfsfunktionen
# ══════════════════════════════════════════════════════════════════════════════

def neutral_tactic() -> dict:
    """Standard-Taktik ohne Bedingungen — Referenz-Baseline."""
    return {
        "attack_focus": "ausgewogen",
        "buildup": {
            "defense": "standard",
            "defense_height": "standard",
            "midfield": "standard",
            "attack": "standard",
            "tempo": 50,
        },
        "defending": {
            "deckung": "hybrid",
            "zweikampf": "normal",
            "breite": "standard",
            "umschalten": "ausgewogen",
        },
        "pressing": {
            "defense": "normal",
            "midfield": "normal",
            "attack": "normal",
        },
        "pressing_triggers": {
            "ballverlust": False,
            "langer_ball": False,
            "schlechter_pass": False,
            "torwart_druck": False,
        },
        "conditions": [],
        "first_half":  {"orientation": 50, "defense": "standard",
                        "midfield": "standard", "attack": "standard", "effort": "normal"},
        "second_half": {"orientation": 50, "defense": "standard",
                        "midfield": "standard", "attack": "standard", "effort": "normal"},
    }


def compact_tactic() -> dict:
    """Defensiv-Kompakt-Taktik (Außenseiter / Szenario 8 Auswärts)."""
    t = neutral_tactic()
    t["pressing"]["defense"]  = "passiv"
    t["pressing"]["midfield"] = "passiv"
    t["pressing"]["attack"]   = "passiv"
    t["defending"]["zweikampf"]  = "hart"
    t["defending"]["umschalten"] = "defensiv"
    t["buildup"]["tempo"] = 20
    t["first_half"]["orientation"]  = 25
    t["second_half"]["orientation"] = 25
    t["_active_plan"] = "kompakt_sichern"
    return t


# ══════════════════════════════════════════════════════════════════════════════
# Team-Fabrik
# ══════════════════════════════════════════════════════════════════════════════

_LINEUP_SCHEMA: list[tuple[str, str]] = [
    ("TW",  "goalkeeper"),
    ("LV",  "defense"),
    ("IV",  "defense"),
    ("IV",  "defense"),
    ("RV",  "defense"),
    ("DM",  "defensive_midfield"),
    ("DM",  "defensive_midfield"),
    ("OM",  "offensive_midfield"),
    ("LF",  "attack"),
    ("ST",  "attack"),
    ("RF",  "attack"),
]
_BENCH_SCHEMA: list[tuple[str, str]] = [
    ("ST",  "attack"),
    ("DM",  "defensive_midfield"),
    ("LV",  "defense"),
    ("IV",  "defense"),
]


def make_team(
    name: str,
    avg_str: float,
    team_id: int = 99,
    tactic: dict | None = None,
    teamwork: int = 70,
) -> dict:
    """Generiert ein künstliches Team mit gleichmäßiger Stärke (4-2-3-1)."""
    tactic = tactic or neutral_tactic()
    players: list[dict] = []
    lineup: list[dict] = []
    pid = team_id * 1000 + 1
    pos_counter: dict[str, int] = {}

    for pos, group in _LINEUP_SCHEMA:
        pos_counter[pos] = pos_counter.get(pos, 0) + 1
        slot = f"{pos}-{pos_counter[pos]}"
        players.append({
            "id": pid,
            "name": f"{name[:4]}_{pos}_{pos_counter[pos]}",
            "main_positions": [pos],
            "secondary_positions": [],
            "age": 25,
            "base_strength": float(avg_str),
            "final_strength": float(avg_str),
            "freshness": 100.0,
            "form_modifier": 0.0,
            "teamwork": teamwork,
            "injury_days": 0,
            "suspension_matches": 0,
            "in_lineup": True,
        })
        lineup.append({"slot": slot, "position": pos, "group": group, "player_id": pid})
        pid += 1

    for pos, group in _BENCH_SCHEMA:
        players.append({
            "id": pid,
            "name": f"{name[:4]}_{pos}_sub",
            "main_positions": [pos],
            "secondary_positions": [],
            "age": 25,
            "base_strength": float(max(100, avg_str - 10)),
            "final_strength": float(max(100, avg_str - 10)),
            "freshness": 100.0,
            "form_modifier": 0.0,
            "teamwork": teamwork,
            "injury_days": 0,
            "suspension_matches": 0,
            "in_lineup": False,
        })
        pid += 1

    return {
        "team": {"id": team_id, "name": name, "fm_inside_id": team_id},
        "formation_raw": "4-2-3-1",
        "players": players,
        "lineup": lineup,
        "tactic": tactic,
    }


# ══════════════════════════════════════════════════════════════════════════════
# 8 Taktik-Varianten für die Heim-Seite
# ══════════════════════════════════════════════════════════════════════════════

def build_matrix_variants(base_tactic: dict) -> list[tuple[str, dict]]:
    """Erzeugt 8 HOME-Taktik-Varianten für die Balancing-Matrix."""
    b = _without_conditions(base_tactic)

    full_plan = _with_conditions(
        deepcopy(b),
        _conditions(
            (85, "rueckstand",  "schlussangriff"),
            (60, "rueckstand",  "aggressiv_risiko"),
            (80, "fuehrung",    "zeitspiel"),
        ),
    )

    def _mod(changes: dict) -> dict:
        t = deepcopy(b)
        for path, val in changes.items():
            parts = path.split(".")
            d = t
            for p in parts[:-1]:
                d = d.setdefault(p, {})
            d[parts[-1]] = val
        return t

    return [
        ("baseline_no_conditions",    b),
        ("conditions_full_matchplan", full_plan),
        ("high_press",                _mod({
            "pressing.defense":  "hoch",
            "pressing.midfield": "hoch",
            "pressing.attack":   "hoch",
        })),
        ("low_press",                 _mod({
            "pressing.defense":  "passiv",
            "pressing.midfield": "passiv",
            "pressing.attack":   "passiv",
        })),
        ("fluegelspiel",              _mod({"attack_focus": "fluegelspiel"})),
        ("durch_mitte",               _mod({"attack_focus": "durch_mitte"})),
        ("zeitspiel_like",            {**deepcopy(b), "_active_plan": "zeitspiel"}),
        ("schlussangriff_like",       {**deepcopy(b), "_active_plan": "schlussangriff"}),
    ]


# ══════════════════════════════════════════════════════════════════════════════
# 8 Szenarien
# ══════════════════════════════════════════════════════════════════════════════

def build_scenarios(
    fixture: dict,
    mid_team: dict,
    low_team: dict,
    low_compact: dict,
) -> list[dict]:
    """Definiert 8 Teamstärke-Szenarien. Away-Taktik ist immer die Seite, gegen die getestet wird."""
    return [
        {
            "id":          "equal_top_vs_equal_top",
            "label":       "Bayern vs Bayern",
            "home":        fixture,
            "away":        fixture,
            "away_tactic": _without_conditions(fixture["tactic"]),
        },
        {
            "id":          "equal_mid_vs_equal_mid",
            "label":       "Mid(150) vs Mid(150)",
            "home":        mid_team,
            "away":        mid_team,
            "away_tactic": neutral_tactic(),
        },
        {
            "id":          "equal_low_vs_equal_low",
            "label":       "Low(130) vs Low(130)",
            "home":        low_team,
            "away":        low_team,
            "away_tactic": neutral_tactic(),
        },
        {
            "id":          "top_vs_mid",
            "label":       "Bayern vs Mid(150)",
            "home":        fixture,
            "away":        mid_team,
            "away_tactic": neutral_tactic(),
        },
        {
            "id":          "mid_vs_top",
            "label":       "Mid(150) vs Bayern",
            "home":        mid_team,
            "away":        fixture,
            "away_tactic": _without_conditions(fixture["tactic"]),
        },
        {
            "id":          "top_vs_low",
            "label":       "Bayern vs Low(130)",
            "home":        fixture,
            "away":        low_team,
            "away_tactic": neutral_tactic(),
        },
        {
            "id":          "low_vs_top_defensive",
            "label":       "Low(130) vs Bayern — Außenseiter defensiv",
            "home":        low_team,
            "away":        fixture,
            "away_tactic": _without_conditions(fixture["tactic"]),
        },
        {
            "id":          "top_attacking_vs_low_compact",
            "label":       "Bayern vs Low(130) kompakt",
            "home":        fixture,
            "away":        low_compact,
            "away_tactic": compact_tactic(),
        },
    ]


# ══════════════════════════════════════════════════════════════════════════════
# CSV-Export
# ══════════════════════════════════════════════════════════════════════════════

def _flat_result(entry: dict) -> dict:
    r = entry["result"]
    row: dict = {
        "scenario_id":    entry["scenario_id"],
        "scenario_label": entry["scenario_label"],
        "home_team":      entry["home_team"],
        "away_team":      entry["away_team"],
        "variant":        r["name"],
        "n":              r["n"],
        "home_win_pct":   round(r["home_win_pct"], 2),
        "draw_pct":       round(r["draw_pct"], 2),
        "away_win_pct":   round(r["away_win_pct"], 2),
        "avg_home_goals": round(r["avg_home_goals"], 3),
        "avg_away_goals": round(r["avg_away_goals"], 3),
        "avg_total_goals": round(r["avg_total_goals"], 3),
        "avg_home_xg":    round(r["avg_home_xg"], 4),
        "avg_away_xg":    round(r["avg_away_xg"], 4),
        "avg_home_shots": round(r["avg_home_shots"], 2),
        "avg_away_shots": round(r["avg_away_shots"], 2),
        "avg_home_possession": round(r["avg_home_possession"], 1),
        "avg_away_possession": round(r["avg_away_possession"], 1),
        "avg_home_fouls":  round(r["avg_home_fouls"], 2),
        "avg_home_yellow": round(r["avg_home_yellow"], 3),
        "avg_home_red":    round(r.get("avg_home_red", 0), 4),
        "avg_away_fouls":  round(r["avg_away_fouls"], 2),
        "avg_away_yellow": round(r["avg_away_yellow"], 3),
        "avg_home_fatigue_cost": round(r["avg_home_fatigue_cost"], 4),
        "avg_plan_activations":  round(r["avg_plan_activations"], 3),
        "lead_after_80_count":      r["lead_after_80_count"],
        "leads_protected_after_80": r["leads_protected_after_80"],
        "leads_lost_after_80":      r["leads_lost_after_80"],
        "lead_protected_pct": round(
            r["leads_protected_after_80"] / r["lead_after_80_count"] * 100
            if r["lead_after_80_count"] else 0, 2),
        "lead_lost_pct": round(
            r["leads_lost_after_80"] / r["lead_after_80_count"] * 100
            if r["lead_after_80_count"] else 0, 2),
        "trailed_at_60_count": r["trailed_at_60_count"],
        "comeback_wins":       r["comeback_wins"],
        "comeback_draws":      r["comeback_draws"],
        "comeback_win_pct": round(
            r["comeback_wins"] / r["trailed_at_60_count"] * 100
            if r["trailed_at_60_count"] else 0, 2),
        "comeback_draw_pct": round(
            r["comeback_draws"] / r["trailed_at_60_count"] * 100
            if r["trailed_at_60_count"] else 0, 2),
    }
    for plan, pss in (r.get("plan_segment_stats") or {}).items():
        p = plan[:8]
        row[f"{p}__xgf_p90"]   = pss.get("xg_for_per_90", 0)
        row[f"{p}__xga_p90"]   = pss.get("xg_against_per_90", 0)
        row[f"{p}__gf_p90"]    = pss.get("goals_for_per_90", 0)
        row[f"{p}__ga_p90"]    = pss.get("goals_against_per_90", 0)
        row[f"{p}__sh_p90"]    = pss.get("shots_for_per_90", 0)
        row[f"{p}__fouls_p90"] = pss.get("fouls_per_90", 0)
        row[f"{p}__gelb_p90"]  = pss.get("yellow_per_90", 0)
        row[f"{p}__fatigue"]   = pss.get("avg_fatigue_cost", 0)
        row[f"{p}__min"]       = pss.get("minutes", 0)
    return row


def write_csv(all_results: list[dict], out_path: Path) -> None:
    rows = [_flat_result(e) for e in all_results]
    if not rows:
        return
    all_keys: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for k in row:
            if k not in seen:
                all_keys.append(k)
                seen.add(k)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=all_keys, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


# ══════════════════════════════════════════════════════════════════════════════
# Zusammenfassungs-Tabelle (Konsole)
# ══════════════════════════════════════════════════════════════════════════════

def print_summary(all_results: list[dict]) -> None:
    print(f"\n{'═' * 110}")
    print("ZUSAMMENFASSUNG — Heimsieg% / Remis% / Auswärtssieg% / xGF / xGA / Fatigue / Führung-gehalten%")
    print(f"{'═' * 110}")
    last_scen = None
    for e in all_results:
        scen = e["scenario_id"]
        if scen != last_scen:
            print(f"\n  [{scen}] {e['scenario_label']}  "
                  f"({e['home_team']} vs {e['away_team']})")
            print(f"  {'Variante':<30} {'Sieg%':>6} {'Remis%':>7} {'Ausw%':>6} "
                  f"{'xGF':>6} {'xGA':>6} {'Tore':>5} {'Geg':>5} "
                  f"{'Fat':>6} {'Führ>80':>8} {'gesch%':>7}")
            print(f"  {'-'*104}")
            last_scen = scen
        r = e["result"]
        la = r["lead_after_80_count"]
        lp_pct = r["leads_protected_after_80"] / la * 100 if la else 0
        print(f"  {r['name']:<30} "
              f"{r['home_win_pct']:>6.1f} {r['draw_pct']:>7.1f} {r['away_win_pct']:>6.1f} "
              f"{r['avg_home_xg']:>6.3f} {r['avg_away_xg']:>6.3f} "
              f"{r['avg_home_goals']:>5.2f} {r['avg_away_goals']:>5.2f} "
              f"{r['avg_home_fatigue_cost']:>6.4f} "
              f"{la:>8,d} {lp_pct:>7.1f}")


# ══════════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    parser = argparse.ArgumentParser(description="Websoccer Balancing Matrix")
    parser.add_argument("n_sims",  nargs="?", type=int, default=5000,
                        help="Simulationen pro Variante (default: 5000)")
    parser.add_argument("fixture", nargs="?", default="bayern_fixture.json",
                        help="Fixture-JSON (default: bayern_fixture.json)")
    parser.add_argument("--out",   default="balance_matrix_results.json",
                        help="JSON-Ausgabedatei")
    args = parser.parse_args()

    fixture_path = Path(args.fixture)
    with fixture_path.open(encoding="utf-8") as f:
        fixture = json.load(f)

    mid_team    = make_team("Mid-Team (150)",    avg_str=150.0, team_id=10, teamwork=70)
    low_team    = make_team("Low-Team (130)",    avg_str=130.0, team_id=11, teamwork=65)
    low_compact = make_team("Low-Kompakt (130)", avg_str=130.0, team_id=12,
                            tactic=compact_tactic(), teamwork=65)

    scenarios  = build_scenarios(fixture, mid_team, low_team, low_compact)
    n_variants = 8
    total_sims = len(scenarios) * n_variants * args.n_sims

    print(f"{'═' * 70}")
    print(f"  Balance-Matrix — {args.n_sims:,} Sims × {n_variants} Varianten × {len(scenarios)} Szenarien")
    print(f"  Gesamt: {total_sims:,} Simulationen")
    print(f"  Bayern: {fixture['team']['name']}")
    print(f"  Mid-Team: 150 Durchschnittsstärke  |  Low-Team: 130")
    print(f"{'═' * 70}\n")

    all_results: list[dict] = []
    t0 = time.perf_counter()

    for scen in scenarios:
        home         = scen["home"]
        away         = scen["away"]
        away_tactic  = scen["away_tactic"]
        variants     = build_matrix_variants(home["tactic"])

        print(f"\n{'═' * 70}")
        print(f"  Szenario: {scen['id']}")
        print(f"  {scen['label']}")
        print(f"  Heim: {home['team']['name']}  vs  Auswärts: {away['team']['name']}")
        print(f"{'═' * 70}")

        for variant_label, home_tactic in variants:
            r = run_batch(
                home, away,
                home_tactic, away_tactic,
                args.n_sims,
                variant_label,
                simulate_match_minutes,
            )
            print_result(r)
            all_results.append({
                "scenario_id":    scen["id"],
                "scenario_label": scen["label"],
                "home_team":      home["team"]["name"],
                "away_team":      away["team"]["name"],
                "variant":        variant_label,
                "result":         r,
            })

    elapsed = time.perf_counter() - t0

    print_summary(all_results)

    json_path = Path(args.out)
    payload = {
        "n_per_variant":        args.n_sims,
        "total_simulations":    total_sims,
        "elapsed_seconds":      round(elapsed, 3),
        "scenario_count":       len(scenarios),
        "variants_per_scenario": n_variants,
        "results":              all_results,
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    csv_path = json_path.with_suffix(".csv")
    write_csv(all_results, csv_path)

    print(f"\n{'═' * 70}")
    print(f"Fertig: {total_sims:,} Simulationen in {elapsed:.1f}s")
    print(f"JSON:  {json_path}")
    print(f"CSV:   {csv_path}")


if __name__ == "__main__":
    main()
