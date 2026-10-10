"""Read-only, shared Elversberg surroundings in the canonical pitch frame.

Buildings come from exact OSM identities, never nearest legacy-footprint guesses.
The immutable evidence extract deliberately labels LVGL heights conditional:
unknown terrain and height reference prevent claims of surveyed sightlines.
"""
from copy import deepcopy
from functools import lru_cache
import hashlib
import json
import logging
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parent / "blueprints" / "v2"
ELVERSBERG_FMI_ID = 121200
STYLE = "elversberg-blueprint"
LOGGER = logging.getLogger(__name__)
SCHEMATIC_HEIGHT = 6.0
RADIUS = 350.0


def _ring(points):
    result = [[float(x), float(y)] for x, y in points]
    if result and result[0] == result[-1]:
        result.pop()
    if len(result) < 3 or any(not math.isfinite(v) for p in result for v in p):
        raise ValueError("Ungültiger Elversberger Umfeldgrundriss.")
    if abs(sum(a[0] * b[1] - b[0] * a[1]
               for a, b in zip(result, result[1:] + result[:1]))) < .001:
        raise ValueError("Elversberger Umfeldgrundriss ohne Fläche.")
    return result


def _bounds(poly):
    return [min(p[0] for p in poly), min(p[1] for p in poly),
            max(p[0] for p in poly), max(p[1] for p in poly)]


def _overlap(a, b):
    return not (a[2] < b[0] or b[2] < a[0] or a[3] < b[1] or b[3] < a[1])


@lru_cache(maxsize=2)
def _source(osm_stamp, blueprint_stamp, evidence_stamp):
    """Cache source parsing only, not current stadium geometry/design."""
    osm_bytes = (ROOT / "elversberg.json").read_bytes()
    osm = json.loads(osm_bytes)
    blueprint = json.loads((ROOT / "elversberg_v2.json").read_text())
    evidence = json.loads((ROOT / "elversberg_height_evidence.json").read_text())
    if hashlib.sha256(osm_bytes).hexdigest() != evidence["osm_sha256"]:
        raise ValueError("Elversberger OSM-Quelle passt nicht zum Höhenbeleg.")
    ways = {e["id"]: e for e in osm["elements"] if e["type"] == "way"}
    reference = ways[1154632806]["geometry"][0]
    latitude, longitude = reference["lat"], reference["lon"]
    scale_x = 111320 * math.cos(math.radians(latitude))

    def local(p):
        return ((p["lon"] - longitude) * scale_x,
                (p["lat"] - latitude) * 111320)

    pitch = ways[31339206]["geometry"][:-1]
    xy = [local(p) for p in pitch]
    center = [sum(p[axis] for p in xy) / len(xy) for axis in (0, 1)]
    _, theta = max(
        (math.hypot(b[0] - a[0], b[1] - a[1]),
         math.atan2(b[1] - a[1], b[0] - a[0]))
        for a, b in zip(xy, xy[1:] + xy[:1])
    )
    ct, st = math.cos(theta), math.sin(theta)

    def native(p):
        east, north = local(p)
        east -= center[0]
        north -= center[1]
        # Native V2 frame: [-u,-v]. Approved half-turn world frame is [-u,+v].
        return [round(-east * ct - north * st, 4),
                round(east * st - north * ct, 4)]

    protected = []
    for way in ways.values():
        tags = way.get("tags", {})
        if tags.get("leisure") in ("pitch", "stadium") or tags.get("building") == "grandstand":
            points = [native(p) for p in way.get("geometry", [])]
            if len(points) >= 3:
                protected.append(_bounds(points))

    buildings = []
    for osm_id, way in ways.items():
        tags = way.get("tags", {})
        geometry = way.get("geometry", [])
        if not tags.get("building") or tags["building"] == "grandstand":
            continue
        if len(geometry) < 4 or geometry[0] != geometry[-1]:
            continue
        poly = _ring([native(p) for p in geometry])
        if min(math.hypot(*p) for p in poly) > RADIUS:
            continue
        values = evidence["values"].get(str(osm_id))
        if values is not None and (
            len(values) != 2 or not 0 < values[0] < 100 or not .45 <= values[1] <= 1
        ):
            raise ValueError("Ungültiger Elversberger Höhenbeleg.")
        buildings.append({
            "id": f"osm-way-{osm_id}",
            "osmId": osm_id,
            "name": tags.get("name", ""),
            "poly": poly,
            "h": values[0] if values else SCHEMATIC_HEIGHT,
            "heightStatus": "conditional-lvgl-envelope" if values else "schematic-not-measured",
            "heightMatchIou": values[1] if values else None,
        })

    legacy = blueprint["surroundings"]
    roads = []
    for index, road in enumerate(legacy["roads"]):
        points = [[float(v) for v in p] for p in road["p"]]
        if len(points) < 2 or any(not math.isfinite(v) for p in points for v in p):
            raise ValueError("Ungültige Elversberger Straßenlinie.")
        roads.append({"id": f"v2-road-{index}", "p": points, "w": road.get("w", 1)})
    green, vegetation = [], []
    occupied = protected + [_bounds(b["poly"]) for b in buildings]
    for index, points in enumerate(legacy["green"]):
        poly = _ring(points)
        # Conservative exclusion: never populate a playing surface, building or
        # stadium with schematic vegetation, even for partly crossing polygons.
        if any(_overlap(_bounds(poly), box) for box in occupied):
            continue
        green.append(poly)
        vegetation.append({
            "id": f"v2-green-{index}", "poly": poly, "height": 3.5,
            "heightStatus": "schematic-not-measured",
            "kind": "schematic-vegetation-group",
        })
    return {
        "style": STYLE, "version": 1, "frame": "pitch",
        "source": "© OpenStreetMap contributors, ODbL 1.0; " + evidence["license"],
        "buildings": buildings, "roads": roads, "green": green,
        "vegetation": vegetation,
        "evidence": {
            "heightStatus": evidence["classification"],
            "heightSource": evidence["source"],
            "heightReference": evidence["height_reference"],
            "schematicHeight": SCHEMATIC_HEIGHT,
            "terrain": "flat-reference-not-surveyed",
            "vegetation": "schematic-groups-not-surveyed-trees-or-forest",
            "roadsAndGreen": "legacy-v2-osm-shapes-without-individual-source-ids",
            "osmSha256": evidence["osm_sha256"],
            "priorityIds": [f"osm-way-{i}" for i in (30887518, 53864244, 53864241)],
        },
    }


def load_surroundings():
    stamps = [(ROOT / name).stat().st_mtime_ns for name in (
        "elversberg.json", "elversberg_v2.json", "elversberg_height_evidence.json",
    )]
    return deepcopy(_source(*stamps))


def club_surroundings(club):
    if getattr(club, "fm_inside_id", None) != ELVERSBERG_FMI_ID:
        return None
    try:
        return load_surroundings()
    except (OSError, ValueError, KeyError, TypeError) as exc:
        LOGGER.warning("Elversberger Umfeldquelle nicht verfügbar: %s", exc)
        return {
            "style": STYLE, "frame": "pitch", "unavailable": True,
            "warning": "Elversberger Umgebung nicht verfügbar; Stadion bleibt sichtbar.",
            "buildings": [], "roads": [], "green": [], "vegetation": [],
        }


def with_editor_surroundings(geometry, club):
    surroundings = club_surroundings(club)
    if surroundings is None:
        return geometry
    result = deepcopy(geometry)
    theta = float(result["meta"]["axisTheta"])
    center = result["meta"].get("fieldC", [0, 0])
    ct, st = math.cos(theta), math.sin(theta)

    def raw(point):
        return [point[0] * ct - point[1] * st + center[0],
                point[0] * st + point[1] * ct + center[1]]

    for building in surroundings["buildings"]:
        building["poly"] = [raw(p) for p in building["poly"]]
    for road in surroundings["roads"]:
        road["p"] = [raw(p) for p in road["p"]]
    surroundings["green"] = [[raw(p) for p in poly] for poly in surroundings["green"]]
    for group in surroundings["vegetation"]:
        group["poly"] = [raw(p) for p in group["poly"]]
    surroundings["frame"] = "editor"
    result["surroundings"] = surroundings
    # Legacy editor bg must not shadow the new common source.
    result.pop("bg", None)
    return result
