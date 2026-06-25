"""
Websoccer Spielstärke-Engine (v2.0)

Reine Python-Berechnungsfunktionen ohne Django-Imports.
Datenbank-Lesen passiert in views_creator._build_strength_tab_context().

Spec: websoccer_spielstaerke_spezifikation_v2 (2026-06-09)
"""

# ---------------------------------------------------------------------------
# Positions-Mapping: Spielcode → Profilschlüssel
# ---------------------------------------------------------------------------

POSITION_TO_PROFILE = {
    # Torwart
    'TW': 'TW',
    # Innenverteidiger
    'IV': 'IV', 'LIV': 'IV', 'RIV': 'IV', 'ZIV': 'IV',
    # Außenverteidiger (LOV/ROV = overlapping fullbacks)
    'LV': 'AV', 'RV': 'AV', 'LAV': 'AV', 'RAV': 'AV', 'LOV': 'AV', 'ROV': 'AV',
    # Defensives Mittelfeld
    'DM': 'DM', 'ZDM': 'DM',
    # Zentrales Mittelfeld
    'ZM': 'ZM', 'CM': 'ZM',
    # Offensives Mittelfeld (LOM/ROM = halboffensiv)
    'OM': 'OM', 'ZOM': 'OM', 'CAM': 'OM', 'LOM': 'OM', 'ROM': 'OM',
    # Flügelspieler (LA/RA sind KEINE Außenverteidiger)
    'LM': 'FL', 'RM': 'FL', 'LA': 'FL', 'RA': 'FL', 'LF': 'FL', 'RF': 'FL',
    # Stürmer
    'ST': 'ST', 'MS': 'ST', 'CF': 'ST', 'HS': 'ST', 'SS': 'ST',
}

PROFILE_KEYS_ORDERED = ['TW', 'IV', 'AV', 'DM', 'ZM', 'OM', 'FL', 'ST']

PROFILE_LABELS = {
    'TW': 'Torwart',
    'IV': 'Innenverteidiger',
    'AV': 'Außenverteidiger',
    'DM': 'Defensives Mittelfeld',
    'ZM': 'Zentrales Mittelfeld',
    'OM': 'Offensives Mittelfeld',
    'FL': 'Flügelspieler',
    'ST': 'Stürmer',
}

# Gewichtungen je Profil (summieren zu 100)
PROFILE_WEIGHTS = {
    'TW': {
        'tw_reflexe': 30, 'tw_fangsicherheit': 20, 'tw_eins_gegen_eins': 20,
        'tw_stellungsspiel': 20, 'tw_passen': 10,
    },
    'IV': {
        'zweikampf': 22, 'defensivstellung': 22, 'kopfball': 18,
        'kraft': 12, 'teamwork': 10, 'passspiel': 8, 'tempo': 8,
    },
    'AV': {
        'tempo': 18, 'ausdauer': 16, 'zweikampf': 16, 'defensivstellung': 14,
        'flanken': 14, 'passspiel': 10, 'technik': 8, 'teamwork': 4,
    },
    'DM': {
        'defensivstellung': 18, 'zweikampf': 18, 'passspiel': 16, 'uebersicht': 14,
        'ausdauer': 12, 'teamwork': 10, 'kraft': 6, 'technik': 6,
    },
    'ZM': {
        'passspiel': 20, 'uebersicht': 18, 'technik': 14, 'ausdauer': 12,
        'teamwork': 10, 'defensivstellung': 8, 'dribbling': 8, 'zweikampf': 6, 'tempo': 4,
    },
    'OM': {
        'uebersicht': 20, 'technik': 18, 'passspiel': 16, 'dribbling': 14,
        'abschluss': 10, 'teamwork': 8, 'tempo': 8, 'ausdauer': 6,
    },
    'FL': {
        'tempo': 22, 'dribbling': 20, 'flanken': 16, 'technik': 12,
        'abschluss': 10, 'passspiel': 8, 'ausdauer': 8, 'uebersicht': 4,
    },
    'ST': {
        'abschluss': 24, 'tempo': 14, 'kopfball': 12, 'technik': 12,
        'dribbling': 10, 'teamwork': 10, 'kraft': 8, 'uebersicht': 6, 'ausdauer': 4,
    },
}

# RL-Form-Skala: Durchschnittsnote → Form-Score (-5 … +5)
RL_FORM_SCALE = [
    (8.0,  float('inf'), 5),
    (7.7,  8.0,          4),
    (7.4,  7.7,          3),
    (7.1,  7.4,          2),
    (6.9,  7.1,          1),
    (6.5,  6.9,          0),
    (6.3,  6.5,         -1),
    (6.1,  6.3,         -2),
    (5.9,  6.1,         -3),
    (5.6,  5.9,         -4),
    (0.0,  5.6,         -5),
]

RL_FORM_FIT = {
    -5: 0.94, -4: 0.95, -3: 0.96, -2: 0.98, -1: 0.99,
     0: 1.00,  1: 1.01,  2: 1.02,  3: 1.04,  4: 1.05,  5: 1.06,
}

# Additive Boni/Mali für die finale Stärkeformel
# final = pre_fit * position_fit + freshness_bonus + rl_form_bonus
RL_FORM_BONUS = {
    -5: -8, -4: -6, -3: -5, -2: -3, -1: -1,
     0:  0,
     1:  1,  2:  2,  3:  4,  4:  5,  5:  6,
}

# (lo, hi, bonus) — hi ist exklusiv; < 50 als Fallback
FRESHNESS_BONUS_TABLE = [
    (85, 101,   0),
    (75,  85,  -2),
    (65,  75,  -5),
    (50,  65, -10),
    ( 0,  50, -18),
]

FRESHNESS_FIT_TABLE = [
    (95, 101,  1.02),
    (85,  95,  1.00),
    (75,  85,  0.97),
    (65,  75,  0.93),
    (50,  65,  0.87),
    ( 0,  50,  0.78),
]

CONSTANCY_LABELS = [
    ( 0,  10, 'sehr konstant'),
    (10,  20, 'zuverlässig'),
    (20,  30, 'schwankend'),
    (30,  50, 'stark schwankend'),
    (50, 999, 'sehr unberechenbar'),
]


# ---------------------------------------------------------------------------
# NULL-sichere Aggregation
# ---------------------------------------------------------------------------

def combine_source_values(*values):
    """
    Variadic NULL-sichere Aggregation.
    - alle None   → None
    - eine vorhanden  → dieser Wert
    - mehrere vorhanden → Durchschnitt (gerundet)
    0 ist ein gültiger Wert; None bedeutet „Quelle liefert nichts".
    """
    valid = [v for v in values if v is not None]
    if not valid:
        return None
    return round(sum(valid) / len(valid))


# ---------------------------------------------------------------------------
# Basis und Potential (0–200)
# ---------------------------------------------------------------------------

def calculate_base_200(fmi_rating, ea_rating):
    """
    Basisstärke auf 0–200.
    beide vorhanden → FMI + CMTracker
    eine vorhanden  → Quelle × 2
    keine vorhanden → None
    """
    if fmi_rating is not None and ea_rating is not None:
        return int(fmi_rating) + int(ea_rating)
    if fmi_rating is not None:
        return int(fmi_rating) * 2
    if ea_rating is not None:
        return int(ea_rating) * 2
    return None


def calculate_potential_200(fmi_potential, ea_potential, base_200):
    """
    Potential auf 0–200.
    beide vorhanden → FMI + CMTracker
    eine vorhanden  → Quelle × 2
    keine vorhanden → None  (keine Quelle → nicht berechenbar, kein Fallback)
    Wenn Potential < Basis: max(potential, base_200)
    """
    if fmi_potential is not None and ea_potential is not None:
        raw = int(fmi_potential) + int(ea_potential)
    elif fmi_potential is not None:
        raw = int(fmi_potential) * 2
    elif ea_potential is not None:
        raw = int(ea_potential) * 2
    else:
        return None  # Keine Quelle → explizit None, kein stilles Fallback

    if base_200 is None:
        return raw
    return max(raw, base_200)


# ---------------------------------------------------------------------------
# Kombinierte Attribute
# ---------------------------------------------------------------------------

def get_combined_attributes(fmi_attrs, ea_attrs, attr_cols):
    """
    Berechnet kombinierte Attributwerte aus FMI- und EA-Dictionaries.

    Args:
        fmi_attrs: dict {col: value_or_None}
        ea_attrs:  dict {col: value_or_None}
        attr_cols: list of column names to process

    Returns:
        list of dicts with keys:
            col, fmi, ea, combined, delta, warning
            warning: None | 'yellow' | 'red'
    """
    result = []
    for col in attr_cols:
        fmi = fmi_attrs.get(col)
        ea = ea_attrs.get(col)
        combined = combine_source_values(fmi, ea)

        if fmi is not None and ea is not None:
            delta = abs(fmi - ea)
        else:
            delta = None

        if delta is None:
            warning = None
        elif delta > 30:
            warning = 'red'
        elif delta > 15:
            warning = 'yellow'
        else:
            warning = None

        result.append({
            'col': col,
            'fmi': fmi,
            'ea': ea,
            'combined': combined,
            'delta': delta,
            'warning': warning,
        })
    return result


# ---------------------------------------------------------------------------
# Positionsprofil
# ---------------------------------------------------------------------------

def get_position_profile(combined_attrs_dict, profile_key):
    """
    Berechnet das gewichtete Positionsprofil (0–100) für einen Profilschlüssel.
    NULL-Attribute werden übersprungen; ihr Gewicht wird proportional auf
    vorhandene Attribute umverteilt.

    Args:
        combined_attrs_dict: dict {col: combined_value_or_None}
        profile_key: 'IV' | 'AV' | 'DM' | 'ZM' | 'OM' | 'FL' | 'ST' | 'TW'

    Returns:
        float 0–100 or None (wenn alle relevanten Attribute fehlen)
    """
    weights = PROFILE_WEIGHTS.get(profile_key, {})
    total_weight = 0
    weighted_sum = 0.0

    for col, weight in weights.items():
        val = combined_attrs_dict.get(col)
        if val is not None:
            weighted_sum += val * weight
            total_weight += weight

    if total_weight == 0:
        return None

    return weighted_sum / total_weight


def get_all_position_profiles(combined_attrs_dict):
    """
    Berechnet alle 8 Positionsprofile auf einmal.

    Returns:
        dict {profile_key: score_or_None}
    """
    return {
        key: get_position_profile(combined_attrs_dict, key)
        for key in PROFILE_KEYS_ORDERED
    }


# ---------------------------------------------------------------------------
# Positions-Fit
# ---------------------------------------------------------------------------

def get_position_fit(played_position, main_positions, secondary_positions):
    """
    Positions-Fit-Faktor.

    Returns:
        (factor: float, label: str, unknown: bool)
    """
    if played_position not in POSITION_TO_PROFILE:
        return (None, '?', True)

    is_gk_played = (played_position == 'TW')
    primary = main_positions[0] if main_positions else ''
    is_gk_player = (primary == 'TW')

    if is_gk_player and not is_gk_played:
        return (0.30, 'Torwart im Feld', False)
    if not is_gk_player and is_gk_played:
        return (0.25, 'Feldspieler im Tor', False)
    if played_position == primary:
        return (1.00, 'Hauptposition', False)
    if played_position in secondary_positions:
        return (0.90, 'Nebenposition', False)
    return (0.70, 'Fremdposition', False)


# ---------------------------------------------------------------------------
# Frische-Fit
# ---------------------------------------------------------------------------

def get_freshness_fit(freshness):
    """
    freshness: float 0–100 (oder None → 1.00 neutral)
    Returns: (factor: float, range_label: str)
    """
    if freshness is None:
        return (1.00, '–')
    f = float(freshness)
    for lo, hi, factor in FRESHNESS_FIT_TABLE:
        if lo <= f < hi:
            hi_label = str(hi) if hi <= 100 else '100'
            return (factor, f'{lo}–{hi_label}')
    return (0.78, '< 50')


def get_freshness_bonus(freshness):
    """Additiver Frische-Bonus für die finale Stärkeformel.

    freshness: float 0–100 (oder None → 0 neutral)
    Returns: (bonus: int, range_label: str)
    """
    if freshness is None:
        return (0, '–')
    f = float(freshness)
    for lo, hi, bonus in FRESHNESS_BONUS_TABLE:
        if lo <= f < hi:
            hi_label = str(hi) if hi <= 100 else '100'
            return (bonus, f'{lo}–{hi_label}')
    return (-18, '< 50')


def get_rl_form_bonus(score):
    """Additiver RL-Form-Bonus für die finale Stärkeformel.

    MVP: RL-Form deaktiviert (bis Abo-Modell verfügbar) → immer 0.
    score: int -5..+5  (wird ignoriert)
    Returns: int (immer 0)
    """
    return 0


# ---------------------------------------------------------------------------
# RL-Form
# ---------------------------------------------------------------------------

def calculate_rl_form_from_snapshots(snapshots, *, no_mapping=False):
    """
    Args:
        snapshots:   list of dicts mit keys 'rating' und 'minutes_played'
                     (maximal 10 Einträge, bereits nach Datum sortiert)
        no_mapping:  True wenn der Spieler überhaupt kein API-Football-Mapping hat.
                     In diesem Fall wird score=0 (neutral) zurückgegeben, NICHT −2.
                     Spieler sollen nicht für fehlende Datenqualität bestraft werden.

    Returns:
        dict mit:
            score:         int -5..+5
            avg_rating:    float or None
            total_minutes: int
            no_data:       bool  – True wenn Mapping vorhanden aber keine Einsätze
            no_mapping:    bool  – True wenn gar kein API-Mapping existiert
    """
    if no_mapping:
        return {
            'score': 0,
            'avg_rating': None,
            'total_minutes': 0,
            'no_data': False,
            'no_mapping': True,
        }

    valid = [s for s in snapshots if s.get('minutes_played', 0) > 0 and s.get('rating') is not None]

    total_minutes = sum(s['minutes_played'] for s in valid)

    if total_minutes == 0:
        return {
            'score': -2,
            'avg_rating': None,
            'total_minutes': 0,
            'no_data': True,
            'no_mapping': False,
        }

    avg_rating = sum(float(s['rating']) * s['minutes_played'] for s in valid) / total_minutes

    for lo, hi, score in RL_FORM_SCALE:
        if lo <= avg_rating < hi:
            raw_score = score
            break
    else:
        raw_score = -5

    if total_minutes < 90:
        raw_score = min(0, round(raw_score * 0.25))
    elif total_minutes < 270:
        raw_score = max(-3, min(2, round(raw_score * 0.50)))
    elif total_minutes < 540:
        raw_score = max(-4, min(3, round(raw_score * 0.75)))

    return {
        'score': raw_score,
        'avg_rating': round(avg_rating, 2),
        'total_minutes': total_minutes,
        'no_data': False,
        'no_mapping': False,
    }


def get_rl_form_fit(score):
    return RL_FORM_FIT.get(score, 1.00)


# ---------------------------------------------------------------------------
# Konstanz-Label
# ---------------------------------------------------------------------------

def get_constancy_label(gap):
    if gap is None:
        return '–'
    for lo, hi, label in CONSTANCY_LABELS:
        if lo <= gap < hi:
            return label
    return 'unberechenbar'


# ---------------------------------------------------------------------------
# Form-Modifier (additive RL-Form-Delta für PlayerStrengthProfile)
# ---------------------------------------------------------------------------

def calculate_form_modifier(base_200, rl_form_factor):
    """
    Wandelt den multiplikativen RL-Form-Fit in einen additiven Modifier um,
    der in PlayerStrengthProfile.form_modifier gespeichert wird.

    form_modifier = base_200 * (rl_form_factor - 1.0)

    Beispiel: base=177, factor=0.98 → modifier = 177 * (-0.02) = -3.54
    """
    from decimal import Decimal
    if base_200 is None:
        return Decimal('0.00')
    result = Decimal(str(base_200)) * (Decimal(str(rl_form_factor)) - Decimal('1'))
    return result.quantize(Decimal('0.01'))


# ---------------------------------------------------------------------------
# Finale Stärke-Range
# ---------------------------------------------------------------------------

def get_strength_range(base_200, potential_200, profile_100, position_fit,
                       freshness_bonus, rl_form_bonus):
    """
    Berechnet die theoretische Stärke-Range [Minimum, Maximum].

    Formel (additiv):
        pre  = match_base × 0.80 + profile_200 × 0.20
        final = pre × position_fit + freshness_bonus + rl_form_bonus

    Args:
        freshness_bonus: int  (aus get_freshness_bonus)
        rl_form_bonus:   int  (aus get_rl_form_bonus)

    Returns:
        (min_strength: int, max_strength: int) or (None, None)
    """
    if base_200 is None or potential_200 is None or position_fit is None:
        return (None, None)

    profile_200 = (profile_100 * 2) if profile_100 is not None else base_200

    def calc(match_base):
        pre = match_base * 0.80 + profile_200 * 0.20
        final = pre * position_fit + freshness_bonus + rl_form_bonus
        return max(1, min(200, round(final)))

    return (calc(base_200), calc(potential_200))
