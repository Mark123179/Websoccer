---
name: Render-only report normalization
description: Keep environment-specific URL normalization out of persisted report backfills.
---

Apply render-only, environment-specific URL normalization after report backfills that can save the supplied report dictionary.

**Why:** The weather backfill persists the entire supplied dictionary when weather is missing. Normalizing image URLs before that step unintentionally writes the current environment's URLs into historical reports.

**How to apply:** Order persistence-capable backfills first, then presentation-only normalization. Test old reports without weather and assert their stored crest fields remain unchanged.