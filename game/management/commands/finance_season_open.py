"""Saisonstart-Finanzjob manuell anstoßen (Spec Kap. 15).

Snapshot, TV-Töpfe und Sponsorangebote für die Saison anlegen.
Idempotent — ein zweiter Lauf ist ein No-op (SeasonFinanceState.opened_at).
"""
from django.core.management.base import BaseCommand

from game.economy.params import current_season
from game.economy.season_jobs import finance_season_open


class Command(BaseCommand):
    help = 'Finanz-Saisonstart: Snapshot, TV-Töpfe, Sponsorangebote (idempotent).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--saison', default=None,
            help='Saison-String (Default: aktuelle Sim-Saison).',
        )

    def handle(self, *args, **options):
        saison = options['saison'] or current_season()
        report = finance_season_open(saison)

        if report.get('skipped'):
            self.stdout.write(self.style.WARNING(
                f'Saison {saison} ist bereits geöffnet — nichts zu tun.'))
            return

        self.stdout.write(f"Gehalts-Anker: {report['gehalts_anker']}")
        self.stdout.write(f"TV-Töpfe: {report['tv_pots']}")
        self.stdout.write(f"Sponsorangebote erzeugt: {report['sponsor_offers']}")
        for err in report['errors']:
            self.stdout.write(self.style.ERROR(f'  Fehler: {err}'))
        self.stdout.write(self.style.SUCCESS(
            f'Finanz-Saisonstart {saison} abgeschlossen.'))
