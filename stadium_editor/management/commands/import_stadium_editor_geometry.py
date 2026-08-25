from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

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
        imported = skipped = 0
        for stadium in stadiums:
            blueprint = by_club.get(_key(stadium.club.name))
            if not blueprint:
                skipped += 1
                self.stdout.write(self.style.WARNING(f'Übersprungen: {stadium.name} ({stadium.club.name})'))
                continue
            geometry = normalise_block_types(stadium, blueprint)
            if not options['dry_run']:
                StadiumGeometry.objects.update_or_create(
                    stadium=stadium,
                    defaults={
                        'geometry': geometry,
                        'source': 'OpenStreetMap/BLUEPRINT-Import',
                        'attribution': 'Blaupause: OpenStreetMap-Daten (ODbL)',
                    },
                )
            imported += 1
            self.stdout.write(f'Importiert: {stadium.name}')
        self.stdout.write(self.style.SUCCESS(
            f'Fertig: {imported} importiert, {skipped} ohne passende Blaupause.'
        ))