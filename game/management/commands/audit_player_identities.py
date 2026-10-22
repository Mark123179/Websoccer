import json

from django.core.management.base import BaseCommand

from game.club_import.identity_audit import audit_player_identities


class Command(BaseCommand):
    help = "Prüft bestehende Spieleridentitäten rein lesend, ohne Paketimport oder Reparatur."
    requires_migrations_checks = False
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument("--format", choices=("text", "json"), default="text")

    def handle(self, *args, **options):
        report = audit_player_identities()
        if options["format"] == "json":
            self.stdout.write(json.dumps(report, ensure_ascii=False, indent=2))
            return
        self.stdout.write("Spieleridentitäten – rein lesender Prüfbericht")
        self.stdout.write(report["policy"])
        self.stdout.write(json.dumps(report["summary"], ensure_ascii=False, sort_keys=True))
        for index, finding in enumerate(report["findings"], 1):
            self.stdout.write(f"\nBefund {index}")
            self.stdout.write(json.dumps(finding, ensure_ascii=False, indent=2))
