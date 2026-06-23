"""Reine (seed-deterministische) Kandidatenfilter und -ziehung.

Alle Funktionen sind seiteneffektfrei und testbar. Die Auswahl wird über einen
``random.Random``-Seed deterministisch gemacht; der Service friert die gezogenen
Spieler-IDs danach in ``ScoutingFind`` ein und berechnet nie neu.
"""

import math
import random

from .constants import (
    COUNTRIES,
    REGIONS,
    PROFILE_STRENGTH_BANDS,
    PROFILE_TALENT_MAX_AGE,
    TOP_STAR_STRENGTH,
    TOP_TALENT_POTENTIAL,
    TOP_TALENT_MAX_AGE,
    region_iso_codes,
    continent_iso_codes,
)
from .geo import player_country_iso2

POSITION_GROUP = {
    'TW': 'gk',
    'IV': 'def', 'LV': 'def', 'RV': 'def', 'LOV': 'def', 'ROV': 'def',
    'DM': 'mid', 'ZM': 'mid', 'LM': 'mid', 'RM': 'mid',
    'LOM': 'att', 'ROM': 'att', 'OM': 'att', 'LF': 'att', 'RF': 'att', 'ST': 'att',
}


def player_base_strength(player):
    sp = getattr(player, 'strength_profile', None)
    if sp is None:
        return 50.0
    try:
        return float(sp.base_strength)
    except (TypeError, ValueError):
        return 50.0


def player_main_positions(player):
    return [p for p in (player.main_position_1, player.main_position_2, player.main_position_3) if p]


def player_secondary_positions(player):
    return [p for p in (player.secondary_position_1, player.secondary_position_2, player.secondary_position_3) if p]


def is_top_reserved(player):
    """True, wenn der Spieler als Top-Star/Top-Talent nicht über Scouting verpflichtbar ist."""
    from game.models import Player
    if player.pool_status == Player.POOL_STATUS_AUCTION_RESERVED:
        return True
    if player.scouting_category in ('topstar', 'toptalent'):
        return True
    if player_base_strength(player) >= TOP_STAR_STRENGTH:
        return True
    age = int(player.age or 99)
    if age <= TOP_TALENT_MAX_AGE and int(player.potential or 0) >= TOP_TALENT_POTENTIAL:
        return True
    return False


def scope_iso_set(scope_type, scope_key):
    if scope_type == 'region':
        return set(region_iso_codes(scope_key))
    return {(scope_key or '').upper()}


def _eligible_in_isos(isos):
    """Scoutbare Poolspieler in einer ISO2-Menge, ohne Top-Stars/Top-Talente."""
    from game.models import Player
    qs = (
        Player.objects
        .filter(club__isnull=True, pool_status=Player.POOL_STATUS_SCOUTABLE)
        .select_related('strength_profile')
    )
    out = []
    for player in qs:
        if player_country_iso2(player) not in isos:
            continue
        if is_top_reserved(player):
            continue
        out.append(player)
    out.sort(key=lambda p: p.id)
    return out


def eligible_players(scope_type, scope_key):
    """Scoutbare Poolspieler im Suchgebiet, ohne Top-Stars/Top-Talente."""
    return _eligible_in_isos(scope_iso_set(scope_type, scope_key))


def widen_iso_levels(scope_type, scope_key):
    """Progressiv weiter werdende ISO2-Mengen (Suchgebiet → Region → Kontinent → Welt).

    Dient als Fallback, um auch bei dünnem Suchgebiet die geforderten genau
    drei Funde garantieren zu können (Aufweitung erst, wenn nötig).
    """
    levels = [scope_iso_set(scope_type, scope_key)]
    if scope_type == 'region':
        cont = (REGIONS.get(scope_key) or {}).get('continent')
        if cont:
            levels.append(set(continent_iso_codes(cont)))
    else:
        rec = COUNTRIES.get((scope_key or '').upper())
        if rec:
            levels.append(set(region_iso_codes(rec['region'])))
            levels.append(set(continent_iso_codes(rec['continent'])))
    levels.append(set(COUNTRIES.keys()))
    return levels


def eligible_players_filled(scope_type, scope_key, min_count):
    """Wie ``eligible_players``, weitet das Gebiet aber bis ``min_count`` auf.

    Solange das Suchgebiet selbst genug Kandidaten liefert, ist das Ergebnis
    identisch zu ``eligible_players``; erst bei Unterdeckung werden Region,
    Kontinent und schließlich die Welt hinzugezogen (Garantie für genau 3 Funde).
    """
    seen = set()
    out = []
    for isos in widen_iso_levels(scope_type, scope_key):
        for player in _eligible_in_isos(isos):
            if player.id not in seen:
                seen.add(player.id)
                out.append(player)
        if len(out) >= min_count:
            break
    return out


def team_average_strength(club):
    from game.models import PlayerStrengthProfile
    from django.db.models import Avg
    if club is None:
        return 65.0
    agg = (
        PlayerStrengthProfile.objects
        .filter(player__club=club)
        .aggregate(avg=Avg('base_strength'))
    )
    return float(agg['avg']) if agg['avg'] is not None else 65.0


def _position_factor(player, position):
    if not position:
        return 1.0
    if position in player_main_positions(player):
        return 1.0
    if position in player_secondary_positions(player):
        return 0.6
    target_group = POSITION_GROUP.get(position)
    for p in player_main_positions(player) + player_secondary_positions(player):
        if POSITION_GROUP.get(p) == target_group:
            return 0.4
    return 0.2


def _profile_factor(player, team_avg, profile):
    bs = player_base_strength(player)
    if profile == 'talent':
        age = int(player.age or 99)
        if age <= 19:
            talent_age = 1.2
        elif age <= PROFILE_TALENT_MAX_AGE:
            talent_age = 1.0
        elif age <= 24:
            talent_age = 0.5
        else:
            talent_age = 0.2
        potential = int(player.potential or 50)
        talent_pot = max(0.5, min(1.5, 0.5 + (potential - 60) / 80.0))
        return talent_age * talent_pot

    lo, hi = PROFILE_STRENGTH_BANDS.get(profile, (-5, 2))
    center = team_avg + (lo + hi) / 2.0
    width = (hi - lo) / 2.0 + 2.0
    fit = math.exp(-(((bs - center) / width) ** 2))
    return 0.2 + 0.8 * fit


def _rarity_factor(player):
    if 'TW' in player_main_positions(player):
        return 1.15
    return 1.0


def score_candidate(player, team_avg, profile, position, precision):
    """Gewicht eines Kandidaten (>0). Höhere ``precision`` schärft die Passung."""
    weight = _profile_factor(player, team_avg, profile) * _position_factor(player, position)
    weight *= _rarity_factor(player)
    exponent = 0.5 + 1.5 * max(0.0, min(1.0, precision))
    final = weight ** exponent
    return max(final, 0.02)


def weighted_sample(candidates, weights, k, rng):
    """Gewichtete Ziehung ohne Zurücklegen (deterministisch über ``rng``)."""
    pool = list(zip(candidates, weights))
    chosen = []
    for _ in range(min(k, len(pool))):
        total = sum(w for _, w in pool)
        if total <= 0:
            chosen.append(pool.pop(0)[0])
            continue
        r = rng.random() * total
        acc = 0.0
        for idx, (cand, w) in enumerate(pool):
            acc += w
            if r <= acc:
                chosen.append(cand)
                pool.pop(idx)
                break
        else:
            chosen.append(pool.pop()[0])
    return chosen


def draw_candidates(candidates, team_avg, profile, position, precision, seed, k=3):
    """Wähle bis zu ``k`` Kandidaten gewichtet und deterministisch (Seed)."""
    if not candidates:
        return []
    rng = random.Random(seed)
    weights = [score_candidate(c, team_avg, profile, position, precision) for c in candidates]
    return weighted_sample(candidates, weights, k, rng)
