"""
CMTracker-Importer: ZIP-Archiv (Erstimport) oder einzelne CSV (Update).

Befehl:
    python manage.py import_sofifa_zip pfad/zur/datei.zip
    python manage.py import_sofifa_zip pfad/zur/datei.csv
    python manage.py import_sofifa_zip --dry-run pfad/...

Workflow:
  1. Lesen + Deduplizieren nach info.playerid
  2. Bestehende Spieler via PlayerExternalId (CMTracker) matchen
  3. Fallback: exakter Namens-Match
  4. Matched  → PlayerSourceRating (source=CMTRACKER) anlegen/aktualisieren
  5. Neu      → Player + PlayerSourceRating + PlayerExternalId anlegen
  6. Stärken neu berechnen (es sei denn --skip-strengths)
"""

import csv
import io
import zipfile
from datetime import date, datetime

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from game.models import (
    Club,
    DataSource,
    Player,
    PlayerExternalId,
    PlayerSourceRating,
)

# ── Spalten-Mapping CSV → PlayerSourceRating-Feld ────────────────────────────
ATTR_MAP = {
    'tempo':              'attributes.sprintspeed',
    'ausdauer':           'attributes.stamina',
    'kraft':              'attributes.strength',
    'dribbling':          'attributes.dribbling',
    'passspiel':          'attributes.shortpassing',
    'flanken':            'attributes.crossing',
    'abschluss':          'attributes.finishing',
    'kopfball':           'attributes.headingaccuracy',
    'zweikampf':          'attributes.standingtackle',
    'defensivstellung':   'attributes.marking',
    'uebersicht':         'attributes.vision',
    'ecken':              'attributes.curve',
    'freistoss':          'attributes.freekickaccuracy',
    'elfmeter':           'attributes.penalties',
    'tw_reflexe':         'attributes.gkreflexes',
    'tw_fangsicherheit':  'attributes.gkhandling',
    'tw_eins_gegen_eins': 'attributes.gkdiving',
    'tw_stellungsspiel':  'attributes.gkpositioning',
    'tw_passen':          'attributes.gkkicking',
}

POSITION_MAP = {
    'GK': 'TW', 'CB': 'IV', 'LB': 'LV', 'RB': 'RV',
    'CDM': 'DM', 'CM': 'ZM', 'LM': 'LM', 'RM': 'RM',
    'CAM': 'OM', 'LW': 'LF', 'RW': 'RF', 'ST': 'ST',
}

FOOT_MAP = {'Left': 'L', 'Right': 'R', 'Both': 'B'}

FREE_AGENT_MARKERS = {'NG - FA', '', None}


def _int(val, lo=0, hi=100):
    try:
        v = int(float(val))
        return max(lo, min(hi, v))
    except (TypeError, ValueError):
        return None


def _parse_date(raw):
    if not raw:
        return None
    try:
        return datetime.strptime(raw[:10], '%Y-%m-%d').date()
    except ValueError:
        return None


def _age_from_dob(dob):
    if not dob:
        return None
    today = date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def _read_csv(filelike):
    text = filelike.read().decode('utf-8', errors='replace')
    return list(csv.DictReader(io.StringIO(text)))


def _load_zip(path):
    rows = []
    with zipfile.ZipFile(path) as z:
        for name in z.namelist():
            if name.lower().endswith('.csv'):
                with z.open(name) as f:
                    rows.extend(_read_csv(f))
    return rows


def _load_csv(path):
    with open(path, 'rb') as f:
        return _read_csv(f)


def _dedupe(rows):
    seen = {}
    for row in rows:
        pid = (row.get('info.playerid') or '').strip()
        if pid and pid not in seen:
            seen[pid] = row
    return seen


def _parse_attrs(row):
    attrs = {}
    for field, col in ATTR_MAP.items():
        v = _int(row.get(col), 0, 99)
        if v is not None:
            attrs[field] = v
    return attrs


def _map_position(csv_pos):
    return POSITION_MAP.get((csv_pos or '').strip().upper(), '')


def _parse_other_positions(raw):
    if not raw or raw.strip() == '-':
        return []
    parts = [p.strip() for p in raw.replace('|', ',').split(',')]
    return [_map_position(p) for p in parts if _map_position(p)]


class Command(BaseCommand):
    help = 'Importiert CMTracker-CSV (ZIP oder einzelne Datei): Attribute + neue Spieler.'

    def add_arguments(self, parser):
        parser.add_argument('file', help='Pfad zur .zip oder .csv Datei')
        parser.add_argument('--dry-run', action='store_true',
                            help='Nur simulieren, nichts schreiben')
        parser.add_argument('--skip-strengths', action='store_true',
                            help='Stärkenberechnung nicht automatisch starten')

    def handle(self, *args, **options):
        path = options['file']
        dry = options['dry_run']
        skip_str = options['skip_strengths']

        if path.lower().endswith('.zip'):
            self.stdout.write(f'Lese ZIP: {path}')
            raw = _load_zip(path)
        else:
            self.stdout.write(f'Lese CSV: {path}')
            raw = _load_csv(path)

        self.stdout.write(f'  {len(raw)} Zeilen gelesen')
        rows = _dedupe(raw)
        self.stdout.write(f'  {len(rows)} unique Spieler (nach Deduplizierung)')

        if dry:
            self.stdout.write(self.style.WARNING('[DRY-RUN] keine DB-Änderungen'))

        stats = self._run_import(rows, dry)

        self.stdout.write(self.style.SUCCESS(
            f'\nErgebnis: {stats["updated"]} aktualisiert | '
            f'{stats["created"]} neu angelegt | '
            f'{stats["skipped"]} übersprungen'
        ))

        if not dry and not skip_str:
            self.stdout.write('Stärken neu berechnen …')
            call_command('calculate_player_strengths', verbosity=0)
            self.stdout.write(self.style.SUCCESS('Stärken aktualisiert.'))

    @transaction.atomic
    def _run_import(self, rows, dry):
        sofifa_src = DataSource.objects.get(code=DataSource.CODE_CMTRACKER)

        # ── Lookups aufbauen ─────────────────────────────────────────────────
        ext_map = {
            eid.external_id: eid.player_id
            for eid in PlayerExternalId.objects.filter(source=sofifa_src)
        }
        name_map = {
            (p.first_name.lower(), p.last_name.lower()): p
            for p in Player.objects.all()
        }
        rating_map = {
            sr.player_id: sr
            for sr in PlayerSourceRating.objects.filter(source=PlayerSourceRating.SOURCE_CMTRACKER)
        }
        club_map = {
            c.name.lower(): c
            for c in Club.objects.all()
        }

        stats = {'updated': 0, 'created': 0, 'skipped': 0}

        new_players = []
        rating_creates = []
        rating_updates = []
        ext_creates = []

        for sofifa_id, row in rows.items():
            first = (row.get('info.name.firstname') or '').strip()
            last  = (row.get('info.name.lastname') or '').strip()
            if not first and not last:
                knownas = (row.get('info.name.knownas') or '').strip()
                parts = knownas.split(None, 1)
                first = parts[0] if parts else ''
                last  = parts[1] if len(parts) > 1 else ''

            if not last:
                stats['skipped'] += 1
                continue

            rating_val = _int(row.get('info.overallrating'), 1, 99)
            if rating_val is None:
                stats['skipped'] += 1
                continue

            attrs = _parse_attrs(row)
            potential = _int(row.get('info.potential'), 1, 99)
            headshot  = (row.get('info.headshot') or '').strip()
            pos       = _map_position(row.get('primary_position', ''))

            # ── Spieler finden ───────────────────────────────────────────────
            player_id = ext_map.get(sofifa_id)
            player = None

            if player_id:
                player = Player.objects.filter(id=player_id).first()

            if player is None:
                player = name_map.get((first.lower(), last.lower()))

            # ── Bestehend: Rating + Attribute aktualisieren ──────────────────
            if player:
                sr = rating_map.get(player.id)
                update_fields = dict(attrs, rating=rating_val)
                if potential is not None:
                    update_fields['potential'] = potential
                if headshot:
                    update_fields['source_url'] = headshot

                if sr:
                    for k, v in update_fields.items():
                        setattr(sr, k, v)
                    rating_updates.append(sr)
                else:
                    rating_creates.append(PlayerSourceRating(
                        player=player, source=PlayerSourceRating.SOURCE_CMTRACKER, **update_fields
                    ))
                    rating_map[player.id] = None

                if player_id is None and not dry:
                    ext_creates.append(PlayerExternalId(
                        player=player,
                        source=sofifa_src,
                        external_id=sofifa_id,
                        profile_url=headshot,
                    ))
                    ext_map[sofifa_id] = player.id

                stats['updated'] += 1

            # ── Neu: Player anlegen ──────────────────────────────────────────
            else:
                club_name = (row.get('info.teams.club_team.name') or '').strip()
                club = None
                if club_name and club_name not in FREE_AGENT_MARKERS:
                    club = club_map.get(club_name.lower())

                dob = _parse_date(row.get('info.birthdate'))
                age = _age_from_dob(dob)
                if age is None:
                    raw_age = _int(row.get('info.age'), 14, 50)
                    age = raw_age if raw_age else 25

                contract_raw = _parse_date(row.get('info.contract.enddate'))

                mv_raw = (row.get('info.valueEUR') or '').strip()
                try:
                    market_value = int(float(mv_raw)) if mv_raw else 0
                except ValueError:
                    market_value = 0

                height = _int(row.get('info.height'), 140, 220)
                foot = FOOT_MAP.get(row.get('info.preferredfoot', '').strip(), '')
                nation = (row.get('info.nation.name') or '').strip()
                jersey = _int(row.get('info.teams.club_team.jerseynumber'), 1, 99)

                others = _parse_other_positions(row.get('other_positions', ''))

                p = Player(
                    first_name=first,
                    last_name=last,
                    position=pos,
                    age=age,
                    date_of_birth=dob,
                    height_cm=height,
                    strong_foot=foot,
                    nationalities=nation,
                    club=club,
                    market_value=market_value,
                    contract_until=contract_raw,
                    shirt_number=jersey if jersey else None,
                    secondary_position_1=others[0] if len(others) > 0 else '',
                    secondary_position_2=others[1] if len(others) > 1 else '',
                )
                new_players.append((p, sofifa_id, headshot, rating_val, potential, attrs))
                stats['created'] += 1

        # ── Bulk-Operationen ─────────────────────────────────────────────────
        if not dry:
            # PlayerSourceRating Updates
            if rating_updates:
                update_cols = list(ATTR_MAP.keys()) + ['rating', 'potential', 'source_url']
                PlayerSourceRating.objects.bulk_update(
                    rating_updates,
                    fields=update_cols,
                    batch_size=500,
                )
                self.stdout.write(f'  {len(rating_updates)} Ratings aktualisiert')

            # PlayerSourceRating Creates (bestehende Spieler ohne CMTracker-Zeile)
            if rating_creates:
                PlayerSourceRating.objects.bulk_create(rating_creates, batch_size=500,
                                                       ignore_conflicts=True)
                self.stdout.write(f'  {len(rating_creates)} neue CMTracker-Ratings (bestehende Spieler)')

            # Neue Spieler anlegen
            if new_players:
                player_objs = [t[0] for t in new_players]
                created = Player.objects.bulk_create(player_objs, batch_size=500)
                self.stdout.write(f'  {len(created)} neue Spieler angelegt')

                new_ext = []
                new_ratings = []
                for p, sofifa_id, headshot, rating_val, potential, attrs in new_players:
                    update_fields = dict(attrs, rating=rating_val)
                    if potential is not None:
                        update_fields['potential'] = potential
                    if headshot:
                        update_fields['source_url'] = headshot
                    new_ratings.append(PlayerSourceRating(
                        player=p, source=PlayerSourceRating.SOURCE_CMTRACKER, **update_fields
                    ))
                    new_ext.append(PlayerExternalId(
                        player=p,
                        source=sofifa_src,
                        external_id=sofifa_id,
                        profile_url=headshot,
                    ))

                PlayerSourceRating.objects.bulk_create(new_ratings, batch_size=500,
                                                       ignore_conflicts=True)
                PlayerExternalId.objects.bulk_create(new_ext, batch_size=500,
                                                     ignore_conflicts=True)
                self.stdout.write(f'  {len(new_ext)} PlayerExternalIds (CMTracker) angelegt')

            # ExternalIds für bestehende Spieler ohne ID
            if ext_creates:
                PlayerExternalId.objects.bulk_create(ext_creates, batch_size=500,
                                                     ignore_conflicts=True)

        return stats
