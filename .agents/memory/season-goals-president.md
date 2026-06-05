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
The hero is a single pre-baked JPG `backgrounds/praesident-office-hoeness.jpg`: Uli Hoeneß composited so he genuinely sits BEHIND the executive desk in `praesident-office-bg.jpg`. Set as `.pr-hero-bg` (cover, background-position center 30%); no floating overlay element. Source `managers/hoeness-cutout.png` is a misnomer — it's the full rectangular interview photo (his own red/trophy/podcast-mic background), NOT freigestellt.

**Why:** user first complained he didn't sit well at the desk; a naive floating-PNG-over-office composite looked pasted-on, and using the raw interview photo full-bleed was too zoomed. The user confirmed the desired look is Hoeneß seated at the desk INSIDE the office background.

**How the bake works (PIL):** `remove_image_background_tool` on hoeness-cutout.png DOES isolate him (≈62% transparent) — but it can silently fail on one run and succeed on a retry, so verify the alpha (composite over green / check histogram) before trusting it. Then crop tight to torso+head (x≈158–540, drop the glass on the left, podcast mic on the right, table at the bottom), darken ~0.84 + warm-tint to match the office light, feather the alpha (~1.2px), place him over the empty chair (cx≈0.36·W, head_top≈0.24·H, height≈0.50·H), and finally re-paste the office region below y≈0.655·H back on top so the desk occludes his lower body — that's what makes him sit behind the desk instead of on it.
