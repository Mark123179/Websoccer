---
name: report_data backfill pattern for old SimulatedMatch snapshots
description: How to handle new report_data fields that are missing from older stored SimulatedMatch records
---

When a new field is added to the match-simulation `report_data` dict (e.g. bench,
cards, shirt numbers, ratings, portraits), old `SimulatedMatch` rows created
before that feature existed will simply lack the key — treat this as expected,
not a bug in the simulation code itself.

**Fix pattern:** add a `_ensure_<field>_in_report(report_data, sm=...)` function in
`game/views.py` next to the existing `_ensure_ratings_in_report`,
`_ensure_portraits_in_report`, `_ensure_shirt_numbers_in_report`,
`_ensure_cards_in_report`, `_ensure_not_fielded_in_report`, `_ensure_bench_in_report`.
It should reconstruct the missing data from current live DB state (never invent
data), and must be chained into BOTH view call sites (`match_report` and
`match_report_by_id`) right after `_ensure_ratings_in_report`.

**Why:** report_data is a frozen JSON snapshot per match; there is no migration
step for old snapshots, so every new field needs a live-DB best-effort backfill
or it silently renders empty/missing for all pre-existing matches.

**How to apply:** when a report-tab element unexpectedly disappears/empty for
old matches but works for new simulations, check whether the underlying
report_data key exists at all (not just empty) — if absent, write a new
`_ensure_*` backfill rather than touching the simulation/template code.
