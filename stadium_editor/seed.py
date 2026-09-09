"""Reproducible BLUEPRINT geometry seeding used by migrations and commands."""

import gzip
import json
import math
import re
from copy import deepcopy
from pathlib import Path


BUNDLED_SOURCE = Path(__file__).with_name('blueprints') / 'stadium_data_all.js.gz'
BVB_V2_SOURCE = Path(__file__).with_name('blueprints') / 'bvb_blocks_v2.json'


def _key(value):
    return re.sub(r'[^a-z0-9]+', '', str(value).casefold())


def build_explicit_roofs(geometry):
    """Build stable roof meshes from the blueprint's verified outer blocks."""
    result = deepcopy(geometry)
    if 'roofs' in result:
        return result
    blocks = [block for block in result.get('blocks', [])
              if isinstance(block, dict) and not block.get('noroof')]
    if not blocks:
        return result
    meta = result.get('meta') or {}
    center = meta.get('fieldC') or [0, 0]
    roof_meta = meta.get('roof') or {}
    depth = float(roof_meta.get('depth', 1.35))
    uniform = roof_meta.get('level') == 'uniform'
    uniform_top = max(float(block.get('z1', 0)) for block in blocks)
    theta = float(meta.get('axisTheta', 0))
    ct, st = math.cos(theta), math.sin(theta)
    pitch_a, pitch_b = (82, 60) if meta.get('track') else (59.5, 41)

    def clamp_inner(outer, target):
        dx, dy = target[0] - outer[0], target[1] - outer[1]
        length = math.hypot(dx, dy) or 1
        local_x = (outer[0] - center[0]) * ct + (outer[1] - center[1]) * st
        local_y = -(outer[0] - center[0]) * st + (outer[1] - center[1]) * ct
        angle = math.atan2(local_y, local_x)
        field_radius = (
            (abs(math.cos(angle)) / pitch_a) ** 6
            + (abs(math.sin(angle)) / pitch_b) ** 6
        ) ** (-1 / 6)
        allowed = max(6, math.hypot(local_x, local_y) - field_radius - 6)
        factor = min(1, allowed / length)
        return [outer[0] + dx * factor, outer[1] + dy * factor]

    info = []
    for block in blocks:
        quad = block.get('quad')
        if not isinstance(quad, list) or len(quad) != 4:
            continue
        outer_mid = ((quad[0][0] + quad[1][0]) / 2,
                     (quad[0][1] + quad[1][1]) / 2)
        radius = math.hypot(outer_mid[0] - center[0], outer_mid[1] - center[1])
        angles = [
            math.atan2(point[1] - center[1], point[0] - center[0])
            for point in quad[:2]
        ]
        width = abs((angles[1] - angles[0] + math.pi) % (2 * math.pi) - math.pi)
        mid_angle = math.atan2(outer_mid[1] - center[1], outer_mid[0] - center[0])
        info.append((block, radius, mid_angle, width))

    outer = []
    for block, radius, angle, width in info:
        covered = False
        for other, other_radius, other_angle, other_width in info:
            if other is block or other_radius <= radius + 2:
                continue
            delta = abs((angle - other_angle + math.pi) % (2 * math.pi) - math.pi)
            if delta < (width + other_width) * .3:
                covered = True
                break
        if not covered:
            outer.append(block)

    roofs = []
    for block in outer:
        quad = block['quad']
        inner_a = clamp_inner(quad[0], [
            quad[0][0] + (quad[3][0] - quad[0][0]) * depth,
            quad[0][1] + (quad[3][1] - quad[0][1]) * depth,
        ])
        inner_b = clamp_inner(quad[1], [
            quad[1][0] + (quad[2][0] - quad[1][0]) * depth,
            quad[1][1] + (quad[2][1] - quad[1][1]) * depth,
        ])
        top = uniform_top if uniform else float(block['z1'])
        inner = top - 2 if uniform else top - (top - float(block['z0'])) * .3
        roofs.append({
            'id': f"roof-{block['id']}",
            'quad': [deepcopy(quad[0]), deepcopy(quad[1]), inner_b, inner_a],
            'heights': [top + 3, top + 3, inner, inner],
        })
    result['roofs'] = roofs
    return result


def load_blueprints(source=BUNDLED_SOURCE):
    source = Path(source)
    opener = gzip.open if source.suffix == '.gz' else open
    with opener(source, 'rt', encoding='utf-8') as handle:
        text = handle.read()
    match = re.search(r'const\s+STADIUMS\s*=\s*(\[.*\])\s*;\s*$', text, re.S)
    if not match:
        raise ValueError('Die BLUEPRINT-Datei enthält keine STADIUMS-JSON-Liste.')
    blueprints = {
        _key(item.get('meta', {}).get('club')): item
        for item in json.loads(match.group(1))
        if isinstance(item, dict)
    }
    # Production never reads attached_assets.  The upstream BVB bundle has
    # 51 legacy shapes, so this checked-in topology supplies stable identities.
    if Path(source) == BUNDLED_SOURCE:
        exact = json.loads(BVB_V2_SOURCE.read_text(encoding='utf-8'))
        bvb = deepcopy(blueprints.get(_key('Borussia Dortmund'), {}))
        bvb.update({key: deepcopy(value) for key, value in exact.items()
                    if key in ('meta', 'outline', 'blocks')})
        if len(bvb.get('blocks', [])) != 52:
            raise ValueError('Die BVB-V2-Ressource muss exakt 52 Blöcke enthalten.')
        blueprints[_key('Borussia Dortmund')] = bvb
    blueprints = {
        key: build_explicit_roofs(blueprint)
        for key, blueprint in blueprints.items()
    }
    return blueprints


def normalise_block_types(stadium, geometry):
    """Ensure every non-empty Stadium bucket owns at least one visual block."""
    result = deepcopy(geometry)
    blocks = result.get('blocks')
    if not isinstance(blocks, list):
        raise ValueError('Die importierte Geometrie enthält keine Blockliste.')
    for stand in ('NORD', 'OST', 'SUED', 'WEST'):
        stand_blocks = [block for block in blocks if str(block.get('stand', '')).upper() == stand]
        targets = [
            ('STEH', int(getattr(stadium, f'{stand.lower()}_standing'))),
            ('SITZ', int(getattr(stadium, f'{stand.lower()}_seating'))),
            ('VIP', int(getattr(stadium, f'{stand.lower()}_vip'))),
        ]
        required = [seat_type for seat_type, capacity in targets if capacity]
        if required and len(stand_blocks) < len(required):
            raise ValueError(f'{stadium.name}: {stand} hat zu wenige Blöcke für die belegten Sitzarten.')
        used = set()
        for seat_type in required:
            matching = next(
                (block for block in stand_blocks if str(block.get('type', 'SITZ')).upper() == seat_type
                 and id(block) not in used),
                None,
            )
            if matching is None:
                matching = next(block for block in stand_blocks if id(block) not in used)
                matching['type'] = seat_type
            used.add(id(matching))
        if stand_blocks:
            primary = max(targets, key=lambda item: item[1])[0]
            for block in stand_blocks:
                block.setdefault('type', primary)
                if not any(capacity and str(block.get('type', '')).upper() == seat_type
                           for seat_type, capacity in targets):
                    block['type'] = primary
    result.setdefault('meta', {})
    result['meta']['name'] = stadium.name
    return result


def seed_existing_stadiums(stadiums, geometry_model):
    """Return (seeded, skipped) after creating only missing geometry rows."""
    blueprints = load_blueprints()
    seeded = skipped = 0
    for stadium in stadiums:
        blueprint = blueprints.get(_key(stadium.club.name))
        if not blueprint:
            skipped += 1
            continue
        geometry_model.objects.get_or_create(
            stadium_id=stadium.pk,
            defaults={
                'geometry': normalise_block_types(stadium, blueprint),
                'schema_version': 2,
                'source': 'OpenStreetMap/BLUEPRINT-Bundle',
                'attribution': 'Blaupause: OpenStreetMap-Daten (ODbL)',
            },
        )
        seeded += 1
    return seeded, skipped