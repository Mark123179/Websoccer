"""cmtracker-API-Importer (CLI).

Holt CMTracker-Ratings direkt von der cmtracker-API und speist sie durch
denselben Service wie der CSV-Upload im Creator-Mode
(``game.sofifa_import_service.run_sofifa_import``). Matching laeuft DOB-first;
es werden ausschliesslich bereits existierende Spieler aktualisiert, nicht
gematchte Spieler werden nur gezaehlt.

Optional (--profiles) werden normalisierte CMT-Spielerprofile
(PlayerCMTProfile, PlayerCMTAttributeProfile) gespeichert.

Der API-Key kommt aus dem Secret ``CMTRACKER_API_KEY``.

Beispiele::

    # Verfuegbare Datenbanken auflisten
    python manage.py import_cmtracker --list-dbs

    # Teams und Ligen einer DB anzeigen
    python manage.py import_cmtracker --list-filters --db 26062400

    # Dry-Run: Bayern-Spieler mit Profil-Vorschau
    python manage.py import_cmtracker --dry-run --db 26062400 --team "FC Bayern"

    # Echter Import inkl. Profilspeicherung
    python manage.py import_cmtracker --db 26062400 --team "FC Bayern" --profiles
"""

from django.core.management.base import BaseCommand, CommandError

from game.cmtracker_api import (
    CmtrackerClient,
    CmtrackerError,
    _dig,
    _extract_list,
    players_to_csv,
)
from game.cmt_profile_service import store_player_profiles
from game.sofifa_import_service import run_sofifa_import

_FILTER_KEYS_TEAM = ('teams', 'clubs', 'club_teams', 'team_list', 'team')
_FILTER_KEYS_LEAGUE = ('leagues', 'competitions', 'league_list', 'league')


class Command(BaseCommand):
    help = 'Importiert CMTracker-Ratings direkt von der cmtracker-API.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--db', default=None,
            help='Datenbank-Slug (Standard: neueste DB der API).',
        )
        parser.add_argument(
            '--team', default=None,
            help='Team-Name oder Team-ID (cmtracker). Bei einem Namen wird '
                 'zunaechst GET /dbs/filters/{db} abgefragt, um die ID zu '
                 'ermitteln. Beispiel: --team "FC Bayern" oder --team 21.',
        )
        parser.add_argument(
            '--league', default=None,
            help='Liga-Name oder Liga-ID (cmtracker). Wird wie --team '
                 'ueber /dbs/filters aufgeloest.',
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
            '--profiles', action='store_true',
            help='Normalisierte CMT-Spielerprofile speichern/aktualisieren '
                 '(PlayerCMTProfile, PlayerCMTAttributeProfile). '
                 'Laeuft nach dem regulaeren Rating-Import. '
                 'Im Dry-Run wird nur die Vorschau ausgegeben.',
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
            '--list-filters', action='store_true',
            help='Zeigt Teams und Ligen der gewaehlten DB (--db Pflicht). '
                 'Gibt Team-/Liga-IDs fuer --team / --league aus. Kein Import.',
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

        if opts['list_filters']:
            if not opts['db']:
                raise CommandError(
                    '--list-filters benoetigt --db. '
                    'Verfuegbare DBs: python manage.py import_cmtracker --list-dbs'
                )
            self._print_filters(client, opts['db'])
            return

        # ── Player-Import: --db ist Pflicht ──────────────────────────────────
        sandbox = opts['sandbox']
        if not opts['db'] and not sandbox:
            raise CommandError(
                'Bitte DB-Slug angeben: --db 26062400\n'
                'Verfuegbare DBs:  python manage.py import_cmtracker --list-dbs\n'
                'Teams in einer DB: python manage.py import_cmtracker --list-filters --db 26062400'
            )

        # ── Filter aufloesen: Namen → IDs via /dbs/filters/{db} ──────────────
        filters = {}
        db_slug = opts['db']

        if opts['team'] and db_slug:
            raw = opts['team']
            try:
                team_id = client.find_team_id(db_slug, raw)
            except CmtrackerError as exc:
                raise CommandError(f'Filter-Abfrage fuer --team fehlgeschlagen: {exc}')
            if team_id is None:
                raise CommandError(
                    f'Team "{raw}" nicht in /dbs/filters/{db_slug} gefunden. '
                    f'Tipp: python manage.py import_cmtracker --list-filters --db {db_slug}'
                )
            self.stdout.write(f'Team "{raw}" → ID {team_id}')
            filters['team__in'] = team_id

        if opts['league'] and db_slug:
            raw = opts['league']
            try:
                league_id = client.find_team_id(db_slug, raw)  # selbe Logik
            except CmtrackerError as exc:
                raise CommandError(f'Filter-Abfrage fuer --league fehlgeschlagen: {exc}')
            if league_id is None:
                raise CommandError(
                    f'Liga "{raw}" nicht in /dbs/filters/{db_slug} gefunden. '
                    f'Tipp: python manage.py import_cmtracker --list-filters --db {db_slug}'
                )
            self.stdout.write(f'Liga "{raw}" → ID {league_id}')
            filters['league__in'] = league_id

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
                db=db_slug,
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

        if opts['dry_run']:
            self.stdout.write(self.style.WARNING(
                '── DRY-RUN: es werden KEINE Aenderungen geschrieben ──'
            ))

        # ── Rating-Import (bestehender Pfad via sofifa_import_service) ───────
        csv_text = players_to_csv(players)
        result = run_sofifa_import(
            csv_text,
            dry_run=opts['dry_run'],
            skip_recalculate=opts['skip_recalculate'],
        )
        if result['fatal_error']:
            raise CommandError(result['fatal_error'])

        self._print_result(result, opts['dry_run'])

        # ── Profil-Import (optional, --profiles) ─────────────────────────────
        if opts['profiles']:
            self.stdout.write('')
            self.stdout.write('Profil-Import (PlayerCMTProfile) …')
            profile_stats = store_player_profiles(
                players=players,
                db_slug=db_slug or '',
                dry_run=opts['dry_run'],
            )
            self._print_profile_result(profile_stats, opts['dry_run'])

    def _print_filters(self, client, dbslug):
        """Zeigt Teams und Ligen der gewaehlten DB (fuer --list-filters)."""
        try:
            data = client.get_db_filters(dbslug)
        except CmtrackerError as exc:
            raise Exception(str(exc))

        self.stdout.write(self.style.SUCCESS(f'Filter fuer DB: {dbslug}'))

        def _show_section(label, keys):
            items = []
            if isinstance(data, dict):
                for k in keys:
                    val = data.get(k)
                    if isinstance(val, list) and val:
                        items = val
                        break
            elif isinstance(data, list):
                items = data
            if not items:
                self.stdout.write(f'  {label}: (keine Daten)')
                return
            self.stdout.write(self.style.WARNING(f'  {label} ({len(items)}):'))
            for entry in items[:80]:
                if isinstance(entry, dict):
                    eid = (entry.get('id') or entry.get('teamid') or
                           entry.get('team_id') or entry.get('clubid') or
                           entry.get('value') or '?')
                    name = (entry.get('name') or entry.get('title') or
                            entry.get('label') or entry.get('club_name') or '?')
                    self.stdout.write(f'    {eid:>8}  {name}')
                else:
                    self.stdout.write(f'    {entry}')

        _show_section('Teams', _FILTER_KEYS_TEAM)
        _show_section('Ligen', _FILTER_KEYS_LEAGUE)

        if isinstance(data, dict):
            known = set(_FILTER_KEYS_TEAM) | set(_FILTER_KEYS_LEAGUE)
            extra = [k for k in data if k not in known]
            if extra:
                self.stdout.write('')
                self.stdout.write('  Weitere Schluessel in der Antwort:')
                for k in extra:
                    val = data[k]
                    preview = repr(val)[:120]
                    self.stdout.write(f'    {k}: {preview}')

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
            f"Rating-Import: {stats.get('new', 0)} neu, "
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

    def _print_profile_result(self, stats, dry_run):
        """Gibt Profil-Import-Statistiken aus."""
        error = stats.get('error')
        if error:
            self.stdout.write(self.style.ERROR(f'  Fehler: {error}'))
            return

        mode = '[DRY-RUN] ' if dry_run else ''
        self.stdout.write(self.style.SUCCESS(
            f'{mode}Profil-Import: '
            f"{stats.get('matched', 0)} gematcht, "
            f"{stats.get('new', 0)} neu, "
            f"{stats.get('updated', 0)} aktualisierbar, "
            f"{stats.get('unchanged', 0)} unveraendert, "
            f"{stats.get('unmatched', 0)} nicht gematcht."
        ))

        unmatched_ids = stats.get('unmatched_ids', [])
        if unmatched_ids:
            self.stdout.write(self.style.WARNING(
                f'  Nicht gematcht (CMT-IDs, erste {len(unmatched_ids)}): '
                + ', '.join(unmatched_ids[:20])
            ))
            if stats.get('unmatched', 0) > len(unmatched_ids):
                self.stdout.write(self.style.WARNING(
                    f'  … und {stats["unmatched"] - len(unmatched_ids)} weitere.'
                ))

        if dry_run:
            self.stdout.write(self.style.WARNING(
                'DRY-RUN: keine Profile gespeichert.'
            ))
