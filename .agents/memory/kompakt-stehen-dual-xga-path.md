---
name: kompakt_stehen dual xGA path + Fix
description: kompakt_stehen hat zwei xGA-Reduktionspfade; defense_delta-Pfad war compiler-unsichtbar und erzeugte Alarm-Kombos. Fix: abnehmende Kompaktheit. Stand: APPLIED 2026-06-15.
---

## Rule
kompakt_stehen wirkt über zwei getrennte xGA-Pfade. Der Compiler zeigt seit Fix
beide Pfade explizit (`effective_total_xga_mult`). Bei künftigen Balancing-Tests
immer `effective_total_xga_mult` als Referenz nehmen, nicht nur `xg_against`.

## Zwei Pfade für xGA-Reduktion

| Pfad | Mechanismus | Compiler-sichtbar? | Größe |
|---|---|---|---|
| A — `xg_against_delta` | Direkter xGA-Multiplikator aus Linienoptionen | ✅ Ja | variabel |
| B — `defense_delta → line_multipliers["defense"]` | Stärke-Boost → Engine reduziert xGA via Exponent 1.25 | Jetzt sichtbar via `effective_xga_from_defense` | ~−0.028 bei full compact |

## Fix: Abnehmende Kompaktheit (2026-06-15)
`compact_defense_bonus` in `tactic_compiler.py` skaliert jetzt mit `_aggressive_lines`:

```
if _aggressive_lines == 0: _compact_bonus = 0.030
if _aggressive_lines == 1: _compact_bonus = 0.0225
if _aggressive_lines == 2: _compact_bonus = 0.015
```

`_aggressive_lines` = Anzahl aktiver offensiver Linien:
- Mittelfeld in {"nachruecken", "offensiv_besetzen"} → +1
- Angriff in {"abwehrkette_binden", "strafraum_besetzen"} → +1

## Neue Debug-Keys im Compiler (seit Fix)
- `compact_defense_bonus` — tatsächlich angewendeter Bonus (0.015 / 0.0225 / 0.030)
- `compact_aggressive_lines` — Anzahl offensiver Linien (0, 1, 2)
- `line_defense_delta` — gesamter defense_delta
- `line_defense_multiplier` — 1.0 + defense_delta
- `effective_xga_from_defense` — def_mult^(-1.25), Pfad-B-Effekt
- `effective_total_xga_mult` — Pfad A × Pfad B kombiniert

## Validierung Post-Fix (n=10k gespiegelt)
| Kombo | Pre-Fix PPG-D | Pre-Fix Flag | Post-Fix PPG-D | Post-Fix xGD-D | Flag |
|---|---|---|---|---|---|
| kompakt/offensiv/abwehrkette | +0.065 | [ALARM] | +0.027 | +0.044 | ok |
| kompakt/nach/strafraum | +0.044 | [VERD] | +0.019 | +0.050 | ok |
| kompakt/absichern/strafraum | +0.043 | [VERD] | +0.032 | +0.059 | ok |
| kompakt/std/std (Control) | +0.035 | ok | unverändert | — | ok |

## Control-Test (Case A vs B — 2026-06-15)
kompakt/std/std vs STD×3 (n=20k): PPG-D=+0.034, xGD-D=+0.036
→ **Case B bestätigt**: kompakt_stehen allein fällt knapp unter Case-A-Schwelle (PPG>0.03 ✓, xGD>0.04 ✗).
→ Es ist ein reiner Interaktionseffekt mit offensiven Linienrollen.

## Why
kompakt_stehen's `defense_delta=+0.03` war vor den neuen Linienoptionen implementiert.
Die Linienoptionen wurden ohne Berücksichtigung von Pfad B balanciert.
In Kombination stapelten sich beide Effekte unsichtbar.

## How to Apply
- Wenn kompakt_stehen mit 2 offensiven Linien → `effective_xga_from_defense ≈ 0.982` (kein signifikanter Vorteil mehr).
- Künftige Kompakt-Optionen oder neue offensive Linien: immer `_aggressive_lines`-Logik prüfen.
- Match Engine V2 Freeze (2026-06-12) gilt weiterhin für match_engine.py; tactic_compiler.py-Fixes sind erlaubt.
