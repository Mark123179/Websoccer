"""Surveyed RoofSurfaces only: no roof or facade reconstruction."""
import math

from shapely import set_precision
from shapely.geometry import Polygon
from shapely.ops import unary_union

from scripts.koln_building_parts import simple_polygons


def roof_plane(rings):
    """Validate a simple, nonvertical planar XYZ surface (centimetre tolerance)."""
    if not rings or any(len(r) < 4 or r[0] != r[-1] for r in rings):
        raise ValueError("RoofSurface rings must be closed")
    if any(len(p) != 3 or not all(math.isfinite(v) for v in p) for r in rings for p in r):
        raise ValueError("Nonfinite RoofSurface")
    polygon = Polygon([[p[0], p[1]] for p in rings[0]],
                      [[[p[0], p[1]] for p in r] for r in rings[1:]])
    if not polygon.is_valid or polygon.area <= 1e-8:
        raise ValueError("Invalid RoofSurface footprint")
    origin = rings[0][0]
    best = None
    for a, b in zip(rings[0][1:], rings[0][2:]):
        u = [a[i]-origin[i] for i in range(3)]
        v = [b[i]-origin[i] for i in range(3)]
        n = [u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0]]
        if best is None or abs(n[2]) > abs(best[2]):
            best = n
    if best is None or abs(best[2]) < 1e-8:
        raise ValueError("Vertical RoofSurface")
    def height(x, y):
        return origin[2]-(best[0]*(x-origin[0])+best[1]*(y-origin[1]))/best[2]
    if any(abs(height(p[0], p[1])-p[2]) > .01 for r in rings for p in r):
        raise ValueError("Nonplanar RoofSurface")
    return polygon, height


def clipped_roofs(candidate, footprint, to_editor):
    """Clip documented planes to the existing unique component partition."""
    roofs = candidate["roofSurfaces"]
    if not roofs or len(roofs) > 128:
        raise ValueError(f"Missing/excessive RoofSurfaces: {candidate['id']}")
    # Keep the already approved quantized boundary coordinates, but do not let
    # GEOS round new roof/OSM intersections to the footprint's precision model.
    footprint = set_precision(footprint, 0)
    result, covered, ids = [], [], set()
    for roof in roofs:
        key = (roof["surfaceId"], roof["polygonId"])
        if key in ids:
            raise ValueError("Duplicate RoofSurface")
        ids.add(key)
        rings = roof["ringsUTM"]
        roof_plane(rings)
        # Preserve the original NHN ordinate; project horizontal coordinates only.
        projected = [[[*to_editor(p[0], p[1]), p[2]] for p in ring] for ring in rings]
        shape, height = roof_plane(projected)
        # Same disclosed 10 µm horizontal grid as official GroundSurfaces.
        # Evaluate heights on the original plane, never on a snapped NHN axis.
        shape = set_precision(set_precision(shape, 1e-5), 0)
        if any(p[2] <= candidate["baseNHN"] or p[2] > candidate["roofNHN"]+.01
               or p[2] < candidate["roofMinNHN"]-.01 for r in rings for p in r):
            raise ValueError("RoofSurface outside documented NHN range")
        clipped = shape.intersection(footprint)
        polygons = simple_polygons(clipped)
        if any(clipped.intersection(other).area > 1e-5 for other in covered):
            raise ValueError("Overlapping RoofSurfaces")
        covered.append(clipped)
        cleaned = []
        for ring in polygons:
            points = []
            for point in ring[:-1]:
                # Boolean intersections may emit two adjacent vertices less
                # than one nanometre apart. They are not distinct survey data.
                if not points or math.dist(point, points[-1]) > 1e-9:
                    points.append(point)
            if len(points) > 1 and math.dist(points[0], points[-1]) <= 1e-9:
                points.pop()
            if len(points) < 3:
                raise ValueError("Collapsed clipped RoofSurface")
            cleaned.append(points + [points[0]])
        result.append({
            "surfaceId": roof["surfaceId"], "polygonId": roof["polygonId"],
            "lodId": candidate["id"], "file": candidate["file"],
            "sourceRingsUTM": rings,
            "polygons": [[[x, y, height(x, y)] for x, y in ring] for ring in cleaned],
        })
    if unary_union(covered).symmetric_difference(footprint).area > 1e-5:
        raise ValueError(f"Incomplete RoofSurface coverage: {candidate['id']}")
    zs = [p[2] for roof in roofs for ring in roof["ringsUTM"] for p in ring]
    if abs(max(zs)-candidate["roofNHN"]) > .01 or abs(min(zs)-candidate["roofMinNHN"]) > .01:
        raise ValueError("RoofSurface extrema differ from evidence")
    return result
