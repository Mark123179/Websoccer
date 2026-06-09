"""SoFIFA-CSV-Importer (CLI).

Duenner Wrapper um ``game.sofifa_import``; die eigentliche Importlogik (Header-
Mapping, Matching, Schreiben, Change-/Import-Log, Neuberechnung) liegt im
gemeinsam mit dem Creator-Upload genutzten Service-Modul.

Pflichtspalten: ``sofifa_id`` (Alias ``player_id``) und ``overall``/``rating``.
Akzeptiert das volle SoFIFA-Export-Format ebenso wie vereinfachte Spaltennamen.
Nach einem echten (nicht ``--dry-run``) Lauf werden die Spielstaerken neu
berechnet, sofern es Aenderungen gab.
"""

import os

from django.core.management.base import BaseCommand, CommandError

from game import sofifa_import


class Command(BaseCommand):
    help = 'Importiert EA/SoFIFA-Ratings aus einer CSV (Matching ueber sofifa_id).'

    def add_arguments(self, parser):
        parser.add_argument('csv_path', help='Pfad zur SoFIFA-CSV-Datei.')
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Zeigt geplante Aenderungen, ohne in die DB zu schreiben.',
        )
        parser.add_argument(
            '--skip-recalculate', action='store_true',
            help='Spielstaerken nach dem Import NICHT neu berechnen.',
        )
        parser.add_argument(
            '--import-version', dest='import_version', default='',
            help='Versionskennung (sonst aus fifa_version/fifa_update_date abgeleitet).',
        )
        parser.add_argument(
            '--delimiter', default=',',
            help='CSV-Trennzeichen (Standard: Komma).',
        )
        parser.add_argument(
            '--encoding', default='utf-8-sig',
            help='Datei-Encoding (Standard: utf-8-sig).',
        )

    def handle(self, *args, **options):
        csv_path = options['csv_path']
        dry_run = options['dry_run']

        if dry_run:
            self.stdout.write(self.style.WARNING(
                '── DRY-RUN: es werden KEINE Aenderungen geschrieben ──'
            ))

        try:
            result = sofifa_import.run_import(
                csv_path,
                version=options['import_version'],
                file_name=os.path.basename(csv_path),
                dry_run=dry_run,
                recalculate=not options['skip_recalculate'],
                delimiter=options['delimiter'],
                encoding=options['encoding'],
            )
        except sofifa_import.ImportError_ as exc:
            raise CommandError(str(exc))

        if result['version']:
            self.stdout.write(f"Version: {result['version']}")

        for row in result['rows']:
            if row['action'] == 'error':
                self.stdout.write(self.style.ERROR(
                    f"  Zeile {row['line']}: {row['diff'][0] if row['diff'] else 'Fehler'}"
                ))
                continue
            if row['action'] == 'unmatched':
                continue
            mark = {'new': '＋', 'updated': '✎', 'unchanged': '·'}[row['action']]
            mode_note = '' if row['mode'] == 'id' else f" [{row['mode']}]"
            detail = ('; '.join(row['diff'])) if row['diff'] else 'keine Aenderung'
            self.stdout.write(
                f"  {mark} {row['name']} ({row['club']}){mode_note}: {detail}"
            )

        stats = result['stats']
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f"Bilanz: {stats['new']} neu, {stats['updated']} aktualisiert, "
            f"{stats['unchanged']} unveraendert, {stats['unmatched']} nicht "
            f"gematcht, {stats['error']} Fehler."
        ))
        if result['unmatched']:
            self.stdout.write(self.style.WARNING('Nicht gematcht:'))
            for entry in result['unmatched']:
                self.stdout.write(self.style.WARNING(f'  - {entry}'))

        if dry_run:
            self.stdout.write(self.style.WARNING(
                'DRY-RUN beendet — nichts geschrieben.'
            ))
            return

        if result['recalculated']:
            self.stdout.write(self.style.SUCCESS('Spielstaerken neu berechnet.'))
        elif stats['new'] + stats['updated'] == 0:
            self.stdout.write('Keine Aenderungen — Neuberechnung uebersprungen.')
