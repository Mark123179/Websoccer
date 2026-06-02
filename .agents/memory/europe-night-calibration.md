---
name: europe-night.png lat/lng calibration
description: How to calibrate lat_lng_to_map_pct() against the europe-night.png satellite map
---

`lat_lng_to_map_pct()` (game/views.py) maps real lat/lng to x/y percent on
`europe-night.png` (1536×1024). x is linear in longitude; y is linear in the
Mercator-projected latitude (`merc_y = ln(tan(pi/4 + lat/2))`).

**Why this was hard / the durable lessons:**
- A 2-point fit (e.g. only London + Milan) compounds errors badly — south-German
  cities ended up ~10° too far north (München rendered near Berlin). Use a
  multi-point least-squares fit across well-separated, isolated cities.
- Auto brightness-peak search snaps to the wrong cluster for any city near a
  brighter neighbour. Barcelona/Naples peaks jumped to southern France / wrong
  spots; sanity-check by confirming cities at the same latitude get the same y.
- Good isolated anchors that worked: London, Madrid, Paris, Rome, Berlin, Milan.

**How to apply:** if markers drift, re-fit with these 6 anchors, verify residuals
are < ~±2.5%, and confirm visually on `/manager/profil/` that München sits in
southern Bavaria (north of the Alps, south of Berlin).
