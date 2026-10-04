"""Persistent news images and read-only URLs for historical inline raster images."""

import base64
from copy import deepcopy
import hashlib
import re
from uuid import uuid4

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.urls import reverse

from .news_validation import validate_image_source


BACKUP_PREFIX = 'news-image-backups/'
LEGACY_RASTER = re.compile(
    r'data:image/(png|jpeg|jpg|gif|webp|avif|bmp|x-icon|vnd\.microsoft\.icon);base64,'
    r'([A-Za-z0-9+/]+={0,2})\Z'
)


def image_slots(card, blocks):
    """Yield only the established custom-image fields; ignore all other content."""
    if isinstance(card, dict):
        yield 'card', card, 'customSrc'
    if isinstance(blocks, list):
        for index, block in enumerate(blocks):
            if isinstance(block, dict) and block.get('k') == 'image':
                yield f'block-{index}', block, 'src'


def persist_news_images(card, blocks):
    """Caller validates the entire publication and permissions before any I/O.

    Never falls back to another backend on a storage failure. The database is
    written only after every image has been stored successfully.
    """
    card, blocks = deepcopy(card), deepcopy(blocks)
    saved = {}
    for _, container, key in image_slots(card, blocks):
        source = container.get(key)
        if not isinstance(source, str) or not source.startswith('data:'):
            continue
        validate_image_source(source)
        if source not in saved:
            mime, encoded = source.split(';base64,', 1)
            extension = mime.split('/')[-1]
            raw = base64.b64decode(encoded, validate=True)
            name = default_storage.save(
                f'news-images/{uuid4().hex}.{extension}', ContentFile(raw)
            )
            # Read-back protects migrations against an incomplete storage write.
            with default_storage.open(name, 'rb') as stored:
                if stored.read() != raw:
                    raise OSError('News image storage verification failed')
            saved[source] = default_storage.url(name)
        container[key] = saved[source]
    return card, blocks


def legacy_image_url(item, slot, source):
    digest = hashlib.sha256(source.encode()).hexdigest()
    return reverse('club_news_legacy_image', args=[item.club_id, item.pk, slot, digest])


def externalize_legacy_article(item, article):
    """Remove large inline rasters from full-page JSON, without writes on GET.

    Historical formats outside this raster set keep their existing inert-image
    rendering. New-upload limits must never truncate or invalidate old images.
    """
    article = deepcopy(article)
    for slot, container, key in image_slots(article.get('card'), article.get('blocks')):
        source = container.get(key)
        if isinstance(source, str) and LEGACY_RASTER.fullmatch(source):
            url = legacy_image_url(item, slot, source)
            container[key] = url
            if article.get('cardImageUrl') == source:
                article['cardImageUrl'] = url
    return article