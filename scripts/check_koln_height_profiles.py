"""Offline, read-only display-vs-native check. Exit 1 = deviation, 2 = missing evidence.

No Django, database writes, source downloads, smoothing, or terrain correction.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys

import numpy as np
from shapely.geometry import LineString, Point, Polygon

from scripts.koln_profile_sources import NativeDGM, model_projection

STUDY = Path("generated-artifacts/koln-study")
ZONES = ("measured", "modelApron", "transition")
# Acceptance alarms, NOT claims about accuracy of either data product.
LIMITS = {
    "measured": {"maxAbsMeters": 2., "p95AbsMeters": .75},
    "modelApron": {"maxAbsMeters": 3., "p95AbsMeters": 2.},
    "transition": {"maxAbsMeters": 3., "p95AbsMeters": 2.},
}
ROAD_LIMITS = {"maxGradeErrorPP": 20., "maxGradeChangeErrorPP": 20.}
BRIDGE = Path(__file__).with_name("sample_koln_profiles.mjs")


def renderer_samples(presentation, points):
    result = subprocess.run(
        ["node", str(BRIDGE)], input=json.dumps({"presentation": presentation, "points": points}),
        text=True, capture_output=True, check=True)
    return json.loads(result.stdout)


def spaced(points, spacing=2.):
    """Keep OSM vertices; insert points so every segment is <=2 m."""
    result = [list(points[0])]
    for a, b in zip(points, points[1:]):
        distance = math.dist(a, b)
        if distance < 1e-9:
            continue
        steps = math.ceil(distance / spacing)
        result.extend([[a[0]+(b[0]-a[0])*k/steps, a[1]+(b[1]-a[1])*k/steps]
                       for k in range(1, steps+1)])
    return result


def profiles_for(presentation, roads, evidence):
    grid = presentation["surroundings"]["groundElevation"]
    x0, z0 = grid["origin"]
    x1 = x0 + grid["step"] * (grid["cols"]-1)
    z1 = z0 + grid["step"] * (grid["rows"]-1)
    profiles = []
    # 7 m phase avoids the 20 m support rows/columns. Covers the full display.
    for z in np.arange(z0+7, z1, 80.):
        profiles.append({"id": f"cross-x-{z:g}", "kind": "cross",
                         "points": spaced([[x0+1, float(z)], [x1-1, float(z)]])})
    for x in np.arange(x0+7, x1, 80.):
        profiles.append({"id": f"cross-z-{x:g}", "kind": "cross",
                         "points": spaced([[float(x), z0+1], [float(x), z1-1]])})
    features = evidence["features"]["roads"]
    if len(features) != len(roads):
        raise ValueError("Road identities do not match the OSM evidence")
    for i, points in enumerate(roads):
        if len(points) < 2 or LineString(points).length < 1e-6:
            continue
        tags = features[i].get("tags", {})
        profiles.append({"id": f"road-{i}", "kind": "road", "osm": features[i]["osm"],
                         "name": tags.get("name"), "highway": tags.get("highway"),
                         "sourceTags": {k: tags[k] for k in ("bridge", "tunnel", "layer") if k in tags},
                         "points": spaced(points)})
    return profiles


def height_stats(rows):
    if not rows:
        raise ValueError("Control zone has no visible samples")
    errors = np.asarray([r["errorMeters"] for r in rows])
    worst = max(rows, key=lambda r: abs(r["errorMeters"]))
    return {"count": len(rows), "biasMeters": float(np.mean(errors)),
            "rmseMeters": float(np.sqrt(np.mean(errors**2))),
            "p95AbsMeters": float(np.percentile(np.abs(errors), 95)),
            "maxAbsMeters": float(np.max(np.abs(errors))),
            "worst": worst}


def evaluate(profiles, offsets, native, reference, ground_level, apron, cutout, width=40.):
    samples, slopes, changes = [], [], []
    cursor = 0
    for profile in profiles:
        identity = {k: profile[k] for k in ("osm", "name", "highway", "sourceTags") if k in profile}
        previous = previous_slope = None
        for station, (x, z) in enumerate(profile["points"]):
            offset = offsets[cursor]
            cursor += 1
            point = Point(x, z)
            if cutout.covers(point):
                previous = previous_slope = None
                continue  # bowl is not rendered ground; never compare across its gap
            distance = apron.distance(point)
            zone = "modelApron" if distance <= 1e-8 else "transition" if distance < width else "measured"
            raw = native(x, z)
            shown = reference + ground_level + offset
            if not all(math.isfinite(n) for n in (raw, shown)):
                raise ValueError("Non-finite profile height")
            row = {**identity, "profile": profile["id"], "kind": profile["kind"], "station": station,
                   "xz": [x, z], "zone": zone, "nativeNHN": raw, "displayNHN": shown,
                   "errorMeters": shown-raw}
            samples.append(row)
            if previous and profile["kind"] == "road":
                a = previous["xz"]
                # Do not bridge a cutout traversed by a short segment.
                if LineString([a, [x, z]]).intersects(cutout):
                    previous_slope = None
                else:
                    length = math.dist(a, [x, z])
                    display_grade = 100*(shown-previous["displayNHN"])/length
                    native_grade = 100*(raw-previous["nativeNHN"])/length
                    slope = {**identity, "profile": profile["id"], "xz": [x, z], "fromXZ": a,
                             "lengthMeters": length,
                             "zones": sorted({zone, previous["zone"]}),
                             "displayGradePct": display_grade, "nativeGradePct": native_grade,
                             "gradeErrorPP": display_grade-native_grade}
                    slopes.append(slope)
                    if previous_slope:
                        display_change = display_grade-previous_slope["displayGradePct"]
                        native_change = native_grade-previous_slope["nativeGradePct"]
                        changes.append({**identity, "profile": profile["id"], "xz": a,
                                        "zones": sorted(set(slope["zones"]+previous_slope["zones"])),
                                        "displayGradeChangePP": display_change,
                                        "nativeGradeChangePP": native_change,
                                        "gradeChangeErrorPP": display_change-native_change})
                    previous_slope = slope
            previous = row
    if cursor != len(offsets):
        raise ValueError("Renderer sample count mismatch")
    return samples, slopes, changes


def summarize(samples, slopes, changes):
    zones, violations = {}, []
    for zone in ZONES:
        stats = height_stats([r for r in samples if r["zone"] == zone])
        for metric, limit in LIMITS[zone].items():
            if stats[metric] > limit:
                violations.append({"zone": zone, "metric": metric, "value": stats[metric], "limit": limit})
        # Empty road subsets are reported explicitly, never as a zero measurement.
        road_slopes = [s for s in slopes if zone in s["zones"]]
        road_changes = [s for s in changes if zone in s["zones"]]
        stats["roadSegments"] = len(road_slopes)
        stats["roadGradeChanges"] = len(road_changes)
        stats["maxAbsDisplayGradePct"] = max(
            (abs(s["displayGradePct"]) for s in road_slopes), default=None)
        stats["maxAbsDisplayGradeChangePP"] = max(
            (abs(s["displayGradeChangePP"]) for s in road_changes), default=None)
        for rows, key, metric in [(road_slopes, "gradeErrorPP", "maxGradeErrorPP"),
                                   (road_changes, "gradeChangeErrorPP", "maxGradeChangeErrorPP")]:
            worst = max(rows, key=lambda r: abs(r[key])) if rows else None
            stats[metric] = abs(worst[key]) if worst else None
            stats[metric+"Location"] = worst
            if worst and stats[metric] > ROAD_LIMITS[metric]:
                violations.append({"zone": zone, "metric": metric, "value": stats[metric],
                                   "limit": ROAD_LIMITS[metric]})
        zones[zone] = stats
    return {"ok": not violations, "zones": zones, "violations": violations,
            "byProfileKind": {kind: height_stats([r for r in samples if r["kind"] == kind])
                              for kind in ("cross", "road")
                              if any(r["kind"] == kind for r in samples)},
            "worstRoadSlopes": sorted(slopes, key=lambda r: abs(r["gradeErrorPP"]), reverse=True)[:20],
            "worstRoadGradeChanges": sorted(changes, key=lambda r: abs(r["gradeChangeErrorPP"]), reverse=True)[:20]}


def run(presentation_path, evidence_path, source_path):
    p = json.loads(presentation_path.read_text())["presentation"]
    ev = json.loads(evidence_path.read_text())
    sources = json.loads(source_path.read_text())
    if hashlib.sha256((evidence_path.parent / "raw.json").read_bytes()).hexdigest() != ev["rawSha256"]:
        raise ValueError("OSM evidence raw hash mismatch")
    if p["surroundings"]["groundElevation"]["step"] != 20:
        raise ValueError("Expected declared Cologne 20 m display raster")
    native = NativeDGM(source_path.parent, sources, model_projection(p, ev, sources))
    reference = float(np.median([native(x, z) for x in (-20, -10, 0, 10, 20)
                                for z in (-35, -17.5, 0, 17.5, 35)]))
    declared = p["surroundings"]["heightEvidence"]["terrainReferenceNHN"]
    if abs(reference-declared) > 1e-6:
        raise ValueError("Native pitch reference differs from the display evidence")
    roads = renderer_samples(p, [])["roads"]
    profiles = profiles_for(p, roads, ev)
    points = [point for profile in profiles for point in profile["points"]]
    offsets = renderer_samples(p, points)["offsets"]
    apron = Polygon(ev["mappedStadiumModelCoordinates"]).buffer(20)
    cutout = Polygon(p["surroundings"]["groundCutout"])
    if not apron.is_valid or not cutout.is_valid:
        raise ValueError("Invalid apron/cutout")
    samples, slopes, changes = evaluate(profiles, offsets, native, reference,
                                       p["surroundings"]["groundLevel"], apron, cutout)
    report = summarize(samples, slopes, changes)
    report.update(schema=1, limits={"height": LIMITS, "roads": ROAD_LIMITS},
                  inputs={str(path): hashlib.sha256(path.read_bytes()).hexdigest()
                          for path in (presentation_path, evidence_path, source_path)},
                  nativeSources=native.sources, referenceNHN=reference,
                  osmRawSha256=ev["rawSha256"],
                  method={"sampleMaxSpacingMeters": 2, "crossProfileSpacingMeters": 80,
                          "crossProfilePhaseMeters": 7, "transitionWidthMeters": 40,
                          "surface": "groundLevel + renderer elevationSampler (no decorative surface offsets)",
                          "limitsMeaning": "Acceptance alarms, not DGM or display accuracy guarantees",
                          "bridges": "DGM describes ground, not bridge decks; sourceTags disclosed, no correction"},
                  profiles=[{k: v for k, v in profile.items() if k != "points"} for profile in profiles],
                  samples=samples, roadSlopes=slopes, roadGradeChanges=changes)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--presentation", type=Path, default=STUDY / "osm-fresh/presentation.json")
    parser.add_argument("--evidence", type=Path, default=STUDY / "osm-fresh/evidence.json")
    parser.add_argument("--sources", type=Path, default=STUDY / "heights/sources.json")
    parser.add_argument("--output", type=Path, default=STUDY / "heights/profile-check.json")
    args = parser.parse_args(argv)
    try:
        report = run(args.presentation, args.evidence, args.sources)
        status = 0 if report["ok"] else 1
    except (OSError, ValueError, KeyError, TypeError, IndexError, subprocess.CalledProcessError) as exc:
        detail = exc.stderr if isinstance(exc, subprocess.CalledProcessError) else str(exc)
        report = {"ok": False, "error": detail, "status": "evidence_error"}
        status = 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
    summary = {k: v for k, v in report.items()
               if k not in ("samples", "roadSlopes", "roadGradeChanges", "profiles", "nativeSources")}
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"{'PASS' if status == 0 else 'FAIL'}: {args.output}", file=sys.stderr)
    return status


if __name__ == "__main__":
    sys.exit(main())
