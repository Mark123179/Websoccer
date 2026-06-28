---
name: Scouting world-map viewBox calibration
description: How CONTINENT_VIEW/REGION_VIEW viewBoxes relate to the map stage aspect ratio in the scouting screen.
---

# Scouting world-map viewBox calibration

The scouting world map (`game/static/game/scouting/world.svg`, intrinsic viewBox `0 0 1010 666`)
is rendered with `preserveAspectRatio="xMidYMid meet"`. `meet` NEVER crops — it only
letterboxes. So any black bars / "too much empty space" / "continent off-frame" bug is an
aspect-ratio mismatch between the chosen viewBox and the `.sc-map-stage` box, not a pan/zoom bug.

**Rule:** Every viewBox in `CONTINENT_VIEW` / `REGION_VIEW` (in `scouting.js`) and the
`.sc-map-stage { aspect-ratio }` (in `scouting.css`) must share the SAME width/height ratio
(currently ≈ `1006/654 ≈ 1.538`). If they match, the landmass fills the frame with no
letterboxing.

**Why:** With `meet`, the rendered scale = min(stageW/vbW, stageH/vbH). If the viewBox ratio
differs from the stage ratio, one axis under-fills → visible empty bands and the user reports
"continent doesn't fit" or "too much sea at the bottom".

**How to apply:** If you resize the stage, change the SVG, or add continents/regions, recompute
each viewBox to the stage aspect (pad the real landmass bbox out to the target ratio, centered).
Verify visually per continent — the screenshot browser is logged out, so temporarily disable
`@login_required` on `transfer_scouting` (or use `?kontinent=<key>`), screenshot, then restore.
Region keys must match `game/scouting/constants.py` (eu_west/eu_east/eu_north/sa_all/af_all/as_all).
