---
name: Match Engine V2 Balancing Freeze
description: Formaler Freeze-Status der Match Engine V2 — welche Werte eingefroren sind und was die Freigabebedingung für Änderungen ist.
---

## Regel
**KEINE Engine-Werte ändern** ohne harte Evidenz aus Multi-Saisons-Daten. Jede Änderung an Konstanten, Formeln oder Modifikatoren erfordert explizite Nutzer-Freigabe.

**Why:** 50-Saisons-Baseline (15.300 Spiele, 0 Fehler) wurde am 2026-06-12 abgenommen. Alle Kernmetriken im Zielbereich. Änderungen ohne Datengrundlage würden den stabilen Stand destabilisieren.

## Eingefrorene Komponenten (Stand 2026-06-12)

| Komponente | Datei | Kern-Konstante |
|---|---|---|
| strength_exp | match_engine.py | `ratio ** 1.25` |
| xG-Formel | match_engine.py | `1.36 * (ratio ** 1.25)` |
| Home Advantage V1 | match_engine.py | HOME_XG_MULTIPLIER |
| Matchplan V2 | tactic_compiler.py | CONDITION_PLAN_MODIFIERS |
| Tactic Compiler | tactic_compiler.py | line_multipliers, zone_factors |
| Minutes Simulation | match_engine.py | _simulate_match_minutes() |
| Conditions / Triggers | tactic_compiler.py | Trigger-Budget = 3 |
| final_strength | models.py | PlayerStrengthProfile.final_strength |
| Zone Factors | match_engine.py | ±7% Zonen-Modifikator |
| Pressing/Coherence/Fatigue | match_engine.py | Stats-Output-Felder |

## Akzeptierte 50-Saisons-Baseline

| Metrik | Wert | Zielbereich |
|---|---|---|
| Ø Tore/Spiel | 2.727 | 2.6–3.0 ✅ |
| Heimsiege | 39.0 % | 36–42 % ✅ |
| Remis | 25.1 % | 22–28 % ✅ |
| Auswärtssiege | 35.9 % | 32–38 % ✅ |
| Favoritensiege | 58.8 % | 55–65 % ✅ |
| r(Stärke-Rang, Ø Rang) | 0.920 | >0.85 ✅ |
| r(xGD, Pkt) | 0.622 | 0.55–0.85 ✅ |
| Fehler | 0 | 0 ✅ |

## Freigabebedingung für Änderungen
Änderungen nur mit:
1. Konkreter Abweichung aus ≥50-Saisons-Daten (z.B. Ø Tore > 3.1 über 3 unabhängige Runs)
2. Expliziter Nutzer-Freigabe im Chat
3. Danach erneuter 50-Saisons-Validierung

## How to apply
- Wird eine Konstante in `match_engine.py` oder `tactic_compiler.py` geändert: STOP, diesen Eintrag prüfen.
- `fast_season --seasons 50` ist das kanonische Validierungswerkzeug.
- JSON-Baseline: `/tmp/fast_season_50x_20260612_095745.json`
