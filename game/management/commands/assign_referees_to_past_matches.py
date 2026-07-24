"""
Management-Command: assign_referees_to_past_matches

Weist allen SimulatedMatch-Zeilen ohne Referee einen zufälligen Schiedsrichter zu.
Idempotent: Zeilen mit bereits gesetztem Referee werden nicht überschrieben.

Optionen:
  --dry-run   Nur anzeigen, wie viele Spiele aktualisiert würden, ohne zu schreiben.
"""

from django.core.management.base import BaseCommand
from game.models import SimulatedMatch, Referee


class Command(BaseCommand):
    help = "Weist Spielen ohne Referee rückwirkend einen zufälligen zu (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **opts):
        if not Referee.objects.exists():
            self.stdout.write("Keine Referees in der DB — nichts zu tun.")
            return
        qs = SimulatedMatch.objects.filter(referee__isnull=True)
        total = qs.count()
        if opts['dry_run']:
            self.stdout.write(f"[Dry-Run] {total} Spiele ohne Referee.")
            return
        updated = 0
        for match in qs.iterator():
            match.referee = Referee.objects.order_by('?').first()
            match.save(update_fields=['referee'])
            updated += 1
        self.stdout.write(self.style.SUCCESS(f"{updated} Spiele aktualisiert."))
