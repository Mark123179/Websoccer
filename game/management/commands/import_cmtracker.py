"""cmtracker-API-Importer (CLI).

Holt EA/SoFIFA-Ratings direkt von der cmtracker-API und speist sie durch
denselben Service wie der CSV-Upload im Creator-Mode
(``game.sofifa_import_service.run_sofifa_import``). Matching laeuft DOB-first;
es werden ausschliesslich bereits existierende Spieler aktualisiert, nicht
gematchte Spieler werden nur gezaehlt.

Der API-Key kommt aus dem Secret ``CMTRACKER_API_KEY``.

Beispiele::

    # Verfuegbare Datenbanken auflisten
    python manage.py import_cmtracker --list-dbs

    # Vorschau: Top-Spieler der neuesten Datenbank (eine Seite)
    python manage.py import_cmtracker --dry-run --limit 25 --max-pages 1

    # Alle Spieler eines Vereins (cmtracker-Team-ID)
    python manage.py import_cmtracker --team 21 --dry-run
"""

from django.core.management.base import BaseCommand, CommandError

from game.cmtracker_api import (
    CmtrackerClient,
    CmtrackerError,
    _dig,
    _extract_list,
    players_to_csv,
)
from game.sofifa_import_service import run_sofifa_import


class Command(BaseCommand):
    help = 'Importiert EA/SoFIFA-Ratings direkt von der cmtracker-API.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--db', default=None,
            help='Datenbank-Slug (Standard: neueste DB der API).',
        )
        parser.add_argument(
            '--team', default=None,
            help='cmtracker-Club-Team-ID (filtert auf einen Verein).',
        )
        parser.add_argument(
            '--league', default=None,
            help='cmtracker-Liga-ID (filtert auf eine Liga).',
        )
        parser.add_argument(
            '--min-overall', type=int, default=None,
            help='Nur Spieler mit overallrating >= Wert.',
        )
        parser.add_argument(
            '--limit', type=int, default=100,
            help='Seitengroesse je API-Request (Standard 100).',
        )
        parser.add_argument(
            '--max-pages', type=int, default=None,
            help='Maximale Anzahl Seiten (Standard: alle).',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Zeigt geplante Aenderungen, ohne in die DB zu schreiben.',
        )
        parser.add_argument(
            '--skip-recalculate', action='store_true',
            help='Spielstaerken nach dem Import NICHT neu berechnen.',
        )
        parser.add_argument(
            '--list-dbs', action='store_true',
            help='Listet verfuegbare Datenbanken auf und beendet.',
        )

    def handle(self, *args, **opts):
        try:
            client = CmtrackerClient()
        except CmtrackerError as exc:
            raise CommandError(str(exc))

        if opts['list_dbs']:
            try:
                dbs = client.list_dbs()
            except CmtrackerError as exc:
                raise CommandError(str(exc))
            self._print_dbs(dbs)
            return

        filters = {}
        if opts['team']:
            filters['team__in'] = opts['team']
        if opts['league']:
            filters['league__in'] = opts['league']
        if opts['min_overall'] is not None:
            filters['overallrating__gte'] = opts['min_overall']

        self.stdout.write('Hole Spieler von cmtracker …')
        try:
            players = list(client.iter_players(
                db=opts['db'],
                limit=opts['limit'],
                max_pages=opts['max_pages'],
                sort='overallrating:desc',
                filters=filters or None,
                sleep=0.2,
            ))
        except CmtrackerError as exc:
            raise CommandError(str(exc))

        if not players:
            self.stdout.write(self.style.WARNING('Keine Spieler erhalten.'))
            return
        self.stdout.write(f'{len(players)} Spieler erhalten.')

        csv_text = players_to_csv(players)

        if opts['dry_run']:
            self.stdout.write(self.style.WARNING(
                '── DRY-RUN: es werden KEINE Aenderungen geschrieben ──'
            ))

        result = run_sofifa_import(
            csv_text,
            dry_run=opts['dry_run'],
            skip_recalculate=opts['skip_recalculate'],
        )
        if result['fatal_error']:
            raise CommandError(result['fatal_error'])

        self._print_result(result, opts['dry_run'])

    def _print_dbs(self, dbs):
        rows = _extract_list(dbs)
        if not rows and isinstance(dbs, list):
            rows = dbs
        if not rows:
            self.stdout.write(repr(dbs)[:500])
            return
        self.stdout.write(self.style.SUCCESS('Verfuegbare Datenbanken:'))
        for d in rows[:80]:
            if isinstance(d, dict):
                slug = d.get('slug') or d.get('db') or d.get('id') or '?'
                name = d.get('name') or d.get('title') or ''
                self.stdout.write(f'  {slug}  {name}')
            else:
                self.stdout.write(f'  {d}')

    def _print_result(self, result, dry_run):
        stats = result['stats']
        for r in result['row_results']:
            if r['action'] == 'error':
                self.stdout.write(self.style.ERROR(
                    f"  Zeile {r['line_no']}: {r['error_msg']}"
                ))
        unmatched = [r for r in result['row_results']
                     if r['action'] == 'unmatched']

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f"Bilanz: {stats.get('new', 0)} neu, "
            f"{stats.get('updated', 0)} aktualisiert, "
            f"{stats.get('unchanged', 0)} unveraendert, "
            f"{stats.get('unmatched', 0)} nicht gematcht, "
            f"{stats.get('error', 0)} Fehler."
        ))

        if unmatched:
            preview = unmatched[:15]
            self.stdout.write(self.style.WARNING(
                f'Nicht gematcht ({len(unmatched)}), erste {len(preview)}:'
            ))
            for r in preview:
                label = r.get('player_name') or r.get('sofifa_id') or '?'
                club = f" ({r['club_name']})" if r.get('club_name') else ''
                self.stdout.write(self.style.WARNING(f'  - {label}{club}'))

        if dry_run:
            self.stdout.write(self.style.WARNING(
                'DRY-RUN beendet — nichts geschrieben.'
            ))
