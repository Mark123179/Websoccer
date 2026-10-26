"""Additive, reversible source-seat design contract (FCB pilot only)."""
from copy import deepcopy


def seat_mode(design):
    """Legacy painted drafts remain custom; missing designs use the source."""
    return design.get("seat_mode", "custom" if design.get("blocks") else "original")


def source_seat_design(geometry, design):
    saved = {block["id"]: block for block in design.get("blocks", [])}
    return {
        "version": 1,
        "mode": seat_mode(design),
        "palette": deepcopy(design.get("palette", [])),
        # Raw editor quads/RLE: never mix with rotated/reversed live-scene quads.
        "blocks": [
            {**{key: deepcopy(block[key]) for key in
                ("id", "quad", "rows", "seats", "tier", "z0", "z1")},
             "rle": deepcopy(saved.get(block["id"], {}).get("rle", []))}
            for block in geometry["blocks"]
        ],
    }
