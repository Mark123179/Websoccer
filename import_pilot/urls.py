from django.http import JsonResponse
from django.urls import path, include


def health(request):
    return JsonResponse({"status": "t1-full-game-no-import", "schema": "import_pilot"})


urlpatterns = [path("health/", health), path("", include("core.urls"))]
