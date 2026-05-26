---
name: Tactics screen layout heights
description: Current fixed heights for the main tactics panels and side-stack rows — these are the reference values for future work.
---

**Current heights (post readability pass):**

Main panels (`.tactics-preview-panel, .tactics-pitch-panel`): `height: 515px`
(`.tactics-status-panel` overrides to `height: auto`)

Side-stack grid-template-rows: `298px 190px minmax(0, 253px)`
- Bank (bench): 298px
- Wechselplanung (substitutions): 190px  
- Standards: minmax(0, 253px)

Halbzeiten: `.tactics-half-panel { height: 135px }`

**Why:** These were increased from 430px/168px after the 28px-select readability pass caused the Standards panel to clip its content. +85px across all three kept proportions balanced.

**How to apply:** When adding more rows to any panel, recalculate total content height before committing. Wechselplanung at 190px fits 5×28px selects + 5px h2 block + 12px padding + 8px gaps = ~185px (tight). Standards at 253px fits 2×28px selects + h2 + padding with room to spare.
