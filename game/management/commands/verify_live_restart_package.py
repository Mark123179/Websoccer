import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from game.club_import.restart_export import HandoffError, read_package
from game.club_import.restart_verify import replay


class Command(BaseCommand):
    help = "Übernahmepaket ausschließlich in leerer isolierter SQLite-Prüfdatei nachweisen."

    def add_arguments(self, parser):
        parser.add_argument("package")
        parser.add_argument("--report", required=True)

    def handle(self, *args, **options):
        try:
            package = read_package(options["package"])
            report = replay(package)
        except HandoffError as exc:
            raise CommandError(str(exc)) from exc
        path = Path(options["report"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        self.stdout.write(json.dumps({
            "report": str(path), "all_tables_identical": report["all_tables_identical"],
            "schema_identical": report["schema_identical"], "acceptance": report["acceptance"],
            "blockers": report["blockers"], "full_restart_ready": False,
        }, ensure_ascii=False, indent=2))
