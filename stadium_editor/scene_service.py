"""Resolve current persisted geometry/design without importing HTTP views."""
from copy import deepcopy

from .live_scene import build_live_scene, standard_design_for_geometry
from .models import StadiumDesign, StadiumGeometry
from .capacity import distribute_capacities
from .contracts import geometry_blocks
from .model_registry import model_manifest
from .seat_design import seat_mode


def current_live_scene(stadium):
    row = StadiumGeometry.objects.get(stadium=stadium)
    geometry = deepcopy(row.geometry)
    if row.steckbrief:
        geometry["steckbrief"] = deepcopy(row.steckbrief)
    design = StadiumDesign.objects.filter(stadium=stadium).first()
    effective = distribute_capacities(stadium, geometry)
    trusted = {block["id"]: block for block in geometry_blocks(effective)}
    for position, block in enumerate(effective["blocks"]):
        block.update(trusted[block.get("id", position)])
    original = standard_design_for_geometry(stadium, effective)
    saved = deepcopy(design.design) if design is not None else {}
    mode = seat_mode(saved)
    payload = saved if mode == "custom" else deepcopy(original)
    if mode == "original" and "grass_variant" in saved:
        payload["grass_variant"] = saved["grass_variant"]
    scene = build_live_scene(stadium, geometry, payload)
    scene["seatMode"] = mode
    scene["originalDesign"] = original
    if stadium.club.fm_inside_id == 907:
        from .dortmund_runtime import runtime_presentation
        from .seat_design import source_seat_design
        scene["presentation"] = runtime_presentation(stadium, geometry, saved)
        scene["presentation"]["seatDesign"] = source_seat_design(geometry, saved)
    elif (manifest := model_manifest(stadium.club.fm_inside_id)) is not None:
        from .unity_runtime import unity_presentation
        scene["presentation"] = unity_presentation(stadium, geometry, saved, manifest)
    return scene
