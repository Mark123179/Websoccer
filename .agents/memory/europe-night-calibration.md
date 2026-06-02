---
name: europe-night.png map markers (placement + rendering pitfalls)
description: How career-station markers are placed on the europe-night.png satellite map, and the two rendering bugs that make markers look off even when the pixels are right
---

The "Trainerstationen · Europa" map on `/manager/profil/` draws markers over
`europe-night.png` (1536×1024, a **perspective satellite render — a tilted globe,
NOT a flat projection**, so scale/rotation vary across it).

## Placement: hand-verified table first, TPS only as fallback
`CITY_MAP_PCT` (game/views.py) holds hand-verified `(x%, y%)` per city, pixel-pinned
against the image via a labelled calibration grid. The marker builder resolves a
station's city through `city_map_pct()` (exact then two-way prefix match, accent
tolerant) and uses the table when it hits; only unknown cities fall back to the
`lat_lng_to_map_pct()` thin-plate-spline formula. **Why table-first:** the TPS
genuinely drifts at the edges (Barcelona landed ~80px inland over the Pyrenees), so
fixed verified values beat the formula for the cities that actually appear.

## The trap: markers can be on the RIGHT pixel and still LOOK wrong
"Barcelona over the Pyrenees" was NOT a coordinate error — pixel (505,760) is
correctly on the NE-Spanish coast. Two *rendering* bugs shifted the visible marker:

1. **Vertical distortion + wrong zoom level.** The zoom JS must work in **image
   pixels** with ONE uniform scale (so the map keeps true 3:2 — no stretch) AND
   fill the whole tile while staying zoomed on the stations. The tile is a
   `flex:1` element so it is usually **wide and short**. `min()` (contain) is
   WRONG there — it shrinks the whole map with black bars. Correct recipe:
   (a) station bbox in px + padding, (b) **expand the bbox to the TILE's aspect
   ratio** (widen/heighten with real surrounding map so nothing is cropped),
   (c) scale `s = max(W/bw, H/bh)` (cover) so the tile is always filled,
   (d) centre on the bbox and clamp `left/top` to `[W-dispW,0]`/`[H-dispH,0]`.
   Size the bg `s*1536 × s*1024`; place markers with the same `s`/offset.
   Re-run on load + resize.
2. **Marker anchor — centre the CREST on the city, not the pin base.** The crest
   badge is the thing the eye reads as "the location", so it must sit ON the city.
   Make the crest the ONLY in-flow child (`.mp-photo-marker-ring` and
   `.mp-photo-marker-label` are `position:absolute`) and anchor with
   `transform: translate(-50%,-50%)` → crest centre lands on the coordinate; ring
   sits at `top:100%` (straddling the crest base) and label below it.
   **Why not anchor the pin base/ring-bottom:** that floats the visible badge
   ~50px above the city and reads as "Barcelona over France" even though the pixel
   is correct.

**Why both matter:** markers and bg share one scale/offset, so distortion never
moves a marker *relative to the map*; the perceived drift came from the anchor (1)
and the stretched coastline (2), not the math linking marker↔pixel.

## Verifying placement reliably
Don't eyeball the tiny/cut-off app screenshot — the satellite perspective fools you
(I twice misread the NE-Spain coast as SW France). Instead **simulate the exact JS
zoom crop in PIL** (resize the source by `s`, paste at the computed offset, draw the
markers) and read a high-res inset around the city. Confirm geography with
unambiguous anchors: Balearics below Barcelona, Sardinia to the SE.

**How to apply:** if a marker drifts, first decide whether it's the pixel or the
render. Add/adjust the city's `(x%,y%)` in `CITY_MAP_PCT` (verify on the grid), and
keep the uniform-scale zoom + label-out-of-flow anchor intact. Custom stations with
no linked club still resolve their name through the table; only truly unknown names
hit the TPS/`resolve_city_latlng` path.

## TPS drifts WEST-to-EAST; the anchor hull ends at Rome (~12.5°E)
The TPS anchors top out around Rome's longitude, so the formula *interpolates*
reliably across Iberia/France/UK/Benelux/Italy/Switzerland but *extrapolates*
(badly) for anything further east. Rome itself (the eastern boundary anchor) lands
~4-5% off onto Corsica; Belgrade (20.5°E) drifts clean into the Adriatic. So:
- West of ~12.5°E (incl. interior Spain, Scandinavia via coastlines) → TPS values
  verify dead-on against light clusters; trust them.
- East of it (Austria, Czechia, Poland, Hungary, Balkans, Greece, Turkey) → must be
  hand-pinned, and that region is **dim**: the bright squiggles there are mostly
  rivers/snow-capped Alps and white country-border overlays, NOT city lights.
  Brightening the PIL crop (`ImageEnhance.Brightness ~2.6`) exposes the borders so
  you can place by geography (coastline/border/river), but pixel-on-cluster accuracy
  is often not achievable — place by geography or leave to the formula.
**Why it matters:** don't add an eastern city to `CITY_MAP_PCT` claiming it's
"verified" when you only matched a river or border. Athens/Istanbul were left to the
formula for exactly this reason; Belgrade/Zagreb were corrected only because the
formula put them offshore and the coastline+borders pin them to the right land.

## South Germany is dim too — pin via affine fit from BRIGHT anchors, not eyeball
München/Stuttgart sit in the dim SE band, so eyeballing put München ~37px too far
WEST in a black patch (it "passt noch nicht" even though direction was right). The
reliable fix: fit an **affine lat/lng→pixel transform** (manual 3×3 least squares,
no numpy) from a handful of UNAMBIGUOUS bright-cluster anchors (Frankfurt, Paris,
Milano, Madrid, London) whose peaks you locate with a Gaussian-blur local-max search,
then project the target city. The fit has a mild eastward overshoot, so reconcile its
prediction with the nearest real light cluster (blurred local max within ~25px) and
snap there. München's true cluster is px (723,602) = (47.07%, 58.79%); the old dark
(706,613) had blur-val 44 vs 79 at the cluster. Validate the fit against a
known-good pin (Barcelona peak (510,757) ≈ pinned (505,760)).

## Zoom must leave bottom room for the southernmost station's LABEL
The label renders BELOW the crest, so a tight crop clips the bottom station's name
(Barcelona at the SW edge). In the zoom JS use an asymmetric bottom pad
(`padBottom = padY + IMG_H*0.055`) before the aspect-ratio expansion so the southern
label always clears the tile edge; top/side padding stay at `padY`/`padX`.
