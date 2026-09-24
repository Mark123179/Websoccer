---
name: Dortmund Bestand source attribution
description: Source evidence versus conjecture for the Dortmund facade and unknown Unity shader.
---

Do not fill apparent gaps in the Dortmund Bestand with invented exterior walls or glazing. The approved Rundum concept is a separate design state, not evidence of the existing stadium. Camera labels like „Gegenseite“ do not identify material or geometry provenance.

**Why:** A prior complaint about „Gegenseite“ meant Bestand, not Rundum; closing perceived gaps on two sides as „reconstructed facades“ invented source architecture. Conversely, hiding all `NoDraw_` faces made source-backed walls disappear. Their shader is unresolved but the saved material state has an enabled renderer, opaque blending, alpha 1, and no color texture.

**How to apply:** Verify model state, coordinates, mesh, renderer, shader and texture evidence before changing geometry. Show source-backed faces with an explicitly approximate source-derived color when their saved state supports it; do not infer Unity's exact output or close unproven gaps. Keep capacity and source data untouched.

For a disputed dark area, compare screenshot pixels with the scene's actual background color before diagnosing a dark material: one strip can include both existing dark parts and true openings. When auditing non-exported Unity meshes, use complete parent transforms, including nonzero positions on unrelated objects; the selected-mesh exporter's zero-translation assertion is not a general whole-bundle transform helper. Without the user's exact orbit values, describe the photographed side and source regions, not a supposedly exact per-pixel triangle match.