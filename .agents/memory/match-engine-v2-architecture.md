---
name: Match Engine V2 Architecture
description: Integration der Standalone-Simulation (exp 1.25 + Taktik-Compiler + Minutenlogik) in Django-Produktionsumgebung.
---

## Regel
`game/tactic_compiler.py` = direkter Copy des Standalone (keine Django-Imports). `game/match_engine.py` enthält ORM-Bridge + portierte Minuten-Simulation. Öffentliche API bleibt `simulate_match(home_club, away_club) → dict`.

**Why:** Standalone war akzeptierter Balancing-Stand (320k Sims, alle Kriterien bestanden). Integration musste 1:1 identisch sein — keine neue Balancing-Logik.

## ORM-Bridge Schlüsselmuster
`_build_team_dict(club, tactic_setup)` konvertiert:
- `TacticSetup.lineup` → `lineup: [{player_id, position, group}]`
- `TacticSetup.instructions` → `tactic: {attack_focus, pressing, pressing_triggers, buildup, defending}`
- `TacticSetup.conditions` → `tactic.conditions`
- `TacticSetup.first_half / second_half` → direkt in tactic_dict
- `PlayerStrengthProfile.final_strength` (nicht base_strength) → `player.final_strength`

## Stärkenberechnung
Neu: `_calculate_lineup_strength()` nutzt Taktik-Compiler-Multiplikatoren (line_multipliers aus `compile_tactic()`). Alt: `calculate_lineup_strength()` aus `match_readiness.py` ignoriert Compiler und bleibt für andere Verwendungszwecke erhalten.

## xG-Formel
`base_xg = 1.36 * (ratio ** 1.25)` — NICHT `1.4 * ratio`. ratio = gewichteter Offensiv/Defensiv-Quotient (not just overall/overall). Plus Zone-Factor (±7%) und Taktik-Multiplikatoren.

## Neue Output-Felder (rückwärtskompatibel addiert)
`home_xg`, `away_xg`, `simulation_mode='minutes'`, `plan_activations`, `condition_debug`, `home/away_compiled_tactic`, `home/away_zone_strengths`. In `match_stats` neu: `*_attacks_left/center/right`, `*_pressing_ball_wins`, `*_pressing_bypassed`, `*_fatigue_cost`, `*_tactic_coherence`, `*_tactic_complexity`.

## Goalevents
Simulation läuft mit dict-basierten `_lineup_players_dict()` (für Taktik-Compiler). Danach werden Tore/Vorlagen per `h_goals_map[pid]` auf ORM-Player-Rows gemappt (für den Spielbericht).

## How to apply
Bei jeder Änderung an der Spielsimulation: Nur `game/tactic_compiler.py` und `game/match_engine.py` anfassen. `CONDITION_PLAN_MODIFIERS` in `tactic_compiler.py` dürfen NICHT verändert werden (abgenommenes Balancing).
