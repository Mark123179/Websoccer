"""Pure projection of source geometry, shared by runtime and local preflight."""
from copy import deepcopy

from .surroundings_ground import validated_ground_fields


def project_surroundings(geometry, *, validate_ground=True):
    """Return renderer data and paths back to the unmodified input objects."""
    legacy = geometry.get("bg") or {}
    live = geometry.get("surroundings") or {}
    data = {
        "source": live.get("source") or legacy.get("source") or "",
        "treeSource": legacy.get("treeSource") or live.get("treeSource") or "",
    }
    paths = {}
    for layer in ("green", "water", "roads", "buildings", "trees"):
        origin = "bg" if legacy.get(layer) else "surroundings"
        values = legacy.get(layer) or live.get(layer) or []
        paths[layer] = [
            f"{origin}.{layer}[{i}]" + (".poly" if layer == "buildings" and isinstance(v, dict) else "")
            for i, v in enumerate(values)
        ]
        data[layer] = deepcopy(values)
    buildings = data["buildings"]
    data["buildingHeights"] = [None if isinstance(b, list) else b.get("h") for b in buildings]
    data["buildingIds"] = [None if isinstance(b, list) else b.get("id") for b in buildings]
    data["buildings"] = [b if isinstance(b, list) else b["poly"] for b in buildings]
    for key in ("heightQuality", "heightEvidence"):
        if key in live:
            data[key] = deepcopy(live[key])
    if validate_ground:
        data.update(validated_ground_fields(live))
    else:
        data.update({k: deepcopy(live[k]) for k in
                     ("groundLevel", "groundCutout", "groundElevation") if k in live})
    return data, paths
