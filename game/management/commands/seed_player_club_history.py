"""Genesis-Seed für die Vereinsstationen-Historie (Phase 0 Finanzsystem).

Erfasst für alle Spieler mit Verein eine Station der aktuellen (oder per
--season angegebenen) Saison. Idempotent — bestehende Zeilen bleiben
unverändert. Vereinslose Spieler und der Pseudo-Verein „Karrierende"
werden übersprungen.
"""

from django.core.management.base import BaseCommand

from game.club_history import get_current_season, snapshot_season
from game.models import PlayerClubHistory


class Command(BaseCommand):
    help = (
        'Genesis-Seed: erfasst alle Spieler mit Verein als Vereinsstation '
        'der aktuellen Saison (idempotent).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--season',
            type=int,
            default=None,
            help='Saisonnummer (Standard: aktuelle Saison aus GameSeasonState).',
        )

    def handle(self, *args, **options):
        season = options['season']
        if season is None:
            season = get_current_season()

        created = snapshot_season(season)
        total = PlayerClubHistory.objects.filter(season=season).count()
        self.stdout.write(self.style.SUCCESS(
            f'Saison {season}: {created} neue Vereinsstationen angelegt '
            f'({total} insgesamt für diese Saison).'
        ))
