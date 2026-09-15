"""Portable adapter around the supplied Blueprint V2 implementation.

The geometry functions intentionally remain in ``blueprint_v2.py``.  This
module only gives Django a small, deterministic interface for selecting one of
the four documented geometry paths.
"""

from copy import deepcopy
import json
from pathlib import Path

from . import blueprint_v2


ROOT = Path(__file__).resolve().parent
STECKBRIEF_PATH = ROOT / 'steckbrief.json'

# This is deliberately keyed by database identity, not a club or stadium
# name.  Tests and operators may replace this mapping before invoking a
# command, which is useful for fixtures with different primary keys.
CLUB_BLUEPRINTS = {
    3: {
        'source': 'bvb',
        'source_key': 'bvb',
        'osm': 'dortmund.json',
        'steckbrief': 'Signal Iduna Park',
    },
    114: {
        'source': 'elversberg',
        'source_key': 'elversberg',
        'osm': 'elversberg.json',
        'steckbrief': 'URSAPHARM-Arena an der Kaiserlinde',
    },
}

# Friendly aliases used by integrations which called the mapping this in
# design discussions.
BLUEPRINT_MAPPING = CLUB_BLUEPRINTS
V2_MAPPING = CLUB_BLUEPRINTS

GENERATORS = {
    'bvb': blueprint_v2.build_dortmund,
    'dortmund': blueprint_v2.build_dortmund,
    'elversberg': blueprint_v2.build_elversberg,
    'campnou': blueprint_v2.build_camp_nou,
    'olympiastadion': blueprint_v2.build_olympiastadion,
}

SURROUNDINGS_BUNDLE_KEYS = {
    'bvb': 'Borussia Dortmund',
    'dortmund': 'Borussia Dortmund',
    'elversberg': 'SV Elversberg',
    'olympiastadion': 'Olympiastadion (PoC)',
}

REFERENCE_SCENES = {
    'bvb': 'bvb_v2.json',
    'dortmund': 'bvb_v2.json',
    'elversberg': 'elversberg_v2.json',
    'campnou': 'campnou_v2.json',
    'olympiastadion': 'olympiastadion_v2.json',
}


def load_steckbrief():
    if STECKBRIEF_PATH.stat().st_size > 128 * 1024:
        raise ValueError('Steckbrief-Datei ist zu groß.')
    return json.loads(STECKBRIEF_PATH.read_text(encoding='utf-8'))


def assert_reviewed_reference(source_key, scene):
    """Refuse writes when generated output drifts from its reviewed scene."""
    source_key = str(source_key).casefold()
    try:
        path = ROOT / REFERENCE_SCENES[source_key]
    except KeyError as exc:
        raise ValueError(
            f'Keine geprüfte Blueprint-V2-Referenz für {source_key}.'
        ) from exc
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError('Blueprint-V2-Referenz ist zu groß.')
    if scene != json.loads(path.read_text(encoding='utf-8')):
        raise ValueError(
            f'Blueprint-V2-Ausgabe weicht von der geprüften Referenz ab: {path.name}.'
        )


def generate(source_key, *, osm_path=None, steckbrief_name=None):
    """Run one authoritative generator with portable input paths."""
    source_key = str(source_key).casefold()
    try:
        generator = GENERATORS[source_key]
    except KeyError as exc:
        raise ValueError(f'Unbekannter Blueprint-V2-Quellschlüssel: {source_key}') from exc

    # The reference keeps OSM as a module-level path to stay recognizable.
    # Temporarily redirect it for test fixtures and operator-provided caches.
    old_osm = blueprint_v2.OSM
    if osm_path is not None:
        path = Path(osm_path)
        blueprint_v2.OSM = path.parent
    try:
        scene = generator()
        bundle_key = SURROUNDINGS_BUNDLE_KEYS.get(source_key)
        if bundle_key:
            bundle = blueprint_v2.load_bundle()
            if bundle_key in bundle:
                blueprint_v2.attach_surroundings(scene, bundle[bundle_key])
            else:
                # The Elversberg surroundings handoff source was not included
                # in the repository.  Its supplied, reviewed scene is therefore
                # the immutable cache for this additive layer; block geometry
                # still comes from the authoritative generator above.
                reference = ROOT / REFERENCE_SCENES[source_key]
                cached = json.loads(reference.read_text(encoding='utf-8'))
                scene['surroundings'] = deepcopy(cached['surroundings'])
    finally:
        blueprint_v2.OSM = old_osm

    if not isinstance(scene, dict) or not isinstance(scene.get('blocks'), list):
        raise ValueError('Blueprint V2 hat keine gültige Blockliste erzeugt.')
    return scene


def scene_to_geometry(scene):
    """Translate a generated stage scene to the editor's stored quad order.

    The stage scene exposes front-left, front-right, back-right, back-left.
    The editor historically stores outer-left, outer-right, inner-right,
    inner-left, hence the explicit reversal rather than a radial heuristic.
    """
    raw = deepcopy(scene)
    blocks = []
    for block in raw.get('blocks', []):
        quad = block.get('quad')
        if not isinstance(quad, list) or len(quad) != 4:
            raise ValueError(f"Block {block.get('id')}: ungültiges Quad.")
        item = deepcopy(block)
        item['quad'] = [deepcopy(quad[3]), deepcopy(quad[2]),
                        deepcopy(quad[1]), deepcopy(quad[0])]
        # The generated scene's visual stream is a valid standard design and
        # is retained until the command deliberately resets it.
        blocks.append(item)
    geometry = {
        'version': 2,
        'physical_grid': 'v2',
        'meta': {
            'name': raw.get('stadium', ''),
            'axisTheta': 0,
            'fieldC': [0, 0],
        },
        'outline': deepcopy(raw.get('outline', [])),
        'blocks': blocks,
    }
    for key in (
        'track', 'groundHole', 'facade', 'facadeSegments',
        'standsBounds', 'surroundings', 'source', 'clubColors', 'capacity',
        'mainStand', 'farStand',
    ):
        if key in raw:
            geometry[key] = deepcopy(raw[key])
    # Roof quads are already in the live-scene convention.  Unlike seat
    # blocks, the scene serializer intentionally does not canonicalise their
    # point order, so retain these points verbatim under the editor's
    # explicit-roof input key.
    roof = raw.get('roof')
    if isinstance(roof, dict) and roof.get('mode') == 'explicit':
        segments = roof.get('segments')
        if isinstance(segments, list):
            geometry['roofs'] = deepcopy(segments)
    geometry['scene_meta'] = {
        key: deepcopy(raw[key])
        for key in (
            'schema', 'version', 'stadium', 'club', 'units', 'frame', 'pitch',
            'homeStand', 'mainStand', 'farStand', 'clubColors', 'capacity',
            'facade', 'facadeSegments', 'standsBounds', 'groundHole',
            'track', 'surroundings',
        )
        if key in raw
    }
    # Geometry metadata is local and must not retain a renderer-only RLE.
    # Keeping the source blocks' RLE here would be harmless, but making every
    # design reset explicit avoids accidentally treating it as user design.
    for block in geometry['blocks']:
        block.pop('rle', None)
    return geometry


def standard_design(scene_or_geometry, *, stadium_name='', geometry=None):
    """Create the editor's complete physical-grid standard visual layer."""
    source = deepcopy(scene_or_geometry)
    if geometry is not None:
        source_blocks = {block.get('id'): block for block in source.get('blocks', [])}
        source['blocks'] = [
            {**source_blocks.get(block.get('id'), {}), **deepcopy(block)}
            for block in geometry.get('blocks', [])
        ]
    blocks = source.get('blocks', [])
    palette = list(source.get('palette') or blueprint_v2.PALETTE)
    for block in blocks:
        rle = block.get('rle')
        expected = int(block.get('rows', 0)) * int(block.get('seats', 0))
        if not (
            isinstance(rle, list)
            and all(isinstance(run, list) and len(run) == 2 for run in rle)
            and sum(run[0] for run in rle) == expected
        ):
            # Synthetic/test scenes without a complete stream still receive
            # the reference implementation's deterministic default.
            blueprint_v2.standard_design(
                [block], palette, palette[0], palette[1])
    return {
        'version': 2,
        'stadium': stadium_name or source.get('stadium', ''),
        'blickrichtung': source.get('blickrichtung', 'NORD'),
        'palette': palette,
        'blocks': [
            {
                key: deepcopy(value)
                for key, value in block.items()
                if key in ('id', 'stand', 'tier', 'order', 'rows', 'seats', 'rle')
            }
            for block in blocks
        ],
    }
