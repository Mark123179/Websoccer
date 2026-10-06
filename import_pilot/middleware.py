from django.http import JsonResponse


class T1ReadOnlyMiddleware:
    """T2–T5 are not authorized: no legacy/new uploader or game mutations."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            return JsonResponse({"error": "Pilot stopped at T1; mutations not authorized."}, status=403)
        return self.get_response(request)
