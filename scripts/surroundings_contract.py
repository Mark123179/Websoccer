"""Shared offline contract. No Django, database writes or production assets."""
import hashlib
import json
import math
import re
from pathlib import Path
from urllib.parse import urlparse

import numpy as np
from PIL import Image, ImageDraw

from geo_probe_geometry import (
    frame_from_osm, ground_rays, lonlat_to_scene, polygon_mask,
    raster_xy, sample_raster, scene_to_lonlat,
)
from probe_image_evidence import verify_probe_image

ROOT = Path(__file__).resolve().parents[1]
ADAPTERS = {"unity-dortmund", "blueprint-v2"}
CATEGORIES = {
    "outside": (35, 170, 105), "cut_stand": (242, 146, 44),
    "inside_other": (126, 103, 163), "occluded": (48, 62, 75),
    "pitch": (224, 237, 228),
}


def read_json(path):
    return json.loads(Path(path).read_text())


def digest(value):
    data = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(data).hexdigest()


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_profile(path):
    profile = read_json(path)
    if profile.get("version") != 1 or not re.fullmatch(r"[a-z0-9-]+", profile.get("id", "")):
        raise ValueError("Invalid profile version/id")
    if profile.get("model_adapter") not in ADAPTERS:
        raise ValueError("Unsupported model adapter; calibrate explicitly, no generic substitute.")
    if profile["ground_source"]["type"] not in {"orthophoto", "osm-schematic"}:
        raise ValueError("Unsupported ground source")
    if profile["ground_source"]["type"] == "orthophoto" and not profile.get("photo_stadium_removal"):
        raise ValueError("Orthophoto needs an explicit source-image stadium removal mask; footprint alone is insufficient")
    for field in ("rear_stand", "hidden_front_stand", "gaps", "camera_bearing_deg"):
        if field not in profile:
            raise ValueError(f"Missing profile field: {field}")
    for reference in profile.get("photo_references", []):
        if urlparse(reference["url"]).scheme not in {"https", "http"}:
            raise ValueError("Photo source must use an HTTP(S) URL")
    return profile


def camera_for(export):
    first = export["states"][0]
    return {"format": export["fitted"]["format"], "position": export["fitted"]["position"],
            "projection": first["projection"], "worldInverse": first["pose"],
            "corners": first["corners"]}


def validate_export(profile, export, approved):
    if export["fitted"].get("fieldScale") != .75 or export["fitted"]["format"] != [1880, 940]:
        raise ValueError("Expected approved 75% camera / 1880×940")
    states = [s for s in export["states"] if s["club"] == profile["id"] and
              s.get("variant", "day") in {"day", "night"}]
    combinations = {(s["roof"], s.get("variant", "day")) for s in states}
    if len(states) != 4 or combinations != {(r, v) for r in (True, False) for v in ("day", "night")}:
        raise ValueError("Both roofs and both times required; missing or duplicate state")
    for state in states:
        if any(state[k] != approved[k] for k in ("projection", "pose", "corners")):
            raise ValueError("Approved field camera changed")
        orientation = state["orientation"]
        if (orientation["modelTurnDegrees"] != 180 or
                orientation["rearStand"] != profile["rear_stand"] or
                orientation["hiddenFrontStand"] != profile["hidden_front_stand"]):
            raise ValueError("Profile/model orientation mismatch")
        if not state["roof"] and state["visibleRoofMeshes"] != 0:
            raise ValueError("Roof-off failed")
    return states


def source_geometry(profile, camera):
    # Reuse the existing source renderer, not a new hand-drawn locality.
    from build_dortmund_geo_probe import osm_raster
    osm = read_json(ROOT / profile["osm_file"])
    ways = {e["id"]: e for e in osm["elements"] if e["type"] == "way"}
    source = profile["ground_source"]
    if source["type"] == "orthophoto":
        metadata = read_json(ROOT / source["metadata"])
        frame, bbox = metadata["frame"], metadata["bbox_3857"]
        raster = Image.open(ROOT / source["image"]).convert("RGB")
        source_details = {**metadata, "raster_sha256": file_sha(ROOT / source["image"])}
    else:
        frame = frame_from_osm(osm, profile["stadium_way"], profile["pitch_way"])
        raster, bbox = osm_raster(osm, frame)
        source_details = {
            "source": "Original local OSM extract, schematic ground polygons",
            "license_url": "https://www.openstreetmap.org/copyright",
            "osm_timestamp": osm.get("osm3s", {}).get("timestamp_osm_base"),
            "frame": frame, "bbox_3857": bbox, "capture_date": None,
        }
    clon, clat = scene_to_lonlat(frame, *[camera["position"][i] for i in (0, 2)], True)
    lon0, lat0 = scene_to_lonlat(frame, 0, 0, True)
    bearing = math.degrees(math.atan2((clon-lon0)*math.cos(math.radians(clat)), clat-lat0)) % 360
    if abs((bearing-profile["camera_bearing_deg"]+180) % 360-180) > .1:
        raise ValueError("Geographic heading differs from calibrated profile")
    ground = ground_rays(camera)
    lon, lat = scene_to_lonlat(frame, ground[0], ground[2], True)
    rx, ry = raster_xy(bbox, raster.size, lon, lat)
    plane = sample_raster(raster, rx, ry, (camera["format"][1], camera["format"][0]))
    photo_mask, projected_photo_mask = None, np.zeros(plane.shape[:2], dtype=bool)
    removal = profile.get("photo_stadium_removal")
    if removal:
        if removal["type"] != "source-raster-polygons" or list(raster.size) != removal["source_size"]:
            raise ValueError("Photo removal mask type/size mismatch")
        if source_details.get("raster_sha256") != removal["source_sha256"]:
            raise ValueError("Photo source changed; visually recalibrate its stadium removal mask")
        photo_mask = Image.new("L", raster.size, 0)
        draw = ImageDraw.Draw(photo_mask)
        for polygon in removal["polygons"]:
            if len(polygon) < 3 or any(not (0 <= x < raster.width and 0 <= y < raster.height) for x, y in polygon):
                raise ValueError("Invalid source-raster removal polygon")
            draw.polygon([tuple(p) for p in polygon], fill=255)
        projected_photo_mask = sample_raster(photo_mask.convert("RGB"), rx, ry, plane.shape[:2])[:, :, 0] > 0
    def scene_polygon(geometry):
        return [lonlat_to_scene(frame, p["lon"], p["lat"], True) for p in geometry]
    site = polygon_mask(camera, scene_polygon(ways[profile["stadium_way"]]["geometry"]))
    pitch = polygon_mask(camera, [(-52.5, -34), (52.5, -34), (52.5, 34), (-52.5, 34)])
    hidden = profile["hidden_footprint"]
    if hidden["type"] == "osm-ring":
        relation = next(e for e in osm["elements"] if e["id"] == hidden["relation_id"] and e["type"] == "relation")
        inner = next(m for m in relation["members"] if m.get("role") == "inner")
        cut = site & ~polygon_mask(camera, scene_polygon(inner["geometry"]))
    elif hidden["type"] == "blueprint-stand":
        model = read_json(ROOT / hidden["path"])
        cut = np.zeros_like(site)
        for block in model["blocks"]:
            if block["stand"] == hidden["stand"]:
                cut |= polygon_mask(camera, [(-x, z) for x, z in block["quad"]])
        for way in ways.values():
            if way.get("tags", {}).get("building") == "grandstand":
                cut |= polygon_mask(camera, scene_polygon(way["geometry"]))
    else:
        raise ValueError("Unsupported hidden-stand footprint")
    cut &= (ground[2].reshape(site.shape) > 35) & site & ~pitch
    return {"frame": frame, "osm": osm, "plane": plane, "raster": raster,
            "site": site, "pitch": pitch, "cut": cut, "bearing": bearing,
            "source_details": source_details,
            "photo_removal_mask": photo_mask, "projected_photo_removal": projected_photo_mask}


def visibility_masks(geometry, silhouette):
    site, pitch, cut = (geometry[k] for k in ("site", "pitch", "cut"))
    occupied = np.asarray(silhouette) > 128
    if occupied.shape != site.shape:
        raise ValueError("Silhouette dimensions mismatch")
    masks = {"outside": ~site & ~pitch & ~occupied,
             "cut_stand": cut & ~occupied,
             "inside_other": site & ~pitch & ~cut & ~occupied,
             "occluded": occupied & ~pitch, "pitch": pitch}
    if not np.all(sum(m.astype(int) for m in masks.values()) == 1):
        raise ValueError("Visibility categories overlap or leave gaps")
    return masks


def background_registration(camera, frame):
    # Deliberately excludes roof, current mesh/stand footprint and capacity.
    return digest({"camera": camera, "frame": frame, "mapping": "X=-u,Z=v"})


def composite(background, original, silhouette, pitch):
    background, original = np.asarray(background.convert("RGB")), np.asarray(original.convert("RGB"))
    if background.shape != original.shape or background.shape[:2] != pitch.shape:
        raise ValueError("Composite dimensions mismatch")
    keep = (np.asarray(silhouette) > 128) | pitch
    result = background.copy()
    result[keep] = original[keep]
    if not np.array_equal(result[pitch], original[pitch]):
        raise ValueError("Protected pitch changed")
    return Image.fromarray(result)


def verified_states(profile, base, approved_path):
    export = read_json(base / "verification.json")
    approved = read_json(approved_path)["states"][0]
    states = validate_export(profile, export, approved)
    images = {}
    for state in states:
        variant = state.get("variant", "day")
        images[(state["roof"], variant)] = verify_probe_image(base, state, export["fitted"], "render")
        if variant == "day":
            images[(state["roof"], "silhouette")] = verify_probe_image(base, state, export["fitted"], "silhouette")
    return export, states, images
