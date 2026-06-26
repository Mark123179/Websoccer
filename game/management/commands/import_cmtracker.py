"""cmtracker-API-Importer (CLI).

Holt CMTracker-Ratings direkt von der cmtracker-API und speist sie durch
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
    help = 'Importiert CMTracker-Ratings direkt von der cmtracker-API.'

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
            '--sandbox', action='store_true',
            help='Sandbox-API-Key: ein parameterfreier Abruf (Filter und '
                 'Pagination sind serverseitig deaktiviert).',
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
        parser.add_argument(
            '--probe-players', action='store_true',
            help='Testet alle bekannten Spieler-Endpoint-Kandidaten und '
                 'zeigt Status-Codes + gekuerzte Antworten. Kein Import. '
                 'API-Key wird nicht ausgegeben.',
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

        if opts['probe_players']:
            self._probe_players(client, opts.get('db'))
            return

        sandbox = opts['sandbox']
        filters = {}
        if opts['team']:
            filters['team__in'] = opts['team']
        if opts['league']:
            filters['league__in'] = opts['league']
        if opts['min_overall'] is not None:
            filters['overallrating__gte'] = opts['min_overall']

        if sandbox and (filters or opts['max_pages']):
            self.stdout.write(self.style.WARNING(
                'Sandbox-Modus aktiv: Filter (--team/--league/--min-overall) '
                'und Pagination (--max-pages) sind serverseitig deaktiviert '
                'und werden ignoriert.'
            ))

        self.stdout.write('Hole Spieler von cmtracker …')
        try:
            players = list(client.iter_players(
                db=opts['db'],
                limit=opts['limit'],
                max_pages=opts['max_pages'],
                sort='overallrating:desc',
                filters=filters or None,
                sleep=0.2,
                sandbox=sandbox,
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

    def _probe_players(self, client, db=None):
        """Testet alle Spieler-Endpoint-Kandidaten und gibt Diagnose aus."""
        import urllib.parse  # noqa: PLC0415

        self.stdout.write(self.style.SUCCESS(
            f'Base-URL: {client.base_url}'
        ))
        if db:
            self.stdout.write(f'DB-Slug:  {db}')
        else:
            self.stdout.write('DB-Slug:  (keiner angegeben — teste auch DB-lose Pfade)')
        self.stdout.write('')

        results = client.probe_players_endpoint(db=db)
        ok_found = False
        last_base = None

        for r in results:
            if r['base'] != last_base:
                marker = ' [ALT-BASE]' if r['base_is_alt'] else ''
                self.stdout.write(self.style.WARNING(
                    f'── Base: {r["base"]}{marker} ─────────────────────'
                ))
                last_base = r['base']

            qs = ('?' + urllib.parse.urlencode(r['params'])) if r['params'] else ''
            status = r['status']

            if r['ok']:
                style = self.style.SUCCESS
                ok_found = True
            elif status in (401, 403):
                style = self.style.ERROR
            elif status == 404:
                style = self.style.WARNING
            elif status == -1:
                style = self.style.ERROR
            else:
                style = self.style.NOTICE

            self.stdout.write(style(
                f'  [{status:>4}]  /{r["path"]}{qs}'
            ))
            if r['body_preview'] and status not in (200,):
                preview = r['body_preview'].replace('\n', ' ')[:200]
                self.stdout.write(f'           {preview}')

        self.stdout.write('')
        if ok_found:
            winning = [r for r in results if r['ok']]
            self.stdout.write(self.style.SUCCESS(
                '✓ Funktionierende Pfade gefunden:'
            ))
            for r in winning:
                import urllib.parse as _up  # noqa: PLC0415
                qs = ('?' + _up.urlencode(r['params'])) if r['params'] else ''
                self.stdout.write(self.style.SUCCESS(
                    f'  {r["base"]}/{r["path"]}{qs}'
                ))
        else:
            self.stdout.write(self.style.ERROR(
                '✗ Kein Endpunkt lieferte HTTP 200. '
                'Bitte CMTracker-Doku / Support fragen welcher /players-Pfad '
                'fuer diesen API-Plan aktiv ist.'
            ))

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
