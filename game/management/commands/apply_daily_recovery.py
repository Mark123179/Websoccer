"""Management Command: apply_daily_recovery

Täglicher Tick: Frische-Regeneration + Verletzungs-Countdown.

Verwendung:
    python manage.py apply_daily_recovery
    python manage.py apply_daily_recovery --dry-run

Im normalen Spielbetrieb einmal täglich aufrufen (z.B. als Cron / Spieltags-Zyklus).
"""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        'Täglicher Tick: Frische-Regeneration für alle nicht-verletzten Spieler '
        'und Verletzungs-Countdown (V1-Modell).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            default=False,
            help='Nur anzeigen, wie viele Spieler betroffen wären — nichts speichern.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        if dry_run:
            from decimal import Decimal
            from game.models import Player, PlayerStrengthProfile

            recovery_count = (
                PlayerStrengthProfile.objects
                .filter(player__ws_injury_days_remaining__lte=0)
                .exclude(freshness__gte=Decimal('100.00'))
                .count()
            )
            injured_count = Player.objects.filter(ws_injury_days_remaining__gt=0).count()
            healed_count = Player.objects.filter(ws_injury_days_remaining=1).count()

            self.stdout.write(
                f'[DRY-RUN] {recovery_count} Spieler würden regeneriert werden.'
            )
            self.stdout.write(
                f'[DRY-RUN] {injured_count} verletzte Spieler — '
                f'davon {healed_count} würden heute genesen.'
            )
            return

        from game.freshness_service import apply_daily_recovery, apply_injury_countdown

        recovery_count = apply_daily_recovery()
        self.stdout.write(
            self.style.SUCCESS(f'✓ {recovery_count} Spieler-Profile regeneriert.')
        )

        decremented, healed = apply_injury_countdown()
        if decremented:
            self.stdout.write(
                self.style.SUCCESS(
                    f'✓ Verletzungs-Countdown: {decremented} Spieler dekrementiert, '
                    f'{healed} genesen.'
                )
            )
        else:
            self.stdout.write('  Keine verletzten Spieler — kein Countdown nötig.')
