---
name: ActiveLineupState — Mid-Match Substitution Engine
description: Architecture and invariants of the ActiveLineupState class that drives real in-game substitutions.
---

## Rule
`ActiveLineupState` in `game/match_engine.py` manages planned substitutions during the simulation loop. All player data (starters + bench) must be pre-loaded before the loop — no ORM inside `_simulate_match_minutes()`.

**Core invariant:** each planned substitution is evaluated exactly ONCE via `_resolved_idxs`. A condition that fails is permanently discarded — never retried later.

## Data flow
1. `simulate_match()` loads lineup + bench PIDs into `_all_pids`, queries once, builds `_make_bench_data()`.
2. Bench data is stored as `home_team['bench_player_data']` and `home_team['planned_substitutions']`.
3. `_simulate_match_minutes()` creates `h_als = ActiveLineupState(lineup, players_by_id, bench_by_id, planned_subs)`.
4. Before each segment: `h_als.process_planned_subs(segment_start, own_goals, opp_goals, dismissed_pids)`.
5. After: `_h_active = h_als.get_active_lineup(h_dismissed_pids)` → used for strength calc + goal events.
6. Return dict includes `h_sim_sub_events` / `a_sim_sub_events`.
7. `simulate_match()` uses sim sub events if planned subs exist, else auto-generated fallback.

## Minute rounding
`_ceil5(63) = 65` — executed minute is always a 5-multiple. Sub at minute 63 fires before segment 66, shown as 65'.

## Position factor consistency
`_pos_factor_dict()` now delegates to `position_service.get_position_fit()`.
`_pos_factor()` (ORM path) uses `_FP_FACTOR = 0.70` (was 0.80 before). Both paths are now consistent.

## Why
One-shot evaluation prevents the engine from "waiting" for a condition to become true — a sub for `fuehrung` that fires at 0-0 segment 66 must be discarded forever, not reconsidered at segment 76 when leading 1-0.

## How to apply
- To add a new condition: add a branch to `_check_sub_condition()` + a test in `CheckSubConditionTests`.
- To change quota: change `MAX_SUBSTITUTIONS` constant (shared: planned + injury subs).
- `get_active_lineup(dismissed_pids)` must always be called with the current dismissed set.
