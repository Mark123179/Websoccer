---
name: Tactics layout media-query override trap
description: @media (max-width: 1440px) block in tactics.css silently resets the three-column grid to original narrow widths — must update both the base rule AND the media block.
---

**Rule:** `.tactics-template-grid` three-column widths are declared twice in `tactics.css`:
1. Base rule (~line 1949) — applies above 1440px
2. `@media (max-width: 1440px)` block (~line 2549) — overrides the base at ALL normal viewports

Any change to `grid-template-columns` on `.tactics-template-grid` must be made in **both** locations or the media-query block silently wins.

**Why:** The golden master is 1440×900 so the media query fires for virtually every user. Editing only the base rule produces zero visible change and is extremely hard to debug because the CSS is served correctly — the override is just later in the file.

**How to apply:** Search `@media (max-width: 1440px)` in `tactics.css` and update the `.tactics-template-grid` block there in the same edit. Also note that `.tactics-main-grid` is dead CSS — no HTML element uses that class; the real layout container is `<main class="tactics-template-grid">`.
