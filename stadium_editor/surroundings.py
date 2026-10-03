"""Read-only map enrichment shared by the Dortmund editor's 2D and 3D views."""

from functools import lru_cache
import json
import math
from pathlib import Path


TREE_CATALOG = Path(__file__).parent / 'blueprints/v2/dortmund_mapped_trees.json'


@lru_cache(maxsize=1)
def _mapped_trees():
    catalog = json.loads(TREE_CATALOG.read_text(encoding='utf-8'))
    points = catalog['points']
    if not all(
        isinstance(point, list) and len(point) == 2
        and all(type(value) in (int, float) and math.isfinite(value) for value in point)
        for point in points
    ):
        raise ValueError('Der Dortmunder Baumkatalog enthält ungültige Positionen.')
    return (
        tuple(tuple(point) for point in points),
        f"{catalog['source']} · lokaler Baumauszug vom {catalog['retrieved']} · {catalog['note']}",
    )


def with_dortmund_mapped_trees(geometry, *, club_id):
    """Add mapped positions to the response, never to persisted geometry.

    Catalog points are in the authoritative Blueprint pitch frame, NOT in
    the independently fitted/scaled frame of the comparison mockup.
    Explicit supplied tree lists (including an empty list) retain precedence.
    """
    if club_id != 3:
        return geometry
    legacy = geometry.get('bg') or {}
    surroundings = geometry.get('surroundings') or {}
    if 'trees' in legacy or 'trees' in surroundings:
        return geometry
    frame = geometry.get('meta') or {}
    center = frame.get('fieldC', [0, 0])
    theta = frame.get('axisTheta', 0)
    if (
        not isinstance(center, (list, tuple)) or len(center) != 2
        or not all(type(value) in (int, float) and math.isfinite(value) for value in center)
        or type(theta) not in (int, float) or not math.isfinite(theta)
    ):
        raise ValueError('Der Koordinatenrahmen des Dortmunder Baumumfelds ist ungültig.')
    points, source = _mapped_trees()
    cosine, sine = math.cos(theta), math.sin(theta)
    trees = [
        [center[0] + x * cosine - y * sine, center[1] + x * sine + y * cosine]
        for x, y in points
    ]
    return {
        **geometry,
        'surroundings': {
            **surroundings, 'trees': trees, 'treeSource': source,
            'source': surroundings.get('source') or 'OpenStreetMap (ODbL)',
        },
    }