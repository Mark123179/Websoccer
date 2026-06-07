import hashlib
import mimetypes

from django.http import HttpResponse, Http404, HttpResponseNotModified


def serve_media(request, name):
    try:
        from replit.object_storage import Client
        client = Client()
        data = client.download_as_bytes(name)
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
    response['Cache-Control'] = 'public, max-age=31536000, immutable'
    return response
