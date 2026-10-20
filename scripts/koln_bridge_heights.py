"""Bridge provenance, deliberately separate from the native *ground* check.

No bridge deck source has been spatially verified. Neither OSM layer nor a
DOM/DGM difference is a measured clearance or an authorised deck correction.
"""
from copy import deepcopy

UNRESOLVED = "unresolved_terrain_derivation"
LABEL = "Brücken: ungeklärte Geländeableitung – keine gemessene Fahrbahn."


def is_bridge(tags):
    return str(tags.get("bridge", "")).strip().lower() not in ("", "no", "false", "0")


def bridge_records(data, evidence):
    roads, features = data["roads"], evidence["features"]["roads"]
    if len(roads) != len(features):
        raise ValueError("Bridge identities do not match the OSM roads")
    return [
        {"index": index, "osm": feature["osm"], "name": feature["tags"].get("name"),
         "sourceTags": {k: feature["tags"][k] for k in ("bridge", "tunnel", "layer")
                        if k in feature["tags"]},
         "editorPoints": deepcopy(road["p"]), "status": UNRESOLVED,
         "deckSource": None, "label": LABEL}
        for index, (road, feature) in enumerate(zip(roads, features))
        if is_bridge(feature.get("tags", {}))
    ]


def bridge_report(profiles, samples, slopes, changes):
    """Supplement, never filter, the original all-road control population."""
    rows = []
    for profile in profiles:
        if profile.get("heightStatus") != UNRESOLVED:
            continue
        selected = [s for s in samples if s["profile"] == profile["id"]]
        segments = [s for s in slopes if s["profile"] == profile["id"]]
        turns = [s for s in changes if s["profile"] == profile["id"]]
        worst = lambda items, key: max(items, key=lambda s: abs(s[key])) if items else None
        rows.append({
            **{k: profile[k] for k in ("id", "osm", "name", "sourceTags", "heightStatus")},
            "deckSource": None, "deckValidation": "not_evaluable_without_spatial_deck_evidence",
            "groundSampleCount": len(selected), "groundSegmentCount": len(segments),
            "maxAbsGroundErrorMeters": max((abs(s["errorMeters"]) for s in selected), default=None),
            "worstGroundSlope": worst(segments, "gradeErrorPP"),
            "worstGroundGradeChange": worst(turns, "gradeChangeErrorPP"),
        })
    return {"label": LABEL, "deckHeightsApplied": 0, "unresolvedCount": len(rows),
            "nativeComparison": "DGM1 ground only, NOT deck error; all original alarms retained",
            "profiles": rows}
