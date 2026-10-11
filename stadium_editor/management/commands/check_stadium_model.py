"""Validate registry and authoritative assets without writing anything."""
import json

from django.core.management.base import BaseCommand, CommandError

from stadium_editor.model_assets import verified_model_asset
from stadium_editor.model_registry import manifest_path, validate_model_manifest


class Command(BaseCommand):
    help = "Prüft ein Stadionmodell-Manifest und optional sämtliche Asset-Prüfsummen (nur lesend)."

    def add_arguments(self, parser):
        parser.add_argument("--fmi", type=int, required=True)
        parser.add_argument("--assets", action="store_true")

    def handle(self, *args, **options):
        fmi = options["fmi"]
        try:
            manifest = json.loads(manifest_path(fmi).read_text(encoding="utf-8"))
            validate_model_manifest(manifest)
            if manifest["clubFmiId"] != fmi:
                raise ValueError("clubFmiId passt nicht zum Dateinamen")
        except (OSError, ValueError) as error:
            raise CommandError(f"Manifest ungültig: {error}") from error
        self.stdout.write(f"Manifest OK: {fmi} · {manifest['stadiumName']} · {manifest['assetVersion']}")
        if options["assets"]:
            for name in ("geometry.bin", *manifest["textures"]):
                try:
                    _, source = verified_model_asset(manifest, name, cache=False)
                except Exception as error:
                    # Provider errors may contain signed URLs; never print their contents.
                    raise CommandError(f"Asset ungültig oder nicht verfügbar: {name} ({type(error).__name__})") from None
                self.stdout.write(f"SHA-256 OK: {name} · {source}")
            self.stdout.write(f"Assets OK: {1 + len(manifest['textures'])} Dateien; keine Schreibzugriffe.")
