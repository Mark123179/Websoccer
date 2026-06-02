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

## TPS anchor hull + residual error for Italian cities
The current TPS has 14 anchors; the easternmost is the Calabria boot-toe at 15.64°E.
East of ~15.6°E (Lecce, Balkans, Greece, Turkey) → extrapolates badly into the sea.

**Even inside the hull (Italy), TPS has ~8-10px residual error** — confirmed 2026-06
via direct RGB analysis: the TPS-predicted pixel for Naples (40.85°N,14.27°E) shows
rgb(85,83,77) warmth=+7, while the actual Naples satellite light cluster is 10px west
at rgb(185,169,147) warmth=+30. Similarly, TPS-Roma pixel shows rgb(19,25,29) coldly
dark; real Rome lights are 8px east at rgb(214,198,176) warmth=+30.

**How to verify any Italian pin:** use RGB warmth analysis — pixel-sample the CITY_MAP_PCT
pixel and check `warmth = (R+G)//2 - B`. Warm urban lights: warmth > +20. Cold/sea: warmth < 0.
If the current pin is cold, scan ±40px for the warmest cluster and move there.
Formula: `warmth = (R+G)//2 - B`; check a 7×7 neighborhood average.

**Correction values (2026-06, verified):**
- Roma NEW (46.88, 74.22) = px(720,760) rgb(214,198,176) warmth=+30
- Napoli NEW (47.27, 77.64) = px(726,795) rgb(185,169,147) warmth=+30

**Berlin note:** TPS pixel(760,480) is geometrically correct (verified by triangle
interpolation from Skagen/Frankfurt/Stockholm anchors: geometric estimate px(765,478)
matches TPS). The brightest nearby cluster (px 772,474) is east of Berlin in the
Oder/Strausberg region — do NOT move Berlin there.

- East of 15.6°E → hand-pin from coastlines/borders; TPS drifts into the sea.
  Lecce (18.17°E) kept near old visual value (50.5, 79.8) not TPS (51.9, 78.7).
  For dim regions (Balkans) brightening PIL crop ×2.6 reveals borders for geography.

## Sicily / southern Italy: TPS y% lands in the sea (~4-5% too north)
The perspective globe render places Sicily ~4-5% further SOUTH on the image than
TPS extrapolates from the mainland anchors. A southward brightness scan from Naples
at x%=47.9 confirms the sea is dark from y%=80–88%; Sicily lights begin at y%≈88.5.
- **Catania** (47.61%, 86.01% by TPS) → sea; scan peak at TPS x=47.61, y≈89.5; pinned (47.6, 89.5)
- **Palermo** (45.97%, 84.25% by TPS) → sea AND TPS x is slightly too west (its column is dark through Sicily's y-range); pinned (46.5, 90.0)
- **Reggio Calabria** (48.41%, 84.44% by TPS) → dark but ON LAND; the Calabria tip anchor (15.64°E, 37.65°N) at pixel (48.24%, 85.64%) is also dark/verified; Reggio 0.46° north at same longitude is correctly placed; pinned (48.4, 84.4)
- **Bari** (TPS 50.76%, 76.66%) → slightly outside hull; EUROPEAN_CITY_COORDS cross-ref gives (308,258) → (49.5%, 77.3%); pinned (49.5, 77.3)
**EUROPEAN_CITY_COORDS** (secondary pixel table, ~line 504) mirrors these; updated Palermo→(286,303), Catania→(294,302), Reggio→(300,283), Bari already correct at (308,258).
**Key diagnostic:** the Calabria column (x%≈48) is completely dark from y%=83–88 because TPS anchor lands on the narrow unlit peninsula; darkness ≠ sea for the boot. The Sicily band brightness at that same x-column (y%=88.5–91.5) is Sicily's lights, NOT mainland.

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
