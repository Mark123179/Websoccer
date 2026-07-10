---
name: Bench "came_on" backfill must use substitution events, not just ratings
description: Why the green up-arrow (eingewechselt) badge can stay missing even after home_bench/away_bench is backfilled
---

`_build_bench_with_status()` in `game/views.py` only marked a bench player as
`came_on` when a matching `home_ratings`/`away_ratings` row existed with
`is_sub=True`. Some older `SimulatedMatch.report_data` snapshots have real,
correctly recorded `home_substitutions`/`away_substitutions` events (in/out
player ids + minute) but are MISSING the corresponding rating row for the
substitute entirely (not just missing the `is_sub` flag) — likely stoppage-time
or edge-case subs that never got a rating computed at simulation time.

**Why:** without cross-checking the substitution event list, the bench UI
falls back to "–" / no green arrow for a player who genuinely came on,
because the ratings-based detection has no row to look at.

**How to apply:** `_build_bench_with_status`'s `_side()` must treat presence in
`sub_on_minute` (built from `rc.home_substitutions`/`away_substitutions`) as
authoritative for `came_on`/`on_minute`, independent of whether a ratings row
exists; only attach `rating`/`goals`/`assists` if a ratings row is actually
present (never invent a rating). Same principle applies to the
`_ensure_bench_in_report` backfill: when reconstructing a missing
`home_bench`/`away_bench` list from the club's current `TacticSetup.bench`,
also union in any player id that appears as `in` in the stored substitution
events, since that player may no longer be on the club's current bench.
