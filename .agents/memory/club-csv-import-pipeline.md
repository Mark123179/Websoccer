---
name: Club CSV import canonical pipeline
description: Two-mode (Vollanlage/Aktualisierung) CSV import design — field schema SSOT, reconcile-upsert, potential invariant, validation exit-code contract.
---

# Club CSV import — canonical pipeline (two modes)

The CSV import is the single canonical path for real-world club/player data.
Game-state/economy is NEVER written by it.

## Modes
- **Vollanlage (MODE_FULL)**: idempotent reconcile-upsert of Stammdaten + full
  player import. Non-empty CSV overwrites master data; empty leaves alone.
- **Aktualisierung (MODE_UPDATE)**: only volatile real-world fields
  (ratings/potential/attrs, market value, positions, current club/loan status).
  Skips brand-new players; never writes identity (name/dob/height/foot/
  nationalities/external IDs). `update_only` is threaded import_candidate →
  import_selected_candidates.

## Potential invariant — clamp at WRITE time, not just fallback
`_write_source_rating` sets `potential = rating` when potential is **None OR
< rating**. This guarantees `potential ≥ rating` on EVERY write path (full,
update, any direct import_candidate caller).
**Why:** the spec only asked for a None→rating fallback, but a present-but-below
potential (e.g. CSV potential 70 < rating 80) would otherwise persist and
violate the acceptance invariant. The clamp is the central guard; the parsed
validator still *reports* the CSV defect so the user knows their data was off.

## Validation semantics — parsed vs DB differ on missing potential
`check_potential(rating, potential, allow_missing=...)`:
- **parsed CSV** validation calls `allow_missing=True` → missing potential is OK
  (the write-time fallback handles it).
- **DB** validation calls default `allow_missing=False` → missing potential is a
  defect (post-import it should never be missing; flags legacy rows for --repair).
- `potential < rating` is always an error in both.

## Exit-code contract (validation.EXIT_OK/EXIT_ERRORS/EXIT_WARNINGS = 0/1/2)
- Import is **non-blocking**: good data is written, defects are reported.
- Single command (`import_club_ready_csv`) raises `SystemExit(exit_code)` when
  nonzero for BOTH dry-run and real imports.
- Batch (`import_clubs_batch`) isolates per-file errors (one bad file never stops
  the others) and aggregates the exit code across all files: file exception OR
  any validation error → 1; only warnings under `--strict` → 2.

## Field schema is SSOT
`field_schema.py` maps every CSV column → model field, lists rating columns and
`PROTECTED_GAME_STATE_FIELDS` (never written). Stadium stand capacities
(nord_*/ost_*/sued_*/west_*) are deliberately NOT in PROTECTED: they are
conditionally initialized only on establish or while `capacity_total == 0`
(see `club_reconcile.reconcile_club`); an existing capacity is preserved and a
mismatch only warns.
