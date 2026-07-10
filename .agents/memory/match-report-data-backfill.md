---
name: Squad data looks like a template bug but is really an unrun seed/backfill command
description: Empty shirt-number badges and missing Auslastung % on the match report were caused by unpopulated DB fields, not template/CSS bugs — existing idempotent management commands already existed to fill them.
---

When a report field renders empty/dash despite the template already outputting
`{{ p.field|default:"" }}` correctly, check the underlying DB data before
assuming a template or pipeline bug.

**Why:** `Player.shirt_number` was `None` for ~820/828 players and
`ClubPublicProfile.average_attendance` was `0` for 21/22 club profiles, even
though `match_report.html` already rendered these fields correctly and
`_ensure_shirt_numbers_in_report()` already had a DB-lookup fallback wired in.
The real gap was that the existing, idempotent management commands
(`assign_shirt_numbers`, `seed_club_profiles`) simply had never been run for
most clubs.

**How to apply:** Before writing new sorting/rendering/fallback code for a
"missing value" complaint, grep `game/management/commands/` for an
existing seeder/assigner for that field and check `Player`/`ClubPublicProfile`
population counts directly via shell. If a safe idempotent command already
exists, just run it instead of inventing new logic. Also: `home_ratings` /
`away_ratings` list order is already position-order (TW→DF→MF→ST) as built by
the match engine — no custom sort needed, just don't apply
`dictsortreversed:"rating"` in the template if position order is wanted.
