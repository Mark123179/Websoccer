"""Saisonende-Finanzjob manuell anstoßen (Spec Kap. 15).

TV-Saisonausschüttung, Pokalprämien-Backstop, Zieljäger-Boni,
Koeffizienten-Fortschreibung. Idempotent; Teil-Läufe erlaubt, solange
noch nicht alle Ligen durchgespielt sind.
"""
import json

from django.core.management.base import BaseCommand

from game.economy.params import current_season
from game.economy.season_jobs import finance_season_close


class Command(BaseCommand):
    help = 'Finanz-Saisonabschluss: TV-Ausschüttung, Prämien, Koeffizienten (idempotent).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--saison', default=None,
            help='Saison-String (Default: aktuelle Sim-Saison).',
        )

    def handle(self, *args, **options):
        saison = options['saison'] or current_season()
        report = finance_season_close(saison)

        if report.get('skipped'):
            self.stdout.write(self.style.WARNING(
                f'Saison {saison} ist bereits abgeschlossen — nichts zu tun.'))
            return

        self.stdout.write(json.dumps(report, indent=2, ensure_ascii=False, default=str))
        if report.get('hinweis'):
            self.stdout.write(self.style.WARNING(report['hinweis']))
        elif report['errors']:
            self.stdout.write(self.style.ERROR(
                f"Abgeschlossen mit {len(report['errors'])} Fehler(n)."))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'Finanz-Saisonabschluss {saison} abgeschlossen.'))
