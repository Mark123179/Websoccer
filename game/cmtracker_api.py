"""cmtracker-API-Client.

Holt CMTracker-Style-Spielerdaten von der cmtracker-API
(``https://api.cmtracker.net/api/v1``) und ueberfuehrt sie in das CSV-Format,
das der bestehende CMTracker-Importer
(``game.sofifa_import_service.run_sofifa_import``) versteht. Dadurch laeuft der
API-Import durch dieselbe Parsing-, Matching- (DOB-first), Logging- und
Spielstaerke-Neuberechnungs-Pipeline wie der CSV-Upload im Creator-Mode.

Auth: API-Key im Header ``X-API-Key`` (Secret ``CMTRACKER_API_KEY``).
Optionaler Override der Basis-URL via ``CMTRACKER_BASE_URL``.

Die ``CSV_COLUMNS`` sind JSON-Pfade in die cmtracker-Antwort. Ihre
Punkt-Schreibweise ist bewusst so gewaehlt, dass der Importer sie ueber
``COLUMN_ALIASES`` erkennt (``normalize_header`` entfernt die Punkte, z. B.
``info.playerid`` -> ``infoplayerid`` -> ``sofifa_id``). Jede Spalte mappt auf
genau ein Zielattribut, damit keine Spalte eine andere ueberschreibt.
"""

import csv
import io
import os
import time

import requests


DEFAULT_BASE_URL = 'https://api.cmtracker.net/api/v1'
API_KEY_ENV = 'CMTRACKER_API_KEY'
BASE_URL_ENV = 'CMTRACKER_BASE_URL'

# Dotted-Key-Spalten -> der Importer mappt sie ueber COLUMN_ALIASES.
# Reihenfolge: Identitaet, Stammdaten, Karten-Pace, Feldspieler, Torwart.
CSV_COLUMNS = [
    # Identitaet / Stammdaten
    'info.playerid',
    'info.name.knownas',
    'info.name.firstname',
    'info.name.lastname',
    'info.teams.club_team.name',
    'info.overallrating',
    'info.potential',
    'info.birthdate',
    # Karten-Pace (= tempo wie auf der CMTracker-Karte)
    'card_attrs.pac',
    # Feldspieler-Attribute
    'attributes.stamina',
    'attributes.strength',
    'attributes.ballcontrol',
    'attributes.dribbling',
    'attributes.shortpassing',
    'attributes.crossing',
    'attributes.finishing',
    'attributes.headingaccuracy',
    'attributes.standingtackle',
    'attributes.marking',
    'attributes.vision',
    'attributes.penalties',
    'attributes.freekickaccuracy',
    # Torwart-Attribute
    'attributes.gkreflexes',
    'attributes.gkhandling',
    'attributes.gkpositioning',
    'attributes.gkkicking',
    'attributes.gkdiving',
]

# Hard-Cap gegen Endlosschleifen, falls der Server ``page`` ignoriert.
_SAFETY_PAGE_CAP = 500


class CmtrackerError(Exception):
    """Fehler beim Abruf oder der Verarbeitung der cmtracker-API."""


def _extract_list(payload):
    """Holt die eigentliche Liste aus moeglichen Antwort-Huellen.

    Die API kann entweder direkt eine Liste oder ein Objekt mit einem
    Listen-Feld (``data``/``results`` …) zurueckgeben.
    """
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ('data', 'results', 'players', 'items', 'rows', 'docs'):
            val = payload.get(key)
            if isinstance(val, list):
                return val
    return []


def _dig(obj, path):
    """Liest einen Wert per Punktpfad.

    Unterstuetzt sowohl verschachtelte Dicts (``{'info': {'playerid': 1}}``)
    als auch bereits abgeflachte Punktschluessel (``{'info.playerid': 1}``).
    Gibt ``None`` zurueck, wenn der Pfad nicht existiert.
    """
    if not isinstance(obj, dict):
        return None
    if path in obj:
        return obj[path]
    cur = obj
    for part in path.split('.'):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def _cell(value):
    """Formatiert einen JSON-Wert als CSV-Zelle."""
    if value is None:
        return ''
    if isinstance(value, bool):
        return '1' if value else '0'
    return str(value)


def player_to_row(player):
    """Eine cmtracker-Spielerantwort -> Zeilenliste passend zu ``CSV_COLUMNS``."""
    return [_cell(_dig(player, col)) for col in CSV_COLUMNS]


def players_to_csv(players):
    """Erzeugt den CSV-Text fuer ``run_sofifa_import`` aus Spieler-Objekten."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(CSV_COLUMNS)
    for p in players:
        writer.writerow(player_to_row(p))
    return buf.getvalue()


class CmtrackerClient:
    """Duenner HTTP-Client fuer die cmtracker-API (nur Lesezugriffe)."""

    def __init__(self, api_key=None, base_url=None, timeout=30):
        self.api_key = api_key or os.environ.get(API_KEY_ENV) or ''
        if not self.api_key:
            raise CmtrackerError(
                f'Kein API-Key gesetzt. Bitte Secret {API_KEY_ENV} hinterlegen.'
            )
        self.base_url = (
            base_url or os.environ.get(BASE_URL_ENV) or DEFAULT_BASE_URL
        ).rstrip('/')
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'X-API-Key': self.api_key,
            'Accept': 'application/json',
        })

    def _get(self, path, params=None):
        url = f'{self.base_url}/{path.lstrip("/")}'
        try:
            resp = self.session.get(url, params=params, timeout=self.timeout)
        except requests.RequestException as exc:
            raise CmtrackerError(f'Netzwerkfehler bei {url}: {exc}') from exc

        if resp.status_code in (401, 403):
            raise CmtrackerError(
                f'Authentifizierung fehlgeschlagen ({resp.status_code}). '
                f'API-Key ({API_KEY_ENV}) pruefen.'
            )
        if resp.status_code == 429:
            raise CmtrackerError(
                'Rate-Limit erreicht (429). Bitte spaeter erneut versuchen.'
            )
        if resp.status_code >= 400:
            raise CmtrackerError(
                f'API-Fehler {resp.status_code} bei {url}: {resp.text[:300]}'
            )
        try:
            return resp.json()
        except ValueError as exc:
            raise CmtrackerError(
                f'Ungueltige JSON-Antwort von {url}.'
            ) from exc

    # ── Endpoints ────────────────────────────────────────────────────────────
    def list_dbs(self):
        """``GET /dbs`` — verfuegbare FIFA/FC-Datenbanken."""
        return self._get('dbs')

    def get_db_filters(self, dbslug):
        """``GET /dbs/filters/{dbslug}`` — Filterwerte (Ligen, Teams, Nationen)."""
        return self._get(f'dbs/filters/{dbslug}')

    def probe_players_endpoint(self, db=None):
        """Testet alle bekannten Endpoint-Kandidaten fuer Spielerabruf.

        Gibt eine Liste von Dicts zurueck::

            [{
                'path':         str,   # relativer Pfad
                'params':       dict,  # Query-Parameter
                'full_url':     str,   # vollstaendige URL (KEIN Key)
                'status':       int,   # HTTP-Status (-1 = Netzwerkfehler)
                'body_preview': str,   # erste 300 Zeichen der Antwort
                'ok':           bool,  # True wenn 200
            }, ...]

        Der API-Key wird NICHT in den Rueckgabewerten ausgegeben.
        """
        import requests  # noqa: PLC0415

        slug = db or ''
        candidates = [
            # (path, params)
            ('players',                 {}),
            ('players',                 {'limit': 1}),
            ('players',                 {'limit': 1, 'db': slug} if slug else {'limit': 1}),
            ('player',                  {}),
            ('player',                  {'limit': 1}),
            (f'dbs/{slug}/players',     {})                        if slug else None,
            (f'dbs/{slug}/players',     {'limit': 1, 'page': 0})   if slug else None,
            (f'dbs/{slug}/player',      {})                        if slug else None,
            ('dbs/players',             {}),
            ('dbs/players',             {'limit': 1}),
        ]

        # Auch alternative Base-URLs pruefen
        alt_bases = []
        if '/api/v1' in self.base_url:
            alt_bases.append(self.base_url.replace('/api/v1', '/v1'))
            alt_bases.append(self.base_url.replace('/api/v1', ''))
        bases = [(self.base_url, False)] + [(b, True) for b in alt_bases if b]

        results = []
        for base, is_alt in bases:
            for entry in candidates:
                if entry is None:
                    continue
                path, params = entry
                url = f'{base.rstrip("/")}/{path.lstrip("/")}'
                try:
                    resp = self.session.get(url, params=params, timeout=self.timeout)
                    status = resp.status_code
                    body = resp.text[:300]
                except requests.RequestException as exc:
                    status = -1
                    body = str(exc)[:200]
                results.append({
                    'base':         base,
                    'base_is_alt':  is_alt,
                    'path':         path,
                    'params':       params,
                    'full_url':     url,
                    'status':       status,
                    'body_preview': body,
                    'ok':           status == 200,
                })
        return results

    def list_players(self, db=None, page=0, limit=25, sort=None, filters=None,
                     paginate=True):
        """``GET /players`` — eine Seite Spieler.

        Im Sandbox-Modus (``paginate=False``) werden ``page``/``limit`` nicht
        gesendet, da Pagination und Filter dort serverseitig deaktiviert sind.
        """
        params = {}
        if paginate:
            params['page'] = page
            params['limit'] = limit
        if db:
            params['db'] = db
        if sort:
            params['sort'] = sort
        if filters:
            params.update(filters)
        return self._get('players', params=params or None)

    def get_player(self, playerid, db=None):
        """``GET /players/{playerid}`` — einzelner Spieler."""
        params = {'db': db} if db else None
        return self._get(f'players/{playerid}', params=params)

    def list_teams(self, db=None, page=0, limit=25, sort=None, filters=None):
        """``GET /teams`` — eine Seite Teams."""
        params = {'page': page, 'limit': limit}
        if db:
            params['db'] = db
        if sort:
            params['sort'] = sort
        if filters:
            params.update(filters)
        return self._get('teams', params=params)

    def find_team_id(self, dbslug, team_name_or_id):
        """Loest einen Team-Namen oder eine Team-ID auf.

        Ist ``team_name_or_id`` bereits numerisch, wird er unveraendert
        zurueckgegeben (Strings wie ``'12345'`` werden akzeptiert).

        Andernfalls wird ``GET /dbs/filters/{dbslug}`` abgefragt und der
        erste Eintrag zurueckgegeben, dessen Name (case-insensitiv) dem
        Suchbegriff entspricht oder ihn enthaelt.

        Gibt ``None`` zurueck, wenn kein Treffer gefunden wurde.
        """
        if str(team_name_or_id).lstrip('-').isdigit():
            return str(team_name_or_id)

        filters = self.get_db_filters(dbslug)
        search = team_name_or_id.lower()

        # Die API liefert Filter entweder als Dict mit Listen oder direkt
        # als Liste. Wir suchen in allen team-artigen Schluessel.
        candidates = []
        if isinstance(filters, dict):
            for key in ('teams', 'clubs', 'club_teams', 'team_list', 'team'):
                val = filters.get(key)
                if isinstance(val, list):
                    candidates = val
                    break
            if not candidates:
                # Fallback: alle Listen-Werte durchsuchen
                for val in filters.values():
                    if isinstance(val, list) and val:
                        candidates = val
                        break
        elif isinstance(filters, list):
            candidates = filters

        for entry in candidates:
            if isinstance(entry, dict):
                name = (
                    entry.get('name') or entry.get('title') or
                    entry.get('label') or entry.get('club_name') or ''
                ).lower()
                team_id = (
                    entry.get('id') or entry.get('teamid') or
                    entry.get('team_id') or entry.get('clubid') or
                    entry.get('value')
                )
                if search in name and team_id is not None:
                    return str(team_id)
            elif isinstance(entry, (int, str)):
                if search == str(entry).lower():
                    return str(entry)
        return None

    def iter_players(self, db=None, limit=100, max_pages=None, sort=None,
                     filters=None, sleep=0.0, sandbox=False):
        """Iteriert paginiert ueber alle passenden Spieler.

        ``db`` (DB-Slug) ist im Live-Modus Pflicht. Fehlt er, wird ein
        ``CmtrackerError`` mit einem Hinweis auf ``--list-dbs`` ausgeloest.

        Terminiert bei leerer Seite, erreichter ``max_pages``, dem Sicherheits-
        Cap oder wenn der Server dieselbe Seite erneut liefert (ignoriert
        ``page``). Liefert die rohen Spieler-Objekte.

        Im Sandbox-Modus (``sandbox=True``) sind Pagination und Filter
        serverseitig deaktiviert: es wird genau ein parameterfreier
        ``GET /players`` ausgefuehrt und dessen Spieler werden geliefert.
        """
        if not db and not sandbox:
            raise CmtrackerError(
                'DB-Slug fehlt. Bitte --db <slug> angeben, z. B. --db 26062400. '
                'Verfuegbare Datenbanken: python manage.py import_cmtracker --list-dbs'
            )

        if sandbox:
            payload = self.list_players(
                db=db, sort=None, filters=None, paginate=False,
            )
            for item in _extract_list(payload):
                yield item
            return

        page = 0
        seen_first = object()  # Sentinel: noch keine Seite gesehen
        while True:
            payload = self.list_players(
                db=db, page=page, limit=limit, sort=sort, filters=filters,
            )
            batch = _extract_list(payload)
            if not batch:
                break

            first_id = _dig(batch[0], 'info.playerid')
            if first_id is not None and first_id == seen_first:
                break  # Server paginiert nicht — Schutz vor Endlosschleife
            seen_first = first_id

            for item in batch:
                yield item

            page += 1
            if max_pages is not None and page >= max_pages:
                break
            if page >= _SAFETY_PAGE_CAP:
                break
            if sleep:
                time.sleep(sleep)
