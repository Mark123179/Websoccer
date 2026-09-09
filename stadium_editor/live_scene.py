"""Canonical runtime scene shared by stadium-editor consumers."""

import math
import re

from .capacity import distribute_capacities
from .contracts import geometry_blocks, rle_length


SCHEMA = 'websoccer.stadium-live-scene'
VERSION = 1
PITCH_LENGTH = 105.0
PITCH_WIDTH = 68.0
STANDS = ('NORD', 'OST', 'SUED', 'WEST')
TYPE_NAMES = {
    'STEH': 'standing',
    'SITZ': 'seating',
    'VIP': 'vip',
}
COLOUR_RE = re.compile(r'^#[0-9a-fA-F]{6}$')
EPSILON = 1e-7


class LiveSceneError(ValueError):
    """Raised when persisted server data cannot form a trustworthy scene."""


def _number(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise LiveSceneError(f'{label} muss eine endliche Zahl sein.')
    value = float(value)
    if not math.isfinite(value):
        raise LiveSceneError(f'{label} muss eine endliche Zahl sein.')
    return value


def _point(value, label):
    if not isinstance(value, list) or len(value) != 2:
        raise LiveSceneError(f'{label} muss aus genau zwei Koordinaten bestehen.')
    return (_number(value[0], label), _number(value[1], label))


def _rotate_to_pitch(point, center, theta):
    """Move a world point into the pitch frame (rotate by ``-theta``)."""
    dx, dy = point[0] - center[0], point[1] - center[1]
    ct, st = math.cos(theta), math.sin(theta)
    return (dx * ct + dy * st, -dx * st + dy * ct)


def _rounded_point(point):
    def clean(value):
        value = round(value, 6)
        return 0.0 if abs(value) < 0.0000005 else value
    return [clean(point[0]), clean(point[1])]


def _cross(a, b, c):
    return ((b[0] - a[0]) * (c[1] - a[1])
            - (b[1] - a[1]) * (c[0] - a[0]))


def _segments_cross(a, b, c, d):
    return (
        _cross(a, b, c) * _cross(a, b, d) < -EPSILON
        and _cross(c, d, a) * _cross(c, d, b) < -EPSILON
    )


def _polygon_area(points):
    return abs(sum(
        points[index][0] * points[(index + 1) % len(points)][1]
        - points[(index + 1) % len(points)][0] * points[index][1]
        for index in range(len(points))
    )) / 2


def _canonical_quad(raw_quad, center, theta, block_id):
    """Return canonical quad and whether each saved RLE row must be reversed.

    Stored editor geometry uses the historical ``outer-left, outer-right,
    inner-right, inner-left`` convention. The scene contract instead exposes
    ``front-left, front-right, back-right, back-left`` from the pitch.
    """
    if not isinstance(raw_quad, list) or len(raw_quad) != 4:
        raise LiveSceneError(f'Block {block_id}: quad muss genau vier Punkte haben.')
    transformed = [
        _rotate_to_pitch(_point(value, f'Block {block_id}: quad'), center, theta)
        for value in raw_quad
    ]
    if len({(round(x, 9), round(y, 9)) for x, y in transformed}) != 4:
        raise LiveSceneError(f'Block {block_id}: quad enthält doppelte Punkte.')

    by_radius = sorted(
        range(4),
        key=lambda index: transformed[index][0] ** 2 + transformed[index][1] ** 2,
    )
    front_indices = set(by_radius[:2])
    back_indices = set(by_radius[2:])
    front_radius = max(
        transformed[index][0] ** 2 + transformed[index][1] ** 2
        for index in front_indices
    )
    back_radius = min(
        transformed[index][0] ** 2 + transformed[index][1] ** 2
        for index in back_indices
    )
    if back_radius - front_radius <= EPSILON:
        raise LiveSceneError(
            f'Block {block_id}: Vorder- und Hinterkante sind nicht eindeutig.'
        )

    centroid = (
        sum(point[0] for point in transformed) / 4,
        sum(point[1] for point in transformed) / 4,
    )
    radius = math.hypot(*centroid)
    if radius <= EPSILON:
        raise LiveSceneError(f'Block {block_id}: quad liegt auf dem Feldmittelpunkt.')
    # From the pitch looking towards the block, this vector points left.
    left = (-centroid[1] / radius, centroid[0] / radius)
    lateral = lambda index: (
        transformed[index][0] * left[0] + transformed[index][1] * left[1]
    )
    front_left, front_right = sorted(
        front_indices, key=lateral, reverse=True)
    back_left, back_right = sorted(
        back_indices, key=lateral, reverse=True)
    canonical = [
        transformed[front_left],
        transformed[front_right],
        transformed[back_right],
        transformed[back_left],
    ]
    if _polygon_area(canonical) <= EPSILON:
        raise LiveSceneError(f'Block {block_id}: quad hat keine Fläche.')
    if (
        _segments_cross(canonical[0], canonical[1], canonical[2], canonical[3])
        or _segments_cross(canonical[1], canonical[2], canonical[3], canonical[0])
    ):
        raise LiveSceneError(f'Block {block_id}: quad ist selbstüberschneidend.')

    # The editor maps columns along raw quad[3] -> raw quad[2]. Preserve the
    # visual choreography while changing the scene contract to left -> right.
    if front_indices != {2, 3}:
        raise LiveSceneError(
            f'Block {block_id}: historische Rasterkante ist nicht spielfeldnah.'
        )
    reverse_rows = front_left == 2
    return [_rounded_point(point) for point in canonical], reverse_rows


def _encode(values):
    result = []
    for colour in values:
        if result and result[-1][1] == colour and result[-1][0] < 65_535:
            result[-1][0] += 1
        else:
            result.append([1, colour])
    return result


def _scene_rle(rle, rows, seats, palette_size, block_id, reverse_rows):
    if not isinstance(rle, list) or len(rle) > 10_000:
        raise LiveSceneError(f'Block {block_id}: ungültige Sitzfolge.')
    values = []
    for pair in rle:
        if (
            not isinstance(pair, list) or len(pair) != 2
            or not isinstance(pair[0], int) or isinstance(pair[0], bool)
            or not isinstance(pair[1], int) or isinstance(pair[1], bool)
            or pair[0] < 1 or pair[0] > 65_535
            or pair[1] < 0 or pair[1] >= palette_size
        ):
            raise LiveSceneError(f'Block {block_id}: ungültige Sitzfolge.')
        values.extend([pair[1]] * pair[0])
        if len(values) > rows * seats:
            raise LiveSceneError(f'Block {block_id}: Sitzfolge ist zu lang.')
    if len(values) != rows * seats or rle_length(rle) != rows * seats:
        raise LiveSceneError(
            f'Block {block_id}: Sitzfolge muss exakt {rows * seats} Plätze haben.'
        )
    if not reverse_rows:
        return [list(pair) for pair in rle]
    reversed_values = []
    for row in range(rows):
        start = row * seats
        reversed_values.extend(reversed(values[start:start + seats]))
    return _encode(reversed_values)


def _home_stand(geometry):
    meta_value = str((geometry.get('meta') or {}).get('homeStand', '')).upper()
    if meta_value in STANDS:
        return meta_value
    standing = {stand: 0 for stand in STANDS}
    for block in geometry.get('blocks', []):
        block_type = str(block.get('type', '')).upper()
        if block_type in ('STEH', 'STANDING', 'STAND'):
            stand = str(block.get('stand', '')).upper()
            if stand in standing:
                try:
                    standing[stand] += int(block['rows']) * int(block['seats'])
                except (KeyError, TypeError, ValueError):
                    continue
    best = max(standing, key=standing.get)
    return best if standing[best] else None


def build_live_scene(stadium, geometry, design):
    """Merge trusted geometry and visual design into one read-only scene."""
    if not isinstance(geometry, dict):
        raise LiveSceneError('Die Stadion-Geometrie hat ein ungültiges Format.')
    if not isinstance(design, dict):
        raise LiveSceneError('Das Stadion-Design hat ein ungültiges Format.')
    meta = geometry.get('meta')
    if not isinstance(meta, dict):
        raise LiveSceneError('Die Stadion-Geometrie enthält keine Metadaten.')
    theta = _number(meta.get('axisTheta'), 'axisTheta')
    center = _point(meta.get('fieldC', [0, 0]), 'fieldC')

    palette = design.get('palette')
    if (
        not isinstance(palette, list) or not palette or len(palette) > 64
        or any(not isinstance(colour, str) or not COLOUR_RE.fullmatch(colour)
               for colour in palette)
    ):
        raise LiveSceneError('Das Stadion-Design enthält keine gültige Palette.')

    effective_geometry = distribute_capacities(stadium, geometry)
    trusted_meta = {block['id']: block for block in geometry_blocks(effective_geometry)}
    raw_blocks = {}
    for position, block in enumerate(effective_geometry.get('blocks', [])):
        block_id = block.get('id', position)
        if block_id in raw_blocks:
            raise LiveSceneError('Die Stadion-Geometrie enthält doppelte Block-IDs.')
        raw_blocks[block_id] = block

    design_blocks = design.get('blocks')
    if not isinstance(design_blocks, list):
        raise LiveSceneError('Das Stadion-Design enthält keine Blockliste.')
    by_design_id = {}
    for block in design_blocks:
        if not isinstance(block, dict) or not isinstance(block.get('id'), int):
            raise LiveSceneError('Das Stadion-Design enthält einen ungültigen Block.')
        if block['id'] in by_design_id:
            raise LiveSceneError(
                f"Block-ID {block['id']} ist im Design doppelt vorhanden.")
        by_design_id[block['id']] = block
    if set(by_design_id) != set(trusted_meta):
        missing = sorted(set(trusted_meta) - set(by_design_id))
        unknown = sorted(set(by_design_id) - set(trusted_meta))
        detail = (
            f'fehlend {missing[:5]}' if missing
            else f'unbekannt {unknown[:5]}'
        )
        raise LiveSceneError(f'Design und Geometrie haben verschiedene Block-IDs: {detail}.')

    scene_blocks = []
    for block_id, trusted in trusted_meta.items():
        raw = raw_blocks[block_id]
        saved = by_design_id[block_id]
        for key in ('rows', 'seats'):
            if saved.get(key) != trusted[key]:
                raise LiveSceneError(
                    f'Block {block_id}: {key} stimmt nicht mit dem Ausbauzustand überein.'
                )
        quad, reverse_rows = _canonical_quad(
            raw.get('quad'), center, theta, block_id)
        z0 = _number(raw.get('z0'), f'Block {block_id}: z0')
        z1 = _number(raw.get('z1'), f'Block {block_id}: z1')
        if z1 <= z0:
            raise LiveSceneError(f'Block {block_id}: z1 muss größer als z0 sein.')
        block_type = str(raw.get('type', 'SITZ')).upper()
        block_type = {
            'STANDING': 'STEH', 'STAND': 'STEH',
            'SEATING': 'SITZ', 'SEAT': 'SITZ', 'SITTING': 'SITZ',
        }.get(block_type, block_type)
        if block_type not in TYPE_NAMES:
            raise LiveSceneError(f'Block {block_id}: unbekannter Blocktyp.')
        scene_blocks.append({
            'id': block_id,
            'stand': trusted['stand'],
            'tier': trusted['tier'],
            'order': trusted['order'],
            'rows': trusted['rows'],
            'seats': trusted['seats'],
            'quad': quad,
            'z0': z0,
            'z1': z1,
            'type': TYPE_NAMES[block_type],
            'rle': _scene_rle(
                saved.get('rle'), trusted['rows'], trusted['seats'],
                len(palette), block_id, reverse_rows,
            ),
        })

    outline = geometry.get('outline')
    if not isinstance(outline, list) or len(outline) < 3:
        raise LiveSceneError('Die Stadion-Geometrie enthält keinen gültigen Umriss.')
    scene_outline = [
        _rounded_point(_rotate_to_pitch(
            _point(value, 'Stadionumriss'), center, theta))
        for value in outline
    ]
    if _polygon_area(scene_outline) <= EPSILON:
        raise LiveSceneError('Der Stadionumriss hat keine Fläche.')

    club = stadium.club
    return {
        'schema': SCHEMA,
        'version': VERSION,
        'stadium': stadium.name,
        'club': {
            'id': club.pk,
            'fmInsideId': club.fm_inside_id,
            'name': club.name,
        },
        'units': 'm',
        'frame': {
            'name': 'pitch',
            'origin': 'pitch-center',
            'xAxis': 'goal-to-goal',
            'yAxis': 'touchline-to-touchline',
            'zAxis': 'up',
        },
        'pitch': {'length': PITCH_LENGTH, 'width': PITCH_WIDTH},
        'homeStand': _home_stand(geometry),
        'palette': [colour.lower() for colour in palette],
        'blocks': scene_blocks,
        'outline': scene_outline,
        'roof': {'mode': 'procedural-ring'},
    }