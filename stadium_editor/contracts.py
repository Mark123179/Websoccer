"""The server-owned version 2 stadium-editor export contract."""

import math

STANDS = {'NORD', 'SUED', 'OST', 'WEST'}
TIERS = {'UNTER', 'OBER'}


def canonical_tier(value):
    value = str(value or '').upper()
    return 'UNTER' if value in ('UNTER', 'RANG1', 'LOWER', '1') else 'OBER'


def axis_theta(geometry):
    """Return the authoritative pitch axis, accepting old source geometry."""
    value = (geometry.get('meta', {}) if isinstance(geometry, dict) else {}).get('axisTheta', 0)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError('Die Geometrie enthält kein gültiges axisTheta.')
    return value


def _number(value):
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value))


def contract_quad(legacy_quad, field_center=(0, 0)):
    """Turn raw A,B,C,D quads into front-left, front-right, back-right, back-left."""
    if (not isinstance(legacy_quad, list) or len(legacy_quad) != 4
            or not all(isinstance(point, list) and len(point) == 2
                       and all(_number(value) for value in point) for point in legacy_quad)):
        raise ValueError('Die Geometrie enthält ein ungültiges Block-Quad.')
    if (not isinstance(field_center, list) or len(field_center) != 2
            or not all(_number(value) for value in field_center)):
        field_center = (0, 0)
    a, b, c, d = legacy_quad
    midpoint = lambda p, q: ((p[0] + q[0]) / 2, (p[1] + q[1]) / 2)
    ab, cd = midpoint(a, b), midpoint(c, d)
    distance = lambda p: (p[0] - field_center[0]) ** 2 + (p[1] - field_center[1]) ** 2
    # Preserve pairs across the trapezoid; the closer pair is the front edge.
    front, back = (cd, ab) if distance(cd) <= distance(ab) else (ab, cd)
    forward = (front[0] - field_center[0], front[1] - field_center[1])
    length = math.hypot(*forward)
    if length < 1e-9:
        # Degenerate location is invalid for a stadium block contract.
        raise ValueError('Die Geometrie enthält ein Block-Quad ohne Feldbezug.')
    left = (-forward[1] / length, forward[0] / length)
    front_points = (c, d) if front == cd else (a, b)
    back_points = (a, b) if front == cd else (c, d)
    score = lambda p: (p[0] - front[0]) * left[0] + (p[1] - front[1]) * left[1]
    fl, fr = sorted(front_points, key=score, reverse=True)
    # Match each back endpoint to its nearest front endpoint.
    if ((back_points[0][0] - fl[0]) ** 2 + (back_points[0][1] - fl[1]) ** 2
            <= (back_points[1][0] - fl[0]) ** 2 + (back_points[1][1] - fl[1]) ** 2):
        bl, br = back_points
    else:
        br, bl = back_points
    return [fl, fr, br, bl]


def legacy_seat_axis_reversed(legacy_quad, field_center=(0, 0)):
    """Whether legacy u=0 (raw D) differs from canonical u=0 (front-left)."""
    return contract_quad(legacy_quad, field_center)[0] != legacy_quad[3]


def geometry_blocks(geometry):
    """Return trusted block metadata, in the geometry's stable source order."""
    raw = geometry.get('blocks') if isinstance(geometry, dict) else None
    if not isinstance(raw, list):
        raise ValueError('Die gespeicherte Geometrie enthält keine Blockliste.')
    result, ids = [], set()
    for position, block in enumerate(raw):
        if not isinstance(block, dict):
            raise ValueError('Die gespeicherte Geometrie enthält einen ungültigen Block.')
        block_id = block.get('id', position)
        if not isinstance(block_id, int) or block_id in ids:
            raise ValueError('Die gespeicherte Geometrie enthält doppelte Block-IDs.')
        stand = str(block.get('stand', '')).upper()
        if stand not in STANDS:
            raise ValueError(f'Die Geometrie von Block {block_id} hat keine gültige Tribüne.')
        try:
            rows, seats = int(block['rows']), int(block['seats'])
        except (KeyError, TypeError, ValueError):
            raise ValueError(f'Die Geometrie von Block {block_id} hat ungültige Maße.')
        if rows < 1 or seats < 1:
            raise ValueError(f'Die Geometrie von Block {block_id} hat ungültige Maße.')
        tier = canonical_tier(block.get('tier'))
        z0, z1 = block.get('z0'), block.get('z1')
        if not _number(z0) or not _number(z1) or z1 <= z0:
            raise ValueError(f'Die Geometrie von Block {block_id} hat ungültige Höhen.')
        result.append({'id': block_id, 'stand': stand, 'tier': tier,
                       'order': 0, 'rows': rows, 'seats': seats,
                       'quad': contract_quad(block.get('quad'),
                                             geometry.get('meta', {}).get('fieldC', [0, 0])),
                       'z0': z0, 'z1': z1, '_legacy_quad': block.get('quad')})
        ids.add(block_id)
    groups = {}
    for block in result:
        groups.setdefault((block['stand'], block['tier']), []).append(block)
    for (stand, _tier), members in groups.items():
        def left_to_right(block):
            quad = block['_legacy_quad']
            if not isinstance(quad, list) or len(quad) != 4:
                return block['id']
            x = sum(point[0] for point in quad) / 4
            y = sum(point[1] for point in quad) / 4
            # Seen from the pitch while looking at the respective stand.
            return {
                'NORD': x,
                'SUED': -x,
                'OST': -y,
                'WEST': y,
            }[stand]
        for order, block in enumerate(sorted(members, key=left_to_right)):
            block['order'] = order
    return [{key: value for key, value in block.items() if key != '_legacy_quad'}
            for block in result]


def _is_complete_canonical(block, supplied_axis):
    """A complete spatial V2 record already uses the canonical seat axis.

    Its dimensions may legitimately describe the previous expansion state, so
    this marker must not depend on equality with today's effective geometry.
    """
    return (isinstance(block, dict) and _number(supplied_axis)
            and all(key in block for key in
                    ('stand', 'tier', 'order', 'rows', 'seats', 'quad', 'z0', 'z1')))


def hydrate_design(design, geometry, stadium_name, blickrichtung='NORD'):
    """Build a complete V2 response from visual data and server geometry."""
    if not isinstance(design, dict):
        design = {}
    trusted = geometry_blocks(geometry)
    raw = {block.get('id', index): block for index, block in
           enumerate(geometry.get('blocks', []))}
    expected_axis = axis_theta(geometry)
    saved = {item.get('id'): item for item in design.get('blocks', [])
             if isinstance(item, dict)}
    blocks = []
    for meta in trusted:
        old = saved.get(meta['id'], {})
        old_rows, old_seats = old.get('rows'), old.get('seats')
        rle = old.get('rle', [])
        if not isinstance(old_rows, int) or not isinstance(old_seats, int) or old_rows < 1 or old_seats < 1:
            old_rows, old_seats = meta['rows'], meta['seats']
        # Earlier V2 was serialized in the editor's raw D→C seat direction.
        # A complete spatial record is the durable marker that RLE is already
        # canonical FL→FR, making repeated hydration idempotent.
        if (not _is_complete_canonical(old, design.get('axisTheta'))
                and legacy_seat_axis_reversed(raw[meta['id']]['quad'],
                                              geometry.get('meta', {}).get('fieldC', [0, 0]))):
            rle = reverse_rle_rows(rle, old_rows, old_seats)
        if (old_rows, old_seats) != (meta['rows'], meta['seats']):
            rle = project_rle(rle, (old_rows, old_seats), (meta['rows'], meta['seats']))
        elif rle_length(rle) != meta['rows'] * meta['seats']:
            rle = project_rle(rle, (old_rows, old_seats), (meta['rows'], meta['seats']))
        blocks.append({**meta, 'rle': rle or [[meta['rows'] * meta['seats'], 0]]})
    direction = str(design.get('blickrichtung', blickrichtung)).upper()
    if direction not in STANDS:
        direction = blickrichtung if blickrichtung in STANDS else 'NORD'
    return {'version': 2, 'stadium': stadium_name, 'axisTheta': expected_axis,
            'blickrichtung': direction, 'palette': design.get('palette', []), 'blocks': blocks}


def rle_length(rle):
    return sum(pair[0] for pair in rle)


def decode_rle(rle, limit):
    """Decode no more than the trusted target grid can consume."""
    values = []
    for count, colour in rle:
        remaining = limit - len(values)
        if remaining <= 0:
            break
        values.extend([colour] * min(count, remaining))
    return values


def project_rle(rle, old_shape, new_shape):
    """2D nearest-neighbour projection, preserving row and seat position."""
    old_rows, old_seats = old_shape
    new_rows, new_seats = new_shape
    new_size = new_rows * new_seats
    source = decode_rle(rle, old_rows * old_seats)
    if not source:
        return [[new_size, 0]]
    # Old V1 streams can end at capacity instead of the padded grid.  Missing
    # cells are concrete/base colour, not an implicit repeat of the last seat.
    source = (source + [0] * max(0, old_rows * old_seats - len(source)))[:old_rows * old_seats]
    projected = [source[min(old_rows - 1, r * old_rows // new_rows) * old_seats +
                        min(old_seats - 1, s * old_seats // new_seats)]
                 for r in range(new_rows) for s in range(new_seats)]
    out = []
    for colour in projected:
        if out and out[-1][1] == colour and out[-1][0] < 65535:
            out[-1][0] += 1
        else:
            out.append([1, colour])
    return out


def _quad_point(quad, u, v):
    a, b, c, d = quad
    inner = (d[0] + u * (c[0] - d[0]), d[1] + u * (c[1] - d[1]))
    outer = (a[0] + u * (b[0] - a[0]), a[1] + u * (b[1] - a[1]))
    return (inner[0] + v * (outer[0] - inner[0]),
            inner[1] + v * (outer[1] - inner[1]))


def _quad_uv(quad, point):
    """Invert the editor's bilinear quad transform using Newton iteration."""
    u = v = .5
    for _ in range(12):
        x, y = _quad_point(quad, u, v)
        fx, fy = x - point[0], y - point[1]
        eps = 1e-5
        xu, yu = _quad_point(quad, u + eps, v)
        xv, yv = _quad_point(quad, u, v + eps)
        a, b = (xu - x) / eps, (xv - x) / eps
        c, d = (yu - y) / eps, (yv - y) / eps
        det = a * d - b * c
        if abs(det) < 1e-12:
            return None
        u -= (d * fx - b * fy) / det
        v -= (-c * fx + a * fy) / det
    return (u, v) if -.001 <= u <= 1.001 and -.001 <= v <= 1.001 else None


def _encode(values):
    out = []
    for value in values:
        if out and out[-1][1] == value and out[-1][0] < 65535:
            out[-1][0] += 1
        else:
            out.append([1, value])
    return out


def reverse_rle_rows(rle, rows, seats):
    """Reverse the seat axis of a bounded row-major RLE stream, preserving rows."""
    size = rows * seats
    values = decode_rle(rle, size)
    values = (values + [0] * max(0, size - len(values)))[:size]
    return _encode([value for row in range(rows)
                    for value in reversed(values[row * seats:(row + 1) * seats])])


def spatial_project_design(old_design, old_geometry, new_geometry, stadium_name,
                           blickrichtung='NORD'):
    """Project seats through world-space quads for topology replacements."""
    old_meta = {block['id']: block for block in geometry_blocks(old_geometry)}
    saved = {block.get('id'): block for block in old_design.get('blocks', [])}
    sources = []
    raw_old = {block.get('id', i): block
               for i, block in enumerate(old_geometry.get('blocks', []))}
    for block_id, meta in old_meta.items():
        item = saved.get(block_id, {})
        rle = item.get('rle', [])
        # Historical design metadata is untrusted/can be corrupt.  The
        # effective old server geometry is the only allocation bound.
        rows = meta['rows']
        seats = meta['seats']
        declared_size = rows * seats
        values = decode_rle(rle, declared_size)
        values = (values + [0] * (rows * seats))[:rows * seats]
        if (_is_complete_canonical(item, old_design.get('axisTheta'))
                and legacy_seat_axis_reversed(raw_old[block_id]['quad'],
                                              old_geometry.get('meta', {}).get('fieldC', [0, 0]))):
            values = decode_rle(reverse_rle_rows(_encode(values), rows, seats), declared_size)
        sources.append((raw_old[block_id]['quad'], rows, seats, values))
    raw_new = {block.get('id', i): block
               for i, block in enumerate(new_geometry.get('blocks', []))}
    blocks = []
    for meta in geometry_blocks(new_geometry):
        values = []
        quad = raw_new[meta['id']]['quad']
        for row in range(meta['rows']):
            for seat in range(meta['seats']):
                point = _quad_point(quad, (seat + .5) / meta['seats'],
                                    (row + .5) / meta['rows'])
                colour = 0
                for old_quad, old_rows, old_seats, source in sources:
                    uv = _quad_uv(old_quad, point)
                    if uv is not None:
                        col = min(old_seats - 1, max(0, int(uv[0] * old_seats)))
                        old_row = min(old_rows - 1, max(0, int(uv[1] * old_rows)))
                        colour = source[old_row * old_seats + col]
                        break
                values.append(colour)
        if legacy_seat_axis_reversed(raw_new[meta['id']]['quad'],
                                     new_geometry.get('meta', {}).get('fieldC', [0, 0])):
            values = decode_rle(reverse_rle_rows(_encode(values), meta['rows'], meta['seats']),
                                meta['rows'] * meta['seats'])
        blocks.append({**meta, 'rle': _encode(values)})
    return {'version': 2, 'stadium': stadium_name, 'axisTheta': axis_theta(new_geometry),
            'blickrichtung': blickrichtung, 'palette': old_design.get('palette', []),
            'blocks': blocks}


def visible_blocks(design, blickrichtung):
    """The opposite stand plus lower blocks on both side stands."""
    opposite = (blickrichtung or 'NORD').upper()
    if opposite not in STANDS:
        opposite = 'NORD'
    side_map = {'NORD': ('WEST', 'OST'), 'SUED': ('OST', 'WEST'),
                'OST': ('NORD', 'SUED'), 'WEST': ('SUED', 'NORD')}
    sides = side_map[opposite]
    return [block for block in design.get('blocks', [])
            if block.get('stand') == opposite
            or (block.get('stand') in sides and block.get('tier') == 'UNTER')]