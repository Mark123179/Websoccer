"""Vereinsbezogener Ticker-Verweis; keine Spiel-/Designänderungen."""
from django.urls import reverse

from stadium_editor.elversberg_environment import ELVERSBERG_FMI_ID, STYLE
from stadium_editor.models import StadiumGeometry


def ticker_scene_context(club):
    if club is None or club.fm_inside_id != ELVERSBERG_FMI_ID:
        return None
    stadium = getattr(club, "stadium", None)
    if stadium is None or not StadiumGeometry.objects.filter(stadium=stadium).exists():
        return None
    return {
        "renderer": "canonical",
        "sceneUrl": reverse("stadium_live_scene", args=[club.pk]),
        "stadium": stadium.name,
        "clubId": club.pk,
        "environmentStyle": STYLE,
    }
