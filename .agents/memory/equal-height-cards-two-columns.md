---
name: Equal-height cards across two flank columns
description: Why per-column flex fails for equal-height/bottom-aligned cards flanking a center element, and the display:contents grid fix.
---

# Equal-height cards across two flank columns

When cards must be equal height AND bottom-aligned across two SEPARATE columns
that flank a center element (e.g. stadionumfeld: left+right asides around the
scene), do NOT size them per-column with flex.

**What fails:**
- `flex:0 0 auto` → each card is its own content height; columns unequal.
- `flex:1 1 0` (± `min-height:0`) inside each flex-column aside → splits each
  column's own height in half. But the two columns are independent, so when
  their content differs the columns end up different total heights → bottoms
  do NOT line up across columns (observed ~30px seam offset).

**The fix:** make all cards share ONE grid's row tracks. Set the asides to
`display:contents` so their card children become direct grid items of the outer
shell, give the shell `grid-template-rows: 1fr 1fr`, and place each card
(`grid-column`/`grid-row` via `:nth-of-type`). The center element spans both
rows (`grid-row: 1 / span 2`). `1fr 1fr` in an auto-height grid sizes both rows
to the tallest row's content → every card equals the tallest card, exact bottom
alignment, no overflow.

**Why:** flex equal-basis only equalizes within a single flex container; it
cannot cross-align siblings in a different container. Shared grid tracks can.

**How to apply:** any "cards flanking a centerpiece, all equal height" layout.
Note `display:contents` drops the aside's own box (its gap/flex are gone — use
the grid's gap). Solo/empty case: reset with `grid-template-rows:auto` and
`grid-column/row:auto` on the centerpiece.
