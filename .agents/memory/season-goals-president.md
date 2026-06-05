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

## Season number & admin-gated reveal
Season numbering comes from an admin-controlled `GameSeasonState` singleton (NOT from `PlayerSeasonStat`, which had unrelated high season numbers). Season counter starts at **0**. The season goal stays **verdeckt** (sealed card, no tier/rank/strength leaked to the template) until the admin sets `is_started=True`; on first view after start the goal is auto-declared and revealed.

**Why:** the trainer must never see the league power balance (Kräfteverhältnis / squad-strength ranking) — that whole section was removed, and even the goal card only shows tier + required end place. Pre-start disclosure was also possible via a trainer-facing declare endpoint, so that POST route was removed entirely; reveal is admin-gated only.

**How to apply:** read season via `current_season_number()`/`is_season_started()` (both back onto `GameSeasonState`); season 0 is falsy so use `is None` checks, never `or`, when defaulting a season arg.

## Hero image
`hoeness-cutout.png` is a misnomer — it is NOT background-removed, it's the full rectangular interview photo of Hoeneß seated at a table with the CL trophy + Meisterschale behind him. `remove_image_background_tool` fails to isolate him on it (subject not detected). So do NOT composite it as a floating PNG over a separate office background (looks pasted-on / "sitzt nicht am Tisch"). Instead it IS the hero scene: set it as `.pr-hero-bg` (background-size:cover, background-position center ~18% to keep his face in frame) and drop any floating `.pr-hoeness` overlay. `praesident-office-bg.jpg` is the old empty-office background, now unused.

**Why:** user complained Hoeneß didn't sit well at the desk — the floating-cutout composite never aligned with the office desk because the "cutout" still had its own background.
