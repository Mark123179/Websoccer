import sys

from django.apps import AppConfig
from django.core.exceptions import ImproperlyConfigured
from django.db import connection


class ImportPilotConfig(AppConfig):
    name = "import_pilot"

    def ready(self):
        if any(argument in {"worker", "beat"} for argument in sys.argv[1:]):
            raise ImproperlyConfigured("Pilot workers and schedulers are disabled.")
        connection.ensure_connection()
