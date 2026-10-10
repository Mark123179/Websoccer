"""Original-map visibility audit of BOTH clubs at the exact approved camera."""
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from geo_probe_geometry import (
    frame_from_osm, ground_rays, lonlat_to_scene, mercator, polygon_mask,
    raster_xy, sample_raster, scene_to_lonlat,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "generated-artifacts/stadium-main-stand-back-probe"
OLD = ROOT / "generated-artifacts/dortmund-site-study"
COLORS = {"outside": (35, 170, 105), "cut_stand": (242, 146, 44),
          "inside_other": (126, 103, 163), "occluded": (48, 62, 75),
          "pitch": (224, 237, 228)}


def osm_raster(osm, frame):
    """North-up original OSM polygons/ways, NOT an aerial photo."""
    lon, lat = scene_to_lonlat(frame, 0, 0, True)
    mx, my = mercator(lon, lat)
    bbox = [mx-900, my-900, mx+900, my+900]
    image = Image.new("RGB", (2048, 2048), "#e0e3df")
    draw = ImageDraw.Draw(image)
    for e in osm["elements"]:
        geometry, tags = e.get("geometry", []), e.get("tags", {})
        if len(geometry) < 2:
            continue
        points = [raster_xy(bbox, image.size, p["lon"], p["lat"]) for p in geometry]
        color = None
        if tags.get("landuse") in ("forest", "grass", "meadow") or tags.get("natural") in ("wood", "scrub"):
            color = "#88b28c"
        if tags.get("leisure") in ("pitch", "park"):
            color = "#a4c999"
        if tags.get("amenity") == "parking":
            color = "#b6bec4"
        if tags.get("building"):
            color = "#8e9296"
        if color and geometry[0] == geometry[-1]:
            draw.polygon(points, fill=color)
        if tags.get("highway"):
            draw.line(points, fill="#f8f6ec", width=5)
    return image, bbox


def check_camera(camera, states, approved):
    assert camera["format"] == [1880, 940]
    assert camera["modelTurnDegrees"] == 180
    assert camera["projection"] == approved["projection"]
    assert camera["worldInverse"] == approved["pose"]
    assert camera["corners"] == approved["corners"]
    assert len(states) == 4
    assert {(s["club"], s["roof"]) for s in states} == {
        (c, r) for c in ("dortmund", "elversberg") for r in (True, False)}
    for state in states:
        assert state["projection"] == camera["projection"]
        assert state["pose"] == camera["worldInverse"]
        assert state["corners"] == camera["corners"]
        assert state["orientation"]["modelTurnDegrees"] == 180
        assert state["roof"] or state["visibleRoofMeshes"] == 0


def audit_club(club, camera, states, ground):
    width, height = camera["format"]
    osm_path = ROOT / f"stadium_editor/blueprints/v2/{club}.json"
    osm = json.loads(osm_path.read_text())
    stadium_id, pitch_id = ((17235929, 17235988) if club == "dortmund"
                            else (1154632806, 31339206))
    ways = {e["id"]: e for e in osm["elements"] if e["type"] == "way"}
    if club == "dortmund":
        source = json.loads((OLD / "source.json").read_text())
        frame = source["frame"]
        raster_path = OLD / "orthophoto_north_up.jpg"
        raster = Image.open(raster_path).convert("RGB")
        bbox = source["bbox_3857"]
        provenance = {**source, "raster_sha256": hashlib.sha256(raster_path.read_bytes()).hexdigest()}
    else:
        frame = frame_from_osm(osm, stadium_id, pitch_id)
        raster, bbox = osm_raster(osm, frame)
        provenance = {"source": "Original local OSM extract, schematic ground polygons",
                      "license": "ODbL 1.0, © OpenStreetMap contributors",
                      "osm_timestamp": osm.get("osm3s", {}).get("timestamp_osm_base"),
                      "bbox_3857": bbox, "frame": frame, "capture_date": None}
    provenance["osm_sha256"] = hashlib.sha256(osm_path.read_bytes()).hexdigest()
    (OUT / f"{club}_source.json").write_text(json.dumps(provenance, indent=2))
    raster.save(OUT / f"{club}_source_north_up.png")
    lon, lat = scene_to_lonlat(frame, ground[0], ground[2], True)
    rx, ry = raster_xy(bbox, raster.size, lon, lat)
    plane = sample_raster(raster, rx, ry, (height, width))
    Image.fromarray(plane).save(OUT / f"{club}_ground_projection_raw.jpg", quality=94)

    def scene_poly(geometry):
        return [lonlat_to_scene(frame, p["lon"], p["lat"], True) for p in geometry]

    site = polygon_mask(camera, scene_poly(ways[stadium_id]["geometry"]))
    # Field keep-mask comes from the CURRENT 75% camera, never old pack masks.
    keep = polygon_mask(camera, [(-52.5, -34), (52.5, -34), (52.5, 34), (-52.5, 34)])
    if club == "dortmund":
        relation = next(e for e in osm["elements"] if e.get("id") == 531985)
        inner = next(m for m in relation["members"] if m.get("role") == "inner")
        stand_ground = site & ~polygon_mask(camera, scene_poly(inner["geometry"]))
        cut_stand = stand_ground & (ground[2].reshape(height, width) > 35)
        footprint_label = "OSM building stadium outer ring; hidden east stand = ring at scene Z > 35"
    else:
        # The leisure=stadium polygon is a site boundary, not a surveyed
        # building footprint. Report it as such; distinguish actual stands.
        mapped = np.zeros((height, width), dtype=bool)
        for e in osm["elements"]:
            if e.get("tags", {}).get("building") == "grandstand":
                mapped |= polygon_mask(camera, scene_poly(e["geometry"]))
        model = json.loads((ROOT / "stadium_editor/blueprints/v2/elversberg_v2.json").read_text())
        parametric = np.zeros_like(mapped)
        for block in model["blocks"]:
            if block["stand"] == "NORD":
                # New isolated adapter ends with X=-u, Z=v (two turns cancel).
                parametric |= polygon_mask(camera, [(-x, y) for x, y in block["quad"]])
        cut_stand = (mapped | parametric) & (ground[2].reshape(height, width) > 35)
        footprint_label = "OSM leisure=stadium site boundary; north stand additionally parametric model, not mapped survey"
    cut_stand &= site & ~keep
    categories = {}
    for roof in (True, False):
        stem = f"{club}_{'roof' if roof else 'no_roof'}"
        silhouette = np.asarray(Image.open(OUT / f"{stem}_silhouette.png").convert("L")) > 128
        assert silhouette.shape == site.shape
        masks = {"outside": ~site & ~keep & ~silhouette,
                 "cut_stand": cut_stand & ~silhouette,
                 "inside_other": site & ~keep & ~cut_stand & ~silhouette,
                 "occluded": silhouette & ~keep,
                 "pitch": keep}
        assert np.all(sum(m.astype(int) for m in masks.values()) == 1), "Categories do not partition image"
        diagnostic = np.zeros_like(plane)
        for key, mask in masks.items():
            diagnostic[mask] = COLORS[key]
            Image.fromarray((mask*255).astype("uint8")).save(OUT / f"{stem}_{key}_mask.png")
        Image.fromarray(diagnostic).save(OUT / f"{stem}_visibility.png")
        render = np.asarray(Image.open(OUT / f"{stem}.png").convert("RGB"))
        approved_render = np.asarray(Image.open(
            ROOT / f"generated-artifacts/stadium-middle-probe/{stem}.png").convert("RGB"))
        assert np.array_equal(render[keep], approved_render[keep]), "Approved field pixels changed"
        # Actual original ground only outside the site. Under-stadium ground
        # is unknown; mark it, never fill with a hallucinated environment.
        composite = plane.copy()
        composite[masks["cut_stand"]] = COLORS["cut_stand"]
        composite[masks["inside_other"]] = COLORS["inside_other"]
        composite[silhouette | keep] = render[silhouette | keep]
        assert np.array_equal(composite[keep], approved_render[keep]), "Map composite changed field pixels"
        Image.fromarray(composite).save(OUT / f"{stem}_registered_map.png")
        categories[stem] = {
            "pixels": {k: int(m.sum()) for k, m in masks.items()},
            "pct_of_entire_image": {k: round(float(m.mean()*100), 4) for k, m in masks.items()},
            "free_ground_before_occlusion_pct": round(float((~keep & ~site).mean()*100), 4),
            "outside_site_occluded_pixels": int((~site & ~keep & silhouette).sum()),
            "free_inside_share_of_all_free_pct": round(float(
                ((masks["cut_stand"] | masks["inside_other"]).sum()) /
                max(1, (~keep & ~silhouette).sum()) * 100), 4),
            "approved_field_pixels_identical": True,
        }

    # Feature evidence uses the original source geometries and ground ray
    # samples; no landmark can be moved to obtain a larger visible count.
    ix, iy = np.rint(rx).astype(int), np.rint(ry).astype(int)
    visible_features = {f"{club}_{r}": [] for r in ("roof", "no_roof")}
    outside_masks = {
        stem: np.asarray(Image.open(OUT / f"{stem}_outside_mask.png")) > 128
        for stem in visible_features}
    for element in osm["elements"]:
        tags, geometry = element.get("tags", {}), element.get("geometry", [])
        if len(geometry) < 2 or not any(k in tags for k in (
                "building", "highway", "landuse", "natural", "amenity", "leisure")):
            continue
        mapped = Image.new("L", raster.size)
        points = [raster_xy(bbox, raster.size, p["lon"], p["lat"]) for p in geometry]
        painter = ImageDraw.Draw(mapped)
        if geometry[0] == geometry[-1]:
            painter.polygon(points, fill=255)
        elif "highway" in tags:
            # Diagnostic line only; its 5px width is NOT a surveyed road width.
            painter.line(points, fill=255, width=5)
        else:
            continue
        projected = (np.asarray(mapped)[iy, ix] > 128).reshape(height, width)
        for stem, visible in outside_masks.items():
            count = int((visible & projected).sum())
            if count:
                visible_features[stem].append({
                    "osm_id": element["id"], "tags": tags, "visible_ground_pixels": count,
                    "line_width_is_symbolic": "highway" in tags and geometry[0] != geometry[-1]})
    for stem, features in visible_features.items():
        categories[stem]["mapped_visible_features"] = sorted(
            features, key=lambda f: -f["visible_ground_pixels"])

    audit = raster.copy()
    draw = ImageDraw.Draw(audit)
    for way_id, color in ((stadium_id, "#e44540"), (pitch_id, "#19a24b")):
        points = [raster_xy(bbox, raster.size, p["lon"], p["lat"]) for p in ways[way_id]["geometry"]]
        draw.line(points, fill=color, width=4)
    border = [int(i) for i in (0, width-1, width*height-1, width*(height-1))]
    draw.line([(float(rx[i]), float(ry[i])) for i in border+[border[0]]], fill="#00a9cf", width=5)
    clon, clat = scene_to_lonlat(frame, camera["position"][0], camera["position"][2], True)
    cx, cy = raster_xy(bbox, raster.size, clon, clat)
    draw.ellipse((cx-10, cy-10, cx+10, cy+10), fill="#00a9cf")
    bearing = float(np.degrees(np.arctan2(
        (clon-scene_to_lonlat(frame, 0, 0, True)[0])*np.cos(np.radians(clat)),
        clat-scene_to_lonlat(frame, 0, 0, True)[1]))) % 360
    font = ImageFont.load_default(size=24)
    draw.rectangle((15, 15, 1700, 150), fill="#10202b")
    draw.text((30, 25), f"{club}: Nord oben | Kamera {bearing:.2f} Grad ab Nord", fill="white", font=font)
    draw.text((30, 65), "Rot: OSM-Stadiongrenze | Gruen: reales Feld | Cyan: Bodenausschnitt + Kamerapunkt",
              fill="white", font=font)
    draw.text((30, 105), "Geobasis NRW, dl-de/zero-2-0 + OSM, ODbL" if club == "dortmund"
              else "Original OSM, ODbL: schematische Karte, KEIN Luftbild / keine Hoehen",
              fill="white", font=font)
    audit.save(OUT / f"{club}_geographic_audit.jpg", quality=94)
    return {"camera_side_bearing_deg": round(bearing, 3),
            "osm_stadium_id": stadium_id, "osm_pitch_id": pitch_id,
            "footprint_definition": footprint_label,
            "map_adapter": "scene X=-u, scene Z=v; half-turn applied about pitch center",
            "states": categories}


def main():
    camera = json.loads((OUT / "camera_exact.json").read_text())
    states = [s for s in json.loads((OUT / "verification.json").read_text())["states"]
              if s.get("variant", "day") == "day"]
    approved = json.loads((ROOT / "generated-artifacts/stadium-middle-probe/verification.json").read_text())["states"][0]
    check_camera(camera, states, approved)
    ground = ground_rays(camera)
    report = {"format": camera["format"], "field_corners_exact": True,
              "approved_field_pixels_exact": True,
              "camera_matrices_exact": True, "denominator": "entire 1880x940 image (1,767,200 pixels)",
              "mask_threshold": "white geometric coverage >128; antialiased edges rounded",
              "limits": ["Ground-plane visibility only, not facade/tree height visibility.",
                         "No geodetic Unity survey; physical-side calibration retained.",
                         "No aerial capture date claimed; Elversberg is OSM, not orthophoto.",
                         "Hidden stand ground is unknown; no landmarks shifted or generated."]}
    for club in ("dortmund", "elversberg"):
        report[club] = audit_club(club, camera, states, ground)
    (OUT / "geo_verification.json").write_text(json.dumps(report, indent=2, ensure_ascii=False))
    font = ImageFont.load_default(size=22)
    board = Image.new("RGB", (1880, 1140), "#101b25")
    draw = ImageDraw.Draw(board)
    for row, club in enumerate(("dortmund", "elversberg")):
        for column, roof in enumerate(("roof", "no_roof")):
            stem = f"{club}_{roof}"
            image = Image.open(OUT / f"{stem}_visibility.png").resize((940, 470))
            board.paste(image, (column*940, 70+row*530))
            pct = report[club]["states"][stem]["pct_of_entire_image"]
            draw.text((column*940+20, 35+row*530),
                      f"{club} / {roof}: echtes Aussenumfeld {pct['outside']:.2f} %", fill="white", font=font)
    draw.text((20, 1100), "Gruen: aussen | Orange: ausgeblendete Tribuene | Violett: sonstiger Innenboden | Dunkel: verdeckt", fill="white", font=font)
    board.save(OUT / "visibility_comparison.jpg", quality=94)
    for row, club in enumerate(("dortmund", "elversberg")):
        for column, roof in enumerate(("roof", "no_roof")):
            stem = f"{club}_{roof}"
            image = Image.open(OUT / f"{stem}_registered_map.png").resize((940, 470))
            board.paste(image, (column*940, 70+row*530))
    draw.rectangle((0, 1090, 1880, 1140), fill="#101b25")
    draw.text((20, 1100), "Dortmund: NRW-Orthofoto | Elversberg: OSM-Bodenkarte | Orange/Violett: unbekannter Innenboden",
              fill="white", font=font)
    board.save(OUT / "registered_map_comparison.jpg", quality=94)
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
