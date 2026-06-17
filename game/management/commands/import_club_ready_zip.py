"""Import eines WS_CLUB_IMPORT_V2-ZIPs (Verein + Spieler) — dünner CLI-Wrapper.

Liest die Master-CSV aus dem ZIP via :mod:`game.club_import.zip_import` und
reicht sie an :func:`game.club_import.club_csv_import.import_club_csv` weiter.
Gleiche Flags wie ``import_club_ready_csv``, plus ``--zip``.

Beispiele:
    python manage.py import_club_ready_zip --zip attached_assets/HSV.zip
    python manage.py import_club_ready_zip --zip HSV.zip --mode update
    python manage.py import_club_ready_zip --zip HSV.zip --dry-run --strict
"""

from django.core.management.base import BaseCommand, CommandError

from game.club_import import validation
from game.club_import.club_csv_import import (
    MODE_FULL, MODE_UPDATE, ClubImportError, import_club_csv,
)
from game.club_import.zip_import import read_zip


class Command(BaseCommand):
    help = (
        'Importiert ein WS_CLUB_IMPORT_V2-ZIP (Vereinsprofil + Spieler) '
        'nicht-destruktiv. Modi: full (Vollanlage) / update (Aktualisierung).'
    )

    def add_arguments(self, parser):
        parser.add_argument('--zip', required=True, help='Pfad zur ZIP-Datei.')
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
        zip_path = options['zip']

        try:
            csv_text, manifest = read_zip(zip_path)
        except (ClubImportError, OSError) as exc:
            raise CommandError(f'ZIP konnte nicht gelesen werden: {exc}')

        self.stdout.write(
            f'ZIP-Paket: {manifest.package_name or zip_path} — '
            f'{manifest.club}, Saison {manifest.season}, '
            f'{manifest.player_count} Spieler, import_ready={manifest.import_ready}'
        )

        try:
            result = import_club_csv(
                csv_text,
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

        if result['stats'] is None:
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
