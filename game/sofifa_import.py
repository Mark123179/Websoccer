"""SoFIFA-CSV-Import-Service.

Gemeinsam genutzte Importlogik fuer den CLI-Command
(``manage.py import_sofifa_csv``) und den Creator-Mode-Upload
(``creator_import_ratings``).

Statt SoFIFA live zu scrapen (Cloudflare blockiert das) werden EA/SoFIFA-
Ratings aus einer CSV importiert. Das Matching laeuft primaer ueber die
SoFIFA-ID (gespeichert als ``PlayerExternalId`` mit SOFIFA-DataSource); ohne
verknuepfte ID greift ein Fallback ueber Name (+ optional Verein), der die
SoFIFA-ID anschliessend dauerhaft verknuepft.

Akzeptiert sowohl die vereinfachten deutschen/englischen Spaltennamen als auch
das vollstaendige SoFIFA-Export-Format (``player_id``, ``attacking_finishing``,
``goalkeeping_reflexes`` …). Nur die in der CSV vorhandenen Attributspalten
werden geschrieben; nicht gelistete Attribute bleiben unveraendert.

Jeder echte Import schreibt einen ``SourceImportRun`` (Import-Log) mit Quelle,
Version, Dateiname, Zeitpunkt und Bilanz. Aenderungen pro Spieler landen
zusaetzlich als ``PlayerEditLog`` (Change-Log). Nach einem echten Lauf werden
die Spielstaerken neu berechnet.
"""

import csv
import difflib
import html
import io
import re
import unicodedata

from django.core.management import call_command
from django.db import transaction
from django.utils import timezone

from .models import (
    Club,
    DataSource,
    Player,
    PlayerEditLog,
    PlayerExternalId,
    PlayerSourceRating,
    PlayerSourceRatingSnapshot,
    SourceImportRun,
)


OUTFIELD_ATTR_COLUMNS = [
    'tempo', 'ausdauer', 'kraft', 'technik', 'dribbling', 'passspiel',
    'flanken', 'abschluss', 'kopfball', 'zweikampf', 'defensivstellung',
    'uebersicht', 'teamwork', 'ecken', 'freistoss', 'elfmeter',
]
GK_ATTR_COLUMNS = [
    'tw_reflexe', 'tw_fangsicherheit', 'tw_eins_gegen_eins',
    'tw_stellungsspiel', 'tw_passen',
]
ALL_ATTR_COLUMNS = OUTFIELD_ATTR_COLUMNS + GK_ATTR_COLUMNS

# Header-Alias -> kanonischer Schluessel (Rating + Attribute).
# Deckt sowohl vereinfachte Namen als auch das volle SoFIFA-Export-Format ab.
# Es ist bewusst nur EINE Quellspalte je Zielattribut gemappt, damit beim vollen
# SoFIFA-Export keine Spalte eine andere ueberschreibt (z. B. nur ``pace`` -> tempo,
# nicht zusaetzlich movement_*).
COLUMN_ALIASES = {
    # Identitaet
    'player_id': 'sofifa_id', 'sofifa_id': 'sofifa_id', 'sofifa': 'sofifa_id',
    'sofifaid': 'sofifa_id', 'id': 'sofifa_id',
    'short_name': 'name_short',
    'long_name': 'name', 'name': 'name', 'full_name': 'name',
    'fullname': 'name', 'spieler': 'name', 'player': 'name',
    'club_name': 'club', 'club': 'club', 'verein': 'club', 'team': 'club',
    'overall': 'rating', 'overall_rating': 'rating', 'rating': 'rating',
    'ovr': 'rating', 'ova': 'rating', 'gesamt': 'rating',
    'potential': 'potential', 'pot': 'potential',
    'player_url': 'profile_url', 'profile_url': 'profile_url',
    'url': 'profile_url', 'sofifa_url': 'profile_url',
    # Feldspieler-Attribute
    'pace': 'tempo',
    'power_stamina': 'ausdauer', 'stamina': 'ausdauer',
    'power_strength': 'kraft', 'strength': 'kraft',
    'dribbling': 'dribbling',
    'attacking_short_passing': 'passspiel', 'short_passing': 'passspiel',
    'attacking_crossing': 'flanken', 'crossing': 'flanken',
    'attacking_finishing': 'abschluss', 'finishing': 'abschluss',
    'attacking_heading_accuracy': 'kopfball',
    'heading_accuracy': 'kopfball', 'heading': 'kopfball',
    'defending_standing_tackle': 'zweikampf', 'standing_tackle': 'zweikampf',
    'defending_marking_awareness': 'defensivstellung',
    'defensive_awareness': 'defensivstellung',
    'mentality_vision': 'uebersicht', 'vision': 'uebersicht',
    'mentality_penalties': 'elfmeter', 'penalties': 'elfmeter',
    'skill_fk_accuracy': 'freistoss', 'fk_accuracy': 'freistoss',
    'free_kick': 'freistoss',
    # Torwart-Attribute
    'goalkeeping_reflexes': 'tw_reflexe', 'gk_reflexes': 'tw_reflexe',
    'reflexes': 'tw_reflexe',
    'goalkeeping_handling': 'tw_fangsicherheit', 'gk_handling': 'tw_fangsicherheit',
    'goalkeeping_positioning': 'tw_stellungsspiel',
    'gk_positioning': 'tw_stellungsspiel',
    'goalkeeping_kicking': 'tw_passen', 'gk_kicking': 'tw_passen',
}
# Attributspalten duerfen auch unter ihrem eigenen Namen stehen.
for _col in ALL_ATTR_COLUMNS:
    COLUMN_ALIASES.setdefault(_col, _col)

# Meta-Spalten (Version + Biografie) — werden nur fuer Versionsableitung und
# als raw_payload protokolliert, nicht in Spielerstammdaten geschrieben.
META_ALIASES = {
    'fifa_version': 'fifa_version',
    'fifa_update': 'fifa_update',
    'fifa_update_date': 'fifa_update_date', 'update_date': 'fifa_update_date',
    'player_positions': 'positions', 'positions': 'positions',
    'position': 'positions',
    'age': 'age',
    'height_cm': 'height_cm', 'height': 'height_cm',
    'weight_kg': 'weight_kg', 'weight': 'weight_kg',
    'preferred_foot': 'preferred_foot', 'foot': 'preferred_foot',
}

SOURCE_SOFIFA = 'sofifa'

# Torwart-Positionscode (SoFIFA liefert GK-Stats fuer ALLE Spieler; Feldspieler
# sollen aber keine tw_*-Werte und Torwarte keine Feldspieler-Attribute bekommen).
GK_POSITION_CODES = {'TW', 'GK'}


def filter_attrs_for_player(player, attrs):
    is_gk = (player.position or '').upper() in GK_POSITION_CODES
    allowed = set(GK_ATTR_COLUMNS if is_gk else OUTFIELD_ATTR_COLUMNS)
    return {k: v for k, v in attrs.items() if k in allowed}


def normalize_header(raw):
    raw = (raw or '').strip().lstrip('\ufeff').lower()
    raw = raw.replace('-', '_').replace(' ', '_')
    raw = re.sub(r'[^a-z0-9_]', '', raw)
    raw = re.sub(r'_+', '_', raw).strip('_')
    return raw


def normalize_name(name):
    name = html.unescape(name or '')
    name = unicodedata.normalize('NFKD', name)
    name = name.encode('ASCII', 'ignore').decode('ASCII')
    return re.sub(r'[^a-zA-Z]', '', name).lower()


def name_similarity(a, b):
    if not a or not b:
        return 0
    if a == b:
        return 200
    if a in b or b in a:
        return 150
    return int(difflib.SequenceMatcher(None, a, b).ratio() * 100)


class ImportError_(Exception):
    """Fehler in Datei/Header, der den gesamten Import abbricht."""


def read_csv_rows(source, *, delimiter=',', encoding='utf-8-sig'):
    """Liest CSV aus Pfad (str) oder Bytes/Text in eine Zeilenliste."""
    if isinstance(source, (bytes, bytearray)):
        text = source.decode(encoding, errors='replace')
        fh = io.StringIO(text)
    elif isinstance(source, str):
        try:
            fh = open(source, newline='', encoding=encoding)
        except FileNotFoundError:
            raise ImportError_(f'CSV-Datei nicht gefunden: {source}')
        except OSError as exc:
            raise ImportError_(f'CSV konnte nicht gelesen werden: {exc}')
    else:
        # bereits ein Datei-/Text-Handle
        fh = source
    try:
        reader = csv.reader(fh, delimiter=delimiter)
        rows = list(reader)
    finally:
        if isinstance(source, str):
            fh.close()
    if not rows:
        raise ImportError_('CSV ist leer.')
    return rows


def build_header_map(header_row):
    """Spaltenindex -> kanonischer Schluessel (Attribute + Meta)."""
    header_map = {}
    for idx, cell in enumerate(header_row):
        norm = normalize_header(cell)
        key = COLUMN_ALIASES.get(norm) or META_ALIASES.get(norm)
        if key and key not in header_map:
            header_map[key] = idx
    return header_map


def derive_version(rows, header_map):
    """Leitet eine Versionskennung aus fifa_version/fifa_update_date ab."""
    fv_idx = header_map.get('fifa_version')
    fd_idx = header_map.get('fifa_update_date')
    for raw_row in rows[1:]:
        if not any(c.strip() for c in raw_row):
            continue
        fv = raw_row[fv_idx].strip() if fv_idx is not None and fv_idx < len(raw_row) else ''
        fd = raw_row[fd_idx].strip() if fd_idx is not None and fd_idx < len(raw_row) else ''
        if fv and fd:
            return f'FC{fv}_{fd}'
        if fd:
            return fd
        if fv:
            return f'FC{fv}'
        break
    return ''


def _parse_int(raw, lo, hi, field, required=False):
    raw = (raw or '').strip()
    if not raw:
        if required:
            raise ValueError(f'{field} fehlt')
        return None
    try:
        val = int(float(raw))
    except ValueError:
        raise ValueError(f'{field} ist keine Zahl: {raw!r}')
    if not (lo <= val <= hi):
        raise ValueError(f'{field}={val} ausserhalb {lo}-{hi}')
    return val


def parse_row(raw_row, header_map):
    def cell(key):
        idx = header_map.get(key)
        if idx is None or idx >= len(raw_row):
            return ''
        return raw_row[idx].strip()

    sofifa_id = cell('sofifa_id')
    if not sofifa_id:
        raise ValueError('sofifa_id fehlt')

    rating = _parse_int(cell('rating'), 0, 100, 'rating', required=True)
    potential = _parse_int(cell('potential'), 0, 100, 'potential')

    attrs = {}
    for col in ALL_ATTR_COLUMNS:
        if col in header_map:
            val = _parse_int(cell(col), 0, 99, col)
            if val is not None:
                attrs[col] = val

    meta = {}
    for key in ('positions', 'age', 'height_cm', 'weight_kg', 'preferred_foot',
                'fifa_version', 'fifa_update', 'fifa_update_date'):
        v = cell(key)
        if v:
            meta[key] = v

    return {
        'sofifa_id': sofifa_id,
        'name': cell('name') or cell('name_short'),
        'club': cell('club'),
        'rating': rating,
        'potential': potential,
        'profile_url': cell('profile_url'),
        'attrs': attrs,
        'meta': meta,
    }


def match_player(parsed, sofifa_ds):
    """Primaer ueber sofifa_id, sonst Fallback ueber Name (+ Verein)."""
    if sofifa_ds is not None:
        ext = (
            PlayerExternalId.objects
            .filter(source=sofifa_ds, external_id=parsed['sofifa_id'])
            .select_related('player', 'player__club')
            .first()
        )
        if ext:
            return ext.player, 'id'

    name = parsed.get('name')
    if not name:
        return None, None

    candidates = Player.objects.select_related('club').all()
    club_name = parsed.get('club')
    if club_name:
        club_norm = normalize_name(club_name)
        club_ids = [
            c.id for c in Club.objects.all()
            if club_norm and (
                club_norm in normalize_name(c.name)
                or normalize_name(c.name) in club_norm
                or club_norm in normalize_name(c.short_name or '')
            )
        ]
        if club_ids:
            candidates = candidates.filter(club_id__in=club_ids)

    target = normalize_name(name)
    scored = []
    for p in candidates:
        score = name_similarity(target, normalize_name(p.full_name))
        if score >= 150:
            scored.append((score, p))

    if not scored:
        return None, None
    scored.sort(key=lambda t: t[0], reverse=True)
    if len(scored) > 1 and scored[0][0] == scored[1][0]:
        return None, None  # mehrdeutig
    return scored[0][1], 'name'


def diff_row(player, parsed):
    """Berechnet die Aenderungsliste ohne zu schreiben."""
    existing = player.source_ratings.filter(
        source=PlayerSourceRating.SOURCE_EA,
    ).first()
    is_new = existing is None

    diff_lines = []
    if is_new:
        diff_lines.append(
            f"EA/SoFIFA: Quelldaten erstmals angelegt (Rating {parsed['rating']})"
        )
    else:
        if existing.rating != parsed['rating']:
            diff_lines.append(
                f"EA/SoFIFA Rating: {existing.rating} → {parsed['rating']}"
            )
        if parsed['potential'] is not None and existing.potential != parsed['potential']:
            old_p = existing.potential if existing.potential is not None else '–'
            diff_lines.append(f"EA/SoFIFA Potential: {old_p} → {parsed['potential']}")
        for col, val in parsed['attrs'].items():
            old_val = getattr(existing, col, None)
            if old_val != val:
                diff_lines.append(
                    f"{col}: {old_val if old_val is not None else '–'} → {val}"
                )

    if is_new:
        action = 'new'
    elif diff_lines:
        action = 'updated'
    else:
        action = 'unchanged'
    return action, diff_lines


def apply_row(player, parsed, sofifa_ds, today, version):
    """Schreibt Quelldaten, Snapshot, ExternalId und Change-Log."""
    with transaction.atomic():
        defaults = {
            'rating': parsed['rating'],
            'source_url': parsed['profile_url'],
            'source_version': version or 'SoFIFA CSV-Import',
            'checked_at': today,
        }
        if parsed['potential'] is not None:
            defaults['potential'] = parsed['potential']
        defaults.update(parsed['attrs'])

        PlayerSourceRating.objects.update_or_create(
            player=player,
            source=PlayerSourceRating.SOURCE_EA,
            defaults=defaults,
        )

        PlayerSourceRatingSnapshot.objects.update_or_create(
            player=player,
            source=sofifa_ds,
            recorded_at=today,
            defaults={
                'rating': parsed['rating'],
                'potential': parsed['potential'],
                'source_url': parsed['profile_url'],
                'source_version': version or 'SoFIFA CSV-Import',
                'update_current': False,
                'raw_payload': {
                    'sofifa_id': parsed['sofifa_id'],
                    'attrs': parsed['attrs'],
                    'meta': parsed['meta'],
                },
            },
        )

        PlayerExternalId.objects.update_or_create(
            player=player,
            source=sofifa_ds,
            defaults={
                'external_id': parsed['sofifa_id'],
                'profile_url': parsed['profile_url'],
                'is_primary': False,
            },
        )


def run_import(source, *, version='', file_name='', dry_run=False,
               created_by=None, recalculate=True, delimiter=',',
               encoding='utf-8-sig', row_limit=None):
    """Fuehrt den Import aus und liefert ein Ergebnis-Dict.

    ``source`` ist ein Dateipfad (str), Bytes oder ein offenes Handle.
    Bei ``dry_run`` wird nichts geschrieben.

    Rueckgabe::

        {
          'stats': {new, updated, unchanged, unmatched, error},
          'rows': [ {line, action, mode, name, club, diff} ],
          'unmatched': [str, ...],
          'errors': [str, ...],
          'version': str,
          'file_name': str,
          'dry_run': bool,
          'import_run_id': int | None,
          'recalculated': bool,
        }
    """
    rows = read_csv_rows(source, delimiter=delimiter, encoding=encoding)
    header_map = build_header_map(rows[0])
    if 'sofifa_id' not in header_map:
        raise ImportError_(
            'CSV-Header braucht eine sofifa_id-Spalte '
            '(Aliase: player_id, sofifa, id).'
        )
    if 'rating' not in header_map:
        raise ImportError_(
            'CSV-Header braucht eine rating-Spalte (Aliase: overall, ovr).'
        )

    if not version:
        version = derive_version(rows, header_map)

    # DataSource (Lookup-Tabelle): im Dry-Run nicht anlegen.
    try:
        sofifa_ds = DataSource.objects.get(code=DataSource.CODE_SOFIFA)
    except DataSource.DoesNotExist:
        if dry_run:
            sofifa_ds = None
        else:
            sofifa_ds = DataSource.objects.create(
                code=DataSource.CODE_SOFIFA, name='SoFIFA',
            )

    today = timezone.localdate()
    stats = {'new': 0, 'updated': 0, 'unchanged': 0, 'unmatched': 0, 'error': 0}
    result_rows = []
    unmatched = []
    errors = []

    for line_no, raw_row in enumerate(rows[1:], start=2):
        if row_limit is not None and len(result_rows) >= row_limit:
            break
        if not any(cell.strip() for cell in raw_row):
            continue
        try:
            parsed = parse_row(raw_row, header_map)
        except ValueError as exc:
            stats['error'] += 1
            msg = f'Zeile {line_no}: {exc}'
            errors.append(msg)
            result_rows.append({
                'line': line_no, 'action': 'error', 'mode': None,
                'name': '', 'club': '', 'diff': [str(exc)],
            })
            continue

        player, mode = match_player(parsed, sofifa_ds)
        if player:
            parsed['attrs'] = filter_attrs_for_player(player, parsed['attrs'])
        if not player:
            stats['unmatched'] += 1
            label = parsed.get('name') or f"sofifa_id={parsed['sofifa_id']}"
            unmatched.append(f'Zeile {line_no}: {label}')
            result_rows.append({
                'line': line_no, 'action': 'unmatched', 'mode': None,
                'name': label, 'club': parsed.get('club', ''), 'diff': [],
            })
            continue

        action, diff_lines = diff_row(player, parsed)
        if not dry_run and action in ('new', 'updated'):
            apply_row(player, parsed, sofifa_ds, today, version)
            PlayerEditLog.objects.create(
                player=player,
                changed_by=created_by,
                category=PlayerEditLog.CATEGORY_SOURCE,
                summary='\n'.join(diff_lines),
            )
        stats[action] += 1
        result_rows.append({
            'line': line_no,
            'action': action,
            'mode': mode,
            'name': player.full_name,
            'club': player.club.name if player.club else '',
            'diff': diff_lines,
        })

    changed = stats['new'] + stats['updated']
    import_run_id = None
    recalculated = False

    if not dry_run:
        run = SourceImportRun.objects.create(
            source=SOURCE_SOFIFA,
            version=version,
            file_name=file_name or '',
            dry_run=False,
            created_by=created_by,
            total_rows=sum(stats.values()),
            count_new=stats['new'],
            count_updated=stats['updated'],
            count_unchanged=stats['unchanged'],
            count_unmatched=stats['unmatched'],
            count_error=stats['error'],
            unmatched=unmatched,
        )
        import_run_id = run.id

        if changed and recalculate:
            call_command('calculate_player_strengths')
            recalculated = True

    return {
        'stats': stats,
        'rows': result_rows,
        'unmatched': unmatched,
        'errors': errors,
        'version': version,
        'file_name': file_name or '',
        'dry_run': dry_run,
        'import_run_id': import_run_id,
        'recalculated': recalculated,
    }
