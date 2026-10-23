"""Approved presentation-only grass choices; no geometry or economy effects."""

GRASS_VARIANTS = frozenset((
    "bestand", "A1", "A2", "A3", "A4", "B1", "B2", "B3",
    "C1", "C2", "D1", "D2", "D3",
))
GRASS_ASSETS = {
    "basis": ("studies/grass-pilot/v1/rasen_basis.webp", "image/webp"),
    "abnutzung": ("studies/grass-pilot/v1/rasen_abnutzung.png", "image/png"),
}


def normalize_grass_variant(value):
    if not isinstance(value, str) or value not in GRASS_VARIANTS:
        raise ValueError("Unbekannte Rasenvariante.")
    return value
