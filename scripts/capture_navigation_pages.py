"""Export real, authenticated pages for shell geometry checks without DB changes.

Run with python scripts/capture_navigation_pages.py /tmp/navigation-before.
All incidental view/session writes are rolled back. Files may contain game data;
keep the output outside the repository.
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
import django

django.setup()

from django.contrib.auth import get_user_model
from django.db import transaction
from django.test import Client
from game.models import Player
from game.views import current_manager_club

destination = Path(sys.argv[1])
destination.mkdir(parents=True, exist_ok=True)
with transaction.atomic():
    user = get_user_model().objects.filter(is_superuser=True).first()
    if not user:
        raise RuntimeError("Geometry capture requires an existing superuser.")
    club = current_manager_club(user)
    if not club:
        raise RuntimeError("Geometry capture requires a managed club.")
    player = Player.objects.filter(club=club).first()
    routes = {
        "overview": "/",
        "tactics": f"/clubs/{club.pk}/tactics/",
        "preview": f"/clubs/{club.pk}/matches/next/",
        "club": f"/clubs/{club.pk}/",
        "table": "/clubs/",
    }
    if player:
        routes["player"] = f"/players/{player.pk}/"
    client = Client()
    client.force_login(user)
    for name, route in routes.items():
        response = client.get(route, HTTP_HOST="localhost")
        if response.status_code != 200:
            raise RuntimeError(f"{route}: HTTP {response.status_code}")
        (destination / f"{name}.html").write_bytes(response.content)
    (destination / "routes.json").write_text(json.dumps(routes))
    transaction.set_rollback(True)