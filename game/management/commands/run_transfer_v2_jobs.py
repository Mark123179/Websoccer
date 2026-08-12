"""Führt die Transfersystem-v2-Hintergrundjobs aus (Master-Spec §4.5).

Einzeln oder gebündelt (Default: alle). Idempotent — mehrfacher Aufruf
schadet nicht. Für Celery-Beat vorgesehen; manuell:

    python manage.py run_transfer_v2_jobs
    python manage.py run_transfer_v2_jobs --only listings
"""
from django.core.management.base import BaseCommand

from game.transfer_v2 import jobs

JOBS = {
    'listings': lambda saison: jobs.close_due_listings(saison=saison),
    'deals': lambda saison: jobs.expire_due_deals(),
    'loans': lambda saison: jobs.end_due_loans(saison=saison),
    'pendings': lambda saison: jobs.execute_due_pendings(saison=saison),
    'locks': lambda saison: jobs.cleanup_expired_locks(),
    'barometer': lambda saison: jobs.update_position_barometer(),
}


class Command(BaseCommand):
    help = 'Transfersystem v2: fällige Auktionen, Anfragen, Leihen, Pendings, Locks, Barometer.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--only', choices=sorted(JOBS), default=None,
            help='Nur einen bestimmten Job ausführen.',
        )
        parser.add_argument('--saison', default=None, help='Sim-Saison (Default: aktuelle).')

    def handle(self, *args, **options):
        only = options['only']
        saison = options['saison']
        auswahl = {only: JOBS[only]} if only else JOBS
        for name, fn in auswahl.items():
            result = fn(saison)
            self.stdout.write(f'{name}: {result}')
