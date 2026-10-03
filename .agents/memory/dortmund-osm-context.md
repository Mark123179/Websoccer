---
name: Dortmund OSM context
description: Source and calibration limits for a real-world 3D setting around the Dortmund stadium concept.
---

Use real mapped surroundings and terrain relief **inside the interactive 3D
scene** for the Dortmund concept; a detailed 2D map below it is not a
substitute for a detailed 3D environment. Use real mapped surroundings,
but label them as a simplified local extract, not surveyed construction data.
Do not add imaginary mountains when the DEM shows only local hills. Individual
tree locations can come from OSM, but their heights and species remain generic.

**Why:** The user explicitly clarified that the additional detail belongs
directly in the 3D model rather than a separate map. OSM alone has no
continuous terrain height field, and the
source Unity model has no reliable north orientation. Exact alignment and
landscape fidelity cannot be inferred from the stadium mesh or its name.

**How to apply:** Pair a locally stored OSM extract with a separate elevation
source, retain attribution, calibrate the OSM stadium outline against the
3D-model footprint, and disclose the coarse terrain resolution. Keep existing
site features distinct from hypothetical building additions; a conceptual
expansion may overlap today's mapped neighbors.

## Productive editor: same surroundings as 2D

For the productive Dortmund editor, carry the **existing 2D surroundings**
into 3D instead of substituting the comparison concept's separate OSM extract.
The user chose a simplified 3D environment: mapped building footprints become
schematic volumes; mapped roads, green areas and water stay on the ground.
Use supplied editor tree locations or mapped trees from the already existing
Dortmund OSM extract, which the user approved adding to both views. Do not
scatter invented trees. A new DEM is not required for this transfer.

**Why:** The user explicitly said the environment present in 2D was missing
in 3D and asked to take that same environment into 3D, then approved the
simplified 3D representation.

**How to apply:** Keep the 2D and productive 3D source identical and preserve
their spatial relationship to the pitch. Do not infer matching coordinate
axes from matching stand names; verify the physical pitch axes. Align the
approved tree extract to the authoritative 2D pitch projection, not to the
comparison concept's independently fitted model scale.

## Neon appearance and trees

The user wants the productive 3D surroundings in the same dark neon scheme
as 2D: cyan map contours and green tree crowns, not a gray/olive environment.
Trees are an explicitly important part of this presentation. Their positions
are mapped; crown shapes, species and dimensions remain schematic.

**Why:** The user said: „Ich hätte es gerne in unserem Neon-Schema wie im 2D
und im Screenshot, wichtig dabei sind mir auch die Bäume“, then selected
mapped trees from the existing OSM extract.

**How to apply:** Preserve this environment style in both editor modes.
Do not interpret it as permission to recolor the stadium's original materials
or to replace mapped positions with decorative random placement.