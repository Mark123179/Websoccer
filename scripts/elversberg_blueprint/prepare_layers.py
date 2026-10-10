#!/usr/bin/env python3
"""Align the checked-in Elversberg V2 surroundings to its documented world frame."""
import json
import sys
from pathlib import Path

from shapely.geometry import LineString, Polygon


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "stadium_editor/blueprints/v2/elversberg_v2.json"
HEIGHTS = ROOT / "generated-artifacts/elversberg-height-visibility/height_inputs.json"


def polygon(coords):
    return Polygon(coords).buffer(0)


def iou(a, b):
    union = a.union(b).area
    return a.intersection(b).area / union if union else 0.0


def transform(point):
    # V2 surroundings were generated in a legacy reflected image frame.
    # Footprint overlap against the canonical height-input OSM frame establishes
    # [source-x, source-y] -> approved-world [x, -z] for this profile.
    return [float(point[0]), -float(point[1])]


def main():
    out = Path(sys.argv[1])
    source = json.loads(SOURCE.read_text())
    height_data = json.loads(HEIGHTS.read_text())
    surroundings = source["surroundings"]
    target_items = [(polygon(item["polygon"]), item) for item in height_data["objects"]
                    if item.get("polygon") and len(item["polygon"]) >= 3]
    targets = [item[0] for item in target_items]
    variants = {
        "identity": lambda p: [p[0], p[1]],
        "half-turn": lambda p: [-p[0], -p[1]],
        "reflect-x": lambda p: [-p[0], p[1]],
        "reflect-y": lambda p: [p[0], -p[1]],
    }
    alignment_counts = {}
    for label, mapper in variants.items():
        overlaps = []
        for item in surroundings["buildings"]:
            footprint = polygon([mapper(point) for point in item["poly"]])
            overlaps.append(max((iou(footprint, target) for target in targets), default=0.0))
        alignment_counts[label] = {
            "over_iou_0_10": sum(value > 0.10 for value in overlaps),
            "over_iou_0_45": sum(value >= 0.45 for value in overlaps),
            "mean_best_iou": sum(overlaps) / max(1, len(overlaps)),
        }
    selected = alignment_counts["reflect-y"]
    alternative = max(alignment_counts[key]["over_iou_0_10"]
                      for key in alignment_counts if key != "reflect-y")
    if selected["over_iou_0_10"] < 20 or selected["over_iou_0_10"] <= alternative:
        raise RuntimeError(f"V2 surroundings frame did not align decisively: {alignment_counts}")

    buildings = []
    for item in surroundings["buildings"]:
        points = [transform(point) for point in item["poly"]]
        footprint = polygon(points)
        matches = [(iou(footprint, target), candidate)
                   for target, candidate in target_items
                   if candidate.get("matched") and candidate.get("height_envelope_m")]
        score, match = max(matches, key=lambda pair: pair[0], default=(0.0, None))
        # V2 h is randomly assigned in its source generator; never treat it as measured.
        envelope = match["height_envelope_m"] if match and score >= 0.45 else None
        buildings.append({
            "poly": points,
            "height": envelope if envelope is not None else 1.7,
            "heightStatus": "conditional measured-height envelope" if envelope is not None
            else "schematic low volume; not a measured height",
            "heightMatchIou": score if envelope is not None else None,
        })

    roads = []
    width_by_class = {1: 3.0, 2: 5.0, 3: 7.0}
    for item in surroundings["roads"]:
        line = LineString(item["p"])
        width = width_by_class.get(item.get("w", 1), 3.0)
        ribbon = line.buffer(width / 2, cap_style=2, join_style=1)
        if ribbon.is_empty or ribbon.area == 0:
            continue
        roads.append({
            "poly": [transform(point) for point in list(ribbon.exterior.coords)[:-1]],
            "sourceClass": item.get("w", 1),
        })

    green = []
    for points in surroundings["green"]:
        coords = [transform(point) for point in points]
        area = polygon(coords)
        if area.is_valid and not area.is_empty:
            green.append({"poly": [list(point) for point in area.exterior.coords[:-1]]})

    data = {
        "alignment": {
            "sourceFrame": "Elversberg V2 surroundings",
            "worldTransform": "[x, y] -> [x, -y]",
            "calibration": "Footprint-IoU comparison against OSM building polygons in height_inputs.frame (canonical approved geographic frame).",
            "overlapCountsByTransform": alignment_counts,
        },
        "counts": {
            "buildings": len(buildings), "roads": len(roads), "greenAreas": len(green),
            "conditionallyHeightMatched": sum(b["heightStatus"].startswith("conditional") for b in buildings),
            "schematicLowVolumes": sum(b["heightStatus"].startswith("schematic") for b in buildings),
        },
        "buildings": buildings, "roads": roads, "green": green,
    }
    (out / "source_layers.json").write_text(json.dumps(data, ensure_ascii=False))
    print(json.dumps({"counts": data["counts"], "alignment": alignment_counts}, ensure_ascii=False))


if __name__ == "__main__":
    main()
