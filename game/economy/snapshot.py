"""SeasonEconomySnapshot — MW-Median & Gehalts-Anker (Spec Kap. 4).

Der Anker wird einmal pro Saison eingefroren und gegenüber dem
Vorsaison-Anker auf max. ±MEDIAN_DAEMPFUNG Bewegung gedämpft. Erste Saison
ohne Vorgänger: roher Median ohne Dämpfung.

ensure_season_snapshot() ist idempotent und wird lazy vom ersten
finance_matchday_run der Saison aufgerufen (Phase 1; ab Phase 2 übernimmt
finance_season_open den Aufruf beim Saisonwechsel).
"""
from decimal import Decimal
from statistics import median

from django.db import transaction

from .params import get_decimal


def _median_or_none(values):
    vals = [v for v in values if v is not None]
    if not vals:
        return None
    return Decimal(str(median([float(v) for v in vals])))


def _mw_kurve(strength_mw_pairs):
    """Median-MW je 5er-Stärkeband (Datenbasis für Schmerzgrenze v2, Phase 4)."""
    bands = {}
    for staerke, mw in strength_mw_pairs:
        if staerke is None or mw is None:
            continue
        band = int(float(staerke) // 5 * 5)
        bands.setdefault(band, []).append(float(mw))
    return {
        str(band): float(median(vals))
        for band, vals in sorted(bands.items())
    }


def compute_snapshot_values(saison):
    """Berechnet Mediane + gedämpften Anker (ohne zu speichern)."""
    from game.models import Player, PlayerStrengthProfile, SeasonEconomySnapshot

    mw_minimum = get_decimal('MW_MINIMUM', saison)
    daempfung = get_decimal('MEDIAN_DAEMPFUNG', saison)

    mws = list(
        Player.objects.filter(market_value__isnull=False)
        .values_list('market_value', flat=True)
    )
    # MW-Clamp auf MW_MINIMUM VOR der Median-Bildung (konsistent zur Formel).
    mw_median = _median_or_none(
        [max(Decimal(str(m)), mw_minimum) for m in mws]
    ) or mw_minimum

    staerke_median = _median_or_none(
        PlayerStrengthProfile.objects.values_list('base_strength', flat=True)
    )

    # Potential-Median nur über Sim-relevante Spieler (mit Stärkeprofil) —
    # dämpft das default=50-Rauschen der Nicht-Sim-Spieler (Phase 4).
    # WICHTIG: auf der 200er-Skala (potential_200), damit der Median mit
    # base_strength vergleichbar ist (Spec 9.2: Potential-Median ~150).
    from .schmerzgrenze import potential_200

    pot_spieler = (
        Player.objects
        .filter(strength_profile__isnull=False)
        .prefetch_related('source_ratings')
    )
    potential_median = _median_or_none(
        [potential_200(p) for p in pot_spieler]
    )

    pairs = list(
        PlayerStrengthProfile.objects
        .filter(player__market_value__isnull=False)
        .values_list('base_strength', 'player__market_value')
    )
    kurve = _mw_kurve(pairs)

    # Dämpfung gegenüber Vorsaison-Anker (numerische Saisons).
    anker = mw_median
    prev = None
    s = str(saison)
    if s.lstrip('-').isdigit():
        prev = (
            SeasonEconomySnapshot.objects
            .filter(saison=str(int(s) - 1))
            .first()
        )
    if prev is not None:
        lo = prev.gehalts_anker * (Decimal('1') - daempfung)
        hi = prev.gehalts_anker * (Decimal('1') + daempfung)
        anker = min(max(mw_median, lo), hi)

    return {
        'mw_median': mw_median.quantize(Decimal('0.01')),
        'staerke_median': staerke_median,
        'potential_median': potential_median,
        'mw_kurve_json': kurve,
        'gehalts_anker': Decimal(anker).quantize(Decimal('0.01')),
    }


def ensure_season_snapshot(saison):
    """Gibt den Snapshot der Saison zurück, berechnet ihn beim ersten Aufruf."""
    from game.models import SeasonEconomySnapshot

    saison = str(saison)
    existing = SeasonEconomySnapshot.objects.filter(saison=saison).first()
    if existing is not None:
        return existing

    values = compute_snapshot_values(saison)
    with transaction.atomic():
        obj, _ = SeasonEconomySnapshot.objects.get_or_create(
            saison=saison, defaults=values,
        )
    return obj
