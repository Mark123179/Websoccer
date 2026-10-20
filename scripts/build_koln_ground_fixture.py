"""Explicit local extraction of small real ground witnesses; never downloads.

Run only against the full, hashed study sources. The checker still owns all
sampling, limits and bridge decisions. No deck height is derived here.
"""
import argparse
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import rasterio
from rasterio.windows import Window, transform
from shapely.geometry import Point, Polygon

from scripts.check_koln_height_profiles import (
    profiles_for, renderer_samples, run, STUDY,
)
from scripts.koln_profile_sources import NativeDGM, model_projection
from scripts.koln_bridge_heights import bridge_records

OUT = Path("game/tests/fixtures/koln-ground")
BRIDGES = ("way/5229974", "way/362049118")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def reconstruct_display(presentation_path, evidence_path, source_path, target):
    """Ground-only replay of refine_koln_heights, without the unrelated LoD2 import.

    Explicit opt-in: writes a NEW diagnostic presentation, never a live asset.
    """
    document = json.loads(presentation_path.read_text())
    p = document["presentation"]
    evidence = json.loads(evidence_path.read_text())
    sources = json.loads(source_path.read_text())
    native = NativeDGM(source_path.parent, sources, model_projection(p, evidence, sources))
    reference = float(np.median([native(x, z) for x in (-20, -10, 0, 10, 20)
                                 for z in (-35, -17.5, 0, 17.5, 35)]))
    apron = Polygon(evidence["mappedStadiumModelCoordinates"]).buffer(20)
    values = []
    for z in range(-1200, 1201, 20):
        for x in range(-1200, 1201, 20):
            measured = native(x, z)
            t = min(1., apron.distance(Point(x, z))/40)
            weight = t*t*(3-2*t)
            values.append(round((measured-reference-p["surroundings"]["groundLevel"])*weight, 4))
    p["surroundings"]["groundElevation"] = {
        "origin": [-1200, -1200], "step": 20, "cols": 121, "rows": 121, "values": values,
        "source": "Geobasis NRW WCS DGM1; EPSG:25832 / DHHN2016; 1 m source, 20 m display grid"}
    p["surroundings"]["heightEvidence"] = {
        "terrainReferenceNHN": reference, "bridges": bridge_records(p["surroundings"], evidence)}
    target.parent.mkdir(parents=True, exist_ok=True)
    write_json(target, document)
    return target


def build(presentation_path, evidence_path, source_path, output):
    # A missing, changed, non-native or incomplete input fails in the real checker.
    report = run(presentation_path, evidence_path, source_path)
    p = json.loads(presentation_path.read_text())["presentation"]
    evidence = json.loads(evidence_path.read_text())
    sources = json.loads(source_path.read_text())
    native = NativeDGM(source_path.parent, sources, model_projection(p, evidence, sources))
    profiles = profiles_for(p, renderer_samples(p, [])["roads"], evidence)
    by_id = {profile["id"]: profile for profile in profiles}
    specs = []
    for osm in BRIDGES:
        profile = next(row for row in profiles if row.get("osm") == osm)
        index = int(profile["id"].split("-")[1])
        specs.append({"id": osm.replace("/", "-"), "profile": deepcopy(profile),
                      "role": "complete_bridge_ground_profile",
                      "editorPoints": p["surroundings"]["roads"][index]["p"],
                      "sourceFeature": evidence["features"]["roads"][index]})
    # Keep actual worst locations, not artificial surfaces that merely fail a limit.
    for violation in report["violations"]:
        zone, metric = violation["zone"], violation["metric"]
        if metric == "p95AbsMeters":
            rows = sorted((r for r in report["samples"] if r["zone"] == zone),
                          key=lambda r: abs(r["errorMeters"]))
            rank = .95 * (len(rows) - 1)  # NumPy's linear percentile convention
            for index in sorted({math.floor(rank), math.ceil(rank)}):
                row = rows[index]
                profile = {**by_id[row["profile"]], "points": [row["xz"]]}
                specs.append({"id": f"{zone}-p95-rank-{index}", "profile": profile,
                              "role": "percentile_rank_witness", "alarm": violation,
                              "population": len(rows), "rank": index,
                              "fractionalRank": rank})
            continue
        stats = report["zones"][zone]
        if metric == "maxAbsMeters":
            row = stats["worst"]
            points = [row["xz"]]
        elif metric == "maxGradeErrorPP":
            row = stats[metric + "Location"]
            points = [row["fromXZ"], row["xz"]]
        else:
            row = stats[metric + "Location"]
            original = by_id[row["profile"]]["points"]
            station = original.index(row["xz"])
            points = original[station-1:station+2]
        specs.append({"id": f"{zone}-{metric}", "role": "worst_alarm_witness",
                      "alarm": violation,
                      "profile": {**by_id[row["profile"]], "points": points}})

    output.mkdir(parents=True, exist_ok=True)
    cases, crops = [], []
    grid = p["surroundings"]["groundElevation"]
    values = np.asarray(grid["values"]).reshape(grid["rows"], grid["cols"])
    for spec in specs:
        points = spec["profile"]["points"]
        utm = [native.project(*point) for point in points]
        pixels = [(~native.affine) * point for point in utm]
        # Include precisely the pixel-centred bilinear 2x2 neighbourhoods.
        left = min(math.floor(c-.5) for c, r in pixels)
        top = min(math.floor(r-.5) for c, r in pixels)
        right = max(math.floor(c-.5)+2 for c, r in pixels)
        bottom = max(math.floor(r-.5)+2 for c, r in pixels)
        window = Window(left, top, right-left, bottom-top)
        crop = native.values[top:bottom, left:right]
        if np.ma.getmaskarray(crop).any() or not np.isfinite(crop).all():
            raise ValueError("Witness crop must contain only real native pixels")
        name = spec["id"] + ".tif"
        path = output / name
        with rasterio.open(path, "w", driver="GTiff", height=bottom-top,
                           width=right-left, count=1, dtype=str(crop.dtype),
                           crs="EPSG:25832", transform=transform(window, native.affine),
                           nodata=-9999, compress="deflate") as ds:
            ds.write(crop, 1)  # exact original values, no resampling or rounding
        crops.append({"file": name, "sha256": sha(path), "bytes": path.stat().st_size,
                      "mosaicWindow": [left, top, right-left, bottom-top],
                      "transform": list(transform(window, native.affine))[:6]})
        # Minimal cells from the real display grid; still sampled by the JS renderer.
        cols = [math.floor((x-grid["origin"][0])/20) for x, z in points]
        rows = [math.floor((z-grid["origin"][1])/20) for x, z in points]
        c0, r0, c1, r1 = min(cols), min(rows), max(cols)+2, max(rows)+2
        local_grid = {**grid, "origin": [grid["origin"][0]+20*c0, grid["origin"][1]+20*r0],
                      "cols": c1-c0, "rows": r1-r0,
                      "values": values[r0:r1, c0:c1].flatten().tolist()}
        expected = {}
        for key in ("samples", "roadSlopes", "roadGradeChanges"):
            selected = [row for row in report[key] if row["profile"] == spec["profile"]["id"]]
            if spec["role"] != "complete_bridge_ground_profile":
                selected = [row for row in selected if
                            (key == "samples" and row["xz"] in points) or
                            (key == "roadSlopes" and row["xz"] in points[1:]) or
                            (key == "roadGradeChanges" and row["xz"] in points[1:-1])]
            expected[key] = selected
        cases.append({**spec, "utmCoordinates": utm, "groundElevation": local_grid,
                      "expected": expected})
    fixture = {
        "schema": 1, "surface": "bare_earth_not_bridge_deck",
        "provider": sources["provider"], "license": sources["license"],
        "licenseUrl": "https://www.govdata.de/dl-de/zero-2-0",
        "osmAttribution": "© OpenStreetMap contributors, ODbL 1.0",
        "osmLicenseUrl": "https://www.openstreetmap.org/copyright",
        "crs": "EPSG:25832", "verticalDatum": sources["verticalDatum"],
        "sourceRasters": [s for s in sources["sources"] if s["file"].endswith(".tif")],
        "sourceInputs": report["inputs"], "osmRawSha256": report["osmRawSha256"],
        "presentation": {k: p[k] for k in ("frame", "calibration")},
        "registration": {k: evidence[k] for k in ("centerLonLat", "axisThetaDegrees")},
        "centerUTM": sources["centerUTM"], "sources": crops,
        "referenceNHN": report["referenceNHN"],
        "groundLevel": p["surroundings"]["groundLevel"],
        "apronBoundary": evidence["mappedStadiumModelCoordinates"],
        "cutout": p["surroundings"]["groundCutout"],
        "fullRun": {"counts": {key: len(report[key]) for key in
                               ("profiles", "samples", "roadSlopes", "roadGradeChanges")},
                    "limits": report["limits"], "violations": report["violations"],
                    "ok": report["ok"]},
        "cases": cases,
    }
    path = output / "ground.json"
    write_json(path, fixture)
    write_json(output / "manifest.json", {"schema": 1, "file": path.name,
                                         "sha256": sha(path), "sources": crops})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--presentation", type=Path, default=STUDY / "osm-fresh/presentation.json")
    parser.add_argument("--evidence", type=Path, default=STUDY / "osm-fresh/evidence.json")
    parser.add_argument("--sources", type=Path, default=STUDY / "heights/sources.json")
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--reconstruct-display", action="store_true",
                        help="Explicitly rebuild the ground-only display into generated-artifacts")
    args = parser.parse_args()
    if args.reconstruct_display:
        args.presentation = reconstruct_display(
            args.presentation, args.evidence, args.sources,
            STUDY / "heights/ground-fixture-presentation.json")
    build(args.presentation, args.evidence, args.sources, args.output)


if __name__ == "__main__":
    main()
