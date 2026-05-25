---
name: Wide-shell scope rule
description: How to scope progressive-horizontal layout improvements without touching the 1440×900 golden master baseline.
---

**Rule:** 1440×900 is the locked golden-master baseline. Never modify global rules on dashboard tile/grid selectors (poster, positions, market, season, injuries, transfer cards, poster media), calendar, navbar, stage scale/height, base artboard, card heights, grid-Y positions, or Saisonleistungen vertical scroll. Any horizontal-real-estate improvement intended for wider viewports (2K/4K) must be scoped under `.dashboard-scaler[data-shell-mode="wide"] ...` or the equivalent `.is-wide-shell` class — never as a bare global rule.

**Why:** User repeatedly hit regressions where unscoped tile/content CSS silently shifted the baseline aspect. After several rebuilds, 1440×900 was declared an inviolable golden master so future widescreen polish cannot leak into baseline geometry.

**How to apply:** Before editing any AAA tile/grid CSS, ask: is this needed at baseline? If only for wider viewports, scope it under the wide-shell parent. To verify a baseline-touching change is truly zero-impact, measure `getBoundingClientRect()` of the dashboard cards at 1440×900 before/after — diffs must be zero. The stage scaler already exposes the `data-shell-mode` flag; consume it, don't reinvent it.

**Audit-before-fix discipline:** Never ship a wide-mode rule on the assumption that it "should help longer content". An earlier attempt to widen the injury row text column by switching its grid to `auto`-sized date column actually shrank effective text space by ~3 logical px because the increased gap ate more than the auto column freed. Always A/B audit (rule on vs rule off, real data vs injected long-text fixture) before committing a wide rule, and only keep it if it produces a measurable, positive delta on the actual or realistic content. A `?measure=1` instrumented audit endpoint + `?fake_vw/vh` viewport simulation in the scaler is the right tool for this.
