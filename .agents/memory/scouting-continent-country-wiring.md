---
name: Scouting continent/country wiring
description: How the scouting map dropdown, regions and countries are wired across constants.py, world.svg and scouting.js — and the gotchas when adding one.
---

# Scouting continent / region / country wiring

Three independent dicts in `game/scouting/constants.py` drive everything; they are NOT
cross-validated, so keep them consistent by hand:

- `CONTINENTS` → the only thing that drives the `#continent-select` map-focus dropdown
  (via `coverage.map_data()['continents']`). Adding a continent here is enough to make it
  appear and let the map zoom/dim to it.
- `REGIONS` → the "Region wählen" dropdown (granular Vorlage set, 24 keys; ordered by
  continent so Django `{% regroup region_options by continent_name %}` produces stable
  `<optgroup>`s). A region WITHOUT countries is intentional and NOT broken: it stays
  selectable as a map-zoom preset / future scaffolding (na_*, as_central/south/southeast,
  as_russia, oc_newzealand currently have no catalog countries). Selecting+scouting such a
  region is rejected cleanly by `is_region_scoutable()` (<100 pool players → `ScoutingError`).
  Region selection does NOT filter the country grid/chips — it only sets the scope + zooms.
- `COUNTRIES` → scoutable catalog. The country grid and scope chips are **not** filtered by
  the selected continent; the continent dropdown only controls map zoom/dimming.

**Hand-kept key parity (footgun):** every `REGIONS` key MUST appear in BOTH `scouting.js`
`REGION_CONT` (region→continent dimming) and `REGION_VIEW` (region→viewBox zoom), and every
`COUNTRIES[x]['region']` must exist in `REGIONS` with a matching continent. Nothing validates
this at runtime; a missing JS key silently falls back to the continent zoom. Verify after any
edit. `map_data()['regions']` carries `continent_name` (from `CONTINENTS`) purely for the
optgroup grouping.

Map focus is purely frontend: `scouting.js` `CONTINENT_VIEW` (per-continent viewBox),
`REGION_CONT` (region→continent for dimming), optional `REGION_VIEW`. `world.svg` paths carry
`data-iso2` / `data-name` / `data-continent`; dimming toggles `is-dimmed` by `data-continent`.

**Rule:** a `COUNTRIES[x]['continent']` MUST equal that country's `data-continent` in
`world.svg`. If they disagree, clicking the country on the map sets the dropdown to the
*catalog* continent (selectScope reads the contract), bouncing focus to the wrong continent.
(This is exactly why AU had to move from `asien` to `ozeanien` when Australien/Ozeanien was
added as a continent.)

**Gotcha — catalog country without a network renders nowhere:** `coverage.country_status()`
returns `STATUS_UNAVAILABLE` for any catalog country with no `CountryNetwork`, and the view
filters out `unavailable` tiles. So adding a country to `COUNTRIES` without seeding a network
(and a player pool to reach scoutable) shows it neither as a scope chip nor a grid tile — it
only appears as the static SVG landmass. Don't add catalog countries just for map visibility.

**Why:** world.svg was pre-tagged and `CONTINENT_VIEW` pre-calibrated for `nordamerika` and
`ozeanien` long before they were exposed, so enabling them was a `CONTINENTS` one-liner (+ AU
re-tag + an Ozeanien region). Remember to bump the `scouting.js` `?v=` cache-bust in
`scouting.html` on any JS edit.
