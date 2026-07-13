---
name: Vereinsnews data wiring
description: How last_match, scorers, MOTM, player stats are wired from DB into VN_DATA for the Vereinsnews editor
---

## last_match population
- `get_last_match(club)` returns the newest **is_played Liga SeasonFixture that HAS a linked simulated_match (report_data)** — i.e. the last *Pflichtspiel mit Bericht*. Report-less fixtures AND standalone friendlies are skipped on purpose.
- **Why:** a fixture can be is_played=True with a score but NO report (played via a bulk/quick sim that only writes the score to SeasonFixture, not a SimulatedMatch). Ordering by scheduled_date alone then returns a bare score with no scorers/MOTM. The user wants "immer das letzte Pflichtspiel" — so both the Vereinsnews card and the Spielbericht page must select the newest fixture WITH a report.
- The Spielbericht page (`club_match_report`) GET view uses the SAME query (newest Liga fixture with report → its simulated_match) so both surfaces always agree. Its admin POST (test-simulate friendly/pokal) redirects to `match_report_by_id` for the new sm so the admin still sees the test result.
- Pokal matches are standalone SimulatedMatch (match_type='pokal') with no SeasonFixture → NOT covered by get_last_match; still reachable via the direct `match_report_by_id` link.
- Do NOT order by `-matchday` (ignores date) and do NOT compare SeasonFixture.scheduled_date against SimulatedMatch.simulated_at.date() — simulated_at is wall-clock creation time, not the in-game match date (a friendly simulated "now" would always win).
- match_type is default 'freundschaft' EVEN for Liga matches (season_service doesn't set it) → cannot use match_type to detect Pflichtspiel; use "linked to a SeasonFixture" instead.
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
