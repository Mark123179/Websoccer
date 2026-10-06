from django.http import JsonResponse
from django.urls import path, include, re_path
from game.club_import.static_assets import serve


def health(request):
    return JsonResponse({"status": "t3-t4-creator", "schema": "import_pilot"})


urlpatterns = [
    path("health/", health),
    re_path(r"^static/(?P<name>.+)$", serve),
    re_path(r"^assets/(?P<name>.+)$", serve, {"asset": True}),
    path("", include("core.urls")),
]
