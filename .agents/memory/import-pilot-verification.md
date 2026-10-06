---
name: Import pilot verification
description: Shared-model activation, proxy metadata, and honest source equality evidence.
---

Keep schema activation and migration deployment coordinated when changing shared Game classes while the existing service remains on its old schema.

**Why:** The user authorizes a shared full Game schema, but explicitly prohibits migrating or stopping the existing public service during pilot work. Unconditionally querying new columns would break that service.

**How to apply:** Use the same classes and migration, not duplicate models or formulas. Do not enable the new schema on the existing service before an approved migration/cutover.

Django proxy metadata can retain cached inherited field lists when base classes are extended after proxies have been constructed. A table-to-columns dict must not be overwritten by a later proxy's narrower cached field list.

**Why:** A real schema audit falsely reported missing Player columns even though the base model and database contained them.

**How to apply:** Clear affected inherited metadata caches, verify concrete-model fields, and combine field inventories for shared tables rather than trusting the last proxy encountered.

Do not equate isolation from writes with byte equality of a concurrently active source. Never restore source rows merely to make an equality check pass.

**Why:** Public profile hashes changed while the existing request middleware continued updating activity and login rewards. Aggregate-only before hashes cannot prove which individual columns changed.

**How to apply:** Capture read-only baseline evidence before work. Report exact mismatching tables and the limits of attribution; retain role/ACL/sequence evidence separately. If column-level attribution is required later, agree on a stronger baseline or an authorized writer pause first.
