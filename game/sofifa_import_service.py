"""CMTracker-Import-Service.

Kern-Logik des CMTracker-CSV-Imports als wiederverwendbare Funktion für CLI und
Browser-Upload. Wird von management/commands/import_sofifa_csv.py UND von
views_creator.creator_sofifa_import genutzt.
"""
import csv
import io

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
)
from .management.commands.import_sofifa_csv import (
    ALL_ATTR_COLUMNS,
    COLUMN_ALIASES,
    GK_ATTR_COLUMNS,
    OUTFIELD_ATTR_COLUMNS,
    name_similarity,
    normalize_header,
    normalize_name,
    parse_dob,
)

GK_POSITION_CODES = {'TW', 'GK'}


def _filter_attrs_for_player(player, attrs):
    """Gibt nur die für die Position erlaubten Attribute zurück."""
    is_gk = (player.position or '').upper() in GK_POSITION_CODES
    allowed = set(GK_ATTR_COLUMNS if is_gk else OUTFIELD_ATTR_COLUMNS)
    return {k: v for k, v in attrs.items() if k in allowed}


def _build_header_map(header_row):
    header_map = {}
    for idx, cell in enumerate(header_row):
        key = COLUMN_ALIASES.get(normalize_header(cell))
        if key:
            header_map[key] = idx
    return header_map


def _parse_int(raw, lo, hi, field, required=False, clip=False):
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
        if clip:
            import logging as _logging
            clipped = max(lo, min(hi, val))
            _logging.getLogger(__name__).warning(
                'sofifa_import_service: %s=%d außerhalb %d-%d, auf %d geclipt',
                field, val, lo, hi, clipped,
            )
            return clipped
        raise ValueError(f'{field}={val} außerhalb {lo}–{hi}')
    return val


def _parse_row(raw_row, header_map):
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
            val = _parse_int(cell(col), 0, 99, col, clip=True)
            if val is not None:
                attrs[col] = val

    name = cell('name')
    if not name:
        first = cell('first_name_raw')
        last = cell('last_name_raw')
        name = (first + ' ' + last).strip() if (first or last) else ''

    dob = parse_dob(cell('dob'))

    return {
        'sofifa_id': sofifa_id,
        'name': name,
        'club': cell('club'),
        'rating': rating,
        'potential': potential,
        'profile_url': cell('profile_url'),
        'dob': dob,
        'attrs': attrs,
    }


def _match_player(parsed, sofifa_ds, club_scope=None):
    """Sucht den passenden Player-Datensatz fuer eine CMT-Zeile.

    Rueckgabe: ``(player_or_None, match_type_or_None, reason_or_None)``

    ``reason`` ist gesetzt wenn ``player`` ``None`` ist und erklaert warum
    kein Match gefunden wurde:

    * ``'no_cmt_id'``       – CMT-ID fehlt in den Rohdaten
    * ``'no_dob'``          – Geburtsdatum fehlt (DOB-Matching nicht moeglich)
    * ``'not_in_ws'``       – Spieler existiert nicht in der WS-DB
    * ``'no_name'``         – Name fehlt (kein Namens-Fallback moeglich)
    * ``'dob_ambiguous'``   – DOB trifft mehrere Spieler, Namenstrennung schlaegt fehl
    * ``'name_ambiguous'``  – Namens-Score gleichauf (kein eindeutiger Treffer)
    * ``'name_no_match'``   – Kein Kandidat ueber Aehnlichkeitsschwelle 150
    * ``'out_of_scope'``    – Spieler gefunden, aber nicht im erwarteten WS-Club
                              (nur wenn club_scope gesetzt)

    Parameters
    ----------
    club_scope : Club | None
        Wenn gesetzt, werden ausschliesslich Spieler dieses WS-Clubs als
        Matching-Kandidaten beruecksichtigt. Verhindert globalen
        Name/DOB-Match ueber fremde Vereine.
    """
    sofifa_id = parsed.get('sofifa_id') or ''
    if not sofifa_id:
        return None, None, 'no_cmt_id'

    ext = (
        PlayerExternalId.objects
        .filter(source=sofifa_ds, external_id=sofifa_id)
        .select_related('player', 'player__club')
        .first()
    )
    if ext:
        # Club-Scope-Check: ID-Match trumpft grundsätzlich, aber bei
        # gesetztem club_scope darf nur der erwartete Verein gematcht werden.
        if club_scope is not None and ext.player.club_id != club_scope.id:
            return None, None, 'out_of_scope'
        return ext.player, 'id', None

    # ── DOB-Matching (club-scoped wenn club_scope gesetzt) ───────────────────
    dob = parsed.get('dob')
    _dob_ambiguous = False
    if dob:
        dob_qs = Player.objects.select_related('club')
        if club_scope is not None:
            dob_qs = dob_qs.filter(club=club_scope)
        dob_matches = list(dob_qs.filter(date_of_birth=dob))
        if len(dob_matches) == 1:
            return dob_matches[0], 'dob', None
        if len(dob_matches) > 1:
            dob_name = parsed.get('name')
            if dob_name:
                target_dob = normalize_name(dob_name)
                scored_dob = sorted(
                    ((name_similarity(target_dob, normalize_name(p.full_name)), p)
                     for p in dob_matches),
                    key=lambda t: t[0], reverse=True,
                )
                if scored_dob[0][0] > scored_dob[1][0]:
                    return scored_dob[0][1], 'dob', None
            _dob_ambiguous = True
            # Mehrdeutig: weiter mit dem Namens-Fallback unten.

    # ── Name-Fallback (club-scoped wenn club_scope gesetzt) ──────────────────
    name = parsed.get('name')
    if not name:
        if not dob:
            return None, None, 'no_dob'
        return None, None, 'no_name'

    if club_scope is not None:
        # Strikt auf den WS-Club beschränkt — CSV-Clubname wird ignoriert
        candidates = Player.objects.select_related('club').filter(club=club_scope)
    else:
        # Globales Matching mit optionalem CSV-Clubname-Filter (Legacy-Pfad)
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
        reason = 'dob_ambiguous' if _dob_ambiguous else 'not_in_ws'
        return None, None, reason
    scored.sort(key=lambda t: t[0], reverse=True)
    if len(scored) > 1 and scored[0][0] == scored[1][0]:
        return None, None, 'name_ambiguous'
    return scored[0][1], 'name', None


def _apply_row(player, parsed, sofifa_ds, today, dry_run):
    existing = player.source_ratings.filter(
        source=PlayerSourceRating.SOURCE_CMTRACKER,
    ).first()
    is_new = existing is None

    diff_lines = []
    if is_new:
        diff_lines.append(
            f"CMTracker: Quelldaten erstmals angelegt (Rating {parsed['rating']})"
        )
    else:
        if existing.rating != parsed['rating']:
            diff_lines.append(
                f"CMTracker Rating: {existing.rating} → {parsed['rating']}"
            )
        if parsed['potential'] is not None and existing.potential != parsed['potential']:
            old_p = existing.potential if existing.potential is not None else '–'
            diff_lines.append(
                f"CMTracker Potential: {old_p} → {parsed['potential']}"
            )
        for col, val in parsed['attrs'].items():
            old_val = getattr(existing, col, None)
            if old_val != val:
                diff_lines.append(
                    f"{col}: {old_val if old_val is not None else '–'} → {val}"
                )

    if not is_new and not diff_lines:
        return 'unchanged', []

    if dry_run:
        return ('new' if is_new else 'updated'), diff_lines

    with transaction.atomic():
        defaults = {
            'rating': parsed['rating'],
            'source_url': parsed['profile_url'],
            'source_version': 'CMTracker-Import',
            'checked_at': today,
        }
        if parsed['potential'] is not None:
            defaults['potential'] = parsed['potential']
        defaults.update(parsed['attrs'])

        PlayerSourceRating.objects.update_or_create(
            player=player,
            source=PlayerSourceRating.SOURCE_CMTRACKER,
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
                'source_version': 'CMTracker-Import',
                'update_current': False,
                'raw_payload': {
                    'sofifa_id': parsed['sofifa_id'],
                    'attrs': parsed['attrs'],
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

        PlayerEditLog.objects.create(
            player=player,
            changed_by=None,
            category=PlayerEditLog.CATEGORY_SOURCE,
            summary='\n'.join(diff_lines),
        )

    return ('new' if is_new else 'updated'), diff_lines


def run_sofifa_import(csv_text, dry_run=False, skip_recalculate=False,
                       club_scope=None):
    """Führt den CMTracker-CSV-Import durch und gibt ein strukturiertes Ergebnis zurück.

    Args:
        csv_text:          Inhalt der CSV-Datei als String (BOM wird automatisch entfernt).
        dry_run:           True → nur Vorschau, keine DB-Schreiboperationen.
        skip_recalculate:  True → Spielstärken nach dem Import NICHT neu berechnen.
        club_scope:        Club | None — wenn gesetzt, werden ausschliesslich Spieler
                           dieses WS-Clubs als Matching-Kandidaten beruecksichtigt.
                           Verhindert globalen Name/DOB-Match ueber fremde Vereine.

    Returns:
        dict mit:
          fatal_error  – str oder None (Abbruchfehler, z.B. fehlende Pflichtspalte)
          stats        – {new, updated, unchanged, unmatched, error}
          row_results  – Liste von Dicts pro Zeile:
                           line_no, action, player_name, club_name,
                           match_mode, diff_lines, error_msg
    """
    if csv_text.startswith('\ufeff'):
        csv_text = csv_text[1:]

    rows = list(csv.reader(io.StringIO(csv_text)))

    if not rows:
        return {'fatal_error': 'CSV ist leer.', 'stats': {}, 'row_results': []}

    header_map = _build_header_map(rows[0])
    if 'sofifa_id' not in header_map:
        return {
            'fatal_error': (
                'CSV-Header braucht eine sofifa_id-Spalte (Aliase: sofifa, id).'
            ),
            'stats': {}, 'row_results': [],
        }
    if 'rating' not in header_map:
        return {
            'fatal_error': (
                'CSV-Header braucht eine rating-Spalte (Aliase: overall, ovr).'
            ),
            'stats': {}, 'row_results': [],
        }

    sofifa_ds, _ = DataSource.objects.get_or_create(
        code=DataSource.CODE_CMTRACKER,
        defaults={'name': 'CMTracker'},
    )
    today = timezone.localdate()

    stats = {'new': 0, 'updated': 0, 'unchanged': 0, 'unmatched': 0, 'error': 0}
    row_results = []

    for line_no, raw_row in enumerate(rows[1:], start=2):
        if not any(cell.strip() for cell in raw_row):
            continue

        try:
            parsed = _parse_row(raw_row, header_map)
        except ValueError as exc:
            stats['error'] += 1
            row_results.append({
                'line_no': line_no,
                'action': 'error',
                'player_name': '',
                'club_name': '',
                'match_mode': '',
                'diff_lines': [],
                'error_msg': str(exc),
            })
            continue

        player, match_mode, unmatch_reason = _match_player(parsed, sofifa_ds,
                                                              club_scope=club_scope)
        if player:
            parsed['attrs'] = _filter_attrs_for_player(player, parsed['attrs'])
        if not player:
            stats['unmatched'] += 1
            row_results.append({
                'line_no': line_no,
                'action': 'unmatched',
                'sofifa_id': parsed.get('sofifa_id') or '',
                'player_name': parsed.get('name') or '',
                'club_name': parsed.get('club', ''),
                'match_mode': '',
                'unmatch_reason': unmatch_reason or 'unknown',
                'diff_lines': [],
                'error_msg': '',
            })
            continue

        action, diff_lines = _apply_row(
            player=player,
            parsed=parsed,
            sofifa_ds=sofifa_ds,
            today=today,
            dry_run=dry_run,
        )
        stats[action] += 1
        row_results.append({
            'line_no': line_no,
            'action': action,
            'player_name': player.full_name,
            'club_name': player.club.name if player.club else '',
            'match_mode': match_mode,
            'diff_lines': diff_lines,
            'error_msg': '',
        })

    if not dry_run and not skip_recalculate:
        changed = stats['new'] + stats['updated']
        if changed:
            call_command('calculate_player_strengths')

    return {'fatal_error': None, 'stats': stats, 'row_results': row_results}
