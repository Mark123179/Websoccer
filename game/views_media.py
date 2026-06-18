import hashlib
import mimetypes
import os
from email.utils import formatdate, parsedate_to_datetime

from django.conf import settings
from django.http import HttpResponse, Http404, HttpResponseNotModified


def serve_media(request, name):
    last_modified = None
    blob = None
    data = None

    # ── 1. Try Replit Object Storage ────────────────────────────────────────
    try:
        from replit.object_storage import Client
        client = Client()

        try:
            bucket = client._Client__bucket()
            blob = bucket.get_blob(name)
            if blob is None:
                raise Http404(f"Media file not found: {name}")
            last_modified = blob.updated
        except Http404:
            raise
        except Exception:
            blob = None

        inm_header = request.META.get('HTTP_IF_NONE_MATCH')
        if last_modified is not None and not inm_header:
            ims_header = request.META.get('HTTP_IF_MODIFIED_SINCE')
            if ims_header:
                try:
                    ims = parsedate_to_datetime(ims_header)
                    if last_modified.replace(microsecond=0) <= ims:
                        return HttpResponseNotModified()
                except Exception:
                    pass

        if blob is not None:
            data = blob.download_as_bytes()
        else:
            data = client.download_as_bytes(name)

    except Http404:
        raise
    except Exception:
        data = None  # Object Storage unavailable — fall through to local FS

    # ── 2. Fallback: local MEDIA_ROOT ────────────────────────────────────────
    if data is None:
        local_path = os.path.join(settings.MEDIA_ROOT, name)
        if not os.path.isfile(local_path):
            raise Http404(f"Media file not found: {name}")
        with open(local_path, 'rb') as fh:
            data = fh.read()
        mtime = os.path.getmtime(local_path)
        import datetime as _dt
        last_modified = _dt.datetime.fromtimestamp(mtime, tz=_dt.timezone.utc)

        inm_header = request.META.get('HTTP_IF_NONE_MATCH')
        if not inm_header:
            ims_header = request.META.get('HTTP_IF_MODIFIED_SINCE')
            if ims_header:
                try:
                    ims = parsedate_to_datetime(ims_header)
                    if last_modified.replace(microsecond=0) <= ims:
                        return HttpResponseNotModified()
                except Exception:
                    pass

    etag = f'"{hashlib.md5(data).hexdigest()}"'

    if request.META.get('HTTP_IF_NONE_MATCH') == etag:
        return HttpResponseNotModified()

    content_type, _ = mimetypes.guess_type(name)
    if not content_type:
        content_type = 'application/octet-stream'

    response = HttpResponse(data, content_type=content_type)
    response['ETag'] = etag
    if last_modified is not None:
        response['Last-Modified'] = formatdate(last_modified.timestamp(), usegmt=True)
    response['Cache-Control'] = 'public, max-age=31536000, immutable'
    return response
