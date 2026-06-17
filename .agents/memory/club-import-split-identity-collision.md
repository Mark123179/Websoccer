---
name: Club import split-identity collision
description: Why an update-or-create import can still hit a unique-constraint crash even when matching works.
---

# Split-identity duplicate collision on import

The same real player can exist as TWO Player rows that each hold a *different*
external ID: row A has `fm_inside_id` but no `transfermarkt_id`, row B has
`transfermarkt_id` but no `fm_inside_id`. A CSV that carries BOTH IDs matches one
row (e.g. B by tm_id), then tries to write the other ID (`fm_inside_id`) onto it —
which collides with row A on the unique constraint `game_player_fm_inside_id_key`.

**Why:** `find_existing_player` returns a single best match by priority; it cannot
know a second row holds the twin ID. Update-or-create + per-row atomic means that
one row fails (IntegrityError) while the rest of the batch succeeds.

**How to apply:** When an import reports exactly one `source_error` with a unique
constraint on `fm_inside_id`/`transfermarkt_id`, suspect a pre-existing split
duplicate, not an adapter bug. Resolve by merging: keep the actively-used row (the
one with edit_logs / import_candidates / stats), verify the orphan has zero cascade
(NestedObjects collector), delete the orphan, then re-run the idempotent import.

**General fix exists:** `manage.py merge_split_players` (dry-run default, `--apply`)
auto-merges twins by normalized name + DOB + complementary, conflict-free external
IDs. It reassigns dependents generically via `Player._meta.related_objects` with a
per-row savepoint: on a unique-constraint collision the canonical row wins and the
twin's row is dropped. Skips >2-member groups (manual review) and same-ID-kind
pairs (= different people). Use it instead of hand-merging.
