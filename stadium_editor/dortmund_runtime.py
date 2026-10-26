"""Read-only BVB presentation shared by editor and match viewers."""
from copy import deepcopy

from .surroundings import with_dortmund_mapped_trees
from .surroundings_data import project_surroundings


def runtime_presentation(stadium, geometry, design):
    from .seat_design import seat_mode
    mode = seat_mode(design)
    enriched = with_dortmund_mapped_trees(deepcopy(geometry), club_id=stadium.club_id)
    surroundings, _ = project_surroundings(enriched)
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
        "seatMode": mode,
        "designColors": {
            stand: palette[max(colors, key=colors.get)]
            for stand, colors in totals.items() if colors
        } if mode == "custom" else {},
        "capacity": stadium.capacity_total,
    }
