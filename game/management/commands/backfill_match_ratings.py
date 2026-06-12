from django.core.management.base import BaseCommand

from game.match_engine import compute_player_ratings
from game.models import SimulatedMatch


class Command(BaseCommand):
    help = (
        'Berechnet Spielernoten für alle SimulatedMatch-Einträge, '
        'bei denen report_data noch kein home_ratings-Feld enthält, '
        'und speichert das Ergebnis dauerhaft in report_data zurück.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Zeigt an, was berechnet würde, ohne zu speichern.',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=200,
            help='Anzahl Einträge pro Datenbankabfrage (Standard: 200).',
        )

    def handle(self, *args, **options):
        dry_run   = options['dry_run']
        batch_size = options['batch_size']

        qs = SimulatedMatch.objects.all().order_by('id')
        total_all = qs.count()

        if dry_run:
            self.stdout.write(
                self.style.WARNING('Dry-run — keine Änderungen werden gespeichert.')
            )

        updated  = 0
        skipped  = 0
        errors   = 0

        offset = 0
        while True:
            batch = list(qs[offset: offset + batch_size])
            if not batch:
                break
            offset += batch_size

            for match in batch:
                data = match.report_data or {}

                if data.get('home_ratings'):
                    skipped += 1
                    continue

                try:
                    ratings = compute_player_ratings(data)
                except Exception as exc:
                    self.stderr.write(
                        f'  [FEHLER] SimulatedMatch #{match.pk}: {exc}'
                    )
                    errors += 1
                    continue

                if dry_run:
                    h = len(ratings.get('home_ratings') or [])
                    a = len(ratings.get('away_ratings') or [])
                    self.stdout.write(
                        f'  [dry] #{match.pk} '
                        f'{match.home_club.short_name} vs {match.away_club.short_name}'
                        f' → {h} Heim- / {a} Auswärtsnoten'
                    )
                else:
                    data.update(ratings)
                    match.report_data = data
                    match.save(update_fields=['report_data'])

                updated += 1

            done = min(offset, total_all)
            self.stdout.write(f'  Verarbeitet: {done}/{total_all} …')

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f'Dry-run abgeschlossen: {updated} würden aktualisiert, '
                    f'{skipped} bereits vorhanden, {errors} Fehler.'
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Fertig: {updated} Einträge aktualisiert, '
                    f'{skipped} bereits vorhanden, {errors} Fehler.'
                )
            )
