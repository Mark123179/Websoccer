"""Management-Command: check_cmt_aliases

Vergleicht alle CMT-Teamnamen einer Datenbank mit der WS-Clubdatenbank und
meldet, welche Namen aufgelöst werden konnten und welche nicht.

Zweck: Die Alias-Tabelle in import_cmtracker.py wird manuell gepflegt.
Dieses Command erkennt fehlende Einträge, bevor ein Import scheitert.

Beispiele::

    # Alle Teams der DB 26062400 prüfen
    python manage.py check_cmt_aliases --db 26062400

    # Mit Ähnlichkeitsvorschlägen für nicht aufgelöste Namen
    python manage.py check_cmt_aliases --db 26062400 --suggest
"""

import difflib

from django.core.management.base import BaseCommand, CommandError

from game.cmtracker_api import CmtrackerClient, CmtrackerError
from game.management.commands.import_cmtracker import (
    _CMT_CLUB_NAME_ALIASES,
    _FILTER_KEYS_TEAM,
)
from game.models import Club

_SUGGEST_N = 3
_SUGGEST_CUTOFF = 0.55


def _extract_team_names(data):
    """Extrahiert (name, id)-Paare aus dem get_db_filters-Antwortobjekt."""
    items = []
    if isinstance(data, dict):
        for k in _FILTER_KEYS_TEAM:
            val = data.get(k)
            if isinstance(val, list) and val:
                items = val
                break
    elif isinstance(data, list):
        items = data

    result = []
    for entry in items:
        if isinstance(entry, dict):
            name = (
                entry.get('name') or entry.get('title') or
                entry.get('label') or entry.get('club_name') or ''
            )
            eid = (
                entry.get('id') or entry.get('teamid') or
                entry.get('team_id') or entry.get('clubid') or
                entry.get('value') or ''
            )
        elif isinstance(entry, str):
            name = entry
            eid = ''
        else:
            continue
        name = name.strip()
        if name:
            result.append((str(eid), name))
    return result


def _resolve_club(cmt_name):
    """Gibt den passenden WS-Club zurück oder None (ohne API-Aufruf).

    Strategie (identisch zu import_cmtracker._resolve_ws_club Schritte 2–4):
      1. Alias-Tabelle (_CMT_CLUB_NAME_ALIASES) → iexact
      2. Direkter iexact-Match
      3. Token-Match (≥ 4 Zeichen, eindeutig)
    """
    key = cmt_name.strip().lower()

    canonical = _CMT_CLUB_NAME_ALIASES.get(key)
    if canonical:
        club = Club.objects.filter(name__iexact=canonical).first()
        if club:
            return club, 'alias'

    club = Club.objects.filter(name__iexact=cmt_name.strip()).first()
    if club:
        return club, 'iexact'

    words = sorted(
        [w for w in cmt_name.split() if len(w) >= 4],
        key=len, reverse=True,
    )
    for keyword in words:
        clean = keyword.replace("'", '').replace('.', '').strip()
        if len(clean) < 4:
            continue
        qs = Club.objects.filter(name__icontains=clean)
        count = qs.count()
        if count == 1:
            return qs.first(), 'token'
    return None, None


class Command(BaseCommand):
    help = (
        'Vergleicht CMT-Teamnamen einer DB mit der WS-Clubdatenbank '
        'und meldet fehlende Alias-Einträge.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--db', required=True,
            help='CMTracker-Datenbank-Slug (z. B. 26062400). '
                 'Verfügbare DBs: python manage.py import_cmtracker --list-dbs',
        )
        parser.add_argument(
            '--suggest', action='store_true',
            help='Zeigt ähnliche WS-Club-Namen für nicht aufgelöste CMT-Namen '
                 '(Levenshtein-Näherung via difflib).',
        )

    def handle(self, *args, **opts):
        dbslug = opts['db']
        suggest = opts['suggest']

        try:
            client = CmtrackerClient()
        except CmtrackerError as exc:
            raise CommandError(str(exc))

        self.stdout.write(f'Hole Filter für DB {dbslug} …')
        try:
            data = client.get_db_filters(dbslug)
        except CmtrackerError as exc:
            raise CommandError(
                f'API-Fehler beim Abrufen der Filter: {exc}\n'
                f'Tipp: python manage.py import_cmtracker --list-filters --db {dbslug}'
            )

        teams = _extract_team_names(data)
        if not teams:
            self.stdout.write(self.style.WARNING(
                'Keine Teams in der API-Antwort gefunden. '
                'Die Antwortstruktur könnte unbekannte Schlüssel verwenden.'
            ))
            self.stdout.write(f'Antwort-Vorschau: {repr(data)[:400]}')
            return

        self.stdout.write(
            f'{len(teams)} CMT-Team(s) in DB {dbslug} gefunden.\n'
        )

        all_ws_names = list(Club.objects.values_list('name', flat=True))

        resolved = []
        unresolved = []

        for cmt_id, cmt_name in teams:
            club, method = _resolve_club(cmt_name)
            if club:
                resolved.append((cmt_id, cmt_name, club, method))
            else:
                unresolved.append((cmt_id, cmt_name))

        self.stdout.write(
            self.style.SUCCESS(
                f'✓ Aufgelöst: {len(resolved)} / {len(teams)}'
            )
        )
        for cmt_id, cmt_name, club, method in resolved:
            id_str = f'[ID {cmt_id}] ' if cmt_id else ''
            self.stdout.write(
                self.style.SUCCESS(
                    f'  {id_str}"{cmt_name}"  →  {club.name}  ({method})'
                )
            )

        if unresolved:
            self.stdout.write('')
            self.stdout.write(
                self.style.WARNING(
                    f'⚠ Nicht aufgelöst: {len(unresolved)} / {len(teams)}'
                )
            )
            self.stdout.write(
                self.style.WARNING(
                    '  → Diese Namen fehlen in der Alias-Tabelle oder existieren '
                    'nicht in der WS-Datenbank.'
                )
            )
            for cmt_id, cmt_name in unresolved:
                id_str = f'[ID {cmt_id}] ' if cmt_id else ''
                self.stdout.write(
                    self.style.WARNING(f'  {id_str}"{cmt_name}"')
                )
                if suggest:
                    hits = difflib.get_close_matches(
                        cmt_name, all_ws_names,
                        n=_SUGGEST_N, cutoff=_SUGGEST_CUTOFF,
                    )
                    if hits:
                        for h in hits:
                            self.stdout.write(f'      ~  {h}')
                    else:
                        self.stdout.write('      (keine ähnlichen WS-Clubs gefunden)')

            self.stdout.write('')
            self.stdout.write(
                'Tipp: Fehlende Aliase in '
                'game/management/commands/import_cmtracker.py '
                'unter _CMT_CLUB_NAME_ALIASES eintragen.'
            )
        else:
            self.stdout.write('')
            self.stdout.write(
                self.style.SUCCESS(
                    'Alle CMT-Teamnamen konnten aufgelöst werden. '
                    'Die Alias-Tabelle ist vollständig.'
                )
            )
