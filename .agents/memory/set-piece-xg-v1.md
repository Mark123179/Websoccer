---
name: Set-Piece xG-Pfade V1
description: Ecken, Freistöße (direkt + Flanke/Kopfball) und Foulelfmeter als unabhängige xG-Quellen im Match Engine V2.
---

## Architektur

- `_best_sp_attrs(player_ids, lineup_list, players_by_id)` — liest FMI-Attribute `ecken`, `freistoss`, `kopfball`, `elfmeter`, `tw_reflexe` aus prefetched source_ratings; kein extra DB-Query; Fallback 70.
- `_build_team_dict` gibt `set_piece_attrs` zurück (wird in `home_team`/`away_team` gespeichert).
- `_set_piece_xg(n_corners, n_fouls, own_sp, opp_sp)` berechnet vier xG-Werte; alle ≥ 0.
- In `_simulate_match_minutes`: nach `_add_segment_stats` folgt Set-Piece-Loop (8 Einträge × 2 Teams), eigener `_poisson`-Draw, `_goal_events(..., goal_type=...)`.
- `_goal_events` hat `goal_type`-Parameter (default `'goal'`); jedes Tor-Event trägt das Feld.

## goal_type → Ticker-Mapping (views.py `_build_combined_events`)

| goal_type   | ticker evt_type       |
|-------------|----------------------|
| corner      | corner_goal          |
| fk_direct   | freekick_goal        |
| fk_cross    | freekick_cross_goal  |
| penalty_sp  | penalty_goal         |
| goal        | goal                 |

## Konstanten (eingefroren 2026-06-18, Nutzer-Freigabe explizit)

```
SET_PIECE_CORNER_BASE_XG    = 0.025
SET_PIECE_FK_DIRECT_BASE_XG = 0.045
SET_PIECE_FK_CROSS_BASE_XG  = 0.028
SET_PIECE_FK_RATE            = 0.120
SET_PIECE_FK_DIRECT_PROB    = 0.380
SET_PIECE_PENALTY_RATE       = 0.012
SET_PIECE_PENALTY_BASE_XG   = 0.730
SET_PIECE_ATTR_COEFF         = 0.005
```

Erwartete Inflation: +0.28 xG/Team/Spiel bei Ø-Attributen.

**Why:** `ecken` und `freistoss` hatten zuvor null Engine-Einfluss (Audit Task #584 bestätigt).

**How to apply:** Konstantenänderung nur mit ≥50-Saisons-Evidenz + expliziter Nutzer-Freigabe. Ticker-Texte in `_CORNER_GOAL_TEXTS` + `_FREEKICK_CROSS_GOAL_TEXTS` pools.
