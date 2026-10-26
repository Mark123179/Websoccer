"""Resolve current persisted geometry/design without importing HTTP views."""
from copy import deepcopy

from .live_scene import build_live_scene, standard_design_for_geometry
from .models import StadiumDesign, StadiumGeometry
from .capacity import distribute_capacities
from .contracts import geometry_blocks
from .model_registry import model_manifest


def current_live_scene(stadium):
    row = StadiumGeometry.objects.get(stadium=stadium)
    geometry = deepcopy(row.geometry)
    if row.steckbrief:
        geometry["steckbrief"] = deepcopy(row.steckbrief)
    design = StadiumDesign.objects.filter(stadium=stadium).first()
    if design is not None:
        payload = design.design
    else:
        effective = distribute_capacities(stadium, geometry)
        trusted = {block["id"]: block for block in geometry_blocks(effective)}
        for position, block in enumerate(effective["blocks"]):
            block.update(trusted[block.get("id", position)])
        payload = standard_design_for_geometry(stadium, effective)
    scene = build_live_scene(stadium, geometry, payload)
    if stadium.club.fm_inside_id == 907:
        from .dortmund_runtime import runtime_presentation
        scene["presentation"] = runtime_presentation(stadium, geometry, payload)
    elif (manifest := model_manifest(stadium.club.fm_inside_id)) is not None:
        from .unity_runtime import unity_presentation
        # The approved Allianz source seats must not be recoloured by a synthetic
        # fallback design. Explicitly saved manager designs still take precedence.
        presentation_design = {} if stadium.club.fm_inside_id == 915 and design is None else payload
        scene["presentation"] = unity_presentation(stadium, geometry, presentation_design, manifest)
    return scene
