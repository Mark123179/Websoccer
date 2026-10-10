"""Read-only height/source matching for the isolated approved NE camera.

Input GML is downloaded separately from the documented LVGL WFS. No guessed
storey heights, no database access, no edits to source OSM or production scenes.
"""
import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

from shapely.geometry import Polygon
from shapely.ops import unary_union

from geo_probe_geometry import frame_from_osm, lonlat_to_scene

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "generated-artifacts/elversberg-height-visibility"
BASE = ROOT / "generated-artifacts/stadium-main-stand-back-probe"
NS = {
    "g": "http://www.opengis.net/gml/3.2",
    "b": "http://inspire.ec.europa.eu/schemas/bu-core3d/4.0",
    "a": "http://inspire.ec.europa.eu/schemas/bu-base/4.0",
}
WFS = "https://geoportal.saarland.de/gdi-sl/inspirewfs_Gebaeude_3D_LoD2"
BBOX = "49.316,7.120,49.319,7.125,urn:ogc:def:crs:EPSG::4326"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_buildings():
    buildings = []
    page_counts = []
    for filename in ("buildings.gml", "buildings-page2.gml"):
        path = OUT / "sources" / filename
        root = ET.parse(path).getroot()
        members = root.findall(".//b:Building", NS)
        page_counts.append(len(members))
        for b in members:
            polys = []
            for pos in b.findall(".//b:geometry3DLoD2//g:exterior/g:LinearRing/g:posList", NS):
                values = list(map(float, pos.text.split()))
                # EPSG:4326 official response is latitude, longitude, 2D.
                assert len(values) % 2 == 0
                poly = Polygon([(values[i + 1], values[i])
                                for i in range(0, len(values), 2)]).buffer(0)
                if not poly.is_empty and poly.area:
                    polys.append(poly)
            if not polys:
                continue
            value = b.find(".//a:HeightAboveGround/a:value", NS)
            if value is None or value.text is None:
                continue
            assert value.get("uom") == "m"
            status = b.find(".//a:HeightAboveGround/a:status", NS)
            status = status.get("{http://www.w3.org/1999/xlink}href", "") if status is not None else ""
            if not status.endswith("/measured"):
                continue
            buildings.append({
                "id": b.get(f"{{{NS['g']}}}id"),
                "height_m": float(value.text),
                "height_status": status,
                "version": b.findtext(".//a:beginLifespanVersion", namespaces=NS),
                "footprint": unary_union(polys),
            })
    # The service reports numberReturned=0 even for nonempty pages. Count
    # actual members and require a short final page rather than trusting it.
    assert page_counts[0] == 200 and 0 < page_counts[-1] < 200, page_counts
    assert len({b["id"] for b in buildings}) == len(buildings)
    return buildings, page_counts


def main():
    osm_path = ROOT / "stadium_editor/blueprints/v2/elversberg.json"
    osm = json.loads(osm_path.read_text())
    geo = json.loads((BASE / "geo_verification.json").read_text())
    frame = frame_from_osm(osm, 1154632806, 31339206)
    visible = {f["osm_id"] for state in geo["elversberg"]["states"].values()
               for f in state["mapped_visible_features"] if f["tags"].get("building")}
    buildings, page_counts = read_buildings()
    objects = []
    for e in osm["elements"]:
        tags = e.get("tags", {})
        if e["type"] != "way" or not tags.get("building") or tags["building"] == "grandstand":
            continue
        geometry = e.get("geometry", [])
        if len(geometry) < 4 or geometry[0] != geometry[-1]:
            continue
        polygon = Polygon([(p["lon"], p["lat"]) for p in geometry]).buffer(0)
        if polygon.is_empty:
            continue
        scores = sorted([
            (polygon.intersection(b["footprint"]).area /
             polygon.union(b["footprint"]).area, b)
            for b in buildings
        ], key=lambda pair: pair[0], reverse=True)
        iou, best = scores[0]
        parts = []
        for score, b in scores:
            overlap = polygon.intersection(b["footprint"]).area / polygon.area
            # Component evidence, not a geocoded name or nearest-point guess.
            if overlap >= .10 and score >= .10:
                parts.append({k: v for k, v in b.items() if k != "footprint"} |
                             {"iou": score, "osm_coverage": overlap})
        accepted = iou >= .45
        if not accepted and e["id"] not in visible:
            continue
        objects.append({
            "osm_id": e["id"], "name": tags.get("name", str(e["id"])),
            "osm_tags": tags, "ground_visible": e["id"] in visible,
            "polygon": [list(lonlat_to_scene(frame, p["lon"], p["lat"], True))
                        for p in geometry[:-1]],
            "matched": accepted, "best_iou": iou,
            "candidate_id": best["id"],
            "measured_height_m": best["height_m"] if accepted else None,
            "height_components": parts,
            "height_envelope_m": max(p["height_m"] for p in parts) if accepted else None,
        })
    assert {30887518, 53864241, 53864244} <= {o["osm_id"] for o in objects}
    report = {
        "classification": "Conditional measured-height envelope visibility study; NOT surveyed facade visibility",
        "camera": json.loads((BASE / "camera_exact.json").read_text()),
        "frame": frame, "objects": objects,
        "matching": {"iou_acceptance": .45, "page_member_counts": page_counts,
                     "ground_visible_buildings": len(visible),
                     "ground_visible_matched": sum(o["matched"] and o["ground_visible"] for o in objects),
                     "reason": "OSM footprints remain fixed; LVGL polygon union used only to match measured heights."},
        "provenance": {
            "wfs": WFS, "bbox_lat_lon": BBOX, "retrieved_date": "2026-10-10",
            "query": {"SERVICE": "WFS", "VERSION": "2.0.0", "REQUEST": "GetFeature",
                      "TYPENAMES": "bu-core3d:Building",
                      "SRSNAME": "urn:ogc:def:crs:EPSG::4326", "BBOX": BBOX,
                      "COUNT": 200, "STARTINDEX": [0, 200]},
            "license": "©LVGL 2022, dl-de/by-2-0, www.lvgl.saarland.de",
            "osm_license": "© OpenStreetMap contributors, ODbL 1.0",
            "osm_timestamp": osm["osm3s"]["timestamp_osm_base"],
            "height_reference": "HeightStatus=measured; lowReference=unknown, heightReference=nil",
            "no_capture_date_claim": True,
            "sha256": {str(p.relative_to(ROOT)): sha(p) for p in [
                osm_path, BASE / "verification.json", BASE / "camera_exact.json",
                BASE / "geo_verification.json", OUT / "sources/buildings.gml",
                OUT / "sources/buildings-page2.gml", OUT / "sources/lod2-capabilities.xml",
            ]},
        },
        "limits": [
            "Flat common y=0 terrain datum. No real relative ground elevations.",
            "OSM block envelopes at measured maximum height, not original LoD2 roof/facade geometry.",
            "TVE consists of multiple official buildings; envelope is deliberately conservative.",
            "Lidl correspondence is rejected; its height remains UNKNOWN, not 6.105m.",
            "Unmatched buildings and vegetation are not assigned invented heights.",
            "Trees, signs, terrain, and missing buildings can invalidate conditional sightlines.",
            "No production integration, no AI images, no camera or source-location changes.",
        ],
    }
    (OUT / "height_inputs.json").write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(json.dumps(report["matching"], indent=2))
    for o in objects:
        if o["osm_id"] in (30887518, 53864241, 53864244):
            print(o["name"], o["best_iou"], o["height_envelope_m"], o["height_components"])


if __name__ == "__main__":
    main()
