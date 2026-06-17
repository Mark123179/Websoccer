"""Import einer „import_ready"-CSV (Verein + Spieler) — dünner CLI-Wrapper.

Die gesamte Logik liegt in :mod:`game.club_import.club_csv_import`. Dieser
Command ist nur die Kommandozeilen-Hülle mit zwei Modi:

* ``--mode full``   (Standard) — Vollanlage: Stammdaten-Reconcile + voller Import.
* ``--mode update`` — Aktualisierung: nur volatile Echtweltdaten, keine neuen
  Spieler, keine Stammdaten-/Stadionänderungen.

Spielstand/Ökonomie wird in keinem Modus angefasst.

Beispiele:
    python manage.py import_club_ready_csv --csv pfad/zur.csv
    python manage.py import_club_ready_csv --csv pfad/zur.csv --mode update
    python manage.py import_club_ready_csv --csv pfad/zur.csv --dry-run --strict
"""

from django.core.management.base import BaseCommand, CommandError

from game.club_import import validation
from game.club_import.club_csv_import import (
    MODE_FULL, MODE_UPDATE, ClubImportError, import_club_csv,
)


class Command(BaseCommand):
    help = (
        'Importiert eine import_ready-CSV (Vereinsprofil + Spieler) '
        'nicht-destruktiv. Modi: full (Vollanlage) / update (Aktualisierung).'
    )

    def add_arguments(self, parser):
        parser.add_argument('--csv', required=True, help='Pfad zur CSV-Datei.')
        parser.add_argument(
            '--mode', choices=[MODE_FULL, MODE_UPDATE], default=MODE_FULL,
            help='full = Vollanlage (Standard), update = nur volatile Daten.',
        )
        parser.add_argument(
            '--tm-club-id', type=int, default=None,
            help='Überschreibt die in der CSV genannte Transfermarkt-Vereins-ID.',
        )
        parser.add_argument(
            '--club-name', default=None,
            help='Alternative Vereinsauflösung per Name (statt TM-ID).',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Nur analysieren und Plan/Validierung ausgeben — nichts schreiben.',
        )
        parser.add_argument(
            '--strict', action='store_true',
            help='Warnungen als Exit-Code 2 melden (sonst 0).',
        )
        parser.add_argument(
            '--no-recalculate', action='store_true',
            help='Stärkeprofile nach dem Import NICHT neu berechnen.',
        )

    def handle(self, *args, **options):
        try:
            with open(options['csv'], encoding='utf-8-sig') as fh:
                text = fh.read()
        except OSError as exc:
            raise CommandError(f'CSV konnte nicht gelesen werden: {exc}')

        try:
            result = import_club_csv(
                text,
                mode=options['mode'],
                tm_override=options['tm_club_id'],
                name_override=options['club_name'],
                recalculate=not options['no_recalculate'],
                dry_run=options['dry_run'],
                strict=options['strict'],
            )
        except (ClubImportError, ValueError) as exc:
            raise CommandError(str(exc))

        club = result['club']
        self.stdout.write(
            f'Zielverein: {club.name} (#{club.id}, TM {club.transfermarkt_id}) '
            f'— Modus {result["mode"]}'
        )

        for warning in result['parse_warnings']:
            self.stdout.write(self.style.WARNING(f'  ⚠ {warning}'))
        for note in result['reconcile_notes']:
            self.stdout.write(f'  Stammdaten: {note}')
        for warning in result['reconcile_warnings']:
            self.stdout.write(self.style.WARNING(f'  ⚠ {warning}'))

        self._print_validation(result['validation_issues'])

        if result['stats'] is None:  # dry-run
            self.stdout.write(
                f"{len(result['players'])} Spielerzeilen gelesen (DRY-RUN)."
            )
            self.stdout.write(self.style.NOTICE('DRY-RUN — nichts geschrieben.'))
        else:
            for name in result['skipped_players']:
                self.stdout.write(self.style.WARNING(
                    f'  ⚠ {name}: fehlende/doppelte TM-ID — übersprungen.'
                ))
            stats = result['stats']
            self.stdout.write(self.style.SUCCESS(
                'Fertig: {created} neu, {updated} aktualisiert, '
                '{skipped} übersprungen, {failed} fehlgeschlagen.'.format(**stats)
            ))

        # Exit-Code spiegelt das Validierungsergebnis (0 ok / 1 Fehler /
        # 2 Warnungen unter --strict) — auch nach echtem Import, damit
        # CI/Skripte Datendefekte erkennen. Der Import selbst bleibt
        # nicht-blockierend: gute Daten werden geschrieben, Defekte gemeldet.
        if result['exit_code'] != validation.EXIT_OK:
            raise SystemExit(result['exit_code'])

    def _print_validation(self, issues):
        if not issues:
            return
        self.stdout.write('  Validierung:')
        for issue in issues:
            style = self.style.ERROR if issue['level'] == 'error' else self.style.WARNING
            ref = f" ({issue['ref']})" if issue['ref'] else ''
            self.stdout.write(style(
                f"    [{issue['level']}] {issue['message']}{ref}"
            ))
