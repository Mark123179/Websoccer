"""Resolve current persisted geometry/design without importing HTTP views."""
from copy import deepcopy

from .live_scene import build_live_scene, standard_design_for_geometry
from .models import StadiumDesign, StadiumGeometry
from .capacity import distribute_capacities
from .contracts import geometry_blocks


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
    return build_live_scene(stadium, geometry, payload)
