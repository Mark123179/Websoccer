---
name: europe-night.png map markers (calibration + custom stations)
description: How lat/lng → pixel works on the europe-night.png satellite map, and how career stations resolve their location
---

`lat_lng_to_map_pct()` (game/views.py) maps real lat/lng to x/y percent on
`europe-night.png` (1536×1024). The image is a **perspective satellite render
("tilted globe"), NOT a flat map projection** — scale and rotation vary across it.
A single affine, Mercator, homography, or even a 2nd-order polynomial all leave
~25–40px residuals (south-German cities too far north; Barcelona drifted over the
Pyrenees into France).

**The model that works: thin-plate spline (TPS).** Fit (lng,lat)→(px,py) as a TPS
through hand-verified light-cluster pixels of ~10 well-spread, *unambiguous*
cities (clear starbursts + isolated coastal clusters: madrid, barcelona, lisbon,
porto, paris, london, amsterdam, lyon, milan, rome). TPS interpolates the anchors
exactly and warps smoothly between them. The fitted radial weights + affine part
are embedded as `_MAP_TPS_*` constants; `_tps_eval()` evaluates them at runtime.
**Why:** a global parametric formula cannot absorb the perspective distortion; TPS
is the cleanest model that nails the anchors and stays smooth inside their hull.

**Anchor-pinning method (the part that took the most tries):**
- Use a labelled pixel-coordinate grid overlaid on the image, then zoom-crop each
  city and take the brightness peak inside a *tight* box. Loose boxes snap to a
  brighter neighbour (the recurring failure mode).
- Pick only cities that are clear isolated starbursts or coastal clusters. German
  cities (Munich, Berlin, Hamburg, Frankfurt) are **diffuse and unreliable** to
  pin — they gave the worst residuals. Do NOT use them as anchors; instead fit on
  the reliable set and *verify* the German predictions visually (mark predicted
  pixels on the image and confirm they land on the right city). Keep all station
  cities inside the convex hull of the anchors to avoid extrapolation.

**Custom career stations (no linked club):** `ManagerCareerStation` stores only
legacy `map_x/map_y` (a different small internal map) + `city_name`/
`custom_club_name`, NOT lat/lng. Club-linked stations already carry real
`club.public_profile.map_lat/map_lng`. For custom ones, `resolve_city_latlng()`
looks the name up in `REAL_CITY_LATLNG` (a hand-keyed table of **real** lat/lng,
exact then prefix match so typos like "Barcelon" still resolve) and feeds that
straight into the TPS. **Why a real-coords table, not the legacy map_x/map_y
conversion:** going name→legacy-pixel→lat/lng→satellite-pixel compounds two lossy
approximations (~2°+ error); real coords skip the first hop. The edit-drawer
autocomplete only sets map_x/map_y on an exact match, so typos silently keep the
(271,214) München default — that is why name resolution server-side is the safety
net.

**How to apply:** if markers drift, re-pin the anchor pixels with the grid/zoom
method and re-solve the TPS, confirm anchor residual ≈ 0 and that München sits in
southern Bavaria and Barcelona on the NE-Spanish coast on `/manager/profil/`. Add
new custom cities to `REAL_CITY_LATLNG`, not to the legacy table.
