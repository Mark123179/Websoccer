import json

from django.core.management.base import BaseCommand
from django.utils import timezone

from game.club_import.identity_audit import audit_player_identities
from game.models import PlayerIdentityAuditSnapshot


class Command(BaseCommand):
    help = "Prüft bestehende Spieleridentitäten rein lesend, ohne Paketimport oder Reparatur."
    requires_migrations_checks = False
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument("--format", choices=("text", "json"), default="text")
        parser.add_argument(
            "--save", action="store_true",
            help="Prüfbericht für den Creator speichern; nur der Bericht wird geschrieben, keine Spieldaten.",
        )

    def handle(self, *args, **options):
        generated_at = timezone.now()
        report = audit_player_identities()
        if options["save"]:
            PlayerIdentityAuditSnapshot.objects.update_or_create(
                pk=1, defaults={"generated_at": generated_at, "report": report},
            )
        if options["format"] == "json":
            self.stdout.write(json.dumps(report, ensure_ascii=False, indent=2))
            return
        self.stdout.write("Spieleridentitäten – rein lesender Prüfbericht")
        self.stdout.write(report["policy"])
        self.stdout.write(json.dumps(report["summary"], ensure_ascii=False, sort_keys=True))
        for index, finding in enumerate(report["findings"], 1):
            self.stdout.write(f"\nBefund {index}")
            self.stdout.write(json.dumps(finding, ensure_ascii=False, indent=2))
