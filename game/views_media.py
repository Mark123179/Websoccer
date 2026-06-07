import mimetypes

from django.http import HttpResponse, Http404


def serve_media(request, name):
    try:
        from replit.object_storage import Client
        from replit.object_storage.errors import ObjectNotFoundError
        client = Client()
        data = client.download_as_bytes(name)
    except Exception as exc:
        if 'NotFound' in type(exc).__name__ or 'ObjectNotFound' in type(exc).__name__:
            raise Http404(f"Media file not found: {name}")
        raise Http404(f"Could not load media file: {exc}")

    content_type, _ = mimetypes.guess_type(name)
    if not content_type:
        content_type = 'application/octet-stream'

    return HttpResponse(data, content_type=content_type)
