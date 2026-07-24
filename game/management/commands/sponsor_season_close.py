"""Sponsor-Verträge zum Saisonende abschließen (sponsor_season_close).

Setzt alle aktiven SponsorContracts einer Saison auf abgelaufen=True
und bucht ausstehende variable Boni (SPEC §9).

Idempotent: Bereits abgelaufene Verträge werden übersprungen.

Läuft automatisch über Celery Beat / finance_season_close.
"""
import logging

from django.core.management.base import BaseCommand

from game.economy.params import current_season

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Sponsor-Verträge zum Saisonende schließen (abgelaufen=True setzen).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--saison', default=None,
            help='Saison-String (Default: aktuelle Sim-Saison)',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Nur anzeigen, was geschlossen würde',
        )

    def handle(self, *args, **options):
        from game.economy.sponsors import expire_contracts_v2
        from game.models import SponsorContract

        saison = options['saison'] or current_season()
        dry = options['dry_run']

        offen = SponsorContract.objects.filter(saison=saison, abgelaufen=False)
        count = offen.count()

        if dry:
            self.stdout.write(self.style.WARNING(
                f'DRY-RUN: {count} aktive Verträge in Saison {saison} '
                f'würden auf abgelaufen=True gesetzt.'
            ))
            return

        n = expire_contracts_v2(saison)
        self.stdout.write(self.style.SUCCESS(
            f'sponsor_season_close Saison {saison}: {n} Verträge abgelaufen gesetzt.'
        ))
        logger.info('sponsor_season_close: %d Verträge Saison %s abgelaufen', n, saison)
