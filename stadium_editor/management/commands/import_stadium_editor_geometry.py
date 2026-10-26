from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from game.models import Stadium
from stadium_editor.models import StadiumGeometry
from stadium_editor.seed import _key, load_blueprints, normalise_block_types


class Command(BaseCommand):
    help = 'Importiert OSM-Stadiongeometrien aus dem BLUEPRINT stadium_data_all.js-Paket.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--source',
            help='Optionaler Pfad zu stadium_data_all.js; ohne Angabe wird das mitgelieferte Bundle genutzt.',
        )
        parser.add_argument('--stadium', type=int, help='Nur diese Stadium-ID importieren')
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument(
            '--missing-only', action='store_true',
            help='Nur fehlende Verknüpfungen ergänzen; bestehende Geometrien und Entwürfe unverändert lassen.',
        )

    def handle(self, *args, **options):
        try:
            source = Path(options['source']) if options['source'] else None
            if source and not source.is_file():
                raise CommandError(f'Quelldatei nicht gefunden: {source}')
            by_club = load_blueprints(source) if source else load_blueprints()
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        stadiums = Stadium.objects.select_related('club').order_by('pk')
        if options['stadium']:
            stadiums = stadiums.filter(pk=options['stadium'])
        imported = skipped = unchanged = 0
        for stadium in stadiums:
            if options.get('missing_only') and StadiumGeometry.objects.filter(stadium=stadium).exists():
                unchanged += 1
                self.stdout.write(f'Unverändert: {stadium.name} (Blaupause bereits vorhanden)')
                continue
            blueprint = by_club.get(_key(stadium.club.name))
            if not blueprint:
                skipped += 1
                self.stdout.write(self.style.WARNING(f'Übersprungen: {stadium.name} ({stadium.club.name})'))
                continue
            geometry = normalise_block_types(stadium, blueprint)
            if not options['dry_run']:
                with transaction.atomic():
                    defaults = {
                        'geometry': geometry,
                        'schema_version': 2,
                        'source': 'OpenStreetMap/BLUEPRINT-Import',
                        'attribution': 'Blaupause: OpenStreetMap-Daten (ODbL)',
                    }
                    if options.get('missing_only'):
                        # Serialize against concurrent editor/activation operations.
                        Stadium.objects.select_for_update().order_by('pk').get(pk=stadium.pk)
                        _, created = StadiumGeometry.objects.get_or_create(
                            stadium=stadium, defaults=defaults,
                        )
                        if created:
                            from stadium_editor.scene_service import current_live_scene
                            current_live_scene(stadium)
                    else:
                        StadiumGeometry.objects.update_or_create(
                            stadium=stadium, defaults=defaults,
                        )
            imported += 1
            self.stdout.write(f'{"Geprüft" if options["dry_run"] else "Importiert"}: {stadium.name}')
        self.stdout.write(self.style.SUCCESS(
            f'Fertig: {imported} {"geprüft" if options["dry_run"] else "importiert"}, '
            f'{unchanged} unverändert, {skipped} ohne passende Blaupause.'
        ))