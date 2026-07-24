"""
Management-Command: assign_referees_to_past_matches

Weist allen SimulatedMatch-Zeilen ohne Referee einen zufälligen Schiedsrichter zu.
Idempotent: Zeilen mit bereits gesetztem Referee werden nicht überschrieben.

Optionen:
  --dry-run   Nur anzeigen, wie viele Spiele aktualisiert würden, ohne zu schreiben.
  --limit N   Maximal N Spiele aktualisieren (Standard: unbegrenzt).
"""

import random
from django.core.management.base import BaseCommand
from game.models import SimulatedMatch, Referee


class Command(BaseCommand):
    help = 'Weist Spielen ohne Schiedsrichter einen zufälligen Referee zu (Backfill).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            default=False,
            help='Nur anzeigen, ohne zu schreiben.',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=None,
            help='Maximal N Spiele aktualisieren.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        limit   = options['limit']

        referee_pks = list(Referee.objects.values_list('pk', flat=True))
        if not referee_pks:
            self.stdout.write(self.style.WARNING(
                'Keine Schiedsrichter in der Datenbank — nichts zu tun.'
            ))
            return

        qs = SimulatedMatch.objects.filter(referee__isnull=True).order_by('pk')
        total = qs.count()

        if total == 0:
            self.stdout.write(self.style.SUCCESS(
                'Alle Spiele haben bereits einen Schiedsrichter — nichts zu tun.'
            ))
            return

        if limit:
            qs = qs[:limit]

        if dry_run:
            count = qs.count() if limit else total
            self.stdout.write(
                f'[dry-run] Würde {count} von {total} Spielen einen Schiedsrichter zuweisen.'
            )
            return

        updated = 0
        for sm in qs.iterator(chunk_size=500):
            sm.referee_id = random.choice(referee_pks)
            sm.save(update_fields=['referee'])
            updated += 1

        self.stdout.write(self.style.SUCCESS(
            f'{updated} Spiel(e) mit Schiedsrichter belegt '
            f'({total - updated} bereits gesetzt oder außerhalb Limit).'
        ))
