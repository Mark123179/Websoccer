---
name: club-import diff Decimal-vs-int trap
description: Why old/new value comparison in the importer review glue must type-normalize before comparing and before saving to JSONField
---

# Importer review diffs: DB Decimal vs raw int

In the Creator-Mode importer, `compute_detected_changes(player, nd)` compares a
**DB-loaded** Player against freshly parsed raw data (`normalized_data`).

Two distinct hazards, both caused by `DecimalField`:

1. **False diffs.** A player loaded fresh from the DB returns money/number
   fields as `Decimal('100000000.00')`, while the parsed raw value is a plain
   `int` `100000000`. Naive `str()` comparison sees `'100000000.00' != '100000000'`
   and reports a phantom change → candidate misclassified as `existing_changed`
   instead of `existing_unchanged`. In-memory test objects hide this because
   Django doesn't coerce assigned values until a DB round-trip.

2. **JSONField serialization crash.** Storing `Decimal` (or `date`) directly into
   `detected_changes` (a JSONField) raises `TypeError: Object of type Decimal is
   not JSON serializable` on save.

**Fix / rule:** `review.py` has `_jsonable()` (Decimal→int if integral else float,
date→ISO string, recurse lists) used in BOTH places — `_norm()` calls it before
string-comparing, and the diff dict coerces `old`/`new` through it before save.

**How to apply:** any new comparable field added to the diff `rows` must survive a
DB round-trip comparison. Test existing-unchanged with a player saved AND the
field read back from DB, not just an in-memory object, or the trap stays hidden.
