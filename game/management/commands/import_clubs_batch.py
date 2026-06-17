"""Stapel-Import mehrerer import_ready-CSVs und/oder WS_CLUB_IMPORT_V2-ZIPs
aus einem Ordner.

Jede Datei wird isoliert in einer eigenen Transaktion verarbeitet: ein Fehler
(nicht auflösbarer Verein, kaputte CSV …) bricht den Stapel **nicht** ab, sondern
wird im Abschlussbericht protokolliert. Modi wie beim Einzelimport.

Mischbetrieb im selben Ordner: *.csv und *.zip werden gemeinsam gefunden und
jeweils über den passenden Reader verarbeitet.

Beispiele:
    python manage.py import_clubs_batch --dir attached_assets/imports
    python manage.py import_clubs_batch --dir imports --mode update
    python manage.py import_clubs_batch --dir imports --pattern *.zip
"""

import glob
import os

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from game.club_import.club_csv_import import (
    MODE_FULL, MODE_UPDATE, ClubImportError, import_club_csv,
)
from game.club_import import validation
from game.club_import.zip_import import read_zip


def _collect_paths(directory, pattern):
    """Sammelt Dateipfade passend zum Muster.

    Ist das Muster ``*.csv`` (Standard), werden *zusätzlich* alle ``*.zip``-
    Dateien im selben Ordner mitgenommen (Mischbetrieb). Bei einem anderen
    expliziten Muster werden nur die passenden Dateien geliefert.
    """
    matched = sorted(glob.glob(os.path.join(directory, pattern)))
    if pattern == '*.csv':
        zips = sorted(glob.glob(os.path.join(directory, '*.zip')))
        all_paths = sorted(set(matched) | set(zips))
    else:
        all_paths = matched
    return all_paths


class Command(BaseCommand):
    help = (
        'Importiert alle import_ready-CSVs und WS_CLUB_IMPORT_V2-ZIPs eines '
        'Ordners nicht-destruktiv. Fehler einzelner Dateien isolieren den Rest.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--dir', required=True, help='Ordner mit Dateien.')
        parser.add_argument(
            '--pattern', default='*.csv',
            help='Glob-Muster (Standard *.csv; *.zip ergänzt automatisch).',
        )
        parser.add_argument(
            '--mode', choices=[MODE_FULL, MODE_UPDATE], default=MODE_FULL,
            help='full = Vollanlage (Standard), update = nur volatile Daten.',
        )
        parser.add_argument('--dry-run', action='store_true', help='Nichts schreiben.')
        parser.add_argument('--strict', action='store_true', help='Warnungen → Exit-Code 2.')
        parser.add_argument(
            '--no-recalculate', action='store_true',
            help='Stärkeprofile nach dem Import NICHT neu berechnen.',
        )

    def handle(self, *args, **options):
        directory = options['dir']
        if not os.path.isdir(directory):
            raise CommandError(f'Ordner nicht gefunden: {directory}')

        paths = _collect_paths(directory, options['pattern'])
        if not paths:
            raise CommandError(
                f'Keine Dateien zu „{options["pattern"]}" (inkl. *.zip) in {directory}.'
            )

        report = []
        for path in paths:
            report.append(self._process_one(path, options))

        self._print_report(report)

        # Exit-Code aggregiert über alle Dateien gemäß Validierungs-Kontrakt:
        # Datei-Ausnahme ODER Validierungsfehler → 1; nur Warnungen unter
        # --strict → 2; sonst 0. Die Fehlerisolierung bleibt erhalten — jede
        # Datei läuft eigenständig, der Exit-Code spiegelt nur das Gesamtbild.
        has_file_error = any(r['status'] == 'error' for r in report)
        has_val_error = any(r.get('val_errors') for r in report)
        has_val_warning = any(r.get('val_warnings') for r in report)
        if has_file_error or has_val_error:
            raise SystemExit(validation.EXIT_ERRORS)
        if options['strict'] and has_val_warning:
            raise SystemExit(validation.EXIT_WARNINGS)

    def _read_file(self, path):
        """Gibt ``(csv_text, file_label)`` zurück — unterstützt CSV und ZIP."""
        if path.lower().endswith('.zip'):
            csv_text, manifest = read_zip(path)
            label = (
                f'{os.path.basename(path)} '
                f'[ZIP: {manifest.club}, {manifest.season}, '
                f'{manifest.player_count} Spieler]'
            )
            return csv_text, label
        with open(path, encoding='utf-8-sig') as fh:
            return fh.read(), os.path.basename(path)

    def _process_one(self, path, options):
        name = os.path.basename(path)
        try:
            text, file_label = self._read_file(path)
        except (ClubImportError, OSError) as exc:
            return {'file': name, 'status': 'error', 'detail': str(exc)}

        try:
            with transaction.atomic():
                result = import_club_csv(
                    text,
                    mode=options['mode'],
                    recalculate=not options['no_recalculate'],
                    dry_run=options['dry_run'],
                    strict=options['strict'],
                )
                if options['dry_run']:
                    transaction.set_rollback(True)
        except Exception as exc:  # noqa: BLE001 — Fehler isolieren, Stapel läuft weiter
            return {'file': name, 'status': 'error', 'detail': str(exc)}

        errors, warnings = validation.count_levels(result['validation_issues'])
        return {
            'file': file_label,
            'status': 'ok',
            'club': result['club'].name,
            'stats': result['stats'],
            'val_errors': errors,
            'val_warnings': warnings,
        }

    def _print_report(self, report):
        self.stdout.write('── Stapel-Bericht ───────────────────────────')
        ok = err = 0
        for r in report:
            if r['status'] == 'error':
                err += 1
                self.stdout.write(self.style.ERROR(
                    f"  ✗ {r['file']}: {r['detail']}"
                ))
                continue
            ok += 1
            stats = r['stats']
            stat_txt = (
                'DRY-RUN' if stats is None
                else '{created}+/{updated}~/{skipped}>/{failed}!'.format(**stats)
            )
            self.stdout.write(self.style.SUCCESS(
                f"  ✓ {r['file']}: {r['club']} [{stat_txt}] "
                f"(Val: {r['val_errors']}E/{r['val_warnings']}W)"
            ))
        self.stdout.write(
            f'Gesamt: {ok} ok, {err} fehlgeschlagen, {len(report)} Dateien.'
        )
