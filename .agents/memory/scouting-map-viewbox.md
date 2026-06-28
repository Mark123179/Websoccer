---
name: Scouting world-map viewBox calibration
description: The scouting map must use the reference Natural Earth SVG + its exact projected continent viewBoxes, not self-computed ones.
---

# Scouting world-map viewBox calibration

The scouting world map (`game/static/game/scouting/world.svg`) is the user's reference
("Vorlage") Natural Earth equirectangular projection, intrinsic viewBox
`5.6 19.4 988.8 386.2` (~1000×500 projected px), rendered with
`preserveAspectRatio="xMidYMid meet"`. `meet` NEVER crops — it only letterboxes, and the
letterbox bands are intentionally ocean/radar, not a bug.

**Rule:** Use the Vorlage's EXACT projected continent viewBoxes verbatim in `CONTINENT_VIEW`
(in `scouting.js`). Do NOT self-compute viewBoxes, and do NOT try to force every viewBox to
match the `.sc-map-stage` aspect ratio. The reference viewBoxes (keyed by continent slug):
welt `5.6 19.4 988.8 386.2`; europa `463.9 50 155.5 108.3`; nordamerika `27.8 44.4 333.3 191.7`;
suedamerika `269.4 211.1 138.9 194.5`; afrika `444.4 141.7 202.8 211.1`;
asien `572.2 77.8 344.5 202.8`; ozeanien `800 266.7 200 122.2`.

**Why:** The old map used a DIFFERENT SVG (intrinsic `0 0 1010 666`, data-iso2 from a non-Natural-Earth
source) with viewBoxes hand-padded to the stage aspect. That projection did not match the Vorlage,
so zoom/shape looked wrong and the user explicitly said "everything needed was already provided".
Regenerating world.svg straight from the reference + copying its viewBoxes is what makes it 1:1.
With `meet`, mismatched aspect just letterboxes (here = ocean), which is the intended look — chasing
a shared aspect ratio is the trap that broke fidelity before.

**How to apply:**
- Regions DO have their own Vorlage sub-views now: `REGION_VIEW` carries the exact per-region
  viewBox for all 24 granular keys (copied 1:1 from the Vorlage), and `REGION_CONT` maps each
  key to its parent continent only for dimming. A region missing from `REGION_VIEW` falls back
  to its continent zoom.
- Country/chip jumps resolve via `contract[key].continent` (slug) → `CONTINENT_VIEW[slug]`; the SVG's
  `data-continent` must use the same slugs (europa/nordamerika/suedamerika/afrika/asien/ozeanien).
- Focus dimming: toggle `.is-dimmed` on paths whose `data-continent` ≠ focused key (welt clears all).
- Stage is capped (`.sc-map-stage { max-height }`) so the coverage bar + country chips below the map
  are not pushed off the 1440×900 fold — that was the "abgeschnitten" complaint, not SVG cropping.
- Colors are dezent, NO red: locked/unavailable = slate `rgba(35,55,65,.45)`.
- Verify visually per continent — the screenshot browser is logged out, so temporarily remove
  `@login_required` on `transfer_scouting`, screenshot `?kontinent=<slug>`, then RESTORE it.
