"""Read-only compatibility serving for images embedded in historical news."""

import base64
import binascii
import hashlib

from django.http import Http404, HttpResponse, HttpResponseNotModified
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_safe

from .models import ClubNewsItem
from .news_image_storage import LEGACY_RASTER, image_slots


@require_safe
def club_news_legacy_image(request, club_id, news_id, slot, digest):
    item = get_object_or_404(
        ClubNewsItem.objects.only('card_data', 'blocks'), pk=news_id, club_id=club_id
    )
    source = next(
        (container.get(key) for name, container, key
         in image_slots(item.card_data, item.blocks) if name == slot), None
    )
    match = LEGACY_RASTER.fullmatch(source) if isinstance(source, str) else None
    if not match or hashlib.sha256(source.encode()).hexdigest() != digest:
        raise Http404
    etag = f'"{digest}"'
    if request.headers.get('If-None-Match') == etag:
        response = HttpResponseNotModified()
    else:
        try:
            raw = base64.b64decode(match[2], validate=True)
        except binascii.Error:
            raise Http404
        mime = 'jpeg' if match[1] == 'jpg' else match[1]
        response = HttpResponse(raw, content_type=f'image/{mime}')
    response['ETag'] = etag
    response['Cache-Control'] = 'public, max-age=31536000, immutable'
    response['X-Content-Type-Options'] = 'nosniff'
    response['Content-Security-Policy'] = "default-src 'none'; sandbox"
    return response