"""Offline fallback render of the extracted mesh binary; no WebGL required.

Run after export_dortmund_miniature.py. This renders source triangles, not
the old procedural stadium scene. Added tier triangles are labeled separately.
"""
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from numba import njit

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "stadium_editor/static/stadium_editor/dortmund_original"
WIDTH, HEIGHT = 1120, 600
AZ, EL, DIST = .58, .65, 490


@njit
def raster(tris, colors, background):
    frame = np.empty((HEIGHT, WIDTH, 3), dtype=np.uint8)
    frame[:] = background
    zbuffer = np.full((HEIGHT, WIDTH), 1e8, dtype=np.float32)
    for k in range(len(tris)):
        p = tris[k]
        if min(p[0, 2], p[1, 2], p[2, 2]) < 1:
            continue
        left = max(0, int(min(p[0, 0], p[1, 0], p[2, 0])))
        right = min(WIDTH - 1, int(max(p[0, 0], p[1, 0], p[2, 0])) + 1)
        top = max(0, int(min(p[0, 1], p[1, 1], p[2, 1])))
        bottom = min(HEIGHT - 1, int(max(p[0, 1], p[1, 1], p[2, 1])) + 1)
        if left > right or top > bottom:
            continue
        a, b, c = p
        area = (b[0]-a[0])*(c[1]-a[1]) - (b[1]-a[1])*(c[0]-a[0])
        if abs(area) < .01:
            continue
        for y in range(top, bottom + 1):
            for x in range(left, right + 1):
                u = ((b[0]-x)*(c[1]-y) - (b[1]-y)*(c[0]-x)) / area
                v = ((c[0]-x)*(a[1]-y) - (c[1]-y)*(a[0]-x)) / area
                w = 1-u-v
                if min(u, v, w) < 0:
                    continue
                # Perspective-correct depth from reciprocal depth.
                depth = 1 / (u/a[2] + v/b[2] + w/c[2])
                if depth < zbuffer[y, x]:
                    zbuffer[y, x] = depth
                    frame[y, x] = colors[k]
    return frame


def shade(material, mesh_name):
    n = (material + mesh_name).lower()
    if "pitch" in n or "dtmnd" in n:
        return [51, 119, 71]
    if "seat" in n:
        return [184, 157, 60]
    if "pllr" in n or "iron" in n or "trus" in n:
        return [219, 183, 48]
    if "sgbd" in n or "coat_band" in n:
        return [198, 171, 63]
    if "roof" in n or "irpl" in n:
        return [159, 169, 169]
    if "glas" in n:
        return [93, 122, 128]
    if "wall" in n or "cncr" in n:
        return [108, 117, 119]
    return [145, 153, 152]


def project(vertices, az=AZ, el=EL):
    sa, ca, se, ce = np.sin(az), np.cos(az), np.sin(el), np.cos(el)
    relative = vertices - np.array([DIST*sa*ce, 24 + DIST*se, DIST*ca*ce])
    right = np.array([ca, 0, -sa])
    up = np.array([-sa*se, ce, -ca*se])
    forward = np.array([-sa*ce, -se, -ca*ce])
    depth = relative @ forward
    focal = WIDTH / (2*np.tan(np.radians(42)/2))
    return np.column_stack([WIDTH/2 + (relative @ right)*focal/depth,
                            HEIGHT/2 - (relative @ up)*focal/depth, depth]).astype(np.float32)


def add_quad(triangles, colors, a, b, c, d, color):
    triangles.extend(([a, b, c], [a, c, d]))
    colors.extend((color, color))


def additions(bounds, cutaway=False):
    triangles, colors = [], []
    rear, top = bounds[2][1], bounds[1][1]
    left, right, rows, depth, rise = -108, 105, 18, .91, .43
    outer = rear + rows * depth
    for i in range(rows):
        za, zb = rear + i*depth, rear + (i+1)*depth
        ya, yb = top + i*rise, top + (i+1)*rise
        add_quad(triangles, colors, [left,ya,za],[right,ya,za],
                 [right,ya,zb],[left,ya,zb], [105, 111, 109])
        add_quad(triangles, colors, [left,ya,zb],[right,ya,zb],
                 [right,yb,zb],[left,yb,zb], [161, 164, 153])
        for x in np.arange(left + 1, right - 1, .61):
            if min(abs(x+56), abs(x+3), abs(x-54)) < 1.2:
                continue
            z, y = za + .42, ya + .21
            color = [218, 177, 44] if int(x*4 + i*7) % 9 > 2 else [32, 39, 41]
            add_quad(triangles, colors, [x-.2,y,z-.2],[x+.2,y,z-.2],
                     [x+.2,y,z+.2],[x-.2,y,z+.2], color)
    for sign in (-1, 1):
        x = left if sign < 0 else right
        side = sign * 115
        for i in range(14):
            t, u = i/14, (i+1)/14
            add_quad(triangles, colors,
                     [x,top+8*t,rear+16*t],[side,top+8*t,80+19*t],
                     [side,top+8*u,80+19*u],[x,top+8*u,rear+16*u], [154, 156, 148])
        if not cutaway:
            add_quad(triangles, colors,
                     [side,43,82],[x,43,rear-2],[x,54,outer+7],[side,51,104], [78, 85, 87])
    add_quad(triangles, colors, [left-3,0,outer+2],[right+3,0,outer+2],
             [right+3,top+18,outer+2],[left-3,top+18,outer+2], [62, 71, 73])
    for x in np.arange(left-3,right+3,11.5):
        add_quad(triangles, colors, [x,8,outer+2.15],[x+6.5,8,outer+2.15],
                 [x+6.5,40,outer+2.15],[x,40,outer+2.15], [94, 117, 120])
    if not cutaway:
        add_quad(triangles, colors, [left-5,43,rear-2],[right+5,43,rear-2],
                 [right+7,55,outer+7],[left-7,55,outer+7], [169, 176, 174])
    add_quad(triangles, colors, [left-7,55,outer+7],[right+7,55,outer+7],
             [right+7,53,outer+7],[left-7,53,outer+7], [220, 172, 41])
    return np.asarray(triangles, dtype=np.float32), np.asarray(colors, dtype=np.uint8)


def main():
    meta = json.loads((ASSETS / "manifest.json").read_text())
    data = (ASSETS / "geometry.bin").read_bytes()
    triangle_groups, color_groups = [], []
    for mesh in meta["meshes"]:
        vertices = np.frombuffer(data, "<f4", mesh["vertexCount"]*3,
                                 mesh["positionOffset"]).reshape(-1, 3)
        for part in mesh["parts"]:
            indices = np.frombuffer(data, "<u4", part["indexCount"],
                                    part["indexOffset"]).reshape(-1, 3)
            triangle_groups.append(vertices[indices])
            color_groups.append(np.tile(shade(part["material"], mesh["name"]),
                                        (len(indices), 1)))
    original = np.concatenate(triangle_groups)
    palette = np.concatenate(color_groups).astype(np.uint8)
    overlay, overlay_colors = additions(meta["backUpperSeatBounds"])
    open_overlay, open_colors = additions(meta["backUpperSeatBounds"], cutaway=True)
    for label, geom, colors in (("original", original, palette),
                                ("ausbau", np.concatenate([original, overlay]),
                                 np.concatenate([palette, overlay_colors])),
                                ("ausbau-offen", np.concatenate([original, open_overlay]),
                                 np.concatenate([palette, open_colors]))):
        projected = project(geom.reshape(-1, 3),
                            az=.18 if label == "ausbau-offen" else AZ,
                            el=1.18 if label == "ausbau-offen" else EL).reshape(-1, 3, 3)
        pixels = raster(projected, colors, np.array([23, 35, 38], dtype=np.uint8))
        image = Image.fromarray(pixels)
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((15, 15, 302, 54), 7, fill=(18, 29, 32))
        draw.text((29, 27), {"original": "ORIGINAL", "ausbau": "ORIGINAL + AUSBAUPROBE",
                              "ausbau-offen": "AUSBAUPROBE / DACHHAUT AUS"}[label],
                  fill=(249, 207, 92))
        image.save(ASSETS / f"{label}-2d.webp", "WEBP", quality=86)
        print(label, "triangles", len(geom), "image bytes",
              (ASSETS / f"{label}-2d.webp").stat().st_size)


if __name__ == "__main__":
    main()