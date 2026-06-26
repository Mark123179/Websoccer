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
from game.cmt_profile_service import create_player_from_cmt_raw, store_player_profiles
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
            '--auto-create', action='store_true',
            help='Legt vereinslose Spieler an, die nicht in der WS-DB '
                 'gefunden wurden (reason=not_in_ws). Nützlich für '
                 'Leihspieler, deren Stammverein noch nicht importiert wurde. '
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

        # ── Auto-Create (optional, --auto-create) ────────────────────────────
        if opts['auto_create']:
            self.stdout.write('')
            ws_club = None
            cmt_team_name_for_resolve = ''

            if opts.get('team') and db_slug:
                raw_team_arg = opts['team']
                if str(raw_team_arg).lstrip('-').isdigit():
                    # Numerische ID → echten Namen aus CMT-API holen
                    try:
                        cmt_team_name_for_resolve = (
                            client.find_team_name(db_slug, team_id) or ''
                        )
                        if cmt_team_name_for_resolve:
                            self.stdout.write(
                                f'Auto-Create: CMT-Teamname für ID {team_id}'
                                f' → "{cmt_team_name_for_resolve}"'
                            )
                    except Exception:
                        pass
                else:
                    cmt_team_name_for_resolve = raw_team_arg

                ws_club = self._resolve_ws_club(
                    team_id, db_slug, cmt_team_name_for_resolve
                )
                if ws_club:
                    self.stdout.write(
                        f'Auto-Create: WS-Club aufgelöst → {ws_club.name}'
                    )
                else:
                    _no_club_msg = (
                        f'Auto-Create: kein WS-Club für "{raw_team_arg}"'
                        + (f' / "{cmt_team_name_for_resolve}"'
                           if cmt_team_name_for_resolve != raw_team_arg else '')
                        + ' gefunden.\n'
                        + f'  Tipp: ClubExternalId(CMTRACKER, {team_id}, {db_slug})'
                        + ' in der DB anlegen oder den Club zuerst importieren.'
                    )
                    if not opts['dry_run']:
                        raise CommandError(
                            _no_club_msg +
                            '\n  Im Dry-Run (--dry-run) wird die Vorschau'
                            ' trotzdem angezeigt.'
                        )
                    self.stdout.write(self.style.ERROR(_no_club_msg))
                    self.stdout.write(self.style.WARNING(
                        '── Dry-Run-Vorschau mit club=None ──'
                    ))

            self._auto_create_players(
                result=result,
                players=players,
                db_slug=db_slug or '',
                ws_club=ws_club,
                dry_run=opts['dry_run'],
            )

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

    def _resolve_ws_club(self, cmt_team_id, db_slug, cmt_team_name):
        """Löst den WS-Club aus CMT-Team-ID oder CMT-Teamname auf.

        Strategie:
          1. ClubExternalId(CMTRACKER, external_id=cmt_team_id, db_slug) → direkt
          2. Name-Suche: jedes Wort des cmt_team_name (≥ 3 Zeichen, längste zuerst)
             → Club.name__icontains
        Der cmt_team_name muss der echte Teamname aus der CMT-API sein,
        keine rohe numerische Team-ID.
        """
        from game.models import Club, ClubExternalId, DataSource
        try:
            cmt_source = DataSource.objects.get(code='CMTRACKER')
            ext = ClubExternalId.objects.filter(
                source=cmt_source,
                external_id=str(cmt_team_id),
                db_slug=db_slug,
            ).select_related('club').first()
            if ext:
                return ext.club
        except Exception:
            pass

        if cmt_team_name and not str(cmt_team_name).lstrip('-').isdigit():
            words = sorted(
                [w for w in cmt_team_name.split() if len(w) >= 3],
                key=len, reverse=True,
            )
            for keyword in words:
                club = Club.objects.filter(name__icontains=keyword).first()
                if club:
                    return club
        return None

    def _auto_create_players(self, result, players, db_slug, ws_club, dry_run):
        """Legt Spieler für alle CMT-Einträge mit reason=not_in_ws an.

        Entscheidungsmatrix (siehe create_player_from_cmt_raw):
          ws_club + loan_team → club=ws_club, loaned_in
          ws_club + kein loan → club=ws_club, none
          None    + loan_team → club=None,    extern_loan
          None    + kein loan → club=None,    none
        """
        # Index: CMT-playerid → Rohpayload
        raw_by_cmt_id = {}
        for raw in players:
            pid = str(_dig(raw, 'info.playerid') or '').strip()
            if pid:
                raw_by_cmt_id[pid] = raw

        candidates = [
            r for r in result.get('row_results', [])
            if r.get('action') == 'unmatched'
            and r.get('unmatch_reason') == 'not_in_ws'
        ]

        if not candidates:
            self.stdout.write('Auto-Create: keine not_in_ws-Kandidaten.')
            return

        mode = 'DRY-RUN' if dry_run else 'Anlegen'
        self.stdout.write(
            self.style.WARNING(
                f'Auto-Create ({mode}): {len(candidates)} Kandidaten …'
            )
        )
        if dry_run:
            self.stdout.write(
                f'  {"Name":<28}  {"WS":>3}  {"CMT-Pos":<24}  {"OVR":>3}  '
                f'{"CMT-Verein":<22}  {"Leihgeber":<18}  '
                f'{"Status":<12}  {"Ziel-WS-Club / Grund"}'
            )
            self.stdout.write('  ' + '─' * 126)

        created = skipped = errors = blocked = 0
        for row in candidates:
            cmt_id = str(row.get('sofifa_id', '')).strip()
            raw = raw_by_cmt_id.get(cmt_id)
            if raw is None:
                self.stdout.write(
                    self.style.ERROR(f'  CMT-ID {cmt_id}: kein Rohpayload gefunden')
                )
                errors += 1
                continue

            # tm_position ist hier immer None — TM.de-Positionen kommen aus dem
            # TM-Import/CSV, nicht aus dem CMT-Auto-Create-Pfad.
            # Fehlende TM-Position → status='blocked' (kein aktiver Spieler).
            r = create_player_from_cmt_raw(
                raw, db_slug=db_slug, ws_club=ws_club, dry_run=dry_run,
                tm_position=None,
            )
            cmt_pos_raw = r.get('cmt_pos_raw', '') or ''
            overall     = r.get('overall', '?')

            if r['status'] == 'blocked':
                # Kein aktiver Kaderspieler ohne TM-Position — nur Diagnose ausgeben
                self.stdout.write(
                    f'  ⊘ {r["name"]:<28}  '
                    f'CMT-Pos: {cmt_pos_raw or "?":<20}  OVR {overall}  '
                    f'→ BLOCKIERT: TM-Position fehlt → kein aktiver Auto-Create'
                )
                blocked += 1
            elif r['status'] == 'created':
                pos         = r.get('position', '?')
                club_team   = r.get('club_team_name') or ''
                loan_team   = r.get('loan_team_name') or ''
                status_str  = r.get('decided_status', '?')
                target      = r.get('target_club')
                target_name = target.name if target else 'vereinslos'
                reason_short = r.get('decision_reason', '')
                icon         = '(dry)' if dry_run else '✓'

                if dry_run:
                    self.stdout.write(
                        f'  {icon} {r["name"]:<28}  {pos:>3}  {cmt_pos_raw:<24}  '
                        f'{overall:>3}  '
                        f'{club_team:<22}  {loan_team:<18}  '
                        f'{status_str:<12}  {target_name} — {reason_short}'
                    )
                else:
                    loan_tag = (
                        f'  ↩ Leihe von {loan_team}' if loan_team else ''
                    )
                    self.stdout.write(
                        f'  ✓ {r["name"]:<28}  [{pos}]  OVR {overall}'
                        f'  → {target_name}  [{status_str}]{loan_tag}'
                    )
                created += 1
            elif r['status'] == 'skipped':
                self.stdout.write(
                    f'  –  {r["name"]:<28}  bereits vorhanden: {r["reason"]}'
                )
                skipped += 1
            else:
                self.stdout.write(
                    self.style.ERROR(f'  ✗  {r["name"]}: {r["reason"]}')
                )
                errors += 1

        if dry_run:
            summary = f'Auto-Create (DRY-RUN): {blocked} blockiert (TM-Position fehlt)'
            if created:
                summary += f', {created} würden angelegt'
        else:
            summary = f'Auto-Create abgeschlossen: {created} angelegt'
            if blocked:
                summary += f', {blocked} blockiert (TM-Position fehlt → via TM-Import anlegen)'
        if skipped:
            summary += f', {skipped} übersprungen'
        if errors:
            summary += f', {errors} Fehler'
        self.stdout.write(self.style.SUCCESS(summary))

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
            # Gruppieren nach Grund
            _REASON_LABEL = {
                'not_in_ws':      'Spieler fehlt in Websoccer-DB',
                'no_cmt_id':      'CMT-ID fehlt in Rohdaten',
                'no_dob':         'Geburtsdatum fehlt (kein DOB-Match moeglich)',
                'no_name':        'Name fehlt (kein Namens-Fallback moeglich)',
                'dob_ambiguous':  'DOB mehrdeutig (mehrere Treffer, keine Namenstrennung)',
                'name_ambiguous': 'Namens-Score gleichauf (mehrdeutig)',
                'name_no_match':  'Namensaehnlichkeit unter Schwelle 150',
                'unknown':        'Unbekannter Grund',
            }
            by_reason = {}
            for r in unmatched:
                reason = r.get('unmatch_reason') or 'unknown'
                by_reason.setdefault(reason, []).append(r)

            self.stdout.write(self.style.WARNING(
                f'Nicht gematcht ({len(unmatched)}) — Gruppen:'
            ))
            for reason, rows in sorted(by_reason.items(),
                                       key=lambda x: -len(x[1])):
                label = _REASON_LABEL.get(reason, reason)
                self.stdout.write(self.style.WARNING(
                    f'  [{len(rows):>3}]  {label}'
                ))
                for r in rows[:8]:
                    name = r.get('player_name') or r.get('sofifa_id') or '?'
                    club = f" ({r['club_name']})" if r.get('club_name') else ''
                    cmt_id = f" [CMT:{r['sofifa_id']}]" if r.get('sofifa_id') else ''
                    self.stdout.write(f'          • {name}{club}{cmt_id}')
                if len(rows) > 8:
                    self.stdout.write(f'          … und {len(rows) - 8} weitere')

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
