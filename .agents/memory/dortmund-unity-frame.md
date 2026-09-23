---
name: Dortmund Unity seat and mesh frames
description: Why Unity seating JSON must be aligned with exported world meshes before expanding a stand.
---

The Dortmund seating JSON uses its unrotated section frame, while the exported
mesh vertices have the parent's 90° Y rotation baked in. For comparisons,
transform seat positions `(x,y,z)` into mesh coordinates `(z,y,-x)`, and
rotate chair orientation accordingly. Do not infer the physical side from
mesh naming alone; some named structural pieces cross stand boundaries.

**Why:** A first expansion put seat rows on a different axis from the roof.
Comparing the source back-section seat bounds with the `C_back2` world-mesh
bounds exposed the 90° mismatch. A roof-clearance calculation in mismatched
frames can look numerically plausible while moving the wrong stadium edge.

**How to apply:** Before using newly exported Unity geometry with seat JSON,
check transformed section-seat bounds against the corresponding named
crowd-surface bounds on all four sides. Use world-space positions, not a
mesh-name prefix, to determine which side receives a displacement.