---
name: Static asset cache-bust gotcha (CSS + JS)
description: Why any edit to a templated CSS/JS asset must bump its ?v= version, including JS not just CSS, or the user sees stale code
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

**This applies to JS too, not just CSS.** On match_report.html, the CSS `?v=` was diligently bumped
on every edit but the paired `<script src="match_report_v2.js">` tag's `?v=` was left stale across
several edits — the browser kept serving old JS while the CSS updates landed fine, producing a
confusing "half the fix works" symptom (new styles present, but the new JS behavior wiring absent).
**How to apply generally:** whenever a template links a versioned CSS file AND a versioned JS file
for the same feature, bump BOTH `?v=` query strings together on every edit to either, even if you
only touched one of the two files this time.

## Update Juli 2026: DEBUG-No-Store-Middleware
?v=-Bump allein reicht nicht, wenn der Client das HTML selbst (mit altem ?v=-Link) aus Browser-/Proxy-Cache lädt. Seitdem: `game.middleware.DevNoCacheMiddleware` (erste Position in MIDDLEWARE, nur bei DEBUG aktiv) setzt `Cache-Control: no-store` auf alle dynamischen Antworten. Statische Dateien laufen in runserver NICHT durch die Middleware — dafür bleibt der ?v=-Bump nötig.
