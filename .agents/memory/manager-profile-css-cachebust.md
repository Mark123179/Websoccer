---
name: manager-profile CSS cache-bust gotcha
description: Why CSS edits to manager_profile must bump the ?v= version or the user sees stale CSS
---

Every edit to `game/static/game/css/manager-profile.css` MUST be accompanied by bumping
the cache-bust query string `?v=hNNN-NN` on the `<link>` in `game/templates/game/manager_profile.html`
(near line 13). Otherwise the browser serves the **previously cached** CSS file under the same
URL and your change never reaches the user.

**Why:** Fresh-context tools (screenshot/app_preview) load CSS with no cache, so MY screenshots
show the fix while the USER's browser keeps the stale file under the same `?v=` URL. A marker
crest-anchor CSS fix once shipped this way and the user kept seeing the old floating badge —
reported as "cities wrong / München wrong / no zoom" even though the fix was live in my screenshots.

**How to apply:** Treat the `?v=` bump as part of the same edit as any manager-profile.css change.
If a user reports a CSS/visual fix "didn't work" while your own screenshots show it working, suspect
a missing cache-bust bump before re-deriving any math.

**Marker placement is math-locked:** europe-night map markers are positioned by source pixels via
CITY_MAP_PCT, so perceived drift comes from the anchor transform + stale CSS, never from a broken
bg/marker link. (Verified once by a user hand-placing a city dot that landed exactly on the marker's
rendered anchor — the pixel was already right.)
