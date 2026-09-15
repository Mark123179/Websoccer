"""Server-side geometry maintenance after authoritative capacity changes."""

from copy import deepcopy
import math

from django.db import transaction

from .capacity import SEAT_TYPES, STANDS, _field
from .capacity import distribute_capacities
from .models import StadiumGeometry
from .models import StadiumDesign
from .contracts import geometry_blocks, project_rle, rle_length

MAX_ROWS = 42


def _block_field(block):
    stand = str(block.get('stand', '')).upper()
    seat_type = str(block.get('type', 'SITZ')).upper()
    if seat_type in ('STANDING', 'STAND'):
        seat_type = 'STEH'
    elif seat_type in ('SEATING', 'SEAT', 'SITTING'):
        seat_type = 'SITZ'
    return _field(stand, seat_type)


def _grow_existing_rows(stadium, geometry):
    """Grow existing matching blocks only; never create a new tier."""
    blocks = geometry.get('blocks')
    if not isinstance(blocks, list):
        return geometry, 'Die gespeicherte Geometrie ist ungültig.'

    original = deepcopy(geometry)
    for stand in STANDS:
        for seat_type in SEAT_TYPES:
            field = _field(stand, seat_type)
            target = int(getattr(stadium, field))
            members = []
            for index, block in enumerate(blocks):
                if not isinstance(block, dict) or _block_field(block) != field:
                    continue
                try:
                    rows, seats = int(block['rows']), int(block['seats'])
                except (KeyError, TypeError, ValueError):
                    return original, 'Die gespeicherte Geometrie enthält ungültige Blockmaße.'
                members.append((index, rows, seats))

            if target and not members:
                return original, f'Kein passender Block für {field} vorhanden.'
            current = sum(rows * seats for _index, rows, seats in members)
            if target <= current:
                continue
            available = sum(max(0, MAX_ROWS - rows) * seats for _index, rows, seats in members)
            if target - current > available:
                return original, (
                    f'Ausbau für {field} wird nur im Kapazitätsmodell geführt: '
                    f'Bestehende Blöcke würden mehr als {MAX_ROWS} Reihen benötigen. '
                    'Zusätzliche Ränge sind in dieser Ausbaustufe gesperrt.'
                )

            # Largest compatible block first; ties by stable source position.
            order = sorted(members, key=lambda item: (-item[2], item[0]))
            remaining = target - current
            for index, _rows, seats in order:
                block = blocks[index]
                room = MAX_ROWS - int(block['rows'])
                if room <= 0:
                    continue
                added_rows = min(room, (remaining + seats - 1) // seats)
                block['rows'] = int(block['rows']) + added_rows
                remaining -= added_rows * seats
                if remaining <= 0:
                    break
    return geometry, ''


def _move_back_edge(block, distance):
    """Move the stored outer edge (quad points 0/1) along its normal."""
    quad = block.get('quad')
    if not isinstance(quad, list) or len(quad) != 4:
        return
    outer = (
        (float(quad[0][0]) + float(quad[1][0])) / 2,
        (float(quad[0][1]) + float(quad[1][1])) / 2,
    )
    inner = (
        (float(quad[3][0]) + float(quad[2][0])) / 2,
        (float(quad[3][1]) + float(quad[2][1])) / 2,
    )
    dx, dy = outer[0] - inner[0], outer[1] - inner[1]
    length = (dx * dx + dy * dy) ** .5 or 1
    dx, dy = dx / length * distance, dy / length * distance
    for index in (0, 1):
        quad[index][0] = round(float(quad[index][0]) + dx, 6)
        quad[index][1] = round(float(quad[index][1]) + dy, 6)


def _outward_unit(block):
    quad = block['quad']
    outer = (
        (float(quad[0][0]) + float(quad[1][0])) / 2,
        (float(quad[0][1]) + float(quad[1][1])) / 2,
    )
    inner = (
        (float(quad[3][0]) + float(quad[2][0])) / 2,
        (float(quad[3][1]) + float(quad[2][1])) / 2,
    )
    dx, dy = outer[0] - inner[0], outer[1] - inner[1]
    length = math.hypot(dx, dy) or 1
    return dx / length, dy / length


def _existing_rake(block):
    """Derive the supplied rake from the existing physical block itself."""
    depth = max(.8, int(block['rows']) * .8)
    return max(0.0, (float(block['z1']) - float(block['z0'])) / depth)


def _outer_tier_quad(template, rows):
    """Start a new stored-order tier beyond the template's outer edge."""
    ux, uy = _outward_unit(template)
    gap, depth = 2.0, rows * .8
    outer_left, outer_right = template['quad'][0], template['quad'][1]

    def moved(point, distance):
        return [
            round(float(point[0]) + ux * distance, 6),
            round(float(point[1]) + uy * distance, 6),
        ]

    inner_left = moved(outer_left, gap)
    inner_right = moved(outer_right, gap)
    return [
        moved(inner_left, depth),
        moved(inner_right, depth),
        inner_right,
        inner_left,
    ]


def _grow_v2_geometry(stadium, geometry):
    """Grow physical V2 rows, adding deterministic outer tiers when needed."""
    blocks = geometry.get('blocks')
    if not isinstance(blocks, list):
        return geometry, 'Die gespeicherte V2-Geometrie ist ungültig.'
    original = deepcopy(geometry)
    next_id = max(
        (int(block.get('id', -1)) for block in blocks if isinstance(block, dict)),
        default=-1,
    ) + 1
    total_physical = sum(
        int(block.get('rows', 0)) * int(block.get('seats', 0))
        for block in blocks if isinstance(block, dict)
    )
    total_target = sum(
        int(getattr(stadium, _field(stand, seat_type), 0) or 0)
        for stand in STANDS for seat_type in SEAT_TYPES
    )
    if total_target <= total_physical:
        return distribute_capacities(stadium, geometry), ''

    members_by_field = {
        _field(stand, seat_type): [
            block for block in blocks
            if isinstance(block, dict)
            and _block_field(block) == _field(stand, seat_type)
        ]
        for stand in STANDS for seat_type in SEAT_TYPES
    }
    deltas = {}
    for stand in STANDS:
        for seat_type in SEAT_TYPES:
            field = _field(stand, seat_type)
            target = int(getattr(stadium, field))
            assigned = sum(
                int(block.get('capacity', 0) or 0)
                for block in members_by_field[field]
            )
            deltas[field] = max(0, target - assigned)
    overflow = total_target - total_physical
    delta_total = sum(deltas.values())
    if not delta_total:
        return original, (
            'V2-Geometrie hat keinen Kapazitätszuwachs, dem der '
            'physische Überlauf zugeordnet werden kann.'
        )
    growth = {
        field: overflow * delta // delta_total
        for field, delta in deltas.items()
    }
    remainder = overflow - sum(growth.values())
    order = sorted(
        (field for field, delta in deltas.items() if delta),
        key=lambda field: (-deltas[field], field),
    )
    for offset in range(remainder):
        growth[order[offset % len(order)]] += 1

    for stand in STANDS:
        for seat_type in SEAT_TYPES:
            field = _field(stand, seat_type)
            target = int(getattr(stadium, field))
            members = members_by_field[field]
            if target and not members:
                return original, f'Kein passender Block für {field} vorhanden.'
            remaining = growth[field]
            if not remaining:
                continue
            # Keep each block's long-lived identity and allocate a new row to
            # the widest block first, exactly as the legacy path does.
            order = sorted(
                members,
                key=lambda block: (-int(block.get('seats', 0)), int(block.get('id', 0))),
            )
            for block in order:
                rows, seats = int(block['rows']), int(block['seats'])
                room = max(0, MAX_ROWS - rows)
                added = min(room, (remaining + seats - 1) // seats)
                if not added:
                    continue
                rake = _existing_rake(block)
                block['rows'] = rows + added
                block['capacity'] = int(block.get('capacity', rows * seats) or 0) + added * seats
                _move_back_edge(block, added * .8)
                block['z1'] = round(
                    float(block['z1']) + added * .8 * rake, 2)
                remaining -= added * seats
                if remaining <= 0:
                    break
            while remaining > 0:
                # Once 42 physical rows are full, append an outer tier.  Its
                # ID is allocated from the monotonic source range, so later
                # expansions and designs can refer to it stably.
                template = max(
                    members,
                    key=lambda b: (int(b.get('seats', 0)), int(b.get('id', 0))),
                )
                seats = int(template['seats'])
                rows = min(MAX_ROWS, max(1, (remaining + seats - 1) // seats))
                new = deepcopy(template)
                new['id'] = next_id
                next_id += 1
                new['tier'] = 'OBER'
                new['rows'] = rows
                new['capacity'] = rows * seats
                new['quad'] = _outer_tier_quad(template, rows)
                new['z0'] = round(float(template['z1']) + 2.0, 2)
                new['z1'] = round(
                    new['z0'] + rows * .8 * math.tan(math.radians(30)), 2)
                new['order'] = int(template.get('order', 0))
                blocks.append(new)
                members.append(new)
                remaining -= rows * seats
    # Physical cells and economic capacity are separate.  Persist the exact
    # authoritative allocation after changing the raster, never the rounded-up
    # number of newly available physical cells.
    return distribute_capacities(stadium, geometry), ''


def refresh_geometry_after_capacity_change(stadium):
    """Apply the row-only geometry refresh after a completed StadiumExpansion.

    The Stadium model is still the sole capacity source. A failed visual resize
    cannot roll back a valid financial/capacity expansion.
    """
    with transaction.atomic():
        try:
            row = StadiumGeometry.objects.select_for_update().get(stadium=stadium)
        except StadiumGeometry.DoesNotExist:
            return ''
        old_geometry = deepcopy(row.geometry)
        try:
            if (
                row.geometry.get('physical_grid') in ('v2', 'V2', 'physical', True)
                or row.geometry.get('grid') in ('physical-v2', 'physical')
            ):
                updated, warning = _grow_v2_geometry(stadium, deepcopy(row.geometry))
            else:
                updated, warning = _grow_existing_rows(stadium, deepcopy(row.geometry))
        except (KeyError, TypeError, ValueError, IndexError) as exc:
            # Capacity/economic expansion has already completed.  A malformed
            # visual row must therefore become a warning, never a blocker.
            updated, warning = old_geometry, f'V2-Geometrie konnte nicht wachsen: {exc}'
        update_fields = []
        if updated != row.geometry:
            row.geometry = updated
            update_fields.append('geometry')
        if warning != row.last_warning:
            row.last_warning = warning
            update_fields.append('last_warning')
        if update_fields:
            update_fields.append('updated_at')
            row.save(update_fields=update_fields)
        # A completed expansion changes the authoritative raster.  Project the
        # saved visual layer to it while retaining row-major orientation.
        design_row = StadiumDesign.objects.select_for_update().filter(stadium=stadium).first()
        if design_row and design_row.design.get('version') == 2:
            try:
                trusted_blocks = geometry_blocks(distribute_capacities(stadium, updated))
                current_blocks = design_row.design.get('blocks', [])
                current_shapes = {
                    item.get('id'): (item.get('rows'), item.get('seats'))
                    for item in current_blocks
                }
                trusted_shapes = {
                    block['id']: (block['rows'], block['seats'])
                    for block in trusted_blocks
                }
                if current_shapes != trusted_shapes:
                    old_by_id = {
                        block['id']: block for block in current_blocks
                    }
                    new_blocks = []
                    for block in trusted_blocks:
                        previous = next(
                            (item for item in current_blocks
                             if item.get('id') == block['id']), None)
                        if previous:
                            old_meta = old_by_id.get(block['id'], block)
                            rle = project_rle(previous.get('rle', []),
                                              (old_meta['rows'], old_meta['seats']),
                                              (block['rows'], block['seats']))
                        else:
                            rle = [[block['rows'] * block['seats'], 0]]
                        new_blocks.append({**block, 'rle': rle})
                    design = deepcopy(design_row.design)
                    design['blocks'] = new_blocks
                    design_row.design = design
                    design_row.save(update_fields=['design', 'updated_at'])
            except (KeyError, TypeError, ValueError, IndexError) as exc:
                warning = warning or f'Visualisierung nach Ausbau nicht aktualisiert: {exc}'
                if warning != row.last_warning:
                    row.last_warning = warning
                    row.save(update_fields=['last_warning', 'updated_at'])
        return warning