---
name: KO-Spielmodus V1
description: Verlängerung (91-120 Min) + Elfmeterschießen — öffentliche API, Konstanten, Seed-Konvention und Testmuster.
---

## Öffentliche API
- `simulate_ko_match(home, away, ...)` → alias for `simulate_match(is_cup=True)`
- `simulate_match(..., is_cup=False)` → Step 7 fügt decided_by, home/away_goals_90/et, home/away_penalties, winner_club_id, penalty_events hinzu
- decided_by: 'regular_time' | 'extra_time' | 'penalties'

## Konstanten (eingefroren, Freeze-Datum 2026-06-14)
- PENALTY_BASE_PROB = 0.760
- PENALTY_SHOOTER_COEFF = 0.002
- PENALTY_GK_COEFF = 0.0015
- EXTRA_TIME_SUBSTITUTION_BONUS = 1 (ermöglicht 6. Wechsel in VL)
- Wahrscheinlichkeit geclampt [0.55, 0.92]

## Seed-Konvention
- Elfmeter-RNG: `random.Random(match_seed ^ 0xE1F3A2B1)`
- Kein 0xE1FM3TE2 — M ist kein gültiges Hex-Zeichen

## ALS-Zustand für ET
- `_simulate_match_minutes(_return_als_state=True)` liefert h_als, a_als, h/a_dismissed_pids, h/a_gk_str_override
- ALS wird IN-PLACE durch `_simulate_extra_time_minutes()` modifiziert

## Testmuster
- PlayerSourceRating innerhalb `_simulate_penalty_shootout` ist lokaler Import → muss via `game.models.PlayerSourceRating` gemockt werden
- `_make_als(dismissed_pids_filter=True)` gibt side_effect-Mock zurück, der dismissed_pids herausfiltert

**Why:** KO-Modus wurde als Step 7 in simulate_match() integriert (nicht als separate Funktion), um alle bestehenden Spieler-Rows, Rating-Berechnungen und Dict-Keys wiederverwendbar zu machen.
