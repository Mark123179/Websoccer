"""Only SELECT/schema reads; no execute/apply/reset flag is available."""
import json
import re
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from game.club_import.reset_preview import build_preview, render_sql


class Command(BaseCommand):
    help = "Lesende Reset-Vorschau; --sql druckt nur einen nicht ausgeführten Entwurf."

    def add_arguments(self, parser):
        parser.add_argument("--sql", action="store_true")
        parser.add_argument("--restore-check-name",
                            help="Nur eine isolierte PostgreSQL-Prüfkopie, niemals eine Live-/Pilot-DB.")

    def handle(self, *args, **options):
        conn = connection
        copied = None
        if options["restore_check_name"]:
            name = options["restore_check_name"]
            if connection.vendor != "postgresql" or not re.fullmatch(r"import_restore_check_[a-z0-9_]{1,32}", name):
                raise CommandError("Prüfdatenbank muss import_restore_check_<Kennung> heißen.")
            if name == connection.settings_dict["NAME"] or options["sql"]:
                raise CommandError("Prüfkopie muss getrennt sein; dort keinen Reset-Entwurf erzeugen.")
            copied = connection.copy(alias="restore_check")
            copied.settings_dict["NAME"] = name
            conn = copied
        try:
            plan = build_preview(conn)
            if copied:
                plan["scope"] = "isolated_restore_check_not_live"
            self.stdout.write(render_sql(plan, conn.ops.quote_name) if options["sql"]
                              else json.dumps(plan, ensure_ascii=False, indent=2))
        finally:
            if copied:
                copied.close()
