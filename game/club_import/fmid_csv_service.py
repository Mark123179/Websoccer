"""CSV-Import zur Sicherung der Spieler-Identität + FM-ID (Creator-Mode).

Pro Verein wird eine Moneyball-Export-CSV hochgeladen. Die CSV stellt **nur die
Identität** sicher (Name, Geburtsdatum, Nationalitäten) und stempelt vor allem
die ``fm_inside_id`` (Spalte „Unique ID"). Sie enthält **keine** Stärke,
Attribute oder Marktwerte — diese bleiben ``NULL`` und werden später vom lokalen
Importer per FM-ID-Direktaufruf angereichert.

Spalten-Mapping (immer gleich, ``;``-getrennt):
    Verein       → aktueller Verein. Leih-Erkennung: ``Verein != Zielverein``
                   ⇒ der Spieler ist verliehen → Vereinslos-Pool.
    Ansässig in  → ignoriert
    Liga         → ignoriert
    Unique ID    → fm_inside_id (Pflicht)
    Aufgestellt  → ignoriert
    Spieler      → Name (erstes Token = Vorname, Rest = Nachname)
    2. Nation    → zweite Nationalität
    Nation       → Haupt-Nationalität
    Geb.         → Geburtsdatum im Format ``T.M.JJJJ``

Matching-/Schreibregeln (konservativ — nie kuratierte Daten überschreiben):
    1. Treffer per ``fm_inside_id`` (stark): Spieler ist bereits verknüpft.
       Es werden nur leere Felder ergänzt; Vereinszuordnung nur gesetzt, wenn
       aktuell keiner vorhanden ist.
    2. Treffer per Name + Geburtsdatum (schwach): die ``fm_inside_id`` wird
       nachgetragen (Backfill). Eine ID-Kollision ist ausgeschlossen, weil ein
       ID-Treffer Vorrang hätte (Regel 1).
    3. Kein Treffer: neue Spieler-Hülle (Identität + FM-ID, ohne Werte).

Verein/Leihe:
    - ``Verein == Zielverein`` → ``club = Zielverein``, ``loan_status='none'``.
    - ``Verein != Zielverein`` → ``club = None`` (Vereinslos),
      ``loan_status='loaned_out'``, ``real_life_club = Zielverein``. Der
      Ziel-Leihverein wird nur protokolliert, nicht als Platzhalter angelegt.
"""

import csv
import io
from datetime import date, datetime

from django.db import transaction

from .normalization import normalize_name
from .matching import find_existing_player

# Erwartete Header (nach Normalisierung auf Kleinbuchstaben + getrimmt).
COL_VEREIN = 'verein'
COL_UNIQUE_ID = 'unique id'
COL_SPIELER = 'spieler'
COL_NATION = 'nation'
COL_NATION2 = '2. nation'
COL_GEB = 'geb.'

REQUIRED_COLS = (COL_UNIQUE_ID, COL_SPIELER)

ACTION_NEW = 'new'
ACTION_UPDATED = 'updated'
ACTION_UNCHANGED = 'unchanged'
ACTION_ERROR = 'error'


def _norm_header(value):
    return (value or '').replace('\ufeff', '').strip().lower()


def _parse_german_date(value):
    """Parst ``T.M.JJJJ`` (auch einstellig) → ``date`` oder ``None``."""
    text = (value or '').strip()
    if not text:
        return None
    parts = text.split('.')
    if len(parts) != 3:
        return None
    try:
        day, month, year = (int(p) for p in parts)
        return date(year, month, day)
    except (ValueError, TypeError):
        return None


def _split_name(value):
    """„Vorname Nachname" → (first, last). Ein Token → (\"\", token)."""
    parts = (value or '').split()
    if not parts:
        return '', ''
    if len(parts) == 1:
        return '', parts[0]
    return parts[0], ' '.join(parts[1:])


def _build_nationalities(primary, secondary):
    """Haupt-Nationalität zuerst, dann zweite — dedupliziert, ``;``-getrennt."""
    out = []
    for nat in (primary, secondary):
        nat = (nat or '').strip()
        if nat and nat not in out:
            out.append(nat)
    return ', '.join(out)


def _compute_age(dob):
    if not dob:
        return None
    today = datetime.now().date()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def parse_fmid_csv(csv_text):
    """Parst die CSV. Returns ``(rows, fatal_error)``.

    ``rows`` ist eine Liste von Dicts ``{line_no, fm_id, raw_name, dob, nation,
    nation2, verein, parse_error}``.
    """
    try:
        reader = csv.reader(io.StringIO(csv_text), delimiter=';')
        header_raw = next(reader, None)
    except Exception as exc:  # noqa: BLE001
        return [], f'CSV konnte nicht gelesen werden: {exc}'

    if not header_raw:
        return [], 'Die CSV ist leer.'

    header = [_norm_header(h) for h in header_raw]
    idx = {name: header.index(name) for name in header if name}

    missing = [c for c in REQUIRED_COLS if c not in idx]
    if missing:
        return [], (
            'Pflichtspalten fehlen im CSV-Header: '
            + ', '.join(missing)
            + '. Erwartet wird u. a. „Unique ID" und „Spieler".'
        )

    def cell(cols, name):
        i = idx.get(name)
        if i is None or i >= len(cols):
            return ''
        return (cols[i] or '').strip()

    rows = []
    line_no = 1
    for cols in reader:
        line_no += 1
        if not any((c or '').strip() for c in cols):
            continue  # Leerzeile überspringen

        raw_id = cell(cols, COL_UNIQUE_ID)
        raw_name = cell(cols, COL_SPIELER)
        parse_error = None
        fm_id = None

        if not raw_id:
            parse_error = 'Keine Unique ID.'
        else:
            try:
                fm_id = int(raw_id)
            except ValueError:
                parse_error = f'Unique ID „{raw_id}" ist keine Zahl.'

        if not parse_error and not raw_name:
            parse_error = 'Kein Spielername.'

        rows.append({
            'line_no': line_no,
            'fm_id': fm_id,
            'raw_name': raw_name,
            'dob': _parse_german_date(cell(cols, COL_GEB)),
            'nation': cell(cols, COL_NATION),
            'nation2': cell(cols, COL_NATION2),
            'verein': cell(cols, COL_VEREIN),
            'parse_error': parse_error,
        })

    if not rows:
        return [], 'Die CSV enthält keine Datenzeilen.'

    return rows, None


def _apply_row(row, target_club, target_key, dry_run):
    """Verarbeitet eine geparste Zeile. Returns Ergebnis-Dict für die Vorschau."""
    from ..models import Player

    line_no = row['line_no']
    base = {
        'line_no': line_no,
        'fm_id': row['fm_id'],
        'player_name': row['raw_name'],
        'club_name': row['verein'],
        'match_mode': None,
        'diff_lines': [],
        'error_msg': None,
    }

    if row['parse_error']:
        base['action'] = ACTION_ERROR
        base['error_msg'] = row['parse_error']
        return base

    fm_id = row['fm_id']
    dob = row['dob']
    first_name, last_name = _split_name(row['raw_name'])
    nationalities = _build_nationalities(row['nation'], row['nation2'])
    at_club = bool(row['verein']) and normalize_name(row['verein']) == target_key

    match = find_existing_player(
        fm_inside_id=fm_id,
        name=row['raw_name'],
        date_of_birth=dob,
    )
    player = match['player']
    match_type = match['match_type']

    # ── Neuer Spieler ────────────────────────────────────────────────────────
    if player is None:
        diff = ['FM-ID gesetzt']
        if at_club:
            diff.append(f'Verein: {target_club.name}')
        else:
            diff.append(f'→ Vereinslos (verliehen an {row["verein"] or "?"})')
        base['action'] = ACTION_NEW
        base['diff_lines'] = diff
        if dry_run:
            return base
        with transaction.atomic():
            new_player = Player(
                first_name=first_name,
                last_name=last_name,
                date_of_birth=dob,
                age=_compute_age(dob) or 0,
                nationalities=nationalities,
                fm_inside_id=fm_id,
            )
            if at_club:
                new_player.club = target_club
                new_player.real_life_club = target_club
                new_player.loan_status = 'none'
            else:
                new_player.club = None
                new_player.real_life_club = target_club
                new_player.loan_status = 'loaned_out'
            new_player.save()
        return base

    # ── Treffer (stark per FM-ID oder schwach per Name+Geburtsdatum) ─────────
    diff = []
    if match_type == 'name_dob':
        base['match_mode'] = 'name'
        diff.append('FM-ID nachgetragen (Backfill)')

    if not dry_run:
        changed_fields = []

    # FM-ID Backfill (nur im Name-Treffer-Fall; bei FM-Treffer schon vorhanden).
    if match_type == 'name_dob' and not player.fm_inside_id:
        if not dry_run:
            player.fm_inside_id = fm_id
            changed_fields.append('fm_inside_id')

    # Leere Identitätsfelder ergänzen — kuratierte Werte nie überschreiben.
    if dob and not player.date_of_birth:
        diff.append('Geburtsdatum ergänzt')
        if not dry_run:
            player.date_of_birth = dob
            if not player.age:
                player.age = _compute_age(dob) or 0
                changed_fields.append('age')
            changed_fields.append('date_of_birth')
    if nationalities and not player.nationalities:
        diff.append('Nationalität ergänzt')
        if not dry_run:
            player.nationalities = nationalities
            changed_fields.append('nationalities')

    # Vereinszuordnung / Leihe.
    if at_club:
        # Spieler ist beim Zielverein. Verein nur ergänzen, wenn keiner gesetzt
        # ist (echte WS-Vereinszuordnung nie überschreiben).
        if player.club_id is None:
            diff.append(f'Verein: {target_club.name}')
            if not dry_run:
                player.club = target_club
                changed_fields.append('club')
        if player.loan_status == 'loaned_out':
            diff.append('Leihstatus aufgehoben')
            if not dry_run:
                player.loan_status = 'none'
                changed_fields.append('loan_status')
    else:
        # Verein ≠ Zielverein ⇒ verliehen → Vereinslos (club=None,
        # loan_status='loaned_out') — auch wenn aktuell ein Verein gesetzt ist.
        moved = player.club_id is not None
        status_change = player.loan_status != 'loaned_out'
        if moved:
            diff.append(f'→ Vereinslos (verliehen an {row["verein"] or "?"})')
        elif status_change:
            diff.append(f'verliehen an {row["verein"] or "?"} (Leihstatus gesetzt)')
        if not dry_run:
            if moved:
                player.club = None
                changed_fields.append('club')
            if status_change:
                player.loan_status = 'loaned_out'
                changed_fields.append('loan_status')

    # Stammverein (Eigentümer) ergänzen, wenn unbekannt.
    if player.real_life_club_id is None:
        if not at_club:
            diff.append(f'Stammverein: {target_club.name}')
        if not dry_run:
            player.real_life_club = target_club
            changed_fields.append('real_life_club')

    if not dry_run and changed_fields:
        with transaction.atomic():
            player.save(update_fields=list(dict.fromkeys(changed_fields)))

    base['diff_lines'] = diff
    base['action'] = ACTION_UPDATED if diff else ACTION_UNCHANGED
    return base


def run_fmid_csv_import(csv_text, target_club, dry_run=True):
    """Importiert die FM-ID-CSV für ``target_club``.

    Returns ``{fatal_error, stats, row_results}``.
    """
    rows, fatal = parse_fmid_csv(csv_text)
    if fatal:
        return {'fatal_error': fatal, 'stats': {}, 'row_results': []}

    target_key = normalize_name(target_club.name)
    stats = {ACTION_NEW: 0, ACTION_UPDATED: 0, ACTION_UNCHANGED: 0,
             ACTION_ERROR: 0, 'loaned': 0}
    row_results = []

    for row in rows:
        try:
            result = _apply_row(row, target_club, target_key, dry_run)
        except Exception as exc:  # noqa: BLE001 — eine Zeile darf den Stapel nicht abbrechen
            result = {
                'line_no': row['line_no'], 'fm_id': row.get('fm_id'),
                'player_name': row.get('raw_name', ''), 'club_name': row.get('verein', ''),
                'match_mode': None, 'diff_lines': [], 'action': ACTION_ERROR,
                'error_msg': str(exc),
            }
        stats[result['action']] = stats.get(result['action'], 0) + 1
        if row.get('verein') and normalize_name(row['verein']) != target_key:
            stats['loaned'] += 1
        row_results.append(result)

    return {'fatal_error': None, 'stats': stats, 'row_results': row_results}
