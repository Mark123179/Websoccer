from django.http import JsonResponse


class T1ReadOnlyMiddleware:
    """Only approved Creator mutations and ordinary login/logout are writable."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path_info
        allowed = path.startswith("/creator/packages/") or path in (
            "/auth/login/", "/auth/logout/")
        if request.method not in ("GET", "HEAD", "OPTIONS") and not allowed:
            return JsonResponse({"error": "Im Pilot sind nur die freigegebenen Creator-Schreibwege geöffnet."}, status=403)
        return self.get_response(request)
