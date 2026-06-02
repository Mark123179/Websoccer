"""
Thin-plate spline calibration for europe-night.png (1536×1024).

Run from the project root:
    python3 game/calibration/calibrate_city_map.py

Outputs
-------
- Prints the new _MAP_TPS_ANCHORS / _MAP_TPS_WX / _MAP_TPS_WY tuples
  (paste these into game/views.py to update the in-code transform).
- Saves game/calibration/verify_overlay.png  — satellite image with
  the geographic lat/lng grid and all CITY_MAP_PCT pins drawn on top,
  for visual quality-check before committing.
- Prints per-anchor residuals (all should be 0.0 px for an interpolating TPS).

Requirements: Pillow  (pip install Pillow)

Anchor methodology
------------------
Each anchor is a (lat, lng, px_x, px_y) tuple where (px_x, px_y) is the
source-image pixel on europe-night.png (1536×1024).  Anchors must be
identified WITHOUT relying on pixel brightness (except London and Paris,
which are explicitly approved via the two starburst brightness peaks).

Approved anchor types
- City starbursts:  Frankfurt, Madrid, Barcelona, München  (bright, unambiguous)
- Brightness-allowed: London, Paris (project policy permits brightness for these two)
- Coastal/geographic:  identified by matching coastline shape to grid overlays,
  NOT by brightness peak.  E.g. "the Jutland northern tip" or "Calabria boot toe".
- Urban-pattern coast:  Lisboa and Porto — the Tejo estuary and Douro mouth are
  distinctive shapes that pinpoint the city without requiring brightness.
- Archipelago:  Stockholm — the Baltic archipelago island pattern in g_stockholm.png.

To add or replace an anchor:
1. Generate a coordinate grid overlay of the region (see make_grid_inset() below).
2. Identify the geographic feature at the target pixel.
3. Add/replace the entry in ANCHORS and re-run this script.
4. Paste the printed weights into game/views.py.
5. Visually verify verify_overlay.png before committing.
"""

import math
import os
import sys

try:
    from PIL import Image, ImageDraw
except ImportError:
    print("Pillow not installed. Run: pip install Pillow", file=sys.stderr)
    sys.exit(1)

# ─── Anchor set ──────────────────────────────────────────────────────────────
# (lat_deg_N, lng_deg_E_positive_W_negative, source_pixel_x, source_pixel_y, label)
ANCHORS = [
    (50.11,  8.68, 665, 543, "Frankfurt        (city starburst)"),
    (40.42, -3.70, 340, 802, "Madrid           (city starburst)"),
    (41.39,  2.17, 505, 760, "Barcelona        (city starburst)"),
    (48.14, 11.58, 723, 602, "München          (city starburst)"),
    (51.51, -0.13, 491, 485, "London           (brightness allowed)"),
    (48.85,  2.35, 530, 578, "Paris            (brightness allowed)"),
    (49.73, -1.93, 467, 541, "Cap de la Hague  (coastal peninsula grid)"),
    (48.41, -4.72, 358, 567, "Brittany/Corsen  (coastal point grid)"),
    (37.65, 15.64, 741, 877, "Calabria tip     (boot-toe coast grid)"),
    (57.73, 10.58, 720, 338, "Skagen           (Jutland tip grid)"),
    (55.30, -5.71, 415, 367, "Mull of Kintyre  (Scottish peninsula grid)"),
    (38.72, -9.14, 244, 837, "Lisboa           (Tejo estuary urban pattern)"),
    (41.15, -8.61, 235, 755, "Porto            (Douro coast urban pattern)"),
    (59.33, 18.07, 840, 270, "Stockholm        (Baltic archipelago grid)"),
]

IMG_W = 1536
IMG_H = 1024


# ─── TPS solver ──────────────────────────────────────────────────────────────
def _phi(r):
    return r * r * math.log(r) if r > 1e-10 else 0.0


def _dist(x1, y1, x2, y2):
    return math.sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2)


def _gauss_solve(M, b):
    nn = len(b)
    aug = [M[i][:] + [b[i]] for i in range(nn)]
    for c in range(nn):
        p = max(range(c, nn), key=lambda r: abs(aug[r][c]))
        aug[c], aug[p] = aug[p], aug[c]
        pv = aug[c][c]
        if abs(pv) < 1e-15:
            continue
        for j in range(c, nn + 1):
            aug[c][j] /= pv
        for r in range(nn):
            if r != c:
                f = aug[r][c]
                for j in range(c, nn + 1):
                    aug[r][j] -= f * aug[c][j]
    return [aug[i][nn] for i in range(nn)]


def fit_tps(anchors):
    """Fit TPS in (lng, lat) coordinate space (matching _tps_eval convention).

    Returns (xs, ys, wx, wy) where xs[i]=lng, ys[i]=lat of anchor i.
    """
    xs = [a[1] for a in anchors]   # lng
    ys = [a[0] for a in anchors]   # lat
    pxs = [a[2] for a in anchors]
    pys = [a[3] for a in anchors]
    n = len(anchors)

    N = n + 3
    K = [[0.0] * N for _ in range(N)]
    for i in range(n):
        for j in range(n):
            K[i][j] = _phi(_dist(xs[i], ys[i], xs[j], ys[j]))
        K[i][n] = 1.0
        K[i][n + 1] = xs[i]
        K[i][n + 2] = ys[i]
        K[n][i] = 1.0
        K[n + 1][i] = xs[i]
        K[n + 2][i] = ys[i]

    wx = _gauss_solve(K, pxs + [0.0, 0.0, 0.0])
    wy = _gauss_solve(K, pys + [0.0, 0.0, 0.0])
    return xs, ys, wx, wy


def tps_eval(weights, xs, ys, lng, lat):
    n = len(xs)
    val = weights[n] + weights[n + 1] * lng + weights[n + 2] * lat
    for i in range(n):
        r = _dist(lng, lat, xs[i], ys[i])
        if r > 0:
            val += weights[i] * _phi(r)
    return val


def city_px(xs, ys, wx, wy, lat, lng):
    px = max(0.0, min(IMG_W, tps_eval(wx, xs, ys, lng, lat)))
    py = max(0.0, min(IMG_H, tps_eval(wy, xs, ys, lng, lat)))
    return round(px / IMG_W * 100, 2), round(py / IMG_H * 100, 2)


# ─── Grid inset helper ───────────────────────────────────────────────────────
def make_grid_inset(src, box, name, step=10, scale=4):
    """Crop a region of *src*, zoom it, draw a pixel-coordinate grid, save it."""
    x0, y0, x1, y1 = box
    crop = src.crop(box).resize(((x1 - x0) * scale, (y1 - y0) * scale), Image.LANCZOS)
    d = ImageDraw.Draw(crop)
    gx = ((x0 // step) + 1) * step
    while gx < x1:
        X = (gx - x0) * scale
        d.line([(X, 0), (X, crop.height)], fill=(80, 80, 120), width=1)
        d.text((X + 1, 1), str(gx), fill=(220, 220, 255))
        gx += step
    gy = ((y0 // step) + 1) * step
    while gy < y1:
        Y = (gy - y0) * scale
        d.line([(0, Y), (crop.width, Y)], fill=(80, 80, 120), width=1)
        d.text((1, Y + 1), str(gy), fill=(220, 220, 255))
        gy += step
    out = os.path.join(os.path.dirname(__file__), name)
    crop.save(out)
    print(f"  Saved {out}")


# ─── Main calibration routine ─────────────────────────────────────────────────
def main():
    script_dir = os.path.dirname(__file__)
    bg_path = os.path.join(
        script_dir, "..", "static", "game", "images", "backgrounds", "europe-night.png"
    )
    if not os.path.exists(bg_path):
        print(f"ERROR: background not found at {bg_path}", file=sys.stderr)
        sys.exit(1)

    src = Image.open(bg_path).convert("RGB")

    # Fit TPS
    xs, ys, wx, wy = fit_tps(ANCHORS)
    n = len(ANCHORS)

    # Print residuals
    print("=== Anchor residuals (should all be 0.0 px) ===")
    max_err = 0.0
    for lat, lng, apx, apy, label in ANCHORS:
        px = tps_eval(wx, xs, ys, lng, lat)
        py = tps_eval(wy, xs, ys, lng, lat)
        err = math.hypot(px - apx, py - apy)
        max_err = max(max_err, err)
        status = "OK" if err < 0.01 else "WARN"
        print(f"  [{status}] {label}: pred=({px:.1f},{py:.1f}) actual=({apx},{apy}) Δ={err:.2f}px")
    print(f"  max residual: {max_err:.2f}px\n")

    # Print code blocks for views.py
    print("# ── Paste into game/views.py ─────────────────────────────────────")
    print("_MAP_TPS_ANCHORS = (")
    for lat, lng, apx, apy, label in ANCHORS:
        print(f"    ({lng:7.2f}, {lat:.2f}),   # {label}")
    print(")")
    print("_MAP_TPS_WX = (")
    for v in wx:
        print(f"    {v:.6f},")
    print(")")
    print("_MAP_TPS_WY = (")
    for v in wy:
        print(f"    {v:.6f},")
    print(")")
    print()

    # Sanity checks
    print("=== Key city positions (x%, y%) ===")
    checks = [
        ("Paris",     48.85,  2.35),
        ("London",    51.51, -0.13),
        ("Frankfurt", 50.11,  8.68),
        ("Madrid",    40.42, -3.70),
        ("Barcelona", 41.39,  2.17),
        ("Sevilla",   37.39, -5.99),
        ("Lisboa",    38.72, -9.14),
        ("Stockholm", 59.33, 18.07),
        ("Oslo",      59.91, 10.75),
        ("Kopenhagen",55.68, 12.57),
    ]
    for name, lat, lng in checks:
        xp, yp = city_px(xs, ys, wx, wy, lat, lng)
        print(f"  {name:12}: ({xp:.2f}%, {yp:.2f}%)")
    print()

    # Generate verification overlay
    overlay = src.copy()
    d = ImageDraw.Draw(overlay)

    # Geographic grid 5°
    for lat_g in range(30, 72, 5):
        pts = []
        for lng_step in range(-15 * 2, 45 * 2 + 1):
            lng_g = lng_step / 2.0
            px = tps_eval(wx, xs, ys, lng_g, lat_g)
            py = tps_eval(wy, xs, ys, lng_g, lat_g)
            if 0 < px < IMG_W and 0 < py < IMG_H:
                pts.append((int(px), int(py)))
        for k in range(len(pts) - 1):
            d.line([pts[k], pts[k + 1]], fill=(40, 80, 40), width=1)
    for lng_g in range(-15, 46, 5):
        pts = []
        for lat_step in range(30 * 2, 72 * 2 + 1):
            lat_g = lat_step / 2.0
            px = tps_eval(wx, xs, ys, lng_g, lat_g)
            py = tps_eval(wy, xs, ys, lng_g, lat_g)
            if 0 < px < IMG_W and 0 < py < IMG_H:
                pts.append((int(px), int(py)))
        for k in range(len(pts) - 1):
            d.line([pts[k], pts[k + 1]], fill=(40, 80, 40), width=1)

    # Anchor squares (blue)
    for lat, lng, apx, apy, label in ANCHORS:
        d.rectangle([apx - 6, apy - 6, apx + 6, apy + 6], outline=(80, 120, 255), width=2)
        d.text((apx + 8, apy - 5), label.split()[0][:5], fill=(80, 180, 255))

    # City pins from the main CITY_MAP_PCT sample
    SAMPLE_CITIES = [
        ("Paris",     48.85,  2.35),  ("London",    51.51, -0.13),
        ("Frankfurt", 50.11,  8.68),  ("München",   48.14, 11.58),
        ("Berlin",    52.52, 13.40),  ("Hamburg",   53.55,  9.99),
        ("Madrid",    40.42, -3.70),  ("Barcelona", 41.39,  2.17),
        ("Sevilla",   37.39, -5.99),  ("Lisboa",    38.72, -9.14),
        ("Porto",     41.15, -8.61),  ("Málaga",    36.72, -4.42),
        ("Nantes",    47.22, -1.55),  ("Bordeaux",  44.84, -0.58),
        ("Lyon",      45.76,  4.84),  ("Marseille", 43.30,  5.37),
        ("Amsterdam", 52.37,  4.90),  ("Brussel",   50.85,  4.35),
        ("Zürich",    47.37,  8.54),  ("Stockholm", 59.33, 18.07),
        ("Oslo",      59.91, 10.75),  ("Kopenhagen",55.68, 12.57),
        ("Glasgow",   55.86, -4.25),  ("Dublin",    53.35, -6.26),
        ("Bilbao",    43.26, -2.92),  ("Vigo",      42.24, -8.72),
        ("Dortmund",  51.51,  7.47),  ("Stuttgart", 48.78,  9.18),
    ]
    for name, lat, lng in SAMPLE_CITIES:
        px = int(tps_eval(wx, xs, ys, lng, lat))
        py = int(tps_eval(wy, xs, ys, lng, lat))
        px = max(5, min(IMG_W - 5, px))
        py = max(5, min(IMG_H - 5, py))
        d.ellipse([px - 5, py - 5, px + 5, py + 5], outline=(80, 255, 80), width=2)
        d.text((px + 7, py - 4), name[:3], fill=(80, 255, 80))

    out_path = os.path.join(script_dir, "verify_overlay.png")
    overlay.resize((1152, 768), Image.LANCZOS).save(out_path)
    print(f"Verification overlay saved: {out_path}")


if __name__ == "__main__":
    main()
