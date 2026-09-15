"""Distribution of authoritative Stadium capacities over geometry blocks."""

from copy import deepcopy
import math


STANDS = ('NORD', 'OST', 'SUED', 'WEST')
SEAT_TYPES = ('STEH', 'SITZ', 'VIP')
TYPE_ALIASES = {
    'STANDING': 'STEH',
    'STAND': 'STEH',
    'SEATING': 'SITZ',
    'SEAT': 'SITZ',
    'SITTING': 'SITZ',
}


class CapacityDistributionError(ValueError):
    pass


def _field(stand, seat_type):
    suffix = {
        'STEH': 'standing',
        'SITZ': 'seating',
        'VIP': 'vip',
    }[seat_type]
    return f'{stand.lower()}_{suffix}'


def _normalise_type(block):
    raw = str(block.get('type', 'SITZ')).upper()
    return TYPE_ALIASES.get(raw, raw if raw in SEAT_TYPES else 'SITZ')


def _stadium_capacity_total(stadium):
    """Work for runtime and historical migration model instances alike."""
    return sum(
        int(getattr(stadium, _field(stand, seat_type), 0) or 0)
        for stand in STANDS
        for seat_type in SEAT_TYPES
    )


def distribute_capacities(stadium, geometry):
    """Return geometry with exact server-authoritative block capacities.

    Geometry only supplies block shape and classification. Browser-provided
    capacities are ignored. Remainders are allocated by descending geometric
    block size, then stable block id.
    """
    result = deepcopy(geometry or {})
    blocks = result.get('blocks')
    if not isinstance(blocks, list) or not blocks:
        raise CapacityDistributionError('Die Stadion-Geometrie enthält keine Blöcke.')

    groups = {field: [] for stand in STANDS for seat_type in SEAT_TYPES
              for field in (_field(stand, seat_type),)}
    for index, block in enumerate(blocks):
        if not isinstance(block, dict):
            raise CapacityDistributionError('Ungültiger Block in der Stadion-Geometrie.')
        stand = str(block.get('stand', '')).upper()
        seat_type = _normalise_type(block)
        field = _field(stand, seat_type)
        if field not in groups:
            raise CapacityDistributionError(
                f'Block {block.get("id", index)} hat keine gültige Tribünenzuordnung.'
            )
        try:
            weight = max(1, int(block.get('rows', 0)) * int(block.get('seats', 0)))
        except (TypeError, ValueError):
            raise CapacityDistributionError('Blockmaße müssen ganzzahlig sein.')
        groups[field].append((index, weight, str(block.get('id', index))))

    # V2 rows/seats describe the physical raster (0.8m x 0.5m), not an
    # economic capacity-derived grid.  Capacity still gets distributed
    # exactly as before, but never changes that physical shape.  Historical
    # geometry has no marker and deliberately keeps the old behaviour.
    physical_grid = (
        result.get('physical_grid') in ('v2', 'V2', 'physical', True)
        or result.get('grid') in ('physical-v2', 'physical')
    )
    for stand in STANDS:
        for seat_type in SEAT_TYPES:
            field = _field(stand, seat_type)
            target = int(getattr(stadium, field))
            members = groups[field]
            if target and not members:
                raise CapacityDistributionError(
                    f'{field} benötigt Plätze, aber die Geometrie hat keinen passenden Block.'
                )
            if not members:
                continue
            total_weight = sum(item[1] for item in members)
            allocations = []
            assigned = 0
            for index, weight, block_id in members:
                value = (target * weight) // total_weight
                allocations.append([index, value, weight, block_id])
                assigned += value
            remainder = target - assigned
            allocations.sort(key=lambda item: (-item[2], item[3], item[0]))
            for offset in range(remainder):
                allocations[offset % len(allocations)][1] += 1
            for index, value, _weight, _block_id in allocations:
                blocks[index]['capacity'] = value
                blocks[index]['type'] = _normalise_type(blocks[index])
                # The editor contract uses a complete rectangular grid.  Its
                # width is geometric, while its height follows authoritative
                # assigned capacity; the final row is intentionally padded.
                if not physical_grid:
                    width = max(1, int(blocks[index]['seats']))
                    blocks[index]['rows'] = max(1, math.ceil(value / width))
    result['capacity_source'] = 'Stadium'
    result['capacity_total'] = _stadium_capacity_total(stadium)
    return result