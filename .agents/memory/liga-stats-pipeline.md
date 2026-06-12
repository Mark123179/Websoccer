---
name: Liga-Stats-Pipeline
description: How player goals/assists/minutes/form ratings get written after each Bundesliga matchday simulation.
---

# Liga-Stats-Pipeline

## Rule
`_update_player_season_stats(fixture, data)` in `game/season_service.py` is the canonical function that writes per-player stats after every liga simulation. It must be called from both code paths:
1. `season_service.simulate_matchday()` — used by the web UI control panel
2. `game/management/commands/play_matchday.py` — used by the CLI command

## What it writes
- `PlayerFormSnapshot` — one row per player per fixture, `source='ws_liga'`, `fixture_id='ws_liga_{fixture.id}'`. Unique constraint: `(player, source, fixture_id)`.
- `PlayerSeasonStat` — recalculated from ALL ws_liga snapshots for affected players (idempotent for --force re-sims). Fields written: `goals`, `assists`, `matches`, `minutes_played`.

## What it does NOT write
- `average_grade` on `PlayerSeasonStat` — intentionally left to Task #405/#412 to avoid conflicts.

**Why:**
Separating goals/assists/minutes (always available from simulate_match result) from average_grade (computed by compute_player_ratings, managed by Task #405) prevents merge conflicts and makes each concern independently testable.

## How to apply
Any new simulation pathway (cup fixtures, friendlies, etc.) must also call `_update_player_season_stats()` after writing the SeasonFixture result.

## Season label
`PlayerSeasonStat.season = '2026/27'` (matches `CURRENT_SQUAD_SEASON` in views.py and `CURRENT_SEASON` in club_profile_highlights.py). `competition = 'Liga'`.
