"""Connect the approved FCB presentation without replacing manager data."""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from game.models import Stadium
from stadium_editor.model_registry import model_manifest
from stadium_editor.models import StadiumGeometry
from stadium_editor.scene_service import current_live_scene
from stadium_editor.seed import load_blueprints, normalise_block_types


class Command(BaseCommand):
    help = "Aktiviert die abgenommene Allianz-Darstellung; ergänzt ausschließlich fehlende Editor-Geometrie."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Fehlende Verknüpfung tatsächlich anlegen.")

    def handle(self, *args, **options):
        if model_manifest(915) is None:
            raise CommandError("Das registrierte Allianz-Arena-Modell fehlt.")
        try:
            stadium = Stadium.objects.select_related("club").get(club__fm_inside_id=915)
        except Stadium.DoesNotExist as error:
            raise CommandError("Das FCB-Stadion fehlt.") from error
        exists = StadiumGeometry.objects.filter(stadium=stadium).exists()
        if not options["apply"]:
            self.stdout.write(
                f"FCB-Stadion {stadium.pk}: "
                + ("vorhandene Editor-Geometrie bleibt erhalten." if exists
                   else "fehlende Editor-Verknüpfung wird mit --apply ergänzt.")
            )
            return
        with transaction.atomic():
            stadium = Stadium.objects.select_for_update().order_by("pk").get(pk=stadium.pk)
            row = StadiumGeometry.objects.filter(stadium=stadium).first()
            created = row is None
            if created:
                geometry = normalise_block_types(stadium, load_blueprints()["fcbayernmnchen"])
                row = StadiumGeometry.objects.create(
                    stadium=stadium, geometry=geometry, schema_version=2,
                    source="OpenStreetMap/BLUEPRINT-Bundle",
                    attribution="Blaupause: OpenStreetMap-Daten (ODbL)",
                )
            # Validate the entire live contract before committing the new link.
            scene = current_live_scene(stadium)
            if scene["presentation"]["clubFmiId"] != 915:
                raise CommandError("Die Live-Szene gehört nicht zum FCB.")
        self.stdout.write(self.style.SUCCESS(
            "FCB-Darstellung aktiv; "
            + ("fehlende Editor-Geometrie ergänzt." if created else "vorhandene Geometrie unverändert.")
        ))
