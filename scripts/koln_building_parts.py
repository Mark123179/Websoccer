"""Explicit Abelbau components; never a relaxation of the single-height join."""
import math

from shapely import constrained_delaunay_triangles, set_precision
from shapely.geometry import Polygon, mapping
from shapely.ops import transform, unary_union

ABEL_IDS = frozenset(("way/73467119", "way/73467122"))
DATUM = "DHHN2016 / NHN (EPSG:7837)"


def simple_polygons(shape):
    """Encode holes as constrained triangles, preserving every residual m²."""
    if shape.is_empty:
        return []
    polygons = [shape] if shape.geom_type == "Polygon" else list(shape.geoms)
    result = []
    for polygon in polygons:
        # Below 0.00000001 m², Boolean floating-point debris cannot form a
        # drawable Float32 face. Original OSM polygons remain untouched.
        if polygon.area <= 1e-8:
            continue
        if polygon.geom_type != "Polygon" or not polygon.is_valid:
            raise ValueError("Invalid component partition")
        pieces = (constrained_delaunay_triangles(polygon).geoms
                  if polygon.interiors else [polygon])
        result.extend([list(p) for p in piece.exterior.coords] for piece in pieces)
    return result


def component_group(index, osm, polygon, candidates, to_editor, editor_polygon=None):
    """Use only independently proven, planar laser components within this OSM."""
    if osm not in ABEL_IDS:
        return None
    # Partition after projection, on an explicit 10 µm numerical grid. Inverse
    # PROJ on already cut nanometre slivers can otherwise fold their rings.
    # This is display quantization, not repair of invalid official footprints.
    display = (editor_polygon if editor_polygon is not None else
               transform(to_editor, polygon))
    display_footprints = {
        c["id"]: set_precision(transform(to_editor, c["footprint"]), 1e-5)
        for c in candidates
    }
    intersections = [display.intersection(display_footprints[c["id"]]) for c in candidates]
    ambiguous = unary_union([
        a.intersection(b) for i, a in enumerate(intersections) for b in intersections[:i]
        if a.intersection(b).area > 0
    ])
    parts, covered = [], []
    for c in sorted(candidates, key=lambda c: c["id"]):
        intersection = polygon.intersection(c["footprint"])
        if intersection.area == 0:
            continue
        purity = intersection.area / c["footprint"].area
        if (purity < .85 or c["attributes"].get("DatenquelleDachhoehe") != "1000"
                or c["attributes"].get("DatenquelleBodenhoehe") != "1100"
                or not (c.get("heightUnit") or "").endswith(":m")
                or not 1 <= c["height"] <= 100
                or c.get("srsName") != "urn:adv:crs:ETRS89_UTM32*DE_DHHN2016_NH"
                or c.get("baseMaxNHN") != c["baseNHN"]
                or not all(math.isfinite(c.get(k, math.nan))
                           for k in ("baseNHN", "roofNHN"))
                or abs(c["roofNHN"] - c["baseNHN"] - c["height"]) > .01):
            raise ValueError(f"Abelbau component lacks unambiguous NHN evidence: {c['id']}")
        # Rounded source edges can overlap by tiny areas. Do not choose the
        # higher/lower component: retain every disputed patch as unmeasured.
        intersection = display.intersection(display_footprints[c["id"]]).difference(ambiguous)
        if intersection.is_empty:
            raise ValueError(f"No unique footprint left for {c['id']}")
        if any(intersection.intersection(other).area > 1e-6 for other in covered):
            raise ValueError(f"Overlapping Abelbau components: {c['id']}")
        covered.append(intersection)
        parts.append({
            "lodId": c["id"], "file": c["file"],
            "polygons": simple_polygons(intersection),
            "height": c["height"], "baseNHN": c["baseNHN"], "roofNHN": c["roofNHN"],
            "roofMinNHN": c["roofMinNHN"],
            "sourceAttributes": c["attributes"],
            "officialCoverage": purity, "osmCoverage": intersection.area / display.area,
            "officialGroundUTM": mapping(c["footprint"]),
            "srsName": c["srsName"],
        })
    if len(parts) < 2:
        raise ValueError(f"Missing multipart evidence for {osm}")
    union = unary_union(covered)
    residual = display.difference(union)
    return {
        "buildingIndex": index, "osm": osm, "parts": parts,
        "residualPolygons": simple_polygons(residual),
        "residualStatus": "unmeasured_retained_envelope",
        "coveredAreaEditor": union.area, "residualAreaEditor": residual.area,
        "osmAreaUTM": polygon.area,
        "ambiguousAreaEditor": ambiguous.area,
        "ambiguousGroundEditor": mapping(ambiguous),
        "displayPrecisionMeters": 1e-5,
    }
