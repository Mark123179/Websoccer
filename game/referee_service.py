"""
Schiedsrichter-Auswahl nach Berechtigungs- und Rotationsregeln.

Einstiegspunkt : pick_referee(home_club, away_club, *, ...)
Batch-Aufrufe  : preload_referee_pool() einmalig laden und _preloaded= übergeben.

Spec: SPEC_Schiedsrichter.md Kap. 3+4 (Berechtigung + gewichteter Zufall).
"""

import hashlib
import logging
import math
import random

from django.db.models import Count, Q

logger = logging.getLogger(__name__)

# ── Cup-Runden-Klassen ──────────────────────────────────────────────────────
_FINAL_ROUNDS = frozenset({'semi_final', 'final'})
_LATE_ROUNDS  = frozenset({'quarter_final', 'semi_final', 'final'})


# ── Domestic-Tier-Berechnung ────────────────────────────────────────────────
def _tier1_pks_for_nation(nationality):
    """Frozenset der Referee-PKs in Tier 1 der gegebenen Nation.

    Tier 1 = Top-N₁ Refs nach (quote DESC, level DESC).
    N₁ = ceil(Spiele/Spieltag der 1. Liga × 1.5).
    Mindestens 3, damit der Pool nie leer ist.
    """
    from .models import Referee, League

    top_league = (
        League.objects
        .filter(country=nationality, competition_type='league')
        .order_by('level')
        .first()
    )
    spiele_pro_spieltag = (top_league.max_teams // 2) if top_league else 9
    n1 = max(3, math.ceil(spiele_pro_spieltag * 1.5))

    pks = list(
        Referee.objects
        .filter(nationality=nationality)
        .order_by('-quote', '-level', 'pk')
        .values_list('pk', flat=True)[:n1]
    )
    return frozenset(pks)


# ── Rotationssperre ─────────────────────────────────────────────────────────
def _rotation_excluded_pks(home_club, away_club, league, matchday):
    """PKs der Refs, die am unmittelbar vorigen Spieltag eines der Teams hatten.

    Harte Sperre gemäß Spec: Ref beim letzten Spieltag dieses Teams = ausgeschlossen.
    """
    if matchday is None or matchday <= 1:
        return set()
    from .models import SimulatedMatch

    return set(
        SimulatedMatch.objects
        .filter(
            Q(home_club=home_club) | Q(home_club=away_club)
            | Q(away_club=home_club) | Q(away_club=away_club),
            referee__isnull=False,
            season_fixture__league=league,
            season_fixture__matchday=matchday - 1,
        )
        .values_list('referee_id', flat=True)
        .distinct()
    )


# ── Nutzungs-Map (letzte 5 Spieltage) ──────────────────────────────────────
def _usage_map(nationality, league, last5_matchdays):
    """Gibt {referee_pk: einsaetze} für die letzten 5 Spieltage zurück."""
    if not last5_matchdays or league is None:
        return {}
    from .models import SimulatedMatch

    rows = (
        SimulatedMatch.objects
        .filter(
            referee__isnull=False,
            referee__nationality=nationality,
            season_fixture__league=league,
            season_fixture__matchday__in=last5_matchdays,
        )
        .values('referee_id')
        .annotate(cnt=Count('pk'))
    )
    return {r['referee_id']: r['cnt'] for r in rows}


# ── Auswahlgewicht ──────────────────────────────────────────────────────────
def _weight(ref, einsaetze):
    """gewicht = 100 − 5 × einsaetze + quote/20, Untergrenze 10."""
    return max(10, 100 - 5 * einsaetze + ref.quote // 20)


# ── Reproduzierbarer Spieltag-Seed ──────────────────────────────────────────
def _spieltag_seed(league_pk, matchday, season):
    key = f'ref:{league_pk}:{season}:{matchday}'
    return int(hashlib.sha256(key.encode()).hexdigest()[:8], 16)


# ── Pool-Filterung (preloaded dict ODER DB-Fallback) ───────────────────────
def _filter_pool(preloaded, nationality, *, tier_pks=None, min_level=None):
    """Gibt gefilterte Referee-Liste zurück.

    preloaded : dict aus preload_referee_pool() oder None (→ DB-Query).
    nationality: None bedeutet „beliebige Nation" (nur für Freundschaft/Fallback).
    """
    if preloaded is not None:
        pool = preloaded.get(nationality) if nationality else preloaded.get('__all__', [])
        if pool is None:
            pool = []
        if tier_pks is not None:
            pool = [r for r in pool if r.pk in tier_pks]
        if min_level is not None:
            pool = [r for r in pool if r.level >= min_level]
        return list(pool)

    from .models import Referee
    qs = Referee.objects.all()
    if nationality:
        qs = qs.filter(nationality=nationality)
    if tier_pks is not None:
        qs = qs.filter(pk__in=tier_pks)
    if min_level is not None:
        qs = qs.filter(level__gte=min_level)
    return list(qs)


# ── Hauptfunktion ───────────────────────────────────────────────────────────
def pick_referee(home_club, away_club, *,
                 league=None,
                 matchday=None,
                 cup_fixture=None,
                 season='0',
                 _preloaded=None):
    """Wählt gemäß Berechtigungs- und Rotationsregeln einen Schiedsrichter.

    Args:
        home_club, away_club : Club-Instanzen (dürfen None sein, → Fallback)
        league               : SeasonFixture.league  (Liga-Spiele)
        matchday             : Spieltag-Nummer       (Liga, für Rotationssperre)
        cup_fixture          : CupFixture-Instanz    (Pokal-Spiele)
        season               : Saison-String für reproduzierbaren Seed
        _preloaded           : dict aus preload_referee_pool() — vermeidet N DB-Queries

    Returns:
        Referee | None
    """
    # ── Kontext ─────────────────────────────────────────────────────────────
    if cup_fixture is not None:
        art = 'pokal'
        competition = cup_fixture.cup_round.cup_season.competition
        nation      = competition.country
        round_code  = cup_fixture.cup_round.round_code
        league_pk   = competition.pk
    elif league is not None:
        art        = 'liga'
        nation     = league.country
        round_code = None
        league_pk  = league.pk
    else:
        art        = 'freundschaft'
        round_code = None
        league_pk  = 0
        try:
            club_league = getattr(home_club, 'league', None)
            nation = club_league.country if club_league else None
        except Exception:
            nation = None

    md  = matchday or 0
    rng = random.Random(_spieltag_seed(league_pk, md, season))

    # ── Tier-1-Set (liga level-1 + pokal Viertelfinale) ─────────────────────
    tier1_pks = None
    if nation and (
        (art == 'liga') or
        (art == 'pokal' and round_code in _LATE_ROUNDS and round_code not in _FINAL_ROUNDS)
    ):
        tier1_pks = _tier1_pks_for_nation(nation)

    # ── Berechtigungsfilter ─────────────────────────────────────────────────
    if art == 'liga':
        liga_level = league.level if league else 1
        if liga_level <= 1:
            candidates = _filter_pool(_preloaded, nation, tier_pks=tier1_pks)
        else:
            # 2. Liga und darunter: Tier 1 + Tier 2 (= alle nationalen Refs)
            candidates = _filter_pool(_preloaded, nation)

    elif art == 'pokal':
        if round_code in _FINAL_ROUNDS:
            # Halbfinale/Finale: Level ≥ 4, Fallback höchstes verfügbares Level
            candidates = _filter_pool(_preloaded, nation, min_level=4)
            if not candidates:
                alle_nat = _filter_pool(_preloaded, nation)
                if alle_nat:
                    max_lv   = max(r.level for r in alle_nat)
                    candidates = [r for r in alle_nat if r.level == max_lv]
        elif round_code in _LATE_ROUNDS:
            # Viertelfinale: Tier-1-Refs national
            candidates = _filter_pool(_preloaded, nation, tier_pks=tier1_pks)
        else:
            # Frühe Runden (Runde 1–2): alle nationalen Refs, kein Tier-Filter
            candidates = _filter_pool(_preloaded, nation)

    else:
        # Freundschaft: nationale Refs wenn bekannt, sonst beliebig
        candidates = _filter_pool(_preloaded, nation) if nation else []
        if not candidates:
            candidates = _filter_pool(_preloaded, None)

    # ── Rotationssperre (nur Liga) ──────────────────────────────────────────
    excluded = set()
    if art == 'liga' and league and matchday and matchday > 1:
        excluded = _rotation_excluded_pks(home_club, away_club, league, matchday)
    eligible = [r for r in candidates if r.pk not in excluded]

    # ── Ausnahme-Kaskade ────────────────────────────────────────────────────
    if not eligible and excluded:
        eligible = list(candidates)
        logger.warning(
            'referee_pool_exhausted level=1 (rotation_lock_lifted) '
            'league_pk=%s matchday=%s', league_pk, md,
        )

    if not eligible and art == 'liga' and tier1_pks is not None and league and league.level <= 1:
        eligible = _filter_pool(_preloaded, nation)
        logger.warning(
            'referee_pool_exhausted level=2 (tier_limit_lifted) '
            'league_pk=%s matchday=%s', league_pk, md,
        )

    if not eligible:
        eligible = _filter_pool(_preloaded, nation) if nation else []
        if eligible:
            logger.warning(
                'referee_pool_exhausted level=3 (nation_fallback) '
                'league_pk=%s matchday=%s', league_pk, md,
            )

    if not eligible:
        eligible = _filter_pool(_preloaded, None)
        if eligible:
            logger.warning(
                'referee_pool_exhausted level=4 (any_ref_fallback) '
                'league_pk=%s matchday=%s', league_pk, md,
            )

    if not eligible:
        return None

    # ── Gewichtete Auswahl ──────────────────────────────────────────────────
    if art == 'liga' and league and md >= 1:
        last5   = list(range(max(1, md - 4), md + 1))
        nation_str = nation or ''
        usage   = _usage_map(nation_str, league, last5)
    else:
        usage = {}

    weights = [_weight(r, usage.get(r.pk, 0)) for r in eligible]
    return rng.choices(eligible, weights=weights, k=1)[0]


# ── Batch-Preload ───────────────────────────────────────────────────────────
def preload_referee_pool():
    """Lädt alle Referees einmalig aus der DB, gruppiert nach Nationalität.

    Rückgabe: {nationality: [Referee, ...], '__all__': [Referee, ...]}
    Reihenfolge: quote DESC, level DESC (entspricht Tier-1-Priorität).
    """
    from .models import Referee
    all_refs = list(Referee.objects.order_by('-quote', '-level', 'pk'))
    pool = {'__all__': all_refs}
    for r in all_refs:
        pool.setdefault(r.nationality, []).append(r)
    return pool
