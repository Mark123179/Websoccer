import json

from django.core.management.base import BaseCommand, CommandError

from game.club_import.identity_audit_diff import (
    AuditFormatError, compare_reports, load_report, render_text,
)


class Command(BaseCommand):
    help = "Vergleicht zwei gespeicherte Identitätsprüfungen lokal, ohne Bestandsabfragen."
    requires_migrations_checks = False
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument("before")
        parser.add_argument("after")
        parser.add_argument("--format", choices=("text", "json"), default="text")

    def handle(self, *args, **options):
        try:
            report = compare_reports(load_report(options["before"]), load_report(options["after"]))
        except AuditFormatError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(json.dumps(report, ensure_ascii=False, indent=2)
                          if options["format"] == "json" else render_text(report))
