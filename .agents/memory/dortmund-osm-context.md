---
name: Dortmund OSM context
description: Source and calibration limits for a real-world 3D setting around the Dortmund stadium concept.
---

Use real mapped surroundings and terrain relief for the Dortmund concept,
but label them as a simplified local extract, not surveyed construction data.
Do not add imaginary mountains when the DEM shows only local hills. Individual
tree locations can come from OSM, but their heights and species remain generic.

**Why:** The user explicitly chose location-based 3D OSM context rather than a
schematic backdrop. OSM alone has no continuous terrain height field, and the
source Unity model has no reliable north orientation. Exact alignment and
landscape fidelity cannot be inferred from the stadium mesh or its name.

**How to apply:** Pair a locally stored OSM extract with a separate elevation
source, retain attribution, calibrate the OSM stadium outline against the
3D-model footprint, and disclose the coarse terrain resolution. Keep existing
site features distinct from hypothetical building additions; a conceptual
expansion may overlap today's mapped neighbors.