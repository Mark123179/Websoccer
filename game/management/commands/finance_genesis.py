"""Genesis-Lauf (Spec Kap. 13): Startbudgets für alle Bestandsvereine.

Ersetzt die Alt-Kontostände aller Ligavereine durch das formelbasierte
Startbudget (KORREKTUR_ADMIN-Differenzbuchung als erster Ledger-Eintrag).
Idempotent je Verein — bereits behandelte Vereine werden übersprungen.
"""
from django.core.management.base import BaseCommand

from game.economy.params import current_season
from game.economy.startbudget import apply_genesis


class Command(BaseCommand):
    help = 'Genesis: Startbudgets aller Ligavereine setzen (idempotent je Verein).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--saison', default=None,
            help='Saison-String (Default: aktuelle Sim-Saison).',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Nur berechnen und anzeigen, nichts buchen.',
        )

    def handle(self, *args, **options):
        saison = options['saison'] or current_season()
        report = apply_genesis(saison, dry_run=options['dry_run'])

        if options['dry_run']:
            self.stdout.write(self.style.WARNING('DRY-RUN — keine Buchungen.'))

        for eintrag in report['clubs']:
            self.stdout.write(
                f"  {eintrag['club']}: {eintrag['vorher']} € → "
                f"{eintrag['startbudget']} € (Korrektur {eintrag['korrektur']} €)"
            )
        if report['skipped']:
            self.stdout.write(self.style.WARNING(
                f"Übersprungen (Genesis bereits gelaufen): {len(report['skipped'])}"))
        for err in report['errors']:
            self.stdout.write(self.style.ERROR(f'  Fehler: {err}'))
        self.stdout.write(self.style.SUCCESS(
            f"Genesis {saison}: {len(report['clubs'])} Vereine verarbeitet."))
