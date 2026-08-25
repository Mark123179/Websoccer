from django.core.management.base import BaseCommand, CommandError

from game.models import Club
from game.records.engine import rebuild_for_club


class Command(BaseCommand):
    help = 'Berechnet die SIM-Rekorde der Ruhmeshalle für einen oder alle Vereine.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--club',
            type=int,
            default=None,
            help='Primärschlüssel eines Vereins; ohne Angabe werden alle Vereine berechnet.',
        )

    def handle(self, *args, **options):
        clubs = Club.objects.order_by('pk')
        if options['club'] is not None:
            clubs = clubs.filter(pk=options['club'])
            if not clubs.exists():
                raise CommandError(f'Verein {options["club"]} nicht gefunden.')
        totals = {'created': 0, 'changed': 0, 'unchanged': 0, 'empty': 0}
        count = 0
        for club in clubs:
            result = rebuild_for_club(club)
            count += 1
            for key, value in result.items():
                totals[key] += value
        self.stdout.write(
            self.style.SUCCESS(
                f'{count} Verein(e) verarbeitet: '
                + ', '.join(f'{key}={value}' for key, value in totals.items())
            )
        )