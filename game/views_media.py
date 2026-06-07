import hashlib
import mimetypes
from email.utils import formatdate, parsedate_to_datetime

from django.http import HttpResponse, Http404, HttpResponseNotModified


def serve_media(request, name):
    last_modified = None
    blob = None

    try:
        from replit.object_storage import Client
        client = Client()

        # Access the underlying GCS blob for lightweight metadata (avoids a full
        # download just to check If-Modified-Since).  We reach through the private
        # name-mangled attribute intentionally; the package is pinned at 1.0.2 and
        # the source has been verified.
        try:
            bucket = client._Client__bucket()
            blob = bucket.get_blob(name)
            if blob is None:
                raise Http404(f"Media file not found: {name}")
            last_modified = blob.updated  # UTC-aware datetime; may be None
        except Http404:
            raise
        except Exception:
            blob = None  # Fall back to plain download below

        # Short-circuit for If-Modified-Since — but only when If-None-Match is
        # absent.  RFC 7232 §6 requires ETag comparison to take precedence when
        # both headers are present, so we defer to the ETag path in that case.
        inm_header = request.META.get('HTTP_IF_NONE_MATCH')
        if last_modified is not None and not inm_header:
            ims_header = request.META.get('HTTP_IF_MODIFIED_SINCE')
            if ims_header:
                try:
                    ims = parsedate_to_datetime(ims_header)
                    # HTTP dates have 1-second resolution; strip sub-second precision
                    if last_modified.replace(microsecond=0) <= ims:
                        return HttpResponseNotModified()
                except Exception:
                    pass

        # Download content (reuse GCS blob when available, fall back to client API)
        if blob is not None:
            data = blob.download_as_bytes()
        else:
            data = client.download_as_bytes(name)

    except Http404:
        raise
    except Exception as exc:
        if 'NotFound' in type(exc).__name__ or 'ObjectNotFound' in type(exc).__name__:
            raise Http404(f"Media file not found: {name}")
        raise Http404(f"Could not load media file: {exc}")

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
