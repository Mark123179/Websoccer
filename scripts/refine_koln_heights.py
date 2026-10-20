"""Join documented NRW heights to the unchanged Cologne OSM catalog.

Offline only. Run koln_height_sources first; --install is deliberately absent.
Unmatched buildings retain their disclosed schematic envelopes, never guesses
reported as measurements. Neither economic data nor manager designs are read.
"""
from collections import Counter
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np
from pyproj import Transformer
import rasterio
from rasterio.merge import merge
from shapely.geometry import Polygon, Point
from shapely.ops import unary_union, transform as shape_transform
from shapely.strtree import STRtree

from stadium_editor.package_preflight import inspect_package
from scripts.koln_building_parts import component_group, DATUM

STUDY = Path("generated-artifacts/koln-study")
REVIEW = STUDY / "osm-fresh"
HEIGHTS = STUDY / "heights"
NS = {"b": "http://www.opengis.net/citygml/building/1.0",
      "g": "http://www.opengis.net/gml",
      "gen": "http://www.opengis.net/citygml/generics/1.0"}
GID = "{" + NS["g"] + "}id"
from scripts.koln_bridge_heights import bridge_records


def write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def lod_buildings(files):
    """Use explicit GroundSurface rings, not a projected roof or bounding box."""
    result, rejected = {}, []
    for file in files:
        srs_name = None
        for _, root in ET.iterparse(file, events=("end",)):
            if root.tag == "{" + NS["g"] + "}Envelope":
                srs_name = root.get("srsName")
            if root.tag != "{" + NS["b"] + "}Building":
                continue
            components = [root, *root.findall(".//b:BuildingPart", NS)]
            for obj in components:
                polygons, zs = [], []
                for surface in obj.findall("b:boundedBy/b:GroundSurface", NS):
                    for polygon in surface.findall(".//g:Polygon", NS):
                        rings = []
                        for path in ("g:exterior/g:LinearRing/g:posList",
                                     "g:interior/g:LinearRing/g:posList"):
                            for ring in polygon.findall(path, NS):
                                xyz = np.asarray(list(map(float, ring.text.split()))).reshape(-1, 3)
                                rings.append(xyz[:, :2].tolist())
                                zs.extend(xyz[:, 2].tolist())
                        if rings:
                            polygons.append(Polygon(rings[0], rings[1:]))
                height = obj.find("b:measuredHeight", NS)
                if not polygons or height is None:
                    continue
                identity = obj.get(GID)
                if any(not polygon.is_valid or polygon.area <= 0 for polygon in polygons):
                    rejected.append({"id": identity, "file": file.name,
                                     "reason": "invalid_or_zero_area_ground_surface"})
                    continue
                footprint = unary_union(polygons)
                attrs = {a.get("name"): a.findtext("gen:value", namespaces=NS)
                         for a in obj.findall("gen:stringAttribute", NS)}
                entry = {
                    "id": identity, "file": file.name, "footprint": footprint,
                    "height": float(height.text), "heightUnit": height.get("uom"),
                    "baseNHN": min(zs), "baseMaxNHN": max(zs), "attributes": attrs,
                    "srsName": srs_name,
                }
                roof_zs = [float(v) for ring in obj.findall(
                    "b:boundedBy/b:RoofSurface//g:posList", NS)
                    for v in ring.text.split()[2::3]]
                if roof_zs:
                    entry.update(roofNHN=max(roof_zs), roofMinNHN=min(roof_zs))
                entry["roofSurfaces"] = []
                for si, surface in enumerate(obj.findall("b:boundedBy/b:RoofSurface", NS)):
                    for pi, polygon in enumerate(surface.findall(".//g:Polygon", NS)):
                        rings = []
                        for path in ("g:exterior/g:LinearRing/g:posList",
                                     "g:interior/g:LinearRing/g:posList"):
                            for ring in polygon.findall(path, NS):
                                values = list(map(float, ring.text.split()))
                                if len(values) % 3:
                                    raise ValueError(f"Invalid RoofSurface coordinates: {identity}")
                                rings.append([values[i:i+3] for i in range(0, len(values), 3)])
                        entry["roofSurfaces"].append({
                            "surfaceId": surface.get(GID) or f"{identity}/RoofSurface/{si}",
                            "polygonId": polygon.get(GID) or f"{identity}/RoofSurface/{si}/Polygon/{pi}",
                            "ringsUTM": rings,
                        })
                if not footprint.is_valid or footprint.area <= 0:
                    rejected.append({"id": identity, "file": file.name,
                                     "reason": "invalid_or_zero_area_footprint"})
                    continue
                if identity in result:
                    old = result[identity]
                    if (any(old.get(k) != entry.get(k) for k in
                            ("height", "heightUnit", "baseNHN", "baseMaxNHN",
                             "roofNHN", "roofMinNHN", "srsName", "attributes", "roofSurfaces"))
                            or not old["footprint"].equals(footprint)):
                        raise ValueError(f"Conflicting tile duplicate: {identity}")
                else:
                    result[identity] = entry
            root.clear()
    return list(result.values()), rejected


def select_height(polygon, candidates):
    """Symmetric ≥85% overlap, unique match, laser-derived roof heights only."""
    matches = []
    for c in candidates:
        area = polygon.intersection(c["footprint"]).area
        cover, purity = area / polygon.area, area / c["footprint"].area
        if cover >= .85 and purity >= .85:
            matches.append((c, cover, purity))
    if len(matches) != 1:
        return None, "no_unique_symmetric_85pct_match"
    c, cover, purity = matches[0]
    if (c["attributes"].get("DatenquelleDachhoehe") != "1000"
            or not (c["heightUnit"] or "").endswith(":m") or not 1 <= c["height"] <= 100):
        return None, "not_documented_laser_height"
    return (c, cover, purity), None


def refine():
    source = json.loads((HEIGHTS / "sources.json").read_text())
    for item in source["sources"]:
        if hashlib.sha256((HEIGHTS / item["file"]).read_bytes()).hexdigest() != item["sha256"]:
            raise ValueError(f"Source changed: {item['file']}")
    # Always start from the fresh catalog, not a previously refined result.
    original = REVIEW / "height-baseline-presentation.json"
    ev = json.loads((REVIEW / "evidence.json").read_text())
    current = json.loads((REVIEW / "presentation.json").read_text())
    if "groundElevation" not in current["presentation"]["surroundings"]:
        write(original, {**current, "rawSha256": ev["rawSha256"]})
    baseline = json.loads(original.read_text())
    if baseline.get("rawSha256") != ev["rawSha256"]:
        raise ValueError("OSM baseline changed. Rebuild with scripts.build_koln_review before refining.")
    p = baseline["presentation"]
    data = p["surroundings"]
    before = deepcopy(data)
    lon, lat = ev["centerLonLat"]
    meters = np.array([math.cos(math.radians(lat)), 1]) * 6371000 * math.pi / 180
    to_utm = Transformer.from_crs(4326, 25832, always_xy=True)
    if math.dist(to_utm.transform(lon, lat), source["centerUTM"]) > .01:
        raise ValueError("NRW source extent was acquired for a different pitch center; fetch again.")

    def en_to_utm(x, y, z=None):
        return to_utm.transform(lon + np.asarray(x) / meters[0],
                                lat + np.asarray(y) / meters[1])

    from_utm = Transformer.from_crs(25832, 4326, always_xy=True)

    def utm_to_editor(x, y, z=None):
        longitude, latitude = from_utm.transform(x, y)
        return ((np.asarray(longitude) - lon) * meters[0],
                (np.asarray(latitude) - lat) * meters[1])

    theta = p["frame"]["axisTheta"]
    # Inverse of the common editor->model conversion, using the proven +z north frame.
    def model_utm(x, z):
        return en_to_utm(z*math.cos(theta)+x*math.sin(theta),
                         z*math.sin(theta)-x*math.cos(theta))

    datasets = [rasterio.open(HEIGHTS / item["file"]) for item in source["sources"]
                if item["file"].endswith(".tif")]
    try:
        if any(ds.crs.to_epsg() != 25832 or ds.res != (1., 1.) for ds in datasets):
            raise ValueError("Expected native 1 m EPSG:25832 DGM")
        raster, affine = merge(datasets, masked=True)
        values = raster[0]
        def sample(x, z):
            east, north = model_utm(x, z)
            col, row = (~affine) * (east, north)
            col, row = col-.5, row-.5
            i, j = math.floor(col), math.floor(row)
            if i < 0 or j < 0 or i+1 >= values.shape[1] or j+1 >= values.shape[0]:
                raise ValueError("DGM coverage missing")
            window = values[j:j+2, i:i+2]
            if np.ma.getmaskarray(window).any() or not np.isfinite(window).all():
                raise ValueError("DGM nodata: no synthetic replacement allowed")
            a, b = col-i, row-j
            return float(window[0,0]*(1-a)*(1-b) + window[0,1]*a*(1-b) +
                         window[1,0]*(1-a)*b + window[1,1]*a*b)

        reference_samples = [sample(x,z) for x in (-20, -10, 0, 10, 20)
                             for z in (-35,-17.5,0,17.5,35)]
        reference = float(np.median(reference_samples))
        stadium_poly = Polygon(ev["mappedStadiumModelCoordinates"]).buffer(20)
        grid_values, raw_values, transitions = [], [], Counter()
        for z in range(-1200,1201,20):
            for x in range(-1200,1201,20):
                measured = sample(x,z)
                raw_values.append(measured)
                distance = stadium_poly.distance(Point(x,z))
                t = min(1., distance/40)
                weight = t*t*(3-2*t)
                transitions["modelApron" if t == 0 else "measured" if t == 1 else "transition"] += 1
                grid_values.append(round((measured-reference-data["groundLevel"])*weight, 4))
    finally:
        for ds in datasets:
            ds.close()
    data["groundElevation"] = {
        "origin": [-1200,-1200], "step": 20, "cols": 121, "rows": 121,
        "values": grid_values,
        "source": "Geobasis NRW WCS DGM1; EPSG:25832 / DHHN2016; 1 m source, 20 m display grid",
    }
    buildings, rejected = lod_buildings([HEIGHTS / s["file"] for s in source["sources"]
                                        if s["file"].endswith(".gml")])
    tree = STRtree([c["footprint"] for c in buildings])
    matches, groups = [], []
    for index, raw in enumerate(data["buildings"]):
        poly = shape_transform(en_to_utm, Polygon(raw))
        candidates = [buildings[i] for i in tree.query(poly)]
        selected, reason = select_height(poly, candidates)
        group = component_group(index, data["buildingIds"][index], poly, candidates, utm_to_editor,
                                editor_polygon=Polygon(raw))
        if group:
            assert selected is None, "Multipart representation must not grant a whole-building height"
            groups.append(group)
        row = {"index": index, "osm": data["buildingIds"][index],
               "previousHeight": before["buildingHeights"][index]}
        if selected:
            c, cover, purity = selected
            data["buildingHeights"][index] = c["height"]
            row.update(status="official_laser_height", lodId=c["id"], file=c["file"],
                       height=c["height"], baseNHN=c["baseNHN"],
                       osmCoverage=cover, officialCoverage=purity,
                       sourceAttributes=c["attributes"])
        else:
            row.update(status="unmeasured_retained_envelope", reason=reason,
                       previousHeightKind=ev["features"]["buildings"][index]["heightKind"])
        matches.append(row)
    stats = dict(Counter(row["status"] for row in matches))
    data["heightQuality"] = "NRW DGM1 terrain; verified LoD2 laser heights only; unmatched envelopes explicitly unmeasured"
    data["source"] = "© OpenStreetMap contributors (ODbL); Geobasis NRW DGM1 + LoD2 (dl-de/zero-2-0)"
    data["heightEvidence"] = {
        "bridges": bridge_records(data, ev),
        "buildingCounts": stats,
        "buildings": [{k:v for k,v in row.items() if k in
                      ("index","osm","status","lodId","height","reason")} for row in matches],
        "terrainReferenceNHN": reference,
        "terrainTransition": "OSM stadium footprint +20 m kept at source apron; 40 m smooth model transition, not surveyed",
    }
    data["buildingParts"] = {
        "version": 1, "verticalDatum": DATUM, "referenceNHN": reference,
        "source": "Geobasis NRW LoD2 GroundSurface/RoofSurface; roof laser 1000, ground DGM 1100",
        "groups": groups,
    }
    for layer in ("roads","green","water","trees","buildings","buildingIds","groundCutout","groundLevel"):
        assert data[layer] == before[layer], f"Source layer modified: {layer}"
    report = inspect_package(p, axes=p["calibration"]["surroundingsAxes"])
    assert report["ok"] and report["terrainDeclared"] and not report["findings"], report
    provenance = {
        "sources": source, "buildingMatchPolicy": "Unique symmetric overlap >=85%, Dachhoehe source=1000 (laser); no nearest-neighbor guessing.",
        "buildingCoverage": stats, "officialComponentsRead": len(buildings), "buildings": matches,
        "rejectedOfficialComponents": rejected,
        "buildingParts": deepcopy(data["buildingParts"]),
        "terrain": {"referenceNHN": reference, "referenceSamplesNHN": reference_samples,
                    "referenceMethod": "Median of 25 native DGM samples inside the painted pitch; Unity pitch is local zero.",
                    "nativeResolutionMeters": 1, "renderGridMeters": 20,
                    "gridBoundsModelXZ": [-1200,-1200,1200,1200],
                    "nativeSamplesRangeNHN": [min(raw_values),max(raw_values)],
                    "relativeOffsetsRange": [min(grid_values),max(grid_values)],
                    "coverage": dict(transitions), "nodataSamples": 0,
                    "flatApronBoundaryModelXZ": list(map(list,stadium_poly.exterior.coords)),
                    "transitionWidthMeters": 40,
                    "limits": "20 m generalization, model apron/transition is not a measurement; no resurvey or LoD2 roof reconstruction."},
        "unchangedSourceLayers": ["roads","green","water","trees","buildings","buildingIds","groundCutout","groundLevel"],
        "preflight": report,
    }
    write(HEIGHTS / "height-evidence.json", provenance)
    write(REVIEW / "surroundings.json", data)
    write(REVIEW / "presentation.json", {"presentation":p})
    write(REVIEW / "terrain-check.json", report)
    # Preserve model assets/version. This task changes only environment data.
    geometry_path = STUDY / "editor-geometry.json"
    geometry = json.loads(geometry_path.read_text())
    geometry["surroundings"] = deepcopy(data)
    geometry["bg"] = deepcopy(data)
    geometry["bg"]["buildings"] = [{"poly":poly,"h":h,"id":identity}
        for poly,h,identity in zip(data["buildings"],data["buildingHeights"],data["buildingIds"],strict=True)]
    write(geometry_path, geometry)
    print(json.dumps({**stats, "terrain": provenance["terrain"], "preflight":report}))


if __name__ == "__main__":
    refine()
