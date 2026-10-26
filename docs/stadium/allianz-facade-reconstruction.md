# Allianz Arena lower facade closure

The source manifest `915.json` identifies four lower perimeter wall meshes
with exact path IDs and untextured `st011_wall200.*` materials. Their geometry
contains two exterior wall bands: approximately y=9.52–15.37 m and
y=29.11–34.51 m. The source does not include a continuous wall surface in the
intervening 13.73 m interval, which leaves the upper shell visibly detached
from the lower structure.

`allianz_presentation.js` derives a display-only closure from the outer radial
profiles of those four confirmed source meshes at y≈15.37 m and y≈29.11 m.
It interpolates between those profiles to create a continuous circumferential
surface. The surface is named `DERIVED_Allianz_lower_facade_closure` at
runtime and is tagged as reconstruction in `userData`; it is not part of the
source geometry, not a measured survey, and does not modify the model manifest,
capacity, seats, interior or environment.

The derived surface uses the existing Allianz day/night facade finish. The
pre-existing source wall bands and lower red trim remain intact. The renderer's
independent floodlight control, grey inner roof rim and other-club behavior are
unchanged.
