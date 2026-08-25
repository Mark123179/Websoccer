"""Reproducible BLUEPRINT geometry seeding used by migrations and commands."""

import gzip
import json
import re
from copy import deepcopy
from pathlib import Path


BUNDLED_SOURCE = Path(__file__).with_name('blueprints') / 'stadium_data_all.js.gz'


def _key(value):
    return re.sub(r'[^a-z0-9]+', '', str(value).casefold())


def load_blueprints(source=BUNDLED_SOURCE):
    source = Path(source)
    opener = gzip.open if source.suffix == '.gz' else open
    with opener(source, 'rt', encoding='utf-8') as handle:
        text = handle.read()
    match = re.search(r'const\s+STADIUMS\s*=\s*(\[.*\])\s*;\s*$', text, re.S)
    if not match:
        raise ValueError('Die BLUEPRINT-Datei enthält keine STADIUMS-JSON-Liste.')
    return {
        _key(item.get('meta', {}).get('club')): item
        for item in json.loads(match.group(1))
        if isinstance(item, dict)
    }


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
                'source': 'OpenStreetMap/BLUEPRINT-Bundle',
                'attribution': 'Blaupause: OpenStreetMap-Daten (ODbL)',
            },
        )
        seeded += 1
    return seeded, skipped