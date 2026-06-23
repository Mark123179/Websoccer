"""Mindestgebot-Formel für Scouting-Funde.

min_bid = market_value * BASE_PREMIUM * age * strength * potential * league
Struktur ist fix; die Faktoren sind kalibrierbare Startwerte. Verborgene
Attribute (base_strength, potential) fließen NUR in die Zahl ein, werden aber
nie ausgegeben.
"""

from decimal import Decimal, ROUND_HALF_UP

from .constants import (
    BID_BASE_PREMIUM,
    BID_MIN_FLOOR,
    BID_ROUND_TO,
    BID_FALLBACK_MARKET_VALUE,
)


def _player_base_strength(player):
    sp = getattr(player, 'strength_profile', None)
    if sp is None:
        return 50.0
    try:
        return float(sp.base_strength)
    except (TypeError, ValueError):
        return 50.0


def _clamp(value, lo, hi):
    return max(lo, min(hi, value))


def age_factor(age):
    age = int(age or 24)
    if age <= 19:
        return 1.15
    if age <= 23:
        return 1.08
    if age <= 27:
        return 1.00
    if age <= 30:
        return 0.92
    return 0.82


def strength_factor(base_strength):
    return _clamp(1.0 + (base_strength - 65.0) / 120.0, 0.85, 1.25)


def potential_factor(potential):
    return _clamp(1.0 + (int(potential or 50) - 65.0) / 150.0, 0.90, 1.25)


def league_factor(player):
    """RL-Liga-Faktor (V1: neutral 1.0, kalibrierbar)."""
    return 1.0


def min_bid_for_player(player):
    mv = player.market_value
    market_value = float(mv) if mv is not None else float(BID_FALLBACK_MARKET_VALUE)

    raw = (
        market_value
        * BID_BASE_PREMIUM
        * age_factor(player.age)
        * strength_factor(_player_base_strength(player))
        * potential_factor(player.potential)
        * league_factor(player)
    )

    rounded = round(raw / BID_ROUND_TO) * BID_ROUND_TO
    rounded = max(rounded, BID_MIN_FLOOR)
    return Decimal(int(rounded)).quantize(Decimal('1.00'), rounding=ROUND_HALF_UP)
