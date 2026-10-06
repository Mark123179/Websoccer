"""Workspace-only prefix proxy to the separately configured pilot process."""
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from django.http import HttpResponse
from django.conf import settings


class PilotProxyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        prefix = "/import-pilot"
        if not getattr(settings, "IMPORT_PILOT_PROXY_ENABLED", False) or not (
                request.path == prefix or request.path.startswith(prefix + "/")):
            return self.get_response(request)
        path = request.get_full_path()[len(prefix):] or "/"
        if not path.startswith("/"):
            path = "/" + path
        headers = {name: value for name, value in request.headers.items()
                   if name.lower() in ("content-type", "cookie", "origin", "referer", "x-csrftoken")}
        headers.update(Host=request.get_host(), **{"X-Forwarded-Proto": request.headers.get(
            "X-Forwarded-Proto", "https" if request.is_secure() else "http")})
        upstream = Request("http://127.0.0.1:6000" + path,
            data=request.body if request.method not in ("GET", "HEAD") else None,
            headers=headers, method=request.method)
        # Do not follow login redirects into the public app.
        from urllib.request import build_opener, HTTPRedirectHandler
        class NoRedirect(HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, hdrs, newurl):
                return None
        try:
            response = build_opener(NoRedirect).open(upstream, timeout=60)
        except HTTPError as exc:
            response = exc
        except URLError:
            return HttpResponse("Pilot noch nicht erreichbar.", status=503)
        result = HttpResponse(response.read(), status=response.code)
        for name, value in response.headers.items():
            if name.lower() == "set-cookie":
                result.cookies.load(value)
            elif name.lower() not in ("connection", "transfer-encoding", "content-length"):
                result[name] = value
        return result
