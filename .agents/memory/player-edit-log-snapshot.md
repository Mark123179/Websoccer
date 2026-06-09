---
name: PlayerEditLog snapshot trap
description: When building before/after diffs in views that mutate ORM objects in-place, the existing{} dict holds references not copies — snapshot values before the mutation loop.
---

## Rule
In `_save_player_source_ratings`, `existing = {r.source: r for r in ...}` stores live ORM object references. The loop then mutates `row.rating`, `row.potential`, etc. in-place. If you read `existing.get(source_key).rating` **after** the mutation, you get the new value, not the old one — making every diff empty.

**Fix:** At the very start of each loop iteration, before any `setattr` or direct field assignment, capture `_snap_r = row.rating if row else None` and use these snapshots in the log comparison.

**Why:** Python dicts store object references. `existing.get(key)` IS the same object as `row` when the row exists. Any mutation to `row` is immediately visible through the dict.

**How to apply:** Any time you need old/new diff on a queryset-backed dict, snapshot the scalar values (not the object) before entering the mutation block.
