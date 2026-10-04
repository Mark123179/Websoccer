"""Validation for newly published news; never rewrites historical articles."""

import base64
import binascii
from io import BytesIO
import re
from urllib.parse import urlsplit
import warnings

from PIL import Image, UnidentifiedImageError


MAX_IMAGE_BYTES = 1024 * 1024
MAX_NEWS_BODY_BYTES = 2 * 1024 * 1024
MAX_IMAGE_PIXELS = 16_000_000
MAX_URL_LENGTH = 2048
MOTIFS = {'wappen', 'spieler', 'eigenes', 'none'}
DATA_IMAGE = re.compile(r'data:image/(png|jpeg|gif|webp);base64,([A-Za-z0-9+/]*={0,2})\Z')
FORMATS = {'png': 'PNG', 'jpeg': 'JPEG', 'gif': 'GIF', 'webp': 'WEBP'}


def validate_image_source(source):
    """Accept bounded raster data URLs, HTTP(S), or same-origin absolute paths.

    External URLs are not fetched here (no server-side request/SSRF).
    """
    if source is None or source == '':
        return source
    if not isinstance(source, str):
        raise ValueError('Die Bildquelle muss Text sein.')
    if source.startswith('data:'):
        if len(source) > 64 + 4 * ((MAX_IMAGE_BYTES + 2) // 3):
            raise ValueError('Bilder dürfen höchstens 1 MiB groß sein.')
        match = DATA_IMAGE.fullmatch(source)
        if not match:
            raise ValueError('Erlaubte Bildtypen: PNG, JPEG, GIF und WebP.')
        try:
            raw = base64.b64decode(match[2], validate=True)
            if len(raw) > MAX_IMAGE_BYTES:
                raise ValueError('Bilder dürfen höchstens 1 MiB groß sein.')
            with warnings.catch_warnings():
                warnings.simplefilter('error', Image.DecompressionBombWarning)
                with Image.open(BytesIO(raw)) as image:
                    if image.format != FORMATS[match[1]]:
                        raise ValueError('Bildinhalt und Bildtyp stimmen nicht überein.')
                    if image.width * image.height > MAX_IMAGE_PIXELS:
                        raise ValueError('Bilder dürfen höchstens 16 Megapixel haben.')
                    image.verify()
        except (binascii.Error, UnidentifiedImageError, OSError, SyntaxError,
                Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
            raise ValueError('Ungültige Bilddatei.') from exc
        return source
    if len(source) > MAX_URL_LENGTH or re.search(r'[\s\x00-\x1f\x7f<>"\'\\]', source):
        raise ValueError('Ungültige Bild-URL.')
    try:
        url = urlsplit(source)
        if source.startswith('/') and not source.startswith('//') and not url.netloc:
            return source
        if url.scheme in {'http', 'https'} and url.hostname and not url.username and not url.password:
            # Accessing port also rejects malformed ports.
            _ = url.port
            return source
    except ValueError:
        pass
    raise ValueError('Bild-URLs müssen HTTP(S) oder lokale Pfade verwenden.')


def validate_card(card):
    if card is None:
        return None
    if not isinstance(card, dict):
        raise ValueError('Die News-Karte muss ein Objekt sein.')
    if set(card) - {'motiv', 'pid', 'accent', 'customSrc'}:
        raise ValueError('Unbekanntes Kartenfeld.')
    motif = card.get('motiv', 'none')
    if not isinstance(motif, str) or motif not in MOTIFS:
        raise ValueError('Ungültiges Kartenmotiv.')
    pid = card.get('pid', '')
    if not isinstance(pid, str) or not re.fullmatch(r'[0-9]{0,19}', pid):
        raise ValueError('Ungültige Spieler-ID.')
    accent = card.get('accent', '#22e6ff')
    if not isinstance(accent, str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', accent):
        raise ValueError('Ungültige Akzentfarbe.')
    return {
        'motiv': motif, 'pid': pid, 'accent': accent,
        'customSrc': validate_image_source(card.get('customSrc')),
    }


def validate_news_body(body):
    if not isinstance(body, dict):
        raise ValueError('Die Nachricht muss ein Objekt sein.')
    for field in ('titel', 'sub', 'kat', 'outlet'):
        if field in body and not isinstance(body[field], str):
            raise ValueError('Nachrichtenfelder müssen Text sein.')
    card = validate_card(body.get('card'))
    blocks = body.get('blocks', [])
    if not isinstance(blocks, list) or any(not isinstance(block, dict) for block in blocks):
        raise ValueError('Die Bausteine müssen eine Liste von Objekten sein.')
    for block in blocks:
        if not isinstance(block.get('k'), str):
            raise ValueError('Ungültiger Bausteintyp.')
        if block['k'] == 'image':
            validate_image_source(block.get('src'))
    return card, blocks