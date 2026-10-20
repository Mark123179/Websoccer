"""Fresh OSM surroundings for the Mainz review, without ORM/storage/registry writes."""
import argparse
import hashlib
import json
import math
from copy import deepcopy
from pathlib import Path

import numpy as np
from shapely import constrained_delaunay_triangles
from shapely.geometry import Polygon, LineString, Point, MultiPoint, box
from shapely.ops import polygonize, unary_union

from stadium_editor.package_preflight import inspect_package

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "generated-artifacts/mainz-study"
OUT = STUDY / "osm-fresh"
PITCH_ID = 91231799
STADIUM_ID = 91231800
STADIUM_BUILDING_ID = 1338495


def bowl_opening(manifest=None, geometry=None, level=5.8494):
    """Protect the below-grade seating, not a buried foundation footprint."""
    if manifest is None:
        manifest = json.loads((STUDY / "manifest.json").read_text())
    if geometry is None:
        geometry = (STUDY / "source-export/geometry.bin").read_bytes()
    assert hashlib.sha256(geometry).hexdigest() == manifest["geometrySha256"]
    points, source_meshes = [], []
    for mesh in manifest["meshes"]:
        if not mesh["name"].startswith(("C_", "st081_pitch_", "field_")):
            continue
        source_meshes.append(mesh["name"])
        vertices = np.frombuffer(geometry, dtype="<f4", count=mesh["vertexCount"] * 3,
                                 offset=mesh["positionOffset"]).reshape(-1, 3)
        for part in mesh["parts"]:
            indices = np.frombuffer(geometry, dtype="<u4", count=part["indexCount"],
                                    offset=part["indexOffset"]).reshape(-1, 3)
            for triangle in vertices[indices]:
                for a, b in zip(triangle, np.roll(triangle, -1, axis=0)):
                    if a[1] <= level:
                        points.append(a[[0, 2]].tolist())
                    if min(a[1], b[1]) < level < max(a[1], b[1]):
                        intersection = a + (b - a) * (level - a[1]) / (b[1] - a[1])
                        points.append(intersection[[0, 2]].tolist())
    hull = MultiPoint(points).convex_hull
    return {"groundLevel": level,
            "groundCutout": [list(p) for p in hull.exterior.coords[:-1]],
            "method": "Protective source lower-crowd cross-section and pitch/field envelope "
                      "at source apron level. Buried foundations do not define the bowl opening.",
            "geometrySha256": manifest["geometrySha256"], "sourceMeshes": source_meshes,
            "areaSquareMeters": hull.area}


def write(name, data):
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2))


def fetch_source():
    import requests
    endpoint = "https://api.openstreetmap.org/api/0.6/map"
    params = {"bbox": "8.210,49.9755,8.239,49.993"}
    response = requests.get(endpoint, params=params, timeout=120,
                            headers={"Accept": "application/json",
                                     "User-Agent": "Blueprint-Stadium-SourceReview/1.0"})
    response.raise_for_status()
    raw = response.json()
    if not raw.get("elements"):
        raise ValueError("OSM response contains no source elements")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "raw.json").write_bytes(response.content)
    write("fetch.json", {"endpoint": endpoint, "params": params, "format": "json",
                        "fetchedAt": response.headers.get("Date"),
                        "bytes": len(response.content)})


def build(*, study=STUDY, out=OUT, pitch_id=PITCH_ID, stadium_id=STADIUM_ID,
          stadium_building_id=STADIUM_BUILDING_ID, stadium_wikidata="Q392494",
          fmi=918, opening=None, north_axis=False):
    # Explicit configuration lets another reviewed source package reuse the
    # identical projection/selection rules without copying or editing raw OSM.
    def write(name, data):
        (out / name).write_text(json.dumps(data, ensure_ascii=False, indent=2))

    raw_bytes = (out / "raw.json").read_bytes()
    raw = json.loads(raw_bytes)
    nodes = {e["id"]: e for e in raw["elements"] if e["type"] == "node"}
    ways = {e["id"]: e for e in raw["elements"] if e["type"] == "way"}
    pitch = ways[pitch_id]
    ll = np.array([[nodes[n]["lon"], nodes[n]["lat"]] for n in pitch["nodes"][:-1]])
    center = ll.mean(axis=0)
    meters = np.array([math.cos(math.radians(center[1])), 1]) * 6371000 * math.pi / 180

    def xy(node):
        return ((np.array([node["lon"], node["lat"]]) - center) * meters).tolist()

    def coords(way):
        return [xy(nodes[n]) for n in way["nodes"] if n in nodes]

    points = (ll - center) * meters
    edges = np.roll(points, -1, axis=0) - points
    axis = max(edges, key=np.linalg.norm).copy()
    if axis[1 if north_axis else 0] < 0:
        axis = -axis
    theta = math.atan2(axis[1], axis[0])
    frame = {"fieldC": [0, 0], "axisTheta": theta, "maxR": 170}
    axis /= np.linalg.norm(axis)
    short_axis = np.array([-axis[1], axis[0]])

    def model_coords(points):
        return [[-float(np.dot(p, short_axis)), float(np.dot(p, axis))] for p in points]

    stadium = Polygon(coords(ways[stadium_id]))
    extent = box(-800, -800, 800, 800)
    data = {
        "source": "© OpenStreetMap contributors, ODbL; fresh OSM API extract",
        "treeSource": "OSM natural=tree; schematic crowns and heights",
        "green": [], "water": [], "roads": [], "buildings": [],
        "buildingHeights": [], "buildingIds": [], "trees": [],
        "heightQuality": "OSM tag where present; otherwise explicitly schematic",
    }
    evidence = {"rawSha256": hashlib.sha256(raw_bytes).hexdigest(),
                "fetch": json.loads((out / "fetch.json").read_text()),
                "pitchWay": pitch_id, "stadiumWay": stadium_id,
                "centerLonLat": center.tolist(),
                "pitchAxisEastNorth": axis.tolist(),
                "axisThetaDegrees": math.degrees(theta),
                "pitchEdgeLengthsMeters": [float(np.linalg.norm(v)) for v in edges],
                "selectionExtentEastNorthMeters": [-800, -800, 800, 800],
                "selectionNotes": [], "features": {k: [] for k in
                    ("green", "water", "roads", "buildings", "trees")}}

    def add_polygon(polygon, kind, source_id, tags, height=None, height_kind=None):
        if not polygon.is_valid:
            raise ValueError(f"Invalid OSM polygon {source_id}")
        if not polygon.intersects(extent):
            return
        # Selection extent only; never clip against the model or ground cutout.
        clipped = polygon.intersection(extent)
        pieces = list(clipped.geoms) if hasattr(clipped, "geoms") else [clipped]
        for piece in pieces:
            if piece.geom_type != "Polygon" or piece.area < .01:
                continue
            if piece.interiors:
                # Preserve real OSM holes as source-constrained triangles.
                pieces_without_holes = list(constrained_delaunay_triangles(piece).geoms)
                assert abs(sum(p.area for p in pieces_without_holes) - piece.area) < .01
            else:
                pieces_without_holes = [piece]
            for simple in pieces_without_holes:
                data[kind].append([list(p) for p in simple.exterior.coords[:-1]])
                evidence["features"][kind].append(
                    {"osm": source_id, "tags": tags, "heightKind": height_kind})
                if kind == "buildings":
                    data["buildingHeights"].append(height)
                    data["buildingIds"].append(source_id)

    def number(value):
        try:
            return float(str(value).replace(" m", "").replace(",", "."))
        except (TypeError, ValueError):
            return None

    def classify(tags):
        if tags.get("building") not in (None, "no"):
            return "buildings"
        if tags.get("natural") == "water" or tags.get("water") or tags.get("waterway") == "riverbank":
            return "water"
        if (tags.get("landuse") in ("grass", "meadow", "forest", "farmland", "orchard", "vineyard")
                or tags.get("natural") in ("wood", "scrub", "grassland", "heath")
                or tags.get("leisure") in ("park", "garden")):
            return "green"
        return None

    relation_way_ids = set()
    for rel in raw["elements"]:
        if rel["type"] != "relation" or rel.get("tags", {}).get("type") != "multipolygon":
            continue
        if rel["id"] == stadium_building_id:
            if stadium_wikidata:
                assert rel["tags"]["wikidata"] == stadium_wikidata
            else:
                # Some stadium building relations have no name/Wikidata.
                # Bind the explicit relation to both type and pitch location.
                assert rel.get("tags", {}).get("building") == "stadium"
                outer = [LineString(coords(ways[m["ref"]])) for m in rel["members"]
                         if m["type"] == "way" and m.get("role", "outer") == "outer"]
                assert any(poly.covers(Point(0, 0)) for poly in polygonize(unary_union(outer)))
            relation_way_ids.update(m["ref"] for m in rel["members"] if m["type"] == "way")
            evidence["selectionNotes"].append({
                "osm": f"relation/{rel['id']}",
                "reason": "The stadium itself is represented by the original Unity model, "
                          "not duplicated as an OSM building volume.",
            })
            continue
        kind = classify(rel.get("tags", {}))
        if kind not in ("green", "water", "buildings"):
            continue
        members = rel["members"]
        missing = [m["ref"] for m in members if m["type"] == "way" and m["ref"] not in ways]
        if missing:
            evidence["selectionNotes"].append(
                {"osm": f"relation/{rel['id']}", "reason": "incomplete boundary in API selection",
                 "missingWays": missing})
            continue
        rings = {}
        for role in ("outer", "inner"):
            lines = [LineString(coords(ways[m["ref"]])) for m in members
                     if m["type"] == "way" and m.get("role", "outer") == role]
            rings[role] = list(polygonize(unary_union(lines))) if lines else []
        if not rings["outer"]:
            continue
        for outer in rings["outer"]:
            geometry = outer.difference(unary_union(rings["inner"])) if rings["inner"] else outer
            pieces = list(geometry.geoms) if hasattr(geometry, "geoms") else [geometry]
            for polygon in pieces:
                add_polygon(polygon, kind, f"relation/{rel['id']}", rel.get("tags", {}),
                            height=9, height_kind="schematic")
        relation_way_ids.update(m["ref"] for m in members if m["type"] == "way")

    widths = {"motorway": 10, "trunk": 9, "primary": 8, "secondary": 7,
              "tertiary": 6, "residential": 5, "unclassified": 5, "service": 3.5,
              "footway": 1.6, "path": 1.4, "cycleway": 2, "track": 2.8,
              "pedestrian": 4, "steps": 1.6, "living_street": 4}
    for way in ways.values():
        tags = way.get("tags", {})
        pts = coords(way)
        if len(pts) < 2:
            continue
        source_id = f"way/{way['id']}"
        highway = tags.get("highway")
        if highway in widths and tags.get("area") != "yes":
            if tags.get("indoor") == "yes" or tags.get("tunnel") == "yes":
                evidence["selectionNotes"].append(
                    {"osm": source_id, "reason": "indoor or underground, not an outdoor ground feature"})
            else:
                line = LineString(pts).intersection(extent)
                lines = list(line.geoms) if hasattr(line, "geoms") else [line]
                for segment in lines:
                    if segment.geom_type == "LineString" and segment.length > .1:
                        explicit_width = number(tags.get("width"))
                        width = explicit_width or widths[highway]
                        data["roads"].append({"p": [list(p) for p in segment.coords],
                                              "w": width / 2.5, "t": highway})
                        evidence["features"]["roads"].append(
                            {"osm": source_id, "tags": tags,
                             "widthKind": "OSM width" if explicit_width else "schematic",
                             "displayWidthMeters": width,
                             "rendererWidthMultiplier": 2.5})
        if pts[0] != pts[-1] or len(pts) < 4 or way["id"] in relation_way_ids:
            continue
        kind = classify(tags)
        if not kind:
            continue
        # The mapped stadium is evidence for alignment, not another building.
        if way["id"] == stadium_id:
            continue
        height = number(tags.get("height"))
        height_kind = "OSM height"
        if not height:
            levels = number(tags.get("building:levels"))
            height = levels * 3 if levels else (3 if tags.get("building") in
                ("container", "ticket_booth", "service", "tent") else 9)
            height_kind = "derived from OSM levels" if levels else "schematic"
        add_polygon(Polygon(pts), kind, source_id, tags, height, height_kind)

    for node in nodes.values():
        if node.get("tags", {}).get("natural") == "tree" and extent.covers(Point(xy(node))):
            data["trees"].append(xy(node))
            evidence["features"]["trees"].append({"osm": f"node/{node['id']}"})

    opening = bowl_opening() if opening is None else opening
    write("bowl-opening.json", opening)
    data["groundLevel"] = opening["groundLevel"]
    data["groundCutout"] = opening["groundCutout"]
    evidence["terrainMethod"] = opening["method"]
    presentation = deepcopy(json.loads((study / "presentation.json").read_text())["presentation"])
    presentation["frame"] = frame
    presentation["surroundings"] = data
    if fmi == 918:
        presentation["calibration"]["skipMeshPrefixes"] = ["center2_"]
    manifest = json.loads((study / "manifest.json").read_text())
    manifest["calibration"] = deepcopy(presentation["calibration"])
    manifest["limits"] = [
        text for text in manifest["limits"]
        if "Geographic surroundings blocked" not in text
        and "OSM bundle heights" not in text
    ] + [
        "Fresh OSM surroundings; mapped footprints and tree positions, mostly schematic heights.",
        "Terrain is flat at the source apron level, not a measured DEM.",
        "Source bowl opening protects lower seats and pitch; underground foundations remain buried.",
        "OSM pitch polygon includes runoff; original painted lines remain 105x68m.",
    ]
    manifest.pop("assetVersion")
    manifest["assetVersion"] = hashlib.sha256(
        json.dumps(manifest, sort_keys=True).encode()).hexdigest()[:16]
    presentation["modelUrl"] = f"/models/{fmi}/{manifest['assetVersion']}/manifest.json"
    write("manifest.json", manifest)
    evidence["counts"] = {k: len(data[k]) for k in evidence["features"]}
    evidence["mappedStadiumModelCoordinates"] = model_coords(coords(ways[stadium_id]))
    write("surroundings.json", data)
    write("evidence.json", evidence)
    write("presentation.json", {"presentation": presentation})
    report = inspect_package(presentation, axes=presentation["calibration"]["surroundingsAxes"])
    write("terrain-check.json", report)
    print(json.dumps({"counts": evidence["counts"], "terrainOk": report["ok"],
                      "terrainDeclared": report.get("terrainDeclared"),
                      "findings": report.get("findings", [])[:15]}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fetch", action="store_true", help="Explicitly fetch a new OSM snapshot before building")
    args = parser.parse_args()
    if args.fetch:
        fetch_source()
    build()
