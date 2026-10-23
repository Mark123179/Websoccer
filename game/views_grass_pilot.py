"""Read-only, superuser-only grass pilot. No editor or simulation writes."""
import logging

from django.http import Http404, HttpResponse
from django.template.loader import render_to_string
from django.templatetags.static import static
from django.urls import reverse
from django.views.decorators.http import require_GET

from .object_storage_backend import get_client
from .views_story_test import admin_only
from stadium_editor.grass import GRASS_ASSETS

logger = logging.getLogger(__name__)


@admin_only
@require_GET
def grass_pilot(request):
    config = {
        "stadium": "Dortmund",
        "assets": {name: reverse("grass_pilot_asset", args=[name])
                   for name in GRASS_ASSETS},
        "lightsUrl": static("stadium_editor/study_assets/dortmund_lights.json"),
    }
    # Global game context processors can initialize weather/calendar rows.
    # This standalone, GET-only admin page needs no request context or forms.
    response = HttpResponse(render_to_string(
        "game/grass_pilot.html", {"grass_config": config}))
    response["Cache-Control"] = "private, no-store"
    return response


@admin_only
@require_GET
def grass_pilot_asset(request, name):
    asset = GRASS_ASSETS.get(name)
    if asset is None:
        raise Http404
    key, content_type = asset
    try:
        data = get_client().download_as_bytes(key)
    except Exception:
        logger.error("Rasen-Pilot: Material %s nicht verfügbar.", name)
        response = HttpResponse("Rasenmaterial nicht verfügbar.", status=503,
                                content_type="text/plain; charset=utf-8")
        response["Cache-Control"] = "private, no-store"
        return response
    response = HttpResponse(data, content_type=content_type)
    response["Cache-Control"] = "private, max-age=3600"
    response["X-Content-Type-Options"] = "nosniff"
    return response
