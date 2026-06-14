#!/usr/bin/env python3
"""diff_regression.py — Vergleicht zwei seeds_stability.json und alarmiert bei >5% Änderung.

Aufruf:
  python scripts/diff_regression.py <alte.json> <neue.json>
  python scripts/diff_regression.py              # automatisch die zwei neuesten Runs

Exit-Code:
  0 — alle Metriken stabil (≤5% Änderung)
  1 — mindestens eine Metrik hat sich um >5% verändert
  2 — Fehler (Datei nicht gefunden, ungültiges Format, etc.)
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# ── Konfiguration ─────────────────────────────────────────────────────────────

HISTORY_DIR = Path(".local/regression_history")
ALARM_THRESHOLD = 0.05  # 5 %

# Schlüsselmetriken, die im Diff geprüft werden.
# Schlüssel exakt wie in seeds_stability.json (regression_sim.py → _print_stability_table).
KEY_METRICS = [
    "goals_per_game",
    "home_pct",
    "draw_pct",
    "away_pct",
    "yellow_per_game",
    "inj_per_game",
    "spearman",
    "pearson_xgd",
]

# Mindestanzahl Metriken, die in beiden Dateien vorhanden sein müssen.
# Sind weniger als diese Zahl vergleichbar, schlägt der Diff mit Exit 2 fehl.
MIN_COMPARED = 4


# ── Hilfsfunktionen ───────────────────────────────────────────────────────────

def _find_two_latest() -> tuple[Path, Path]:
    """Gibt die zwei neuesten Runs (als Pfad zu seeds_stability.json) zurück."""
    if not HISTORY_DIR.is_dir():
        print(f"FEHLER: History-Verzeichnis nicht gefunden: {HISTORY_DIR}", file=sys.stderr)
        sys.exit(2)

    runs = sorted(
        [d for d in HISTORY_DIR.iterdir() if d.is_dir()],
        key=lambda d: d.name,
        reverse=True,
    )
    stability_runs = [d / "seeds_stability.json" for d in runs if (d / "seeds_stability.json").exists()]

    if len(stability_runs) < 2:
        print(
            f"FEHLER: Weniger als zwei Runs mit seeds_stability.json in {HISTORY_DIR}.",
            file=sys.stderr,
        )
        sys.exit(2)

    return stability_runs[1], stability_runs[0]  # alt, neu


def _load(path: Path) -> dict:
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"FEHLER: Datei nicht gefunden: {path}", file=sys.stderr)
        sys.exit(2)
    except json.JSONDecodeError as e:
        print(f"FEHLER: Ungültiges JSON in {path}: {e}", file=sys.stderr)
        sys.exit(2)


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    n = len(s)
    mid = n // 2
    return (s[mid - 1] + s[mid]) / 2 if n % 2 == 0 else s[mid]


def _metric_median(data: dict, key: str) -> float | None:
    """Median aus der metrics-Zeitreihe, oder None wenn Metrik nicht vorhanden."""
    series = data.get("metrics", {}).get(key)
    if series and isinstance(series, list):
        return _median([float(v) for v in series])
    return None


def _pct_change(old: float, new: float) -> float:
    if old == 0.0:
        return 0.0 if new == 0.0 else float("inf")
    return abs(new - old) / abs(old)


# ── Hauptlogik ────────────────────────────────────────────────────────────────

def compare(old_path: Path, new_path: Path) -> int:
    """Vergleicht zwei seeds_stability.json. Gibt Exit-Code zurück."""
    old_data = _load(old_path)
    new_data = _load(new_path)

    old_label = old_path.parent.name
    new_label = new_path.parent.name

    # ── Seeds-Infos ───────────────────────────────────────────────────────────
    old_seeds = old_data.get("seeds", [])
    new_seeds = new_data.get("seeds", [])

    print("=" * 64)
    print(" Regressions-Diff")
    print(f"  Alt:  {old_label}  (Seeds: {old_seeds})")
    print(f"  Neu:  {new_label}  (Seeds: {new_seeds})")
    print("=" * 64)
    print()

    # ── Metriken-Vergleich ────────────────────────────────────────────────────
    header = f"  {'Metrik':<22} {'Alt':>10} {'Neu':>10} {'Δ%':>8}  Status"
    print(header)
    print("  " + "-" * 60)

    alarms: list[str] = []
    compared = 0

    for key in KEY_METRICS:
        old_val = _metric_median(old_data, key)
        new_val = _metric_median(new_data, key)

        if old_val is None and new_val is None:
            continue
        if old_val is None or new_val is None:
            print(f"  {key:<22} {'n/v':>10} {'n/v':>10} {'?':>8}  ⚠ Metrik fehlt in einem Lauf")
            alarms.append(f"{key}: Metrik fehlt in einem der Läufe")
            continue

        compared += 1
        pct = _pct_change(old_val, new_val)
        status = "✓" if pct <= ALARM_THRESHOLD else "⚠ ALARM"

        print(f"  {key:<22} {old_val:>10.5f} {new_val:>10.5f} {100*pct:>7.2f}%  {status}")

        if pct > ALARM_THRESHOLD:
            alarms.append(
                f"{key}: {old_val:.5f} → {new_val:.5f} "
                f"(Δ {100*pct:.2f}% > {100*ALARM_THRESHOLD:.0f}%)"
            )

    print()

    # ── Guard: zu wenige vergleichbare Metriken ───────────────────────────────
    if compared < MIN_COMPARED:
        print(
            f"FEHLER: Nur {compared} von {len(KEY_METRICS)} Schlüsselmetriken vergleichbar "
            f"(Minimum: {MIN_COMPARED}). Sind die Dateien gültige seeds_stability.json?",
            file=sys.stderr,
        )
        sys.exit(2)

    # ── Stabilitäts-Delta der neuen Seeds_stability ───────────────────────────
    new_stability = new_data.get("stability", {})
    unstable_new = [k for k, v in new_stability.items() if isinstance(v, dict) and not v.get("ok", True)]
    if unstable_new:
        print(f"  ⚠ Neue Datei: {len(unstable_new)} instabile Metrik(en) im Multi-Seed-Lauf:")
        for k in unstable_new:
            sd = new_stability[k]
            print(f"    • {k}: Δ={sd.get('delta_pct', '?'):.1f}%")
        print()

    # ── Zusammenfassung ───────────────────────────────────────────────────────
    print("=" * 64)
    if not alarms:
        print(f"  ✓ STABIL — alle {compared} Metriken ≤{100*ALARM_THRESHOLD:.0f}% Abweichung zwischen den Läufen.")
        if unstable_new:
            print(f"  (Hinweis: {len(unstable_new)} Metrik(en) im neuen Lauf selbst instabil — "
                  "normal bei wenigen Saisons.)")
        print("=" * 64)
        return 0
    else:
        print(f"  ⚠ REGRESSION ERKANNT — {len(alarms)} Alarm(e) zwischen den Läufen:")
        for msg in alarms:
            print(f"    • {msg}")
        print("=" * 64)
        return 1


# ── Entry-Point ───────────────────────────────────────────────────────────────

def main() -> None:
    argv = sys.argv[1:]

    if len(argv) == 0:
        old_path, new_path = _find_two_latest()
    elif len(argv) == 2:
        old_path = Path(argv[0])
        new_path = Path(argv[1])
    else:
        print(__doc__)
        sys.exit(2)

    exit_code = compare(old_path, new_path)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
