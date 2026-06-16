"""Aufbereitung der Kontroll-/Vorschauansicht (Creator-Mode Import-UI).

Diese Schicht verbindet die getrennten Rohdaten eines ``PlayerImportCandidate``
(Transfermarkt / Positionen / FMInside / SoFIFA) zu dem von
``import_service.import_candidate`` erwarteten ``normalized_data``-Schema und
berechnet die Alt→Neu-Diffs gegen einen ggf. bereits vorhandenen Spieler.

Es werden ausschließlich die bereits vorhandenen reinen Logikdienste
(``parsing``, ``positions``, ``matching``, ``normalization``) genutzt — hier
entsteht keine neue Spiel-/Stärkelogik, nur die Orchestrierung für die Anzeige
und den anschließenden verbindlichen Import.

NULL-Erhalt: Fehlende Werte bleiben ``None`` / ``''`` — niemals ``0``.
"""

from datetime import date, datetime
from decimal import Decimal

from .parsing import (
    parse_foot,
    parse_height,
    parse_market_value,
    parse_nationalities,
)
from .positions import compute_positions
from .matching import find_existing_player
from .import_service import validate_candidate


# ── Hilfsfunktionen ─────────────────────────────────────────────────────────

def _to_int(value):
    try:
        if value is None or value == '':
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_dob(value):
    """Wandelt diverse Datumsformate in ISO ``YYYY-MM-DD`` oder ``''``."""
    if not value:
        return ''
    if isinstance(value, (date, datetime)):
        return value.strftime('%Y-%m-%d')
    s = str(value).strip()
    if not s:
        return ''
    for fmt in ('%Y-%m-%d', '%d.%m.%Y', '%d/%m/%Y', '%b %d, %Y', '%B %d, %Y'):
        try:
            return datetime.strptime(s, fmt).strftime('%Y-%m-%d')
        except ValueError:
            continue
    return s  # unbekanntes Format unverändert übernehmen (Import parst ISO)


def _club_ref(sub):
    """{tm_club_id,name,url} → {tm_id,name,profile_url} oder ``None``."""
    if not isinstance(sub, dict):
        return None
    name = (sub.get('name') or '').strip()
    tm_id = _to_int(sub.get('tm_club_id'))
    if not name and not tm_id:
        return None
    return {
        'tm_id': tm_id,
        'name': name,
        'profile_url': sub.get('url') or '',
    }


def _rating_block(raw):
    """fmi_raw/sofifa_raw → {rating,potential,attrs} oder ``None``."""
    if not isinstance(raw, dict):
        return None
    rating = raw.get('rating')
    if rating is None:
        return None
    attrs = raw.get('attrs') if isinstance(raw.get('attrs'), dict) else {}
    return {
        'rating': rating,
        'potential': raw.get('potential'),
        'attrs': attrs,
    }


def _split_name(tm):
    first = (tm.get('first_name') or '').strip()
    last = (tm.get('last_name') or '').strip()
    if first or last:
        return first, last
    display = (tm.get('display_name') or '').strip()
    if not display:
        return '', ''
    parts = display.split()
    if len(parts) == 1:
        return '', parts[0]
    return parts[0], ' '.join(parts[1:])


# ── Normalisierung Roh → normalized_data ────────────────────────────────────

def build_normalized_data(candidate):
    """Erzeugt ``normalized_data`` aus den Rohfeldern eines Kandidaten.

    Returns:
        (normalized_data: dict, warnings: list[str])
    """
    tm = candidate.tm_raw or {}
    pos = candidate.position_raw or {}
    fmi = candidate.fmi_raw or {}
    sofifa = candidate.sofifa_raw or {}
    warnings = []

    first_name, last_name = _split_name(tm)
    primary_nat, joined_nat = parse_nationalities(
        tm.get('nationalities') or tm.get('primary_nationality')
    )

    # Positionen: explizite Listen bevorzugen, sonst aus Leistungsdaten ableiten.
    main_positions = pos.get('main_positions')
    secondary_positions = pos.get('secondary_positions')
    if main_positions:
        main_positions = list(main_positions)
        secondary_positions = list(secondary_positions or [])
    else:
        performance = [
            (a.get('source_position'), a.get('matches'))
            for a in (pos.get('appearances') or [])
            if isinstance(a, dict)
        ]
        computed = compute_positions(
            performance, profile_position=tm.get('profile_position')
        )
        main_positions = computed['main_positions']
        secondary_positions = computed['secondary_positions']
        warnings.extend(computed['warnings'])

    club_assignment = tm.get('club_assignment') or {}
    real_club = _club_ref(club_assignment.get('real_club'))
    loaned_from = _club_ref(club_assignment.get('loaned_from'))

    nd = {
        'tm_player_id': candidate.tm_player_id,
        'transfermarkt_profile_url': tm.get('profile_url') or '',
        'first_name': first_name,
        'last_name': last_name,
        'date_of_birth': _parse_dob(tm.get('date_of_birth')),
        'height_cm': parse_height(tm.get('height_cm')),
        'strong_foot': parse_foot(tm.get('preferred_foot')),
        'primary_nationality': primary_nat,
        'nationalities': joined_nat,
        'market_value': parse_market_value(tm.get('market_value_eur')),
        'profile_position': tm.get('profile_position') or '',
        'main_positions': main_positions,
        'secondary_positions': secondary_positions,
        'fm_inside_id': _to_int(fmi.get('id')),
        'sofifa_id': str(sofifa.get('id')) if sofifa.get('id') else None,
        'sofifa_profile_url': sofifa.get('url') or '',
        'real_club': real_club,
        'loaned_from': loaned_from,
        'fmi_ratings': _rating_block(fmi),
        'sofifa_ratings': _rating_block(sofifa),
    }
    return nd, warnings


# ── Alt→Neu-Diff ────────────────────────────────────────────────────────────

def _player_positions(player, prefix):
    vals = [
        getattr(player, f'{prefix}_1', '') or '',
        getattr(player, f'{prefix}_2', '') or '',
        getattr(player, f'{prefix}_3', '') or '',
    ]
    return [v for v in vals if v]


def _existing_source(player, source):
    from ..models import PlayerSourceRating
    return (
        PlayerSourceRating.objects
        .filter(player=player, source=source)
        .first()
    )


def _existing_sofifa_id(player):
    from ..models import DataSource, PlayerExternalId
    ext = (
        PlayerExternalId.objects
        .filter(player=player, source__code=DataSource.CODE_SOFIFA)
        .first()
    )
    return ext.external_id if ext else None


def _jsonable(value):
    """Wandelt JSONField-untaugliche Werte (z. B. ``Decimal``) in sichere Typen."""
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, (date, datetime)):
        return value.strftime('%Y-%m-%d')
    return value


def _norm(value):
    """Vergleichsnormalform: ``None``/``''`` gleich; Zahlen typunabhängig.

    Wichtig: aus der DB gelesene ``Decimal``-Werte (z. B. ``100000000.00``)
    müssen mit aus Rohdaten geparsten ``int``-Werten vergleichbar sein.
    """
    value = _jsonable(value)
    if value is None:
        return ''
    if isinstance(value, (list, tuple)):
        return ', '.join(str(v) for v in value)
    return str(value).strip()


def compute_detected_changes(player, nd):
    """Liste von Alt→Neu-Unterschieden zwischen vorhandenem Spieler und ``nd``.

    Jeder Eintrag: ``{key, label, old, new, cleared}``. ``cleared`` markiert,
    dass ein vorhandener Wert durch einen leeren neuen Wert ersetzt würde.
    """
    from ..models import PlayerSourceRating

    fm = _existing_source(player, PlayerSourceRating.SOURCE_FM)
    ea = _existing_source(player, PlayerSourceRating.SOURCE_EA)

    rows = [
        ('name', 'Name',
         f'{player.first_name} {player.last_name}'.strip(),
         f"{nd.get('first_name', '')} {nd.get('last_name', '')}".strip()),
        ('date_of_birth', 'Geburtsdatum',
         player.date_of_birth.strftime('%Y-%m-%d') if player.date_of_birth else '',
         nd.get('date_of_birth') or ''),
        ('height_cm', 'Größe (cm)', player.height_cm, nd.get('height_cm')),
        ('strong_foot', 'Starker Fuß', player.strong_foot, nd.get('strong_foot')),
        ('nationalities', 'Nationalität',
         player.nationalities, nd.get('nationalities')),
        ('market_value', 'Marktwert',
         player.market_value, nd.get('market_value')),
        ('main_positions', 'Hauptpositionen',
         _player_positions(player, 'main_position'),
         nd.get('main_positions') or []),
        ('secondary_positions', 'Nebenpositionen',
         _player_positions(player, 'secondary_position'),
         nd.get('secondary_positions') or []),
        ('fm_inside_id', 'FMInside-ID',
         player.fm_inside_id, nd.get('fm_inside_id')),
        ('sofifa_id', 'SoFIFA-ID',
         _existing_sofifa_id(player), nd.get('sofifa_id')),
        ('fmi_rating', 'FMInside-Rating',
         fm.rating if fm else None,
         (nd.get('fmi_ratings') or {}).get('rating') if nd.get('fmi_ratings') else None),
        ('sofifa_rating', 'SoFIFA-Rating',
         ea.rating if ea else None,
         (nd.get('sofifa_ratings') or {}).get('rating') if nd.get('sofifa_ratings') else None),
        ('real_club', 'Real-Verein',
         player.real_life_club.name if player.real_life_club else '',
         (nd.get('real_club') or {}).get('name') if nd.get('real_club') else ''),
        ('loaned_from', 'Leihgeber',
         player.loan_partner_club.name if player.loan_partner_club else '',
         (nd.get('loaned_from') or {}).get('name') if nd.get('loaned_from') else ''),
    ]

    changes = []
    for key, label, old, new in rows:
        if _norm(old) == _norm(new):
            continue
        changes.append({
            'key': key,
            'label': label,
            'old': _jsonable(old),
            'new': _jsonable(new),
            'cleared': bool(_norm(old)) and not _norm(new),
        })
    return changes


# ── Klassifizierung & Refresh ───────────────────────────────────────────────

def refresh_candidate(candidate, reset_selection=False, save=True):
    """Baut ``normalized_data``/``detected_changes`` neu und klassifiziert.

    Args:
        reset_selection: Auswahl-/Überschreiben-Vorgaben anhand der Klasse setzen.
        save: Ergebnis sofort speichern.

    Returns:
        candidate (aktualisiert).
    """
    Cand = candidate.__class__

    nd, warnings = build_normalized_data(candidate)
    candidate.normalized_data = nd
    candidate.source_warnings = [str(w)[:300] for w in warnings[:50]]

    errors = validate_candidate(nd)
    candidate.validation_errors = errors

    match = find_existing_player(
        tm_player_id=nd.get('tm_player_id'),
        fm_inside_id=nd.get('fm_inside_id'),
        sofifa_id=nd.get('sofifa_id'),
        name=f"{nd.get('first_name', '')} {nd.get('last_name', '')}",
        date_of_birth=nd.get('date_of_birth'),
    )
    player = match['player']
    candidate.existing_player = player

    changes = []
    if player is not None:
        changes = compute_detected_changes(player, nd)
    candidate.detected_changes = {
        'match_type': match['match_type'],
        'is_strong': match['is_strong'],
        'items': changes,
    }

    if errors:
        status = Cand.STATUS_INVALID
    elif player is None:
        status = Cand.STATUS_NEW
    elif changes:
        status = Cand.STATUS_EXISTING_CHANGED
    else:
        status = Cand.STATUS_EXISTING_UNCHANGED

    # Bereits importierte/übersprungene Kandidaten behalten ihren Endstatus.
    if candidate.status not in (Cand.STATUS_IMPORTED, Cand.STATUS_SKIPPED):
        candidate.status = status

    if reset_selection:
        if status in (Cand.STATUS_NEW, Cand.STATUS_EXISTING_CHANGED):
            candidate.selected_for_import = True
        else:
            candidate.selected_for_import = False
        # Vorhandene Spieler müssen zum Aktualisieren überschrieben werden.
        candidate.overwrite_existing = player is not None

    if save:
        candidate.save(update_fields=[
            'normalized_data', 'detected_changes', 'validation_errors',
            'source_warnings', 'existing_player', 'status',
            'selected_for_import', 'overwrite_existing', 'updated_at',
        ])
    return candidate


def refresh_job_candidates(job, reset_selection=False):
    """Wertet alle Kandidaten eines Auftrags neu aus."""
    for candidate in job.candidates.all():
        refresh_candidate(candidate, reset_selection=reset_selection)
