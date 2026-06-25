---
name: CMTracker source consolidation
description: Why source naming is CMTRACKER everywhere but many SOFIFA/EA aliases were deliberately kept; how an identity-only rename must preserve strengths.
---

The rating/identity source was consolidated to a single canonical name **CMTRACKER**.

- `DataSource.code = 'CMTRACKER'` (label "CMTracker"); `PlayerSourceRating.source = 'CMTRACKER'`; `SourceImportRun.source = 'cmtracker'`.
- Three rating/identity namespaces remain valid: **TM**, **FM**, **CMTRACKER**. `API_FOOTBALL` / `WSC` DataSource codes are unrelated and were NOT touched.

**Why an identity-only rename:** the match engine is FROZEN. A source rename must not recompute anything. The data migration only relabels source strings — `calculate_player_strengths` is never called — so player strengths are provably identical before/after (verify with a sha256 over `PlayerStrengthProfile(player_id, base_strength, final_strength)` pre/post `migrate`).

**Deliberately KEPT for backward compatibility (do NOT "finish the rename" on these):**
- CSV/dict keys and field name `sofifa_id`, `sofifa_*`; CSV column prefix `sofifa`.
- Constant *names* `SOFIFA_ATTR_MAP` / `SOFIFA_GK_MAP` / `_SOFIFA_ATTR_COLUMNS` (values/usage unchanged).
- `match_type == 'sofifa'` discriminator (asserted in tests — it is an internal match-mode label, not a source code).
- Form prefix `ea` / `src_ea_*`; API response keys `sofifa` / `sofifa_raw`.
- Filenames (`sofifa_import.py`, `sofifa_import_service.py`, `import_sofifa_zip/csv.py`), URL name `creator_sofifa_import`, CSS class `si-col-sofifa`, local vars `ea_row`/`ea_map`/`ea_ids`.
- Staging constants `STATUS_MISSING_SOFIFA` / `STATUS_AMBIGUOUS_SOFIFA` (names + values `missing_sofifa`/`ambiguous_sofifa` kept; only their human labels relabeled "CMTracker fehlt"/"…mehrdeutig").

**How to apply:** when touching source naming, change DataSource/PlayerSourceRating/SourceImportRun source VALUES via their constants only. Hardcoded source query literals (`source='EA'`, `code='SOFIFA'`, `source='sofifa'`) break post-migration — always use the model constants. Historical migrations (0015/0016) reference the OLD `code='SOFIFA'` on purpose; never rewrite them — at their point in history the code was still SOFIFA.
