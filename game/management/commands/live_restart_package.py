"""Export current imported state without a write/import/reset option."""
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from game.club_import.restart_export import HandoffError, build_package, write_package


class Command(BaseCommand):
    help = "Aktuellen Importbestand rein lesend als Übernahmepaket sichern (kein Live-Import)."

    def add_arguments(self, parser):
        parser.add_argument("--output", required=True)

    def handle(self, *args, **options):
        try:
            package = build_package()
            checksum = write_package(Path(options["output"]), package)
        except (HandoffError, FileExistsError) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(json.dumps({
            "output": options["output"], "sha256": checksum,
            "inventory": package["inventory"]["summary"],
            "parity": package["parity"], "blockers": package["blockers"],
            "full_restart_ready": False,
        }, ensure_ascii=False, indent=2))
