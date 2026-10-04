---
name: Collected static parity
description: Checked-in production static assets need content parity, not just a successful collectstatic run.
---

Security fixes must reach both application static sources and checked-in collected production assets. A successful `collectstatic` run alone is not proof of content parity.

**Why:** Timestamp-based collection reported everything unmodified even though the production news script still had the vulnerable implementation. Removing just the stale generated file and collecting again regenerated it correctly.

**How to apply:** Compare bytes for each security-relevant changed asset against its collected counterpart. If collection skips differing contents, remove only that generated output and regenerate it. Keep a focused parity regression for security-critical scripts.