---
name: CMTracker source consolidation
description: Why source naming is CMTRACKER everywhere but many SOFIFA/EA aliases were deliberately kept; how an identity-only rename must preserve strengths.
---

The rating/identity source was consolidated to a single canonical name **CMTRACKER**.

- `DataSource.code = 'CMTRACKER'` (label "CMTracker"); `PlayerSourceRating.source = 'CMTRACKER'`; `SourceImportRun.source = 'cmtracker'`.
- Three rating/identity namespaces remain valid: **TM**, **FM**, **CMTRACKER**. `API_FOOTBALL` / `WSC` DataSource codes are unrelated and were NOT touched.

**Why an identity-only rename:** the match engine is FROZEN. A source rename must not recompute anything. The data migration only relabels source strings — `calculate_player_strengths` is never called — so player strengths are provably identical before/after (verify with a sha256 over `PlayerStrengthProfile(player_id, base_strength, final_strength)` pre/post `migrate`).

**CSV headers — `cmtracker_*` is canonical, `sofifa_*` is a kept alias:** both import paths ACCEPT `cmtracker_*` (preferred) and fall back to `sofifa_*`. `sofifa_import.COLUMN_ALIASES` maps `cmtracker_id`/`cmtracker`/`cmtracker_url` → internal `sofifa_id`/`profile_url`. `import_ready_csv._attr_block` takes a prefix *preference tuple* `('cmtracker','sofifa')`; identity reads use `row.get('cmtracker_id') or row.get('sofifa_id')`. Internal dict keys (`sofifa_id`, `sofifa_ratings`, `sofifa_profile_url`) and the export template columns stay `sofifa_*`.

**User-visible label rule:** human-facing "EA"/"SoFIFA" source labels (admin filters, `source_strength_explanation`, template headers/placeholders/tooltips, CLI stdout) MUST read "CMTracker". But external/contract identifiers stay: field `ea_availability_status`, value `NOT_IN_ACTIVE_EA_FC26_DATABASE` (real EA FC 26 DB flag), CSV col prefix `ea_*`, form params `ea_min/ea_max`, local vars `ea_rating`/template var `source_ea_snapshots`. In the width-locked `vl-th-num` column use short "CMT" (+ `title` tooltip), not "CMTracker".

**Deliberately KEPT for backward compatibility (do NOT "finish the rename" on these):**
- CSV/dict keys and field name `sofifa_id`, `sofifa_*`; legacy CSV column prefix `sofifa` (still accepted as alias).
- Constant *names* `SOFIFA_ATTR_MAP` / `SOFIFA_GK_MAP` / `_SOFIFA_ATTR_COLUMNS` (values/usage unchanged).
- `match_type == 'sofifa'` discriminator (asserted in tests — it is an internal match-mode label, not a source code).
- Form prefix `ea` / `src_ea_*`; API response keys `sofifa` / `sofifa_raw`.
- Filenames (`sofifa_import.py`, `sofifa_import_service.py`, `import_sofifa_zip/csv.py`), URL name `creator_sofifa_import`, CSS class `si-col-sofifa`, local vars `ea_row`/`ea_map`/`ea_ids`.
- Staging constants `STATUS_MISSING_SOFIFA` / `STATUS_AMBIGUOUS_SOFIFA` (names + values `missing_sofifa`/`ambiguous_sofifa` kept; only their human labels relabeled "CMTracker fehlt"/"…mehrdeutig").

**How to apply:** when touching source naming, change DataSource/PlayerSourceRating/SourceImportRun source VALUES via their constants only. Hardcoded source query literals (`source='EA'`, `code='SOFIFA'`, `source='sofifa'`) break post-migration — always use the model constants. Historical migrations (0015/0016) reference the OLD `code='SOFIFA'` on purpose; never rewrite them — at their point in history the code was still SOFIFA.
