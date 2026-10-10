"""Deterministic orthophoto/ground-camera feasibility probe; no app writes."""
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "generated-artifacts/dortmund-site-study"
WIDTH, HEIGHT = 1880, 940


def main():
    source = json.loads((OUT / "source.json").read_text())
    camera = json.loads((OUT / "camera_exact.json").read_text())
    reference = json.loads((ROOT / "attached_assets/higgsfield_stadium_pack/dortmund/camera.json").read_text())
    assert camera["corners"] == reference["corners"], "Study camera changed"
    frame = source["frame"]
    theta = math.radians(frame["thetaDeg"])
    c, s = math.cos(theta), math.sin(theta)
    raster = Image.open(OUT / "orthophoto_north_up.jpg").convert("RGB")
    minx, miny, maxx, maxy = source["bbox_3857"]

    def raster_xy(lon, lat):
        mx = 6378137 * np.radians(lon)
        my = 6378137 * np.log(np.tan(np.pi / 4 + np.radians(lat) / 2))
        return ((mx-minx)/(maxx-minx)*raster.width,
                (maxy-my)/(maxy-miny)*raster.height)

    def scene_to_raster(x, z):
        # Old pitch frame: +u=SOUTH, +v=EAST.
        # Study adapter R_y(+90): scene X=u, scene Z=-v.
        u, v = x, -z
        east, north = u*c-v*s, u*s+v*c
        lon = frame["lon0"] + (east+frame["pitchCenterLocal"][0]) / (
            111320*math.cos(math.radians(frame["lat0"])))
        lat = frame["lat0"] + (north+frame["pitchCenterLocal"][1]) / 111320
        return raster_xy(lon, lat)

    projection = np.array(camera["projection"]).reshape(4, 4, order="F")
    view = np.array(camera["worldInverse"]).reshape(4, 4, order="F")
    inverse = np.linalg.inv(projection @ view)
    yy, xx = np.mgrid[:HEIGHT, :WIDTH]
    clip = np.stack((2*(xx+.5)/WIDTH-1, 1-2*(yy+.5)/HEIGHT,
                     np.full_like(xx, -1), np.ones_like(xx)), axis=0).reshape(4, -1)
    points = inverse @ clip
    points = points[:3] / points[3]
    origin = np.array(camera["position"])[:, None]
    rays = points-origin
    assert np.all(rays[1] < 0), "A horizon entered the fixed view"
    ground = origin + rays * (-origin[1]/rays[1])
    rx, ry = scene_to_raster(ground[0], ground[2])
    assert rx.min() >= 0 and ry.min() >= 0 and rx.max() < raster.width and ry.max() < raster.height
    pixels = np.asarray(raster)
    x0, y0 = np.floor(rx).astype(int), np.floor(ry).astype(int)
    fx, fy = (rx-x0)[:, None], (ry-y0)[:, None]
    sampled = (pixels[y0, x0]*(1-fx)*(1-fy) + pixels[y0, x0+1]*fx*(1-fy)
               + pixels[y0+1, x0]*(1-fx)*fy + pixels[y0+1, x0+1]*fx*fy)
    plane = Image.fromarray(sampled.reshape(HEIGHT, WIDTH, 3).astype("uint8"))
    plane.save(OUT / "ground_projection_raw.jpg", quality=94)

    osm = json.loads((ROOT / "stadium_editor/blueprints/v2/dortmund.json").read_text())
    stadium = next(e for e in osm["elements"] if e.get("id") == 17235929)
    pitch = next(e for e in osm["elements"] if e.get("id") == 17235988)
    roof_mask = Image.new("L", raster.size)
    polygon = [tuple(float(v) for v in raster_xy(p["lon"], p["lat"])) for p in stadium["geometry"]]
    ImageDraw.Draw(roof_mask).polygon(polygon, fill=255)
    site = np.asarray(roof_mask)[np.rint(ry).astype(int), np.rint(rx).astype(int)].reshape(HEIGHT, WIDTH) > 128
    keep = np.array(Image.open(ROOT / "attached_assets/higgsfield_stadium_pack/dortmund/04_keep_pitch_mask.png")) > 128
    clean = np.asarray(plane).copy()
    hatch = np.where(((xx+yy)//14 % 2)[..., None], [81, 88, 92], [69, 76, 81])
    clean[site] = hatch[site]  # Unknown ground, explicitly not fabricated.
    empty = np.array(Image.open(ROOT / "attached_assets/higgsfield_stadium_pack/dortmund/03_empty_site_camera.png").convert("RGB"))
    clean[keep] = empty[keep]
    plate = Image.fromarray(clean)
    plate.save(OUT / "registered_ground_probe.png")

    silhouette = np.array(Image.open(ROOT / "attached_assets/higgsfield_stadium_pack/dortmund/02_stadium_silhouette.png").convert("L")) > 128
    model = np.array(Image.open(OUT / "model_cutaway.png").convert("RGB"))
    composite = clean.copy()
    composite[silhouette | keep] = model[silhouette | keep]
    Image.fromarray(composite).save(OUT / "registered_model_probe.png")

    font = ImageFont.load_default(size=23)
    small = ImageFont.load_default(size=17)
    figure = Image.new("RGB", (1880, 1090), "#0a1720")
    figure.paste(Image.fromarray(composite), (0, 90))
    draw = ImageDraw.Draw(figure)
    draw.text((24, 15), "Dortmund: Originalmodell + echte Orthofoto-Bodenvorlage", fill="#e6edf2", font=font)
    draw.text((24, 50), "Unveraenderte Feldkamera. Schraffur = unbekannter Boden unter dem Originalstadion, nicht fertige Kulisse.", fill="#b8cbd5", font=small)
    draw.text((24, 1045), "Geobasis NRW / nw_dop_rgb / dl-de/zero-2-0. Gebaeude und Baeume sind hier flach projiziert.", fill="#b8cbd5", font=small)
    figure.save(OUT / "camera_feasibility.jpg", quality=94)

    audit = raster.copy()
    draw = ImageDraw.Draw(audit)
    draw.line(polygon+[polygon[0]], fill="#ff775c", width=4)
    pitch_poly = [tuple(float(v) for v in raster_xy(p["lon"], p["lat"])) for p in pitch["geometry"]]
    draw.line(pitch_poly+[pitch_poly[0]], fill="#72ff9f", width=4)
    border = [scene_to_raster(ground[0, i], ground[2, i]) for i in
              [0, WIDTH-1, WIDTH*HEIGHT-1, WIDTH*(HEIGHT-1)]]
    border = [(float(x), float(y)) for x, y in border]
    draw.line(border+[border[0]], fill="#00e6ff", width=5)
    camera_xy = scene_to_raster(camera["position"][0], camera["position"][2])
    draw.ellipse((camera_xy[0]-9, camera_xy[1]-9, camera_xy[0]+9, camera_xy[1]+9), fill="#00e6ff")
    draw.rectangle((15, 15, 1100, 125), fill="#081720")
    draw.text((30, 25), "Nord oben. Cyan: Boden-Bildausschnitt der festen Kamera.", font=font, fill="#00e6ff")
    draw.text((30, 62), "Rot: Stadiongrundriss. Gruen: reales Spielfeld. Punkt: Kamera West.", font=font, fill="#edf4f7")
    draw.text((30, 97), "Quelle: Geobasis NRW + OSM. Keine geodaetische Unity-Vermessung.", font=small, fill="#bcced9")
    audit.save(OUT / "geographic_audit.jpg", quality=94)

    report = {
        "source": source["source"], "license": "https://www.govdata.de/dl-de/zero-2-0",
        "field_projection_identical": True, "osm_pitch_id": 17235988,
        "osm_stadium_id": 17235929,
        "model_coverage_outside_pitch_pct": round(float(silhouette[~keep].mean()*100), 2),
        "ground_outside_stadium_footprint_pct": round(float((~site & ~keep).mean()*100), 2),
        "photo_ground_visible_after_model_pct": round(float((~site & ~keep & ~silhouette).mean()*100), 2),
        "axis_check": "South: continuous large terrace on +scene X; North: split tiers on -scene X. Matches +OSM u=South, +scene Z=West.",
        "heading_limit": "Physical-side visual corroboration, not a geodetic survey of the Unity asset.",
        "limitations": ["Orthophoto capture date not yet established; service update is not capture date.",
                       "Buildings/trees projected onto a ground plane, no upright facade geometry.",
                       "Original stadium footprint neutralized, underlying ground remains unknown.",
                       "Outside-footprint stadium shadows not retouched.",
                       "Masks have hard diagnostic edges; not a final photorealistic plate."],
    }
    (OUT / "verification.json").write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
