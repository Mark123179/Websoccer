"""
Strength service — database-aware wrapper around strength_engine.py.

Provides compute_strength_for_player(player) which runs the full engine
pipeline and returns the calculated strength values. Used by both the
management command and the Creator recalculate view.
"""

from decimal import Decimal

from django.utils import timezone

from . import strength_engine as se
from .models import PlayerFormSnapshot, PlayerRLFormProfile, PlayerSourceRating, PlayerStrengthProfile

OUTFIELD_ATTR_COLS = [
    'tempo', 'ausdauer', 'kraft', 'technik', 'dribbling', 'passspiel',
    'flanken', 'abschluss', 'kopfball', 'zweikampf', 'defensivstellung',
    'uebersicht', 'teamwork',
]

GK_ATTR_COLS = [
    'tw_reflexe', 'tw_fangsicherheit', 'tw_eins_gegen_eins',
    'tw_stellungsspiel', 'tw_passen',
]


def _row_attrs(row, cols):
    if row is None:
        return {c: None for c in cols}
    return {c: getattr(row, c, None) for c in cols}


def compute_strength_for_player(player):
    """
    Runs the full strength_engine pipeline for one player.

    Returns a dict:
        base_strength  — Decimal: engine-calculated strength from base ratings
                         (= str_min cast to Decimal), or None if not computable.
        max_strength   — Decimal: engine-calculated strength from potential
                         (= str_max cast to Decimal), or None.
        str_min        — int or None
        str_max        — int or None
        computable     — bool: False when source ratings are missing
    """
    rows = {r.source: r for r in player.source_ratings.all()}
    fm_row = rows.get(PlayerSourceRating.SOURCE_FM)
    ea_row = rows.get(PlayerSourceRating.SOURCE_EA)

    fmi_rating    = fm_row.rating    if fm_row else None
    fmi_potential = fm_row.potential if fm_row else None
    ea_rating     = ea_row.rating    if ea_row else None
    ea_potential  = ea_row.potential if ea_row else None

    base_200      = se.calculate_base_200(fmi_rating, ea_rating)
    potential_200 = se.calculate_potential_200(fmi_potential, ea_potential, base_200)

    if base_200 is None:
        return {'base_strength': None, 'max_strength': None,
                'str_min': None, 'str_max': None, 'computable': False}

    is_gk = player.position == 'TW'
    attr_cols = GK_ATTR_COLS if is_gk else OUTFIELD_ATTR_COLS

    fmi_attrs = _row_attrs(fm_row, attr_cols)
    ea_attrs  = _row_attrs(ea_row,  attr_cols)

    combined_attrs      = se.get_combined_attributes(fmi_attrs, ea_attrs, attr_cols)
    combined_attrs_dict = {a['col']: a['combined'] for a in combined_attrs}

    main_positions      = player.main_positions
    secondary_positions = player.secondary_positions
    played_pos          = player.position or (main_positions[0] if main_positions else '')

    played_profile_key   = se.POSITION_TO_PROFILE.get(played_pos)
    played_profile_score = (
        se.get_position_profile(combined_attrs_dict, played_profile_key)
        if played_profile_key else None
    )

    pos_fit_factor, _pos_fit_label, _pos_unknown = se.get_position_fit(
        played_pos, main_positions, secondary_positions,
    )

    try:
        sp = player.strength_profile
        freshness_val = float(sp.freshness) if sp.freshness is not None else None
    except PlayerStrengthProfile.DoesNotExist:
        freshness_val = None
    freshness_factor, _ = se.get_freshness_fit(freshness_val)

    form_snapshots_qs = (
        player.form_snapshots
        .filter(source=PlayerFormSnapshot.SOURCE_API_FOOTBALL)
        .order_by('-fixture_date')[:10]
    )
    snapshots_data = [
        {'rating': s.rating, 'minutes_played': s.minutes_played}
        for s in form_snapshots_qs
    ]
    rl_form_result = se.calculate_rl_form_from_snapshots(snapshots_data)
    rl_form_factor = se.get_rl_form_fit(rl_form_result['score'])

    if pos_fit_factor is not None:
        str_min, str_max = se.get_strength_range(
            base_200, potential_200, played_profile_score,
            pos_fit_factor, freshness_factor, rl_form_factor,
        )
    else:
        str_min, str_max = None, None

    base_strength = Decimal(str(str_min)) if str_min is not None else None
    max_strength  = Decimal(str(str_max)) if str_max is not None else None

    return {
        'base_strength': base_strength,
        'max_strength':  max_strength,
        'str_min':       str_min,
        'str_max':       str_max,
        'computable':    base_strength is not None,
    }


def compute_rl_form_for_player(player):
    """Berechnet RL-Form-Score aus PlayerFormSnapshot-Einträgen und schreibt
    das Ergebnis in PlayerRLFormProfile. Erstellt das Profil, falls nötig.

    Returns dict:
        score   — int
        fit     — float
        status  — str (PlayerRLFormProfile.STATUS_*)
    """
    try:
        profile = player.rl_form_profile
        has_mapping = bool(
            profile.api_football_player_id and profile.api_football_team_id
        )
    except PlayerRLFormProfile.DoesNotExist:
        profile = PlayerRLFormProfile(player=player)
        has_mapping = False

    form_snapshots_qs = (
        player.form_snapshots
        .filter(source=PlayerFormSnapshot.SOURCE_API_FOOTBALL)
        .order_by('-fixture_date')[:10]
    )
    snapshots_data = [
        {'rating': s.rating, 'minutes_played': s.minutes_played}
        for s in form_snapshots_qs
    ]

    result = se.calculate_rl_form_from_snapshots(
        snapshots_data, no_mapping=not has_mapping
    )

    total_minutes = result.get('total_minutes', 0)
    games_played  = sum(1 for s in snapshots_data if s.get('minutes_played', 0) > 0)

    profile.rl_form_score         = result['score']
    profile.rl_form_fit           = Decimal(str(se.get_rl_form_fit(result['score'])))
    profile.rl_form_avg_rating    = (
        Decimal(str(result['avg_rating'])) if result.get('avg_rating') is not None else None
    )
    profile.rl_form_minutes       = total_minutes
    profile.rl_form_games_checked = len(snapshots_data)
    profile.rl_form_games_played  = games_played
    profile.rl_form_minutes_share = Decimal(str(round(total_minutes / 900 * 100, 2)))
    profile.rl_form_updated_at    = timezone.now()

    if result.get('no_mapping'):
        profile.rl_form_status = PlayerRLFormProfile.STATUS_NOT_MAPPED
    elif result.get('no_data'):
        profile.rl_form_status = (
            PlayerRLFormProfile.STATUS_MINUTES_WITHOUT_RATING
            if snapshots_data else PlayerRLFormProfile.STATUS_NO_MINUTES
        )
    else:
        profile.rl_form_status = PlayerRLFormProfile.STATUS_FETCHED

    profile.save()

    return {
        'score':  result['score'],
        'fit':    float(profile.rl_form_fit),
        'status': profile.rl_form_status,
    }
