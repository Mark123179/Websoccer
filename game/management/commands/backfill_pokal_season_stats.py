from django.core.management.base import BaseCommand

from game.models import SimulatedMatch
from game.season_service import write_simulated_match_stats


class Command(BaseCommand):
    help = (
        'Berechnet PlayerFormSnapshot- und PlayerSeasonStat-Einträge für alle '
        'SimulatedMatches (Pokal/Freundschaft) nach, die noch keine Snapshots '
        'erzeugt haben. Idempotent: Mehrfachaufruf erzeugt keine Duplikate.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Zeigt an, was verarbeitet würde, ohne zu speichern.',
        )
        parser.add_argument(
            '--match-type',
            choices=['pokal', 'freundschaft', 'all'],
            default='all',
            help='Welcher Match-Typ verarbeitet werden soll (Standard: all).',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=200,
            help='Anzahl Einträge pro Datenbankabfrage (Standard: 200).',
        )

    def handle(self, *args, **options):
        dry_run    = options['dry_run']
        match_type = options['match_type']
        batch_size = options['batch_size']

        qs = SimulatedMatch.objects.order_by('id')
        if match_type != 'all':
            qs = qs.filter(match_type=match_type)

        total_all = qs.count()

        if dry_run:
            self.stdout.write(
                self.style.WARNING('Dry-run — keine Änderungen werden gespeichert.')
            )

        processed = 0
        skipped   = 0
        errors    = 0

        offset = 0
        while True:
            batch = list(
                qs.select_related('home_club', 'away_club')[offset: offset + batch_size]
            )
            if not batch:
                break
            offset += batch_size

            for match in batch:
                data = match.report_data or {}

                if not data.get('home_players') and not data.get('away_players'):
                    skipped += 1
                    continue

                if dry_run:
                    home_n = len(data.get('home_players') or [])
                    away_n = len(data.get('away_players') or [])
                    self.stdout.write(
                        f'  [dry] #{match.pk} {match.match_type} '
                        f'{match.home_club.short_name or match.home_club.name} vs '
                        f'{match.away_club.short_name or match.away_club.name}'
                        f' → {home_n} Heim- / {away_n} Auswärtsspieler'
                    )
                    processed += 1
                    continue

                try:
                    write_simulated_match_stats(match, data)
                    processed += 1
                except Exception as exc:
                    self.stderr.write(
                        f'  [FEHLER] SimulatedMatch #{match.pk}: {exc}'
                    )
                    errors += 1

            done = min(offset, total_all)
            self.stdout.write(f'  Verarbeitet: {done}/{total_all} …')

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f'Dry-run abgeschlossen: {processed} würden verarbeitet, '
                    f'{skipped} ohne Spielerdaten übersprungen, {errors} Fehler.'
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Fertig: {processed} Spiele verarbeitet, '
                    f'{skipped} ohne Spielerdaten übersprungen, {errors} Fehler.'
                )
            )
