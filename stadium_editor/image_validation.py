import base64
import binascii
import io
import re

from PIL import Image, UnidentifiedImageError


DATA_URL_RE = re.compile(r'^data:image/(png|jpeg|jpg|webp);base64,([A-Za-z0-9+/=\s]+)$', re.I)
MAX_EDGE = 480
MAX_DECODED_BYTES = 480 * 480 * 4


class InvalidImageData(ValueError):
    pass


def validate_and_quantize_data_url(value):
    if not isinstance(value, str):
        raise InvalidImageData('Bildquelle muss eine dataURL sein.')
    match = DATA_URL_RE.fullmatch(value.strip())
    if not match:
        raise InvalidImageData('Ungültige Bild-dataURL.')
    try:
        raw = base64.b64decode(match.group(2), validate=True)
    except (binascii.Error, ValueError):
        raise InvalidImageData('Bild-dataURL enthält kein gültiges Base64.')
    if len(raw) > MAX_DECODED_BYTES:
        raise InvalidImageData('Bildquelle ist zu groß.')
    try:
        with Image.open(io.BytesIO(raw)) as source:
            if source.width > MAX_EDGE or source.height > MAX_EDGE:
                raise InvalidImageData('Bildquelle darf höchstens 480 px pro Kante haben.')
            image = source.convert('RGBA').quantize(
                colors=64,
                method=Image.Quantize.FASTOCTREE,
            )
            output = io.BytesIO()
            image.save(output, format='PNG', optimize=True)
    except (UnidentifiedImageError, OSError):
        raise InvalidImageData('Bild-dataURL ist kein gültiges Bild.')
    encoded = base64.b64encode(output.getvalue()).decode('ascii')
    return f'data:image/png;base64,{encoded}'


def sanitize_design_payload(value):
    """Copy a JSON payload while replacing every image dataURL canonically."""
    if isinstance(value, str):
        return validate_and_quantize_data_url(value) if value.startswith('data:') else value
    if isinstance(value, list):
        return [sanitize_design_payload(item) for item in value]
    if isinstance(value, dict):
        return {key: sanitize_design_payload(item) for key, item in value.items()}
    if value is None or isinstance(value, (bool, int, float)):
        return value
    raise InvalidImageData('Design enthält einen nicht unterstützten Datentyp.')


def normalize_design_payload(payload, *, geometry=None, stadium_name=None, blickrichtung='NORD'):
    """Validate visual data and merge it with server-owned V2 geometry.

    ``geometry`` is deliberately required by the save view.  The optional
    legacy mode is retained for old callers and old files only.
    """
    payload = sanitize_design_payload(payload)
    from .grass import normalize_grass_variant
    grass = {}
    if 'grass_variant' in payload:
        grass['grass_variant'] = normalize_grass_variant(payload['grass_variant'])
    palette = payload.get('palette', [])
    blocks = payload.get('blocks', [])
    if not isinstance(palette, list) or not isinstance(blocks, list):
        raise InvalidImageData('Design hat ein ungültiges Format.')
    if not palette:
        raise InvalidImageData('Palette muss mindestens eine Farbe enthalten.')
    if len(palette) > 64 or len(blocks) > 2_000:
        raise InvalidImageData('Design ist zu groß.')
    clean_palette = []
    for color in palette:
        if not isinstance(color, str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', color):
            raise InvalidImageData('Palette enthält eine ungültige Farbe.')
        clean_palette.append(color.lower())
    clean_blocks = []
    for block in blocks:
        if not isinstance(block, dict) or not isinstance(block.get('id'), int):
            raise InvalidImageData('Design enthält einen ungültigen Block.')
        rle = block.get('rle', [])
        if not isinstance(rle, list) or len(rle) > 10_000:
            raise InvalidImageData('Design enthält eine ungültige Sitzfolge.')
        clean_rle = []
        for pair in rle:
            if (
                not isinstance(pair, list) or len(pair) != 2
                or not isinstance(pair[0], int) or not isinstance(pair[1], int)
                or pair[0] < 0 or pair[0] > 65_535
                or pair[1] < 0 or pair[1] >= len(clean_palette)
            ):
                raise InvalidImageData('Design enthält eine ungültige Sitzfolge.')
            clean_rle.append(pair)
        clean_blocks.append({'id': block['id'], 'rle': clean_rle})
    if geometry is None:
        return {'version': 1, 'palette': clean_palette, 'blocks': clean_blocks, **grass}

    from .contracts import geometry_blocks, project_rle, rle_length
    trusted = geometry_blocks(geometry)
    by_id = {}
    for block in clean_blocks:
        if block['id'] in by_id:
            raise InvalidImageData(f"Block-ID {block['id']} wurde mehrfach gesendet.")
        by_id[block['id']] = block
    trusted_ids = {block['id'] for block in trusted}
    unknown = set(by_id) - trusted_ids
    if unknown:
        raise InvalidImageData(f'Unbekannte Block-ID: {min(unknown)}.')
    is_v2 = payload.get('version') == 2
    if payload.get('version', 1) not in (1, 2):
        raise InvalidImageData('Nicht unterstützte Design-Version.')
    result = []
    for meta in trusted:
        supplied = by_id.get(meta['id'])
        if supplied is None:
            rle = [[meta['rows'] * meta['seats'], 0]]
        else:
            original = next(item for item in blocks if item.get('id') == meta['id'])
            if is_v2:
                for key in ('stand', 'tier', 'order', 'rows', 'seats'):
                    if original.get(key) != meta[key]:
                        raise InvalidImageData(
                            f"Block {meta['id']}: {key} stimmt nicht mit der Servergeometrie überein.")
                if supplied['rle'] and rle_length(supplied['rle']) != meta['rows'] * meta['seats']:
                    raise InvalidImageData(
                        f"Block {meta['id']}: Sitzfolge muss exakt {meta['rows'] * meta['seats']} Plätze haben.")
                rle = supplied['rle'] or [[meta['rows'] * meta['seats'], 0]]
            else:
                # V1 did not have dimensions.  Its stream is projected rather
                # than truncated, so existing choreographies remain visible.
                target_size = meta['rows'] * meta['seats']
                source_len = min(rle_length(supplied['rle']), target_size)
                source_rows = max(1, (source_len + meta['seats'] - 1) // meta['seats'])
                rle = project_rle(supplied['rle'], (source_rows, meta['seats']),
                                  (meta['rows'], meta['seats']))
        result.append({**meta, 'rle': rle})
    direction = str(payload.get('blickrichtung', blickrichtung)).upper()
    if direction not in ('NORD', 'SUED', 'OST', 'WEST'):
        raise InvalidImageData('Blickrichtung muss NORD, SUED, OST oder WEST sein.')
    return {'version': 2, 'stadium': stadium_name or payload.get('stadium', ''),
            'blickrichtung': direction, 'palette': clean_palette, 'blocks': result, **grass}