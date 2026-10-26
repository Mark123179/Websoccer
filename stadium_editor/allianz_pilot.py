"""Authenticated, read-only presentation pilot; never seeds missing editor rows."""
from copy import deepcopy

from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponseForbidden, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_GET

from game.models import Stadium
from .model_registry import model_manifest
from .models import StadiumGeometry
from .scene_service import current_live_scene
from .seed import load_blueprints
from .unity_runtime import unity_presentation


def pilot_scene():
    stadium = Stadium.objects.select_related("club").get(club__fm_inside_id=915)
    if StadiumGeometry.objects.filter(stadium=stadium).exists():
        return current_live_scene(stadium)
    # The checked-in original blueprint supplies only the existing scene frame
    # and surroundings. It is NOT saved or used to replace the source 3D model.
    manifest = model_manifest(915)
    if manifest is None:
        raise ValueError("Das freigegebene Allianz-Arena-Modell fehlt.")
    geometry = deepcopy(load_blueprints()["fcbayernmnchen"])
    return {
        "presentation": unity_presentation(stadium, geometry, {}, manifest),
        "geometryOrigin": "bundled-reference-read-only",
    }


@login_required(login_url="/auth/login/")
@require_GET
def allianz_pilot(request):
    if not request.user.is_staff:
        return HttpResponseForbidden("Der Stadionpilot ist nur für Administratoren freigegeben.")
    return render(request, "stadium_editor/allianz_pilot.html", {
        "pilot_scene_url": reverse("allianz_pilot_scene"),
    })


@login_required(login_url="/auth/login/")
@require_GET
def allianz_pilot_scene(request):
    if not request.user.is_staff:
        return HttpResponseForbidden("Der Stadionpilot ist nur für Administratoren freigegeben.")
    try:
        scene = pilot_scene()
    except (Stadium.DoesNotExist, KeyError, ValueError) as error:
        raise Http404("Die Allianz-Arena-Pilotszene ist nicht verfügbar.") from error
    response = JsonResponse(scene)
    response["Cache-Control"] = "private, no-store"
    return response
