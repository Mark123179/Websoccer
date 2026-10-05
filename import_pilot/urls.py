from django.http import JsonResponse
from django.urls import path


def health(request):
    return JsonResponse({"status": "infrastructure-only", "schema": "import_pilot"})


urlpatterns = [path("health/", health)]
