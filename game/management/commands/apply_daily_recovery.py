"""Management Command: apply_daily_recovery

Tägliche Frische-Regeneration für alle nicht-verletzten Spieler.

Verwendung:
    python manage.py apply_daily_recovery
    python manage.py apply_daily_recovery --dry-run

Im normalen Spielbetrieb einmal täglich aufrufen (z.B. als Cron / Spieltags-Zyklus).
"""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Tägliche Frische-Regeneration für alle nicht-verletzten Spieler (V1-Modell).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            default=False,
            help='Nur anzeigen, wie viele Spieler regeneriert würden — nichts speichern.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        if dry_run:
            from game.models import PlayerStrengthProfile
            from decimal import Decimal
            count = (
                PlayerStrengthProfile.objects
                .filter(player__ws_injury_days_remaining__lte=0)
                .exclude(freshness__gte=Decimal('100.00'))
                .count()
            )
            self.stdout.write(
                f'[DRY-RUN] {count} Spieler würden regeneriert werden.'
            )
            return

        from game.freshness_service import apply_daily_recovery
        count = apply_daily_recovery()
        self.stdout.write(
            self.style.SUCCESS(f'✓ {count} Spieler-Profile regeneriert.')
        )
