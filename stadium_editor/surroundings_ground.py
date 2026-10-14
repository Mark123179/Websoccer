"""Validate explicitly declared terrain, without inferring or changing source maps."""
import math
from copy import deepcopy

EPS = 1e-8


def _number(value, limit):
    # Compare before converting huge JSON integers to float in isfinite().
    return (type(value) in (int, float) and abs(value) <= limit
            and math.isfinite(value))


def _cross(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _on(a, b, p):
    return (abs(_cross(a, b, p)) <= EPS
            and min(a[0], b[0]) - EPS <= p[0] <= max(a[0], b[0]) + EPS
            and min(a[1], b[1]) - EPS <= p[1] <= max(a[1], b[1]) + EPS)


def _intersects(a, b, c, d):
    return ((_cross(a, b, c) * _cross(a, b, d) < 0
             and _cross(c, d, a) * _cross(c, d, b) < 0)
            or _on(a, b, c) or _on(a, b, d) or _on(c, d, a) or _on(c, d, b))


def validated_ground_fields(data):
    has_level, has_cutout = "groundLevel" in data, "groundCutout" in data
    if not has_level and not has_cutout:
        return {}
    level = data.get("groundLevel")
    if not has_level or not _number(level, 30):
        raise ValueError("groundLevel benötigt eine endliche Höhe zwischen −30 und 30 Metern.")
    if not has_cutout:
        if level != 0:
            raise ValueError("Eine veränderte groundLevel benötigt eine groundCutout-Aussparung.")
        return {"groundLevel": level}
    raw = data["groundCutout"]
    if (not isinstance(raw, list) or not 3 <= len(raw) <= 257
            or any(not isinstance(p, list) or len(p) != 2
                   or any(not _number(n, 10000) for n in p) for p in raw)):
        raise ValueError("groundCutout benötigt 3–256 endliche Modellpunkte (x,z).")
    polygon = deepcopy(raw)
    if polygon[0] == polygon[-1]:
        polygon.pop()
    if not 3 <= len(polygon) <= 256 or len(set(map(tuple, polygon))) != len(polygon):
        raise ValueError("groundCutout enthält doppelte oder zu wenige Punkte.")
    edges = list(zip(polygon, polygon[1:] + polygon[:1]))
    for i, (a, b) in enumerate(edges):
        c = polygon[(i + 2) % len(polygon)]
        if (abs(_cross(a, b, c)) <= EPS
                and (b[0] - a[0]) * (c[0] - b[0]) + (b[1] - a[1]) * (c[1] - b[1]) < 0):
            raise ValueError("groundCutout enthält eine rücklaufende Kante.")
        for j in range(i + 1, len(edges)):
            if j == i + 1 or (i == 0 and j == len(edges) - 1):
                continue
            if _intersects(a, b, *edges[j]):
                raise ValueError("groundCutout enthält eine Selbstüberschneidung.")
    if abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in edges)) <= EPS:
        raise ValueError("groundCutout besitzt keine Fläche.")
    return {"groundLevel": level, "groundCutout": polygon}
