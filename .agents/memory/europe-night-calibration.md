---
name: europe-night.png map markers (calibration + custom stations)
description: How lat/lng → pixel works on the europe-night.png satellite map, and how career stations resolve their location
---

`lat_lng_to_map_pct()` (game/views.py) maps real lat/lng to x/y percent on
`europe-night.png`. The image is a **perspective satellite view, NOT a flat map
projection**, so scale varies across it — a separable x(lng)/y(lat) formula can
never fit everywhere and left south-German cities too far north.

**Calibration model (the durable fix):** use a full **affine** transform of
`(lng, merc_y)` where `merc_y = ln(tan(pi/4 + lat/2))`:
`x = a*lng + b*merc_y + c`, `y = d*lng + e*merc_y + f`. Fit by least-squares
against brightness-peak pixel positions of well-spread isolated cities (London,
Paris, Madrid, Barcelona, Rome, Milan, Berlin, Hamburg). Affine captures the
rotation/tilt; the separable model could not.

**Why brightness peaks mislead:** auto peak-search snaps to a brighter neighbour
for cities near bigger clusters. Verify by confirming same-latitude cities get
near-equal y. Pin positions from a fine-grid crop of the image, not eyeballing.

**Custom career stations (no linked club):** `ManagerCareerStation` stores only
the legacy `map_x/map_y` (small internal map) + `city_name/custom_club_name`, NOT
lat/lng. Club-linked stations use `club.public_profile.map_lat/map_lng`. Custom
ones used to fall back to München (48.22,11.55), so e.g. a "Barcelona" station
rendered hidden under München. Fix: `resolve_city_latlng()` looks the name up in
`EUROPEAN_CITY_COORDS` (exact then prefix match, so typos like "Barcelon" still
hit "barcelona") and converts via `map_xy_to_lat_lng()` (affine fit of the legacy
map_x/map_y → lat/lng). The edit-drawer autocomplete only sets map_x/map_y on an
exact CITY_COORDS match, so typos silently keep the (271,214) München default —
that is why server/marker-side name resolution is needed as a safety net.

**How to apply:** if markers drift, re-fit the affine with the isolated-city
anchors and confirm residuals < ~±3% and that München sits in southern Bavaria
on `/manager/profil/`. If a custom station lands on München, check its stored
map_x/map_y is the (271,214) default and rely on `resolve_city_latlng`.
