from django.core.management.base import BaseCommand
from game.models import Player


class Command(BaseCommand):
    help = (
        'Setzt nt_nationality für alle Spieler mit genau einer Nationalität, '
        'sofern das Feld noch leer ist. Spieler mit mehreren Nationalitäten '
        'werden nicht angefasst.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Zeigt an, was geändert würde, ohne zu speichern.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        qs = (
            Player.objects
            .filter(nationalities__gt='', nt_nationality='')
            .exclude(nationalities__contains=',')
        )

        total = qs.count()
        self.stdout.write(f'{total} Spieler gefunden (einzelne Nationalität, nt_nationality leer).')

        if dry_run:
            self.stdout.write(self.style.WARNING('Dry-run — keine Änderungen werden gespeichert.'))

        updated = 0
        for player in qs.iterator():
            nation = player.nationalities.strip()
            if not nation:
                continue
            if dry_run:
                self.stdout.write(f'  [dry] {player.full_name}: nt_nationality = {nation!r}')
            else:
                player.nt_nationality = nation
                player.save(update_fields=['nt_nationality'])
            updated += 1

        if dry_run:
            self.stdout.write(self.style.WARNING(f'Dry-run abgeschlossen: {updated} würden gesetzt.'))
        else:
            self.stdout.write(self.style.SUCCESS(f'{updated} Spieler aktualisiert.'))
