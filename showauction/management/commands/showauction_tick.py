"""Beat-Tick der Show-Auktion (E26): startet geplante, wickelt fällige ab.

Läuft jede Minute über Celery Beat (game.tasks.run_management_command)
und ist idempotent — der Lazy-Pfad in den Views ruft dieselbe Logik auf.
"""
from django.core.management.base import BaseCommand

from showauction.service import resolve_due


class Command(BaseCommand):
    help = 'Show-Auktionen: geplante starten, fällige zuschlagen/platzen lassen.'

    def handle(self, *args, **options):
        stats = resolve_due()
        self.stdout.write(
            'Show-Auktion-Tick: '
            f"{stats['gestartet']} gestartet, "
            f"{stats['zugeschlagen']} zugeschlagen, "
            f"{stats['geplatzt']} geplatzt, "
            f"{stats['endspurt']} Endspurt-Meldungen, "
            f"{stats['fehler']} Fehler."
        )
        if stats['fehler']:
            self.stderr.write('Achtung: Einzelne Auktionen konnten nicht abgewickelt werden (siehe Log).')
