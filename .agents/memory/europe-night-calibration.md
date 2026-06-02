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

1. **Vertical distortion.** The zoom JS sized the bg `width/height = S*100%` of a
   non-3:2 container with `object-fit:fill` → Europe stretched vertically. Fix:
   compute the station bounding box in **image pixels**, use a single uniform scale
   `s = min(W/bw, H/bh)` (contain), size the bg `s*1536 × s*1024` (true 3:2), and
   position bg + markers with that same `s`/offset in px. Re-run on load + resize.
2. **Marker anchor.** `.mp-photo-marker { transform: translate(-50%,-100%) }`
   anchored the bottom of the WHOLE flex box — and the lowest child was the label —
   to the coordinate, floating the visible ring/crest ~50px ABOVE the city. Fix:
   pull `.mp-photo-marker-label` out of flow (`position:absolute; top:calc(100%+2px)`)
   so the box bottom = the ring base, which then sits on the coordinate.

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
