# Natural stadium assets — visual library v2

## Sketchfab models

- “Realistic Trees Collection” by Jungle Jim, https://sketchfab.com/3d-models/realistic-trees-collection-fe67c886eebf4bcb988d7c45e69995ad — CC BY 4.0, https://creativecommons.org/licenses/by/4.0/. Changes: selected glTF objects are rendered offline into multi-view, alpha-bearing 2048px WebP impostor atlases. The supplied archive remains in `attached_assets/`.
- “oak trees” by DJMaesen, https://sketchfab.com/3d-models/oak-trees-d841c3bcc5324daebee50f45619e05fc — CC BY 4.0. Changes: selected large oak rendered offline into a multi-view 2048px WebP impostor atlas. The supplied archive remains in `attached_assets/`.
- “Various Forest Assets Pack” by Dari, https://sketchfab.com/3d-models/various-forest-assets-pack-cf138b8eb2d340cda643ed59f824989c — CC BY 4.0. Changes: selected birch, maple, and deciduous shrub rendered offline into multi-view 2048px alpha WebP impostor atlases. The supplied archive remains in `attached_assets/`.
- “Generic passenger car pack” by Comrade1280, https://sketchfab.com/3d-models/generic-passenger-car-pack-20f9af9b8a404d5cb022ac6fe87f21f5 — CC BY 4.0. Changes: local source glTF and textures are instanced on mapped OSM parking polygons; no geometry is invented. Original files retained under `models/generic_passenger_car_pack/`.

Each source package includes the author's original `license.txt`. The supplied archives remain in the workspace's `attached_assets/`; only the car source model and its textures are needed in the runtime static bundle. The three tree source archives are staged temporarily for regeneration and then removed from runtime output by `tools/prepare_natural_graphics.py`. These are attribution licenses, not a blanket assertion that all source objects are used.

Model selection is deliberate: two representative broadleaf tree objects from Realistic Trees Collection, one mature oak from oak trees, and a birch, maple, and deciduous-shrub visual representative from Various Forest Assets Pack. The 334 source tree points are preserved at their exact coordinates. Additional forest and scrub representatives are deterministic, bounded to their corresponding OSM forest/scrub polygons, exclude tagged grass/sports/buildings/surface parking, and are limited to the camera-west half to avoid inventing a tree wall east of the pitch. These representatives express broad mapped land-cover classes; they do not assert a location-specific species. All ten car body variants in Generic passenger car pack are eligible, deterministically selected for visual fill only.

## Poly Haven (CC0)

- Kloofendal 48d Partly Cloudy (Pure Sky), https://polyhaven.com/a/kloofendal_48d_partly_cloudy_puresky — 2K HDR.
- Kloppenheim 07 (Pure Sky), https://polyhaven.com/a/kloppenheim_07_puresky — 2K HDR.
- Aerial Grass Rock, https://polyhaven.com/a/aerial_grass_rock — 2K diffuse, physically tiled over mapped OSM green/forest/scrub polygons.
- Grass Ground, https://polyhaven.com/a/grass_ground — 2K diffuse; used on tagged grass soccer pitches and allotment/ground details, with a restrained green pitch tint.
- Aerial Asphalt 01, https://polyhaven.com/a/aerial_asphalt_01 — 2K diffuse.

## Place data

The mapped environment is supplied separately as the version-1 natural-surroundings package with `visualVersion: 2`. Its source attribution and ODbL obligations remain with the parent Django package/OSM data. This visual library does not query OSM. Areas without source surface tags use a muted, untextured ground base rather than inventing a continuous park or paved area.

Parking polygons are exactly the supplied OSM `parking=surface` features; street-side and untyped parking features are excluded. Display-only cars use a seeded 70% graphic fill on 2.5 × 5m bays, with an aisle every second 5m depth row. Every car footprint stays inside its mapped polygon, outside buildings, and at least 2.5m from source/generated trees and scrub representatives. These vehicles are not live occupancy data. Desktop shadows are 4096px PCFSoft; small-screen/high-DPI mode uses 2048px PCFSoft.

The imported package currently states `model.mirror: false` and `verified: false`. The evidence is limited: seat data is brought into mesh coordinates by the recorded 90° parent transform `(x,y,z) → (z,y,-x)`, and the mapped scene records a pitch-west camera frame with only approximate north/OSM registration. The sources contain no stand-specific registration tying Unity `SUED` or a positive mesh axis to Dortmund's physical Südtribüne, and no matched physical-side comparison establishes that mapping. A seat-frame rotation resolves an axis mismatch; it does **not** verify a south-stand reversal. No mirror has been applied and calibration is not claimed as verified. If later physical evidence establishes `model.mirror: true`, the natural admin wrapper supports a longitudinal-Z model-root mirror only; mapped OSM coordinates and source mesh bytes remain unchanged.

## Offline preparation

`tools/bake_impostor_atlases.mjs` renders source GLTF trees/shrubs with the locally vendored Three.js r170 GLTFLoader, matched to the site's existing Three.js r170 runtime. Each atlas is 2048×2048 with retained alpha; 64 tiles sample the upper-hemisphere octahedral direction grid. Alpha-preserving WebP is used to reduce transfer size without reducing atlas resolution. Rebuild with `python tools/prepare_natural_graphics.py`; this safely stages the supplied tree archives, generates six atlases, and removes tree source copies afterward. The car model remains locally available for runtime loading; no external download is needed.

The separately copied GLTFLoader and BufferGeometryUtils modules are Three.js examples code under the MIT license and import the existing site Three.js r170 module by relative path. The product-wide Three.js installation/version was not changed.
