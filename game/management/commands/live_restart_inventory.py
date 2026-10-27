"""Read-only operator command, deliberately without any apply/reset switches."""
import json

from django.core.management.base import BaseCommand

from game.club_import.live_restart_inventory import build_inventory


class Command(BaseCommand):
    help = "Rein lesendes Inventar für die Live-Neustart-Vorbereitung, ohne Reset/Import."

    def handle(self, *args, **options):
        self.stdout.write(json.dumps(build_inventory(), ensure_ascii=False, indent=2))
