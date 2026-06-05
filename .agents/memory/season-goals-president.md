---
name: Präsident Saisonziele & Hoeneß-Coin
description: How the president season-goal system derives and evaluates goals, and the immutability rule.
---

# Präsident — Saisonziele

Logic lives in `game/season_goals.py`; views in `game/views_management.py` (`president_office`, `president_declare_goal`); page `/management/praesident/`.

## Squad-strength is the single ranking source
A club's strength = sum of the **top-11** `PlayerStrengthProfile.base_strength` (`club_squad_strength`). Clubs in a league are ranked by that. The goal tier is mapped from that rank via `tier_bands(league_size)` (scales with league size; no relegation-place goals).

**Why:** there is no match simulation / real Ligatabelle yet (`club_table` view is a stub). So `evaluate_goal_for_club` derives the *final* rank from squad strength too — meaning a club that performs to its squad strength meets its goal exactly. When real standings exist, only `evaluate_goal_for_club`'s `final_rank` source needs swapping.

## Goal is immutable once declared
`declare_goal_for_club` is idempotent: if a `SeasonGoal` for (club, season) exists it returns it unchanged unless `force=True` (CLI-only). The POST view also rejects re-declaration. Coin is granted once (`was_already_met` guard in `evaluate_goal_for_club`).

**Why:** a code review flagged that `update_or_create` let a manager re-POST the declare endpoint to wipe an already-evaluated goal and re-roll outcomes. A pre-season target must stay fixed.

## Season number
No Season model — `current_season_number()` = max `PlayerSeasonStat.season_number` (default 1).
