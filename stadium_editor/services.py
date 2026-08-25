"""Server-side geometry maintenance after authoritative capacity changes."""

from copy import deepcopy

from django.db import transaction

from .capacity import SEAT_TYPES, STANDS, _field
from .models import StadiumGeometry

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
        updated, warning = _grow_existing_rows(stadium, deepcopy(row.geometry))
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
        return warning