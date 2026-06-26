"""seed_cmt_club_ids — legt ClubExternalId(CMTRACKER)-Einträge an.

Standard-Aufruf (kein --apply): reiner Dry-Run, keine DB-Schreibzugriffe.
Mit --apply werden die Einträge tatsächlich geschrieben.

Zwei Modi:

1. Hardcoded-Modus (Standard, kein --db):
   Trägt alle 18 Bundesliga-Clubs der Saison 2024/25 mit bestätigten
   CMTracker-Team-IDs (DB 26062400) deterministisch ein.
   Kein API-Key nötig.

2. API-Modus (--db <slug>):
   Liest alle Teams aus GET /dbs/filters/{db} (Fallback: /teams paginiert),
   matcht sie per Alias-Tabelle auf WS-Clubs und legt ClubExternalId-Einträge an.
   Benötigt CMTRACKER_API_KEY.

Beispiele::

    # Dry-Run: zeigt was getan würde (kein Schreibzugriff)
    python manage.py seed_cmt_club_ids

    # Tatsächlich in DB schreiben
    python manage.py seed_cmt_club_ids --apply

    # Mit Überschreiben vorhandener Einträge
    python manage.py seed_cmt_club_ids --apply --force

    # Alle Teams einer DB via API laden und matchen (Dry-Run)
    python manage.py seed_cmt_club_ids --db 26062400

    # … und tatsächlich schreiben
    python manage.py seed_cmt_club_ids --db 26062400 --apply

Bekannte CMTracker-Team-IDs (DB 26062400, Saison 2024/25):
    21     FC Bayern München
    22     Borussia Dortmund
    32     Bayer 04 Leverkusen
    36     VfB Stuttgart
    112172 RB Leipzig
    1824   Eintracht Frankfurt
    175    VfL Wolfsburg
    38     SV Werder Bremen
    23     Borussia Mönchengladbach
    25     SC Freiburg
    169    1. FSV Mainz 05
    10029  TSG 1899 Hoffenheim
    100409 FC Augsburg
    110329 FC St. Pauli
    111235 1. FC Heidenheim
    576    Holstein Kiel
    160    VfL Bochum
    1831   1. FC Union Berlin  ← Männer; 132589 = Frauen-Bundesliga (nicht verwenden)
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from game.cmtracker_api import CmtrackerClient, CmtrackerError, _dig, _extract_list

_FILTER_KEYS_TEAM = ('teams', 'clubs', 'club_teams', 'team_list', 'team')

DB_SLUG = '26062400'

BUNDESLIGA_CMT_IDS: list[tuple[str, str]] = [
    ('21',     'FC Bayern München'),
    ('22',     'Borussia Dortmund'),
    ('32',     'Bayer 04 Leverkusen'),
    ('36',     'VfB Stuttgart'),
    ('112172', 'RB Leipzig'),
    ('1824',   'Eintracht Frankfurt'),
    ('175',    'VfL Wolfsburg'),
    ('38',     'SV Werder Bremen'),
    ('23',     'Borussia Mönchengladbach'),
    ('25',     'SC Freiburg'),
    ('169',    '1. FSV Mainz 05'),
    ('10029',  'TSG 1899 Hoffenheim'),
    ('100409', 'FC Augsburg'),
    ('110329', 'FC St. Pauli'),
    ('111235', '1. FC Heidenheim'),
    ('576',    'Holstein Kiel'),
    ('160',    'VfL Bochum'),
    ('1831',   '1. FC Union Berlin'),
]

_CMT_CLUB_NAME_ALIASES: dict[str, str] = {
    "borussia m'gladbach":       "Borussia Mönchengladbach",
    "bor. m'gladbach":           "Borussia Mönchengladbach",
    "m'gladbach":                "Borussia Mönchengladbach",
    "b. monchengladbach":        "Borussia Mönchengladbach",
    "b. mönchengladbach":        "Borussia Mönchengladbach",
    "borussia monchengladbach":  "Borussia Mönchengladbach",
    "rasenballsport leipzig":    "RB Leipzig",
    "rb leipzig":                "RB Leipzig",
    "red bull leipzig":          "RB Leipzig",
    "rbl":                       "RB Leipzig",
    "1. fc union berlin":        "1. FC Union Berlin",
    "union berlin":              "1. FC Union Berlin",
    "fc union berlin":           "1. FC Union Berlin",
    "fc st. pauli 1910":         "FC St. Pauli",
    "st. pauli 1910":            "FC St. Pauli",
    "fc st. pauli":              "FC St. Pauli",
    "st. pauli":                 "FC St. Pauli",
    "tsg 1899 hoffenheim":       "TSG Hoffenheim",
    "1899 hoffenheim":           "TSG Hoffenheim",
    "tsg hoffenheim":            "TSG Hoffenheim",
    "bayer 04 leverkusen":       "Bayer Leverkusen",
    "1. fsv mainz 05":           "1. FSV Mainz 05",
    "fsv mainz 05":              "1. FSV Mainz 05",
    "mainz 05":                  "1. FSV Mainz 05",
    "1. fc heidenheim 1846":     "1. FC Heidenheim 1846",
    "fc heidenheim 1846":        "1. FC Heidenheim 1846",
    "heidenheim 1846":           "1. FC Heidenheim 1846",
    "1. fc koeln":               "1. FC Köln",
    "1. fc köln":                "1. FC Köln",
    "fc koeln":                  "1. FC Köln",
    "hamburger sv":              "Hamburger SV",
    "hsv":                       "Hamburger SV",
    "sc paderborn 07":           "SC Paderborn",
    "paderborn 07":              "SC Paderborn",
    "holstein kiel":             "Holstein Kiel",
    "ksh kiel":                  "Holstein Kiel",
}


def _extract_teams_from_filters(data) -> list[dict]:
    """Extrahiert Team-Einträge aus dem /dbs/filters-Response."""
    if isinstance(data, dict):
        for key in _FILTER_KEYS_TEAM:
            val = data.get(key)
            if isinstance(val, list) and val:
                return val
    if isinstance(data, list):
        return data
    return []


def _team_id_from_entry(entry) -> str | None:
    if not isinstance(entry, dict):
        return None
    raw = (
        entry.get('id') or entry.get('teamid') or
        entry.get('team_id') or entry.get('clubid') or
        entry.get('value')
    )
    return str(raw) if raw is not None else None


def _team_name_from_entry(entry) -> str:
    if not isinstance(entry, dict):
        return ''
    return (
        entry.get('name') or entry.get('title') or
        entry.get('label') or entry.get('club_name') or ''
    )


def _resolve_ws_club_by_name(cmt_team_name: str):
    """Löst einen CMT-Teamnamen (Alias→iexact→Token) auf einen WS-Club auf.

    Der ClubExternalId-Schritt 1 entfällt absichtlich — dieser Command legt
    die Einträge ja erst an.
    """
    from game.models import Club

    if not cmt_team_name or str(cmt_team_name).lstrip('-').isdigit():
        return None

    canonical = _CMT_CLUB_NAME_ALIASES.get(cmt_team_name.strip().lower())
    if canonical:
        club = Club.objects.filter(name__iexact=canonical).first()
        if club:
            return club

    club = Club.objects.filter(name__iexact=cmt_team_name.strip()).first()
    if club:
        return club

    words = sorted(
        [w for w in cmt_team_name.split() if len(w) >= 4],
        key=len, reverse=True,
    )
    for keyword in words:
        clean = keyword.replace("'", '').replace('.', '').strip()
        if len(clean) < 4:
            continue
        qs = Club.objects.filter(name__icontains=clean)
        if qs.count() == 1:
            return qs.first()
    return None


class Command(BaseCommand):
    help = (
        'Legt ClubExternalId(CMTRACKER)-Einträge an. '
        'Ohne --apply: reiner Dry-Run (keine DB-Schreibzugriffe). '
        'Mit --apply: Einträge werden tatsächlich geschrieben. '
        'Ohne --db: hardcoded 18 Bundesliga-Clubs (kein API-Key nötig). '
        'Mit --db: alle Teams einer CMT-DB via API laden und matchen.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply', action='store_true', default=False,
            help='Schreibt Einträge in die DB. Ohne --apply: reiner Dry-Run.',
        )
        parser.add_argument(
            '--db', default=None,
            help=(
                f'Datenbank-Slug (Standard: {DB_SLUG}). '
                'Ohne --db werden die 18 Bundesliga-Clubs hardcoded eingetragen. '
                'Verfügbare DBs: python manage.py import_cmtracker --list-dbs'
            ),
        )
        parser.add_argument(
            '--force', action='store_true',
            help='Überschreibt vorhandene ClubExternalId-Einträge (ändert die '
                 'externe ID falls sich die CMT-Team-ID geändert hat). '
                 'Nur wirksam zusammen mit --apply.',
        )

    def handle(self, *args, **opts):
        from game.models import ClubExternalId, DataSource

        apply_mode = opts['apply']
        force = opts['force']
        db_slug = opts.get('db')

        if not apply_mode:
            self.stdout.write(self.style.WARNING(
                '── DRY-RUN: keine Änderungen werden in die DB geschrieben ──\n'
                '   (mit --apply tatsächlich schreiben)'
            ))
        else:
            self.stdout.write(self.style.SUCCESS('── APPLY-MODUS: Schreibzugriffe aktiv ──'))

        try:
            cmt_source = DataSource.objects.get(code='CMTRACKER')
        except DataSource.DoesNotExist:
            self.stderr.write(self.style.ERROR(
                'DataSource "CMTRACKER" existiert nicht in der DB.\n'
                'Bitte einmalig anlegen:\n'
                '  python manage.py shell -c "'
                'from game.models import DataSource; '
                'DataSource.objects.get_or_create(code=\'CMTRACKER\', '
                'defaults={\'name\': \'CMTracker\', '
                '\'url\': \'https://cmtracker.net\'})"'
            ))
            return

        if db_slug:
            self._handle_api_mode(cmt_source, db_slug, apply_mode, force)
        else:
            self._handle_hardcoded_mode(cmt_source, apply_mode, force)

    def _handle_hardcoded_mode(self, cmt_source, apply_mode: bool, force: bool):
        """Trägt alle 18 Bundesliga-Clubs mit bestätigten CMT-IDs ein."""
        from game.models import Club, ClubExternalId

        self.stdout.write(
            f'\nHardcoded-Modus: {len(BUNDESLIGA_CMT_IDS)} Bundesliga-Clubs '
            f'(DB {DB_SLUG})'
        )

        created = unchanged = conflicts = not_found = 0

        for cmt_id, ws_name in BUNDESLIGA_CMT_IDS:
            club = Club.objects.filter(name__iexact=ws_name).first()
            if club is None:
                self.stdout.write(self.style.ERROR(
                    f'  ✗ WS-Club nicht gefunden: "{ws_name}" '
                    f'(CMT-ID {cmt_id}) – übersprungen'
                ))
                not_found += 1
                continue

            conflict = ClubExternalId.objects.filter(
                source=cmt_source,
                external_id=cmt_id,
            ).exclude(club=club).select_related('club').first()
            if conflict:
                self.stdout.write(self.style.ERROR(
                    f'  ✗ CMT-ID {cmt_id} bereits für '
                    f'"{conflict.club.name}" eingetragen '
                    f'(Konflikt mit "{ws_name}") – übersprungen'
                ))
                conflicts += 1
                continue

            existing = ClubExternalId.objects.filter(
                source=cmt_source, club=club
            ).first()

            if existing:
                if existing.external_id == cmt_id and existing.db_slug == DB_SLUG:
                    self.stdout.write(
                        f'  = {club.name} → CMT {cmt_id} (unverändert)'
                    )
                    unchanged += 1
                elif force and apply_mode:
                    old = existing.external_id
                    existing.external_id = cmt_id
                    existing.db_slug = DB_SLUG
                    existing.last_seen_at = timezone.now()
                    existing.save(update_fields=[
                        'external_id', 'db_slug', 'last_seen_at', 'updated_at',
                    ])
                    self.stdout.write(self.style.WARNING(
                        f'  ↻ {club.name} → CMT {cmt_id} '
                        f'(aktualisiert, war: {old})'
                    ))
                    created += 1
                elif force and not apply_mode:
                    old = existing.external_id
                    self.stdout.write(self.style.WARNING(
                        f'  [DRY] ↻ {club.name} → CMT {cmt_id} '
                        f'(würde aktualisiert, war: {old})'
                    ))
                    created += 1
                else:
                    old = existing.external_id
                    self.stdout.write(self.style.WARNING(
                        f'  ⚠ KONFLIKT {club.name}: vorhanden id={old}, neu={cmt_id} '
                        f'(--force --apply zum Überschreiben)'
                    ))
                    conflicts += 1
            else:
                if apply_mode:
                    ClubExternalId.objects.create(
                        club=club,
                        source=cmt_source,
                        external_id=cmt_id,
                        db_slug=DB_SLUG,
                        last_seen_at=timezone.now(),
                    )
                    self.stdout.write(self.style.SUCCESS(
                        f'  ✓ {club.name} → CMT {cmt_id} (neu angelegt)'
                    ))
                else:
                    self.stdout.write(
                        f'  [DRY] ✓ {club.name} → CMT {cmt_id} (würde angelegt)'
                    )
                created += 1

        self._print_summary(apply_mode, created, unchanged, conflicts, not_found)

        if not_found > 0:
            self.stdout.write(self.style.WARNING(
                '  Hinweis: Nicht gefundene Clubs sind ggf. unter anderem Namen in '
                'der DB eingetragen. WS-Clubnamen prüfen.'
            ))
        self.stdout.write(
            '  Hinweis: Union Berlin Männer = CMT-ID 1831 '
            '(132589 = Frauen-Bundesliga, nicht verwenden).'
        )

    def _handle_api_mode(self, cmt_source, db_slug, apply_mode: bool, force: bool):
        """Lädt alle Teams via CMT-API und trägt Matches ein."""
        from game.models import ClubExternalId

        try:
            client = CmtrackerClient()
        except CmtrackerError as exc:
            raise CommandError(str(exc))

        prefix = '[DRY-RUN] ' if not apply_mode else ''
        self.stdout.write(self.style.SUCCESS(
            f'\n{prefix}API-Modus — DB: {db_slug}'
        ))

        teams = self._load_teams(client, db_slug)
        if not teams:
            raise CommandError(
                f'Keine Teams in /dbs/filters/{db_slug} gefunden. '
                f'Prüfe den DB-Slug: python manage.py import_cmtracker --list-dbs'
            )

        self.stdout.write(f'  {len(teams)} Teams aus CMT-API geladen.')

        created = unchanged = conflicts = unmatched = 0

        for entry in teams:
            team_id = _team_id_from_entry(entry)
            team_name = _team_name_from_entry(entry)

            if not team_id:
                self.stdout.write(self.style.WARNING(
                    f'  SKIP (keine ID): {entry!r:.120}'
                ))
                continue

            ws_club = _resolve_ws_club_by_name(team_name)

            if ws_club is None:
                self.stdout.write(
                    f'  KEIN MATCH  id={team_id:<8}  name={team_name!r}'
                )
                unmatched += 1
                continue

            existing = ClubExternalId.objects.filter(
                club=ws_club, source=cmt_source,
            ).first()

            if existing:
                if existing.external_id == str(team_id) and existing.db_slug == db_slug:
                    self.stdout.write(
                        f'  = (unverändert)  '
                        f'id={team_id:<8}  {team_name!r} → {ws_club.name}'
                    )
                    unchanged += 1
                elif force:
                    old_id = existing.external_id
                    if apply_mode:
                        existing.external_id = str(team_id)
                        existing.db_slug = db_slug
                        existing.last_seen_at = timezone.now()
                        existing.save(update_fields=[
                            'external_id', 'db_slug', 'last_seen_at', 'updated_at',
                        ])
                        self.stdout.write(self.style.WARNING(
                            f'  ↻ UPDATED  id={team_id:<8}  '
                            f'{team_name!r} → {ws_club.name}  (war: {old_id})'
                        ))
                    else:
                        self.stdout.write(self.style.WARNING(
                            f'  [DRY] ↻ UPDATE  id={team_id:<8}  '
                            f'{team_name!r} → {ws_club.name}  (war: {old_id})'
                        ))
                    created += 1
                else:
                    self.stdout.write(self.style.WARNING(
                        f'  ⚠ KONFLIKT  '
                        f'vorhanden: id={existing.external_id}  '
                        f'neu: id={team_id}  '
                        f'{ws_club.name}  (--force --apply zum Überschreiben)'
                    ))
                    conflicts += 1
            else:
                if apply_mode:
                    ClubExternalId.objects.create(
                        club=ws_club,
                        source=cmt_source,
                        external_id=str(team_id),
                        db_slug=db_slug,
                        last_seen_at=timezone.now(),
                    )
                    self.stdout.write(self.style.SUCCESS(
                        f'  ✓ CREATED  id={team_id:<8}  {team_name!r} → {ws_club.name}'
                    ))
                else:
                    self.stdout.write(
                        f'  [DRY] ✓ CREATE  id={team_id:<8}  {team_name!r} → {ws_club.name}'
                    )
                created += 1

        self._print_summary(apply_mode, created, unchanged, conflicts, unmatched)

        if unmatched:
            self.stdout.write(
                '  Tipp: Nicht gematchte Teams in _CMT_CLUB_NAME_ALIASES ergänzen, '
                'dann erneut ausführen.'
            )

    def _print_summary(
        self,
        apply_mode: bool,
        created: int,
        unchanged: int,
        conflicts: int,
        not_found_or_unmatched: int,
    ):
        mode_label = 'Fertig' if apply_mode else 'Dry-Run Vorschau'
        created_label = 'angelegt' if apply_mode else 'würden angelegt'
        self.stdout.write('')
        summary = (
            f'{mode_label}: '
            f'{created} {created_label} / '
            f'{unchanged} unverändert / '
            f'{conflicts} Konflikte'
        )
        if not_found_or_unmatched:
            summary += f' / {not_found_or_unmatched} nicht gefunden'
        if conflicts > 0:
            self.stdout.write(self.style.WARNING(summary))
        else:
            self.stdout.write(self.style.SUCCESS(summary))

    def _load_teams(self, client: CmtrackerClient, db_slug: str) -> list[dict]:
        """Kombiniert Teams aus /dbs/filters und /teams (Deduplizierung per team_id)."""
        seen_ids: set[str] = set()
        teams: list[dict] = []

        try:
            data = client.get_db_filters(db_slug)
            for entry in _extract_teams_from_filters(data):
                tid = _team_id_from_entry(entry)
                if tid and tid not in seen_ids:
                    teams.append(entry)
                    seen_ids.add(tid)
        except CmtrackerError as exc:
            self.stdout.write(self.style.WARNING(
                f'  /dbs/filters/{db_slug} nicht verfügbar: {exc}'
            ))

        if not teams:
            self.stdout.write(
                '  /dbs/filters lieferte keine Teams — versuche /teams paginiert …'
            )
            try:
                for team in client.iter_teams(db=db_slug, limit=100, max_pages=30):
                    tid = str(
                        team.get('teamid') or
                        _dig(team, 'info.teamid') or
                        team.get('id') or
                        team.get('clubid') or ''
                    )
                    name = (
                        _dig(team, 'info.teamname') or
                        team.get('name') or team.get('title') or
                        team.get('club_name') or ''
                    )
                    if tid and tid not in seen_ids:
                        teams.append({'id': tid, 'name': name})
                        seen_ids.add(tid)
            except CmtrackerError as exc:
                self.stdout.write(self.style.WARNING(
                    f'  /teams paginiert nicht verfügbar: {exc}'
                ))

        return teams
