"""Read-only BVB presentation shared by editor and match viewers."""
from copy import deepcopy

from .surroundings import with_dortmund_mapped_trees


def runtime_presentation(stadium, geometry, design):
    enriched = with_dortmund_mapped_trees(deepcopy(geometry), club_id=stadium.club_id)
    legacy = enriched.get("bg") or {}
    live = enriched.get("surroundings") or {}
    buildings = legacy.get("buildings") or live.get("buildings") or []
    surroundings = {
        "source": live.get("source") or legacy.get("source") or "",
        "treeSource": legacy.get("treeSource") or live.get("treeSource") or "",
        "green": legacy.get("green") or live.get("green") or [],
        "water": legacy.get("water") or live.get("water") or [],
        "roads": legacy.get("roads") or live.get("roads") or [],
        "buildings": [b if isinstance(b, list) else b["poly"] for b in buildings],
        "buildingHeights": [None if isinstance(b, list) else b.get("h") for b in buildings],
        "buildingIds": [None if isinstance(b, list) else b.get("id") for b in buildings],
        "trees": legacy.get("trees") or live.get("trees") or [],
    }
    palette = design.get("palette") or []
    stands = {int(b.get("id", i)): b.get("stand") for i, b in enumerate(geometry["blocks"])}
    totals = {}
    for block in design.get("blocks") or []:
        stand = stands.get(int(block["id"]))
        if stand not in ("NORD", "SUED", "OST", "WEST"):
            continue
        colors = totals.setdefault(stand, {})
        for count, color in block.get("rle") or []:
            if isinstance(color, int) and 0 < color < len(palette):
                colors[color] = colors.get(color, 0) + count
    return {
        "renderer": "dortmund-spatial",
        "frame": deepcopy(enriched.get("meta") or {}),
        "surroundings": surroundings,
        "designColors": {
            stand: palette[max(colors, key=colors.get)]
            for stand, colors in totals.items() if colors
        },
        "capacity": stadium.capacity_total,
    }
