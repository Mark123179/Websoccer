---
name: Dortmund roof layers
description: Why concept views need a visual inventory of overlapping exported Unity roof surfaces.
---

For a Dortmund concept that replaces the original roof, inspect the projected
horizontal triangle area of the exported structural meshes and verify from both
exterior and interior viewpoints. Several overlapping layers of roof skin,
ceiling and supporting structure can each cover the seating; hiding only the
obvious roof mesh leaves an apparently unchanged, opaque roof.

**Why:** A concept renderer initially concealed the new stands even though
its first roof mesh had been hidden. A projected-triangle-area inspection of
the original geometry found additional broad roof/ceiling surfaces that were
not apparent from names alone.

**How to apply:** Keep the original source binary intact. When conceptually
retiring its roof, identify every overlapping roof layer visually and preserve
the occupied seating and pitch. Verify the new geometry from the same outside
and inside camera positions rather than relying on a typecheck or mesh names.

For large conceptual builds beyond the measured source-roof footprint, prefer
deforming the exported roof, ceiling, truss and pylon triangles together while
retaining UVs; build any much larger supporting walls as explicitly new
conceptual geometry. A translucent presentation cutaway of the overlapping
source roof layers is acceptable if the viewer is told it is a cutaway, not an
authentic translucent roof. Close the visible wall-to-eave gap explicitly.

**Why:** An opaque enlarged original roof concealed the entire hypothetical
upper tier, while hiding its layers would falsely suggest the original geometry
was used in the extension. The source proves neither a 120,000-seat count nor a
structurally viable new outer shell.

**How to apply:** Keep source and assumption provenance separate in the UI,
retain the original opaque roof in the unchanged baseline, and compare exterior,
interior, corner and opposite viewpoints before treating a concept as integrated.

For Dortmund concept expansions, color every newly constructed rank, seat
symbol, facade, plinth and junction neutral grey; leave the exported Unity
meshes in their source preview materials, including their existing yellow.

**Why:** The user explicitly rejected treating hypothetical new additions as
yellow club-colored surfaces, and a solid yellow slab was read as neither seats
nor standing rows. Neutral micro-seat symbols with gaps express a possible
layout without implying a measured seat count.

**How to apply:** Distinguish source geometry from conceptual construction by
provenance and color. New seating marks are illustrative only; never count them
as evidence for a real stadium capacity.