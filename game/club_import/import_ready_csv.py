"""Adapter für „import_ready"-CSV-Dateien (Komma-getrennt, englische Header).

Liest eine vorgefertigte CSV (ein Verein + Spielerzeilen) und erzeugt daraus
das vom verbindlichen ``import_service`` erwartete ``normalized_data``-Schema —
ohne erneute Normalisierung im Importdienst. Reine Logikschicht: kein DB-Zugriff,
kein Scraper.

CSV-Eigenheiten (siehe HSV_import_ready_2025_26):
* Vereinsfelder stehen redundant in jeder Zeile (club_name, founded_year,
  stadium_*, latitude/longitude, fmi_club_id, tm_club_id, season_*).
* Positionen (``hp_positions``/``np_positions``) sind bereits INTERNE Codes
  (TW, IV, RV …), per ``|`` getrennt — NICHT durch ``map_tm_position`` jagen.
* Nationalitäten sind per ``|`` getrennt und gemischtsprachig; sie werden auf
  deutsche Namen normalisiert (Flaggen-Lookup ist deutsch-keyed) und dedupliziert.
* Leihstatus über ``squad_status`` (``loaned_in``/``loaned_out``).
"""

import csv
import io

from .parsing import parse_height, parse_market_value, parse_foot


# ── Nationalitäten: Englisch/gemischt → Deutsch (COUNTRY_FLAG_ASSETS-keyed) ──
# Nur Übersetzungen, bei denen sich der Name unterscheidet; bereits deutsche
# Namen (Deutschland, Portugal, Nigeria …) bleiben unverändert.
COUNTRY_DE_MAP = {
    'germany': 'Deutschland',
    'france': 'Frankreich',
    'norway': 'Norwegen',
    'croatia': 'Kroatien',
    'comoros': 'Komoren',
    'georgia': 'Georgien',
    'libya': 'Libyen',
    'argentina': 'Argentinien',
    'belgium': 'Belgien',
    'switzerland': 'Schweiz',
    'denmark': 'Dänemark',
    'united states': 'Vereinigte Staaten',
    'usa': 'Vereinigte Staaten',
    'netherlands': 'Niederlande',
    'italy': 'Italien',
    'spain': 'Spanien',
    'portugal': 'Portugal',
    'england': 'England',
    'scotland': 'Schottland',
    'wales': 'Wales',
    'ireland': 'Irland',
    'austria': 'Österreich',
    'poland': 'Polen',
    'sweden': 'Schweden',
    'turkey': 'Türkei',
    'greece': 'Griechenland',
    'serbia': 'Serbien',
    'czechia': 'Tschechien',
    'czech republic': 'Tschechien',
    'slovakia': 'Slowakei',
    'slovenia': 'Slowenien',
    'hungary': 'Ungarn',
    'romania': 'Rumänien',
    'russia': 'Russland',
    'ukraine': 'Ukraine',
    'morocco': 'Marokko',
    'algeria': 'Algerien',
    'tunisia': 'Tunesien',
    'egypt': 'Ägypten',
    'cameroon': 'Kamerun',
    'ivory coast': 'Elfenbeinküste',
    'cote d\'ivoire': 'Elfenbeinküste',
    'senegal': 'Senegal',
    'ghana': 'Ghana',
    'nigeria': 'Nigeria',
    'mali': 'Mali',
    'gambia': 'Gambia',
    'guinea': 'Guinea',
    'tanzania': 'Tansania',
    'eritrea': 'Eritrea',
    'dr congo': 'DR Kongo',
    'congo': 'Kongo',
    'brazil': 'Brasilien',
    'colombia': 'Kolumbien',
    'japan': 'Japan',
    'south korea': 'Südkorea',
    'united states of america': 'Vereinigte Staaten',
    'kosovo': 'Kosovo',
    'albania': 'Albanien',
    'suriname': 'Suriname',
}


# ── Attribut-Mappings (CSV-Spaltensuffix → internes PSR-Feld) ───────────────
# FMInside (Spaltenpräfix ``fmi_``); 21 Attribute, 1:1 zu PSR_ATTR_FIELDS.
FMI_ATTR_MAP = {
    'pace': 'tempo',
    'stamina': 'ausdauer',
    'strength': 'kraft',
    'technique': 'technik',
    'dribbling': 'dribbling',
    'passing': 'passspiel',
    'crossing': 'flanken',
    'tackling': 'zweikampf',
    'positioning': 'defensivstellung',
    'finishing': 'abschluss',
    'heading': 'kopfball',
    'vision': 'uebersicht',
    'teamwork': 'teamwork',
    'corners': 'ecken',
    'free_kick_taking': 'freistoss',
    'penalty_taking': 'elfmeter',
    'gk_reflexes': 'tw_reflexe',
    'gk_handling': 'tw_fangsicherheit',
    'gk_one_on_ones': 'tw_eins_gegen_eins',
    'gk_positioning': 'tw_stellungsspiel',
    'gk_passing': 'tw_passen',
}

# CMTracker (Spaltenpräfix ``sofifa_``). Hat kein technik/teamwork/ecken/
# tw_eins_gegen_eins → bleiben None. ``long_passing`` wird verworfen.
SOFIFA_ATTR_MAP = {
    'pace': 'tempo',
    'stamina': 'ausdauer',
    'strength': 'kraft',
    'dribbling': 'dribbling',
    'short_passing': 'passspiel',
    'crossing': 'flanken',
    'finishing': 'abschluss',
    'heading': 'kopfball',
    'standing_tackle': 'zweikampf',
    'defensive_awareness': 'defensivstellung',
    'vision': 'uebersicht',
    'free_kick': 'freistoss',
    'penalties': 'elfmeter',
    'gk_reflexes': 'tw_reflexe',
    'gk_handling': 'tw_fangsicherheit',
    'gk_positioning': 'tw_stellungsspiel',
    'gk_passing': 'tw_passen',
}


def _clean(value):
    return (value or '').strip()


def _to_int(value):
    value = _clean(value)
    if not value:
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _to_float(value):
    value = _clean(value)
    if not value:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def translate_country(name):
    """Übersetzt einen (ggf. englischen) Ländernamen in seine deutsche Form."""
    name = _clean(name)
    if not name:
        return ''
    return COUNTRY_DE_MAP.get(name.lower(), name)


def normalize_nationalities(primary_raw, nats_raw):
    """``(primary, joined)`` aus ``|``-getrennten, gemischtsprachigen Werten.

    Übersetzt jede Nationalität ins Deutsche, entfernt Duplikate unter Erhalt der
    Reihenfolge und fügt sie mit ``", "`` zusammen (Schema des Importdienstes).
    """
    tokens = []
    for raw in [primary_raw, nats_raw]:
        for part in (raw or '').split('|'):
            de = translate_country(part)
            if de and de not in tokens:
                tokens.append(de)
    primary = tokens[0] if tokens else ''
    return primary, ', '.join(tokens)


def _positions(value):
    """Interne Positionscodes aus ``|``-getrenntem Feld (keine TM-Übersetzung)."""
    return [p for p in (_clean(value).split('|')) if p]


def _attr_block(row, prefix, attr_map):
    """Ratingblock ``{rating, potential, source_url, checked_at, attrs}`` oder ``None``.

    ``prefix`` ist ein Spaltenpräfix (z. B. ``'fmi'``) oder eine Präferenzliste
    von Präfixen. Bei mehreren wird das erste belegte Vorkommen genutzt — so
    werden ``cmtracker_*``-Header bevorzugt, ``sofifa_*`` bleibt rückwärts-
    kompatibler Alias.

    Liest zusätzlich zu Rating/Potential/Attrs:
    * ``source_url``  — Profillink der Quelle (``{prefix}_url``-Spalte)
    * ``checked_at``  — Datum der Quellprüfung (gemeinsame Spalte ``source_checked_at``)
    * ``notes``       — optionale Freitext-Notizen (``{prefix}_notes``-Spalte, falls vorhanden)
    """
    prefixes = (prefix,) if isinstance(prefix, str) else tuple(prefix)

    def _col(suffix):
        for pfx in prefixes:
            val = row.get(f'{pfx}_{suffix}')
            if val is not None and str(val).strip() != '':
                return val
        return None

    rating = _to_int(_col('rating'))
    if rating is None:
        return None
    attrs = {}
    for suffix, field in attr_map.items():
        val = _to_int(_col(suffix))
        if val is not None:
            attrs[field] = val
    raw_pot = _clean(_col('potential'))
    parsed_pot = _to_int(raw_pot)
    block = {
        'rating': rating,
        'potential': parsed_pot,
        'attrs': attrs,
        'source_version': _clean(_col('source_version')),
        'source_url': _clean(_col('url')),
        'checked_at': _clean(row.get('source_checked_at')),
        'notes': _clean(_col('notes')),
    }
    if raw_pot and parsed_pot is None:
        block['potential_raw'] = raw_pot
    return block


def _club_ref(name, url=''):
    name = _clean(name)
    if not name:
        return None
    return {'tm_id': None, 'name': name, 'profile_url': _clean(url)}


EA_NOT_IN_DB_STATUS = 'NOT_IN_ACTIVE_EA_FC26_DATABASE'


def _is_ea_unavailable(row) -> bool:
    """True wenn ea_availability_status anzeigt, dass kein EA-FC-26-Datensatz existiert."""
    return _clean(row.get('ea_availability_status')).upper() == EA_NOT_IN_DB_STATUS


def row_to_normalized(row):
    """Wandelt eine Spielerzeile in ``normalized_data`` + Warnungen.

    Spieler mit ``ea_availability_status = NOT_IN_ACTIVE_EA_FC26_DATABASE``
    erhalten ``sofifa_ratings = None`` — alle sofifa_*-Felder werden ignoriert.
    FMI-only-Gewichtung (×2) greift automatisch, wenn kein CMTracker-Datensatz vorhanden.

    Returns:
        (normalized_data: dict, warnings: list[str])
    """
    warnings = []

    primary_nat, joined_nat = normalize_nationalities(
        row.get('primary_nationality'), row.get('nationalities')
    )

    mains = _positions(row.get('hp_positions'))
    secs = _positions(row.get('np_positions'))
    if not mains:
        warnings.append(
            f"{_clean(row.get('display_name'))}: keine Hauptposition in CSV."
        )

    # Leihstatus aus squad_status. ws_club/real_club/loaned_from der CSV sind
    # je nach Status uneinheitlich belegt; der Zielverein (Eigentümer) ist immer
    # der WS-Verein des Auftrags → für loaned_out genügt loan_status, der
    # Importdienst setzt real_life_club = ws_club und club = None.
    squad_status = _clean(row.get('squad_status')).lower()
    real_club = None
    loaned_from = None
    if squad_status == 'loaned_in':
        loan_status = 'loaned_in'
        loaned_from = _club_ref(row.get('loaned_from'))
        if loaned_from is None:
            warnings.append(
                f"{_clean(row.get('display_name'))}: loaned_in ohne Leihgeber."
            )
    elif squad_status == 'loaned_out':
        loan_status = 'loaned_out'
    else:
        loan_status = 'none'

    ea_unavailable = _is_ea_unavailable(row)
    if ea_unavailable:
        warnings.append(
            f"{_clean(row.get('display_name'))}: "
            f"ea_availability_status={EA_NOT_IN_DB_STATUS} — "
            f'CMTracker-Daten werden ignoriert, FMI-only-Gewichtung greift.'
        )

    nd = {
        'tm_player_id': _to_int(row.get('tm_player_id')),
        'transfermarkt_profile_url': _clean(row.get('tm_url')),
        'transfermarkt_market_value_url': _clean(row.get('tm_market_value_url')),
        'first_name': _clean(row.get('first_name')),
        'last_name': _clean(row.get('last_name')),
        'date_of_birth': _clean(row.get('date_of_birth')) or None,
        'height_cm': parse_height(row.get('height_cm')),
        'strong_foot': parse_foot(row.get('preferred_foot')),
        'primary_nationality': primary_nat,
        'nationalities': joined_nat,
        'nt_nationality': translate_country(row.get('nt_nationality')),
        'market_value': parse_market_value(row.get('tm_market_value_eur')),
        'main_positions': mains,
        'secondary_positions': secs,
        'fm_inside_id': _to_int(row.get('fm_unique_id')),
        'sofifa_id': None if ea_unavailable else (_clean(row.get('cmtracker_id') or row.get('sofifa_id')) or None),
        'sofifa_profile_url': '' if ea_unavailable else _clean(row.get('cmtracker_url') or row.get('sofifa_url')),
        'real_club': real_club,
        'loaned_from': loaned_from,
        'loan_status': loan_status,
        'fmi_ratings': _attr_block(row, 'fmi', FMI_ATTR_MAP),
        'sofifa_ratings': None if ea_unavailable else _attr_block(row, ('cmtracker', 'sofifa'), SOFIFA_ATTR_MAP),
    }
    return nd, warnings


def parse_club_profile(row):
    """Liest die (redundanten) Vereinsfelder aus einer beliebigen Zeile."""
    return {
        'club_name': _clean(row.get('club_name')),
        'club_short_name': _clean(row.get('club_short_name')),
        'founded_year': _to_int(row.get('founded_year')),
        'club_city': _clean(row.get('club_city')),
        'country': _clean(row.get('country')),
        'latitude': _to_float(row.get('latitude')),
        'longitude': _to_float(row.get('longitude')),
        'fmi_club_id': _to_int(row.get('fmi_club_id')),
        'tm_club_id': _to_int(row.get('tm_club_id')),
        'stadium_name': _clean(row.get('stadium_name')),
        'stadium_city': _clean(row.get('stadium_city')),
        'stadium_capacity': _to_int(row.get('stadium_capacity')),
        'season_id': _to_int(row.get('season_id')),
        'season_label': _clean(row.get('season_label')),
        # Optionale (im aktuellen Export noch fehlende) Stammdatenspalten —
        # werden tolerant gelesen, falls vorhanden.
        'club_tm_url': _clean(row.get('club_tm_url')),
        'stadium_image_static_path': _clean(row.get('stadium_image_static_path')),
        'city_image_static_path': _clean(row.get('city_image_static_path')),
    }


def parse_import_ready_csv(text):
    """Parst den CSV-Text vollständig.

    Returns:
        dict {
            'club': <club_profile dict>,
            'players': [ {'normalized_data':…, 'tm_player_id':…, 'squad_status':…,
                          'display_name':…}, … ],
            'warnings': [str, …],
        }
    """
    reader = csv.DictReader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        raise ValueError('CSV enthält keine Datenzeilen.')

    club = parse_club_profile(rows[0])
    players = []
    warnings = []
    for row in rows:
        nd, row_warnings = row_to_normalized(row)
        warnings.extend(row_warnings)
        players.append({
            'tm_player_id': nd['tm_player_id'],
            'display_name': _clean(row.get('display_name'))
            or f"{nd['first_name']} {nd['last_name']}".strip(),
            'squad_status': _clean(row.get('squad_status')),
            'normalized_data': nd,
        })

    return {'club': club, 'players': players, 'warnings': warnings}


# ── Moneyball-Format (Semikolon, deutsche Header, DD.MM.YYYY-Datum) ──────────

def _parse_date_de(value):
    """'20.12.1999' → '1999-12-20' (ISO). Sonst None."""
    value = _clean(value)
    if not value:
        return None
    parts = value.split('.')
    if len(parts) == 3:
        try:
            day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
            return f'{year:04d}-{month:02d}-{day:02d}'
        except ValueError:
            pass
    return None


# CSV-Spaltenname → interner Schlüssel (None = ignorieren).
MONEYBALL_COLUMN_MAP = {
    'Verein':           'verein',
    'Spieler':          'display_name',
    'Unique ID':        'fm_unique_id',
    'Fähigkeit':        'fmi_rating',
    'Pot':              'fmi_potential',
    'Starker Fuß':      'preferred_foot',
    'Nation':           'primary_nationality',
    '2. Nation':        'second_nationality',
    'Geb.':             'date_of_birth',
    'Größe':            'height_cm',
    # FM-Attribute
    'Halten':           'mb_gk_handling',
    'Eins gegen Eins':  'mb_gk_one_on_ones',
    'Reflexe':          'mb_gk_reflexes',
    'Technik':          'mb_technique',
    'Tackling':         'mb_tackling',
    'Elfmeter':         'mb_penalty_taking',
    'Passen':           'mb_passing',
    'Weitschüsse':      None,   # kein Gegenstück im Schema → ignoriert
    'Kopfballtechnik':  'mb_heading',
    'Freistöße':        'mb_free_kick_taking',
    'Abschluss':        'mb_finishing',
    'Dribbling':        'mb_dribbling',
    'Flanken':          'mb_crossing',
    'Ecken':            'mb_corners',
    'Kraft':            'mb_strength',
    'Ausdauer':         'mb_stamina',
    'Schnelligkeit':    'mb_pace',
    'Übersicht':        'mb_vision',
    'Teamwork':         'mb_teamwork',
    'Stellungsspiel':   'mb_positioning',
}


def _moneyball_fmi_block(row):
    """Baut den fmi_ratings-Block aus einer (bereits gemappten) Moneyball-Zeile.

    Besonderheit TW-Attribute ohne GK-Präfix:
    ``Passen`` → passspiel UND tw_passen (FM-Torhüter haben denselben Wert).
    ``Stellungsspiel`` → defensivstellung UND tw_stellungsspiel.
    Für Feldspieler sind die tw_*-Felder irrelevant; der Match-Engine ignoriert
    sie positionsabhängig.
    ``Weitschüsse`` ist in MONEYBALL_COLUMN_MAP auf None gemappt und fehlt hier.
    """
    rating = _to_int(row.get('fmi_rating'))
    if rating is None:
        return None

    raw_pot = _clean(row.get('fmi_potential'))
    parsed_pot = _to_int(raw_pot)
    block = {
        'rating':         rating,
        'potential':      parsed_pot,
        'attrs':          {},
        'source_version': '',
    }
    if raw_pot and parsed_pot is None:
        block['potential_raw'] = raw_pot

    def _a(key):
        return _to_int(row.get(key))

    a = block['attrs']
    if (v := _a('mb_pace'))            is not None: a['tempo']               = v
    if (v := _a('mb_stamina'))         is not None: a['ausdauer']            = v
    if (v := _a('mb_strength'))        is not None: a['kraft']               = v
    if (v := _a('mb_technique'))       is not None: a['technik']             = v
    if (v := _a('mb_dribbling'))       is not None: a['dribbling']           = v
    if (v := _a('mb_passing'))         is not None:
        a['passspiel']       = v
        a['tw_passen']       = v   # TW: Passen = GK-Passing
    if (v := _a('mb_crossing'))        is not None: a['flanken']             = v
    if (v := _a('mb_tackling'))        is not None: a['zweikampf']           = v
    if (v := _a('mb_positioning'))     is not None:
        a['defensivstellung']  = v
        a['tw_stellungsspiel'] = v   # TW: Stellungsspiel = GK-Positioning
    if (v := _a('mb_finishing'))       is not None: a['abschluss']           = v
    if (v := _a('mb_heading'))         is not None: a['kopfball']            = v
    if (v := _a('mb_vision'))          is not None: a['uebersicht']          = v
    if (v := _a('mb_teamwork'))        is not None: a['teamwork']            = v
    if (v := _a('mb_corners'))         is not None: a['ecken']               = v
    if (v := _a('mb_free_kick_taking'))is not None: a['freistoss']           = v
    if (v := _a('mb_penalty_taking'))  is not None: a['elfmeter']            = v
    if (v := _a('mb_gk_reflexes'))     is not None: a['tw_reflexe']          = v
    if (v := _a('mb_gk_handling'))     is not None: a['tw_fangsicherheit']   = v
    if (v := _a('mb_gk_one_on_ones'))  is not None: a['tw_eins_gegen_eins']  = v
    return block


def parse_moneyball_rows(fileobj):
    """Liest eine Moneyball-CSV (Semikolon, deutsche Header).

    Gibt eine Liste von Roh-Dicts zurück — noch keine vollständige
    ``normalized_data``-Struktur, da Vereins- und Positionsdaten fehlen.
    Die Weiterverarbeitung (Matching, DB-Schreiben) erfolgt in einem
    späteren Schritt.

    Args:
        fileobj: Text-Dateiobj oder ``io.StringIO``.

    Returns:
        list[dict] mit den Schlüsseln:
            display_name, fm_unique_id, verein,
            height_cm, strong_foot,
            primary_nationality, nationalities,
            date_of_birth, fmi_ratings.
    """
    reader = csv.DictReader(fileobj, delimiter=';')
    rows = []
    for raw in reader:
        mapped = {}
        for col, val in raw.items():
            internal = MONEYBALL_COLUMN_MAP.get(col)
            if internal is not None:
                mapped[internal] = val

        primary, joined = normalize_nationalities(
            mapped.get('primary_nationality'),
            mapped.get('second_nationality'),
        )

        rows.append({
            'display_name':        _clean(mapped.get('display_name')),
            'fm_unique_id':        _to_int(mapped.get('fm_unique_id')),
            'verein':              _clean(mapped.get('verein')),
            'height_cm':           parse_height(mapped.get('height_cm')),
            'strong_foot':         parse_foot(mapped.get('preferred_foot')),
            'primary_nationality': primary,
            'nationalities':       joined,
            'date_of_birth':       _parse_date_de(mapped.get('date_of_birth')),
            'fmi_ratings':         _moneyball_fmi_block(mapped),
        })
    return rows
