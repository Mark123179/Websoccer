---
name: Screenshot tool viewport limit + below-the-fold verification
description: screenshot(app_preview) only captures the fixed viewport (1280x720), cannot scroll; no browser-use/playwright/selenium available in this env — use Django test client HTML fetch to verify below-the-fold structure instead.
---

The `screenshot` tool's `app_preview` type captures only the current viewport (observed 1280x720) starting at page top — it has no scroll/offset parameter and cannot reach content further down a long page. There is no interactive browser automation available in this environment (`browser-use` CLI is not installed, and `playwright`/`selenium` Python packages are not installed either), so there is no tool-based way to scroll and screenshot arbitrary page positions.

**Why:** Hit this verifying a centered "Auswechslungen" card placed below two tall pitch renderings in the Aufstellungen tab — the target section was below the fold and unreachable via the anchor/tab-hash mechanism (the page's own hash-routing JS only recognizes exact tab names like `#aufstellungen`, so a compound hash trying to also scroll to a sub-element id is not honored, since the panel starts `hidden` and only becomes visible if `switchTab` is called by the JS).

**How to apply:** When a layout change lands below the visible viewport and can't be screenshotted directly:
1. Fetch the fully rendered HTML server-side with Django's test client (`Client().force_login(user)`, then `.get(url)`), which returns the exact same DOM the browser would render (client-side JS here only toggles `hidden`/classes, it doesn't rearrange DOM).
2. Verify structure via string search / regex on the HTML: element counts (e.g. no duplicate cards), and ordering of key markers (`str.find` / `re.finditer` positions) to confirm nesting/placement matches the requirement.
3. Combine with CSS spec guarantees where applicable (e.g. `display:grid` with no `grid-template-columns` stacks children vertically in document order by default) rather than assuming you need a pixel screenshot to confirm basic layout mechanics.
4. Still screenshot whatever portion of the page IS reachable (above the fold) to catch visual regressions in what you can see.
