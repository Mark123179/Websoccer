---
name: Vereinsnews data wiring
description: How last_match, scorers, MOTM, player stats are wired from DB into VN_DATA for the Vereinsnews editor
---

## last_match population
- Use `get_last_match(club)` from `fixture_display.py` — compares SeasonFixture and SimulatedMatch by date, not matchday.
- Direct `SeasonFixture.objects.order_by('-matchday')` is WRONG for club_news; it ignores SimulatedMatches and gets a different fixture than the Spielbericht page uses.
- `FixtureDisplay.scorers` / `SimulatedMatchDisplay.scorers` both call `_scorers_from_goal_events(report_data.get('goal_events', []))`.
- JS expects scorers as `[minute, name]` arrays; Python returns `{'playerName', 'minute', 'team'}` → convert: `[[s['minute'], s['playerName']] for s in raw]`.

## Crowd (Zuschauer)
- `Stadium` is `OneToOneField` to `Club` with `related_name='stadium'` → `club.stadium`.
- Stadium has no `average_attendance` field; use `capacity_total` (a @property summing all sections).

## MOTM block
- `report_data['man_of_the_match']` keys: `{id, name, club_id, club_name, club_crest, club_short, rating, position}`.
- `portrait_url` is backfilled by `_ensure_portraits_in_report` (not always present in raw data).
- Goals/assists for MOTM must be counted manually from `goal_events` by matching `scorer_name`/`assister_name` to `man_of_the_match.name`.
- Access raw report_data: `_lm_obj._f.simulated_match.report_data` (FixtureDisplay) or `_lm_obj._m.report_data` (SimulatedMatchDisplay).

## Player stats in players_dict
- `PlayerSeasonStat` has: `goals`, `assists`, `average_grade` (Decimal, nullable), `matches`, `season_number`.
- Query: `filter(player_id__in=pids, club=club).order_by('-season_number', '-matches')` — take first per player with `_seen_pids` set.
- `Player.age` is an IntegerField (stored, not computed from DOB).

**Why:** The discrepancy between "2:2 vs Mainz" in editor and "3:1 Wolfsburg" on Spielbericht was caused by `order_by('-matchday')` vs. `get_last_match()`'s date comparison. Always use `get_last_match()` as single source of truth.
