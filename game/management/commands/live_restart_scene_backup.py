"""Read-only private snapshot of every club's scene and PostgreSQL sequences."""
import json
import re

from django.core.management.base import BaseCommand, CommandError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import connection, connections

from game.club_import.live_restart_safety import build_scene_snapshot


class Command(BaseCommand):
    help = "Private lesende Sicherung aller Vereinsszenen; kein Import-/Resetmodus."

    def add_arguments(self, parser):
        parser.add_argument("--restore-check-name")

    def handle(self, *args, **options):
        name = options["restore_check_name"]
        conn = connection
        alias = "_live_restart_scene_check"
        if name:
            if (connection.vendor != "postgresql"
                    or not re.fullmatch(r"import_restore_check_[a-z0-9_]{1,32}", name)
                    or name == connection.settings_dict["NAME"]):
                raise CommandError("Nur eine getrennte import_restore_check_<Kennung>-Datenbank.")
            if alias in connections:
                raise CommandError("Prüfverbindung bereits registriert.")
            config = connection.settings_dict.copy()
            config["NAME"] = name
            connections.databases[alias] = config
            conn = connections[alias]
        try:
            self.stdout.write(json.dumps(
                build_scene_snapshot(conn), cls=DjangoJSONEncoder, ensure_ascii=False))
        finally:
            if name:
                conn.close()
                del connections[alias]
                del connections.databases[alias]
