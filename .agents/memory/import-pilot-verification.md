---
name: Import pilot verification
description: Shared-model activation, proxy metadata, and honest source equality evidence.
---

Install the shared schema unconditionally. One temporary flag controls behavior, not fields or models; remove it and legacy branches after takeover.

For FMInside Dynamic, use the observed tooltip range's upper bound as source potential. Include potential_range with min/max/code and preserve raw.potential_text verbatim. This is standard package scope, including players with CMTracker values. Never fill potential from rating or introduce a special strength calculation.

**Why:** Nachtrag 8 explicitly approves the tooltip upper bound as a real source value, not an estimate. The approved source-NULL rule still applies when no range is readable; formulas stay unchanged.

**How to apply:** Read FM26 26.2.0 tooltips, not a range inferred from rating or another database. If no range can be read, retain NULL and report it separately from package player_lock gaps. Package-only corrections do not reimport the pilot; the user uploads the rebuilt package himself.

**Why:** The user corrected the schema-switch approach: ordinary post-merge and server deployment commands run migrate without knowing that switch. Hidden required columns would break old-mode inserts and every later migration.

**How to apply:** Same classes/migrations in both modes, no migration drift. Already applied migrations remain immutable; corrections use a follow-up migration. Existing player locks initialize false, existing ordinary clubs playable and prior placeholders non-playable. Preserve legacy runtime/default behavior until takeover; package initialization writes explicit unknowns and locks.

Django proxy metadata can retain cached inherited field lists when base classes are extended after proxies have been constructed. A table-to-columns dict must not be overwritten by a later proxy's narrower cached field list.

**Why:** A real schema audit falsely reported missing Player columns even though the base model and database contained them.

**How to apply:** Clear affected inherited metadata caches, verify concrete-model fields, and combine field inventories for shared tables rather than trusting the last proxy encountered.

Do not equate isolation from writes with byte equality of a concurrently active source. Never restore source rows merely to make an equality check pass.

**Why:** Public profile hashes changed while the existing request middleware continued updating activity and login rewards. Aggregate-only before hashes cannot prove which individual columns changed.

**How to apply:** Capture read-only baseline evidence before work. Report exact mismatching tables and the limits of attribution; retain role/ACL/sequence evidence separately. If column-level attribution is required later, agree on a stronger baseline or an authorized writer pause first.

The user accepted the earlier profile mismatch as normal last_seen activity. For additive schema work compare original columns and original technical metadata rows, not SELECT * hashes that necessarily change when columns/models are added.

**Why:** The source service is intentionally active and additive schema changes are now explicitly authorized while its preexisting data must stay unchanged.

**How to apply:** Exclude only the accepted activity column; do not ignore whole profiles, old rights or other old fields. Export digests, never personal row values.
