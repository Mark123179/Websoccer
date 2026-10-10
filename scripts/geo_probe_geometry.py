"""Pure geographic helpers for the isolated stadium visibility audit."""
import math

import numpy as np
from PIL import Image, ImageDraw


def frame_from_osm(osm, stadium_id, pitch_id):
    elements = {e["id"]: e for e in osm["elements"] if e["type"] == "way"}
    ref = elements[stadium_id]["geometry"][0]
    lat0, lon0 = ref["lat"], ref["lon"]
    points = elements[pitch_id]["geometry"]
    if points[0] == points[-1]:
        points = points[:-1]
    xy = [((p["lon"]-lon0)*111320*math.cos(math.radians(lat0)),
           (p["lat"]-lat0)*111320) for p in points]
    _, theta = max((math.hypot(b[0]-a[0], b[1]-a[1]),
                    math.atan2(b[1]-a[1], b[0]-a[0]))
                   for a, b in zip(xy, xy[1:]+xy[:1]))
    return {"lat0": lat0, "lon0": lon0,
            "pitchCenterLocal": np.mean(xy, axis=0).tolist(),
            "thetaDeg": math.degrees(theta)}


def scene_to_lonlat(frame, x, z, half_turn):
    # Study model: original +90° adapter X=u, Z=-v.
    # Main-stand-back rotates ONLY model, so its map must turn too.
    sign = -1 if half_turn else 1
    u, v = sign*x, -sign*z
    theta = math.radians(frame["thetaDeg"])
    c, s = math.cos(theta), math.sin(theta)
    east, north = u*c-v*s, u*s+v*c
    return (frame["lon0"]+(east+frame["pitchCenterLocal"][0]) /
            (111320*math.cos(math.radians(frame["lat0"]))),
            frame["lat0"]+(north+frame["pitchCenterLocal"][1])/111320)


def lonlat_to_scene(frame, lon, lat, half_turn):
    east = (lon-frame["lon0"])*111320*math.cos(math.radians(frame["lat0"]))-frame["pitchCenterLocal"][0]
    north = (lat-frame["lat0"])*111320-frame["pitchCenterLocal"][1]
    theta = math.radians(frame["thetaDeg"])
    u = east*math.cos(theta)+north*math.sin(theta)
    v = -east*math.sin(theta)+north*math.cos(theta)
    sign = -1 if half_turn else 1
    return sign*u, -sign*v


def ground_rays(camera):
    width, height = camera["format"]
    projection = np.array(camera["projection"]).reshape(4, 4, order="F")
    view = np.array(camera["worldInverse"]).reshape(4, 4, order="F")
    yy, xx = np.mgrid[:height, :width]
    clip = np.stack((2*(xx+.5)/width-1, 1-2*(yy+.5)/height,
                     np.full_like(xx, -1), np.ones_like(xx)), axis=0).reshape(4, -1)
    points = np.linalg.inv(projection @ view) @ clip
    points = points[:3]/points[3]
    origin = np.array(camera["position"])[:, None]
    rays = points-origin
    assert np.all(rays[1] < 0), "A horizon entered the approved view"
    return origin+rays*(-origin[1]/rays[1])


def project_ground(camera, x, z):
    width, height = camera["format"]
    projection = np.array(camera["projection"]).reshape(4, 4, order="F")
    view = np.array(camera["worldInverse"]).reshape(4, 4, order="F")
    p = projection @ view @ np.array([x, 0, z, 1])
    return ((p[0]/p[3]+1)*width/2, (1-p[1]/p[3])*height/2)


def polygon_mask(camera, polygon):
    image = Image.new("L", tuple(camera["format"]))
    ImageDraw.Draw(image).polygon(
        [project_ground(camera, x, z) for x, z in polygon], fill=255)
    return np.asarray(image) > 128


def mercator(lon, lat):
    return (6378137*np.radians(lon),
            6378137*np.log(np.tan(np.pi/4+np.radians(lat)/2)))


def raster_xy(bbox, size, lon, lat):
    mx, my = mercator(lon, lat)
    minx, miny, maxx, maxy = bbox
    return ((mx-minx)/(maxx-minx)*size[0],
            (maxy-my)/(maxy-miny)*size[1])


def sample_raster(image, rx, ry, shape):
    # Bilinear sampling needs a full extra pixel, not only x < width.
    assert (rx.min() >= 0 and ry.min() >= 0 and
            rx.max() < image.width-1 and ry.max() < image.height-1), "Raster coverage missing"
    pixels = np.asarray(image)
    x0, y0 = np.floor(rx).astype(int), np.floor(ry).astype(int)
    fx, fy = (rx-x0)[:, None], (ry-y0)[:, None]
    sampled = (pixels[y0, x0]*(1-fx)*(1-fy)+pixels[y0, x0+1]*fx*(1-fy)
               +pixels[y0+1, x0]*(1-fx)*fy+pixels[y0+1, x0+1]*fx*fy)
    return sampled.reshape(*shape, 3).astype("uint8")
