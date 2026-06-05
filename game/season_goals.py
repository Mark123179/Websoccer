"""Saisonziel-Logik für das Präsidenten-Büro.

Der Präsident bewertet jeden Verein anhand seiner Kaderstärke
(Summe der Top-11 ``base_strength``) relativ zur restlichen Liga,
leitet daraus eine Ziel-Kategorie ab und prüft sie zu Saisonende.

Hinweis: Solange es keine echte Spielsimulation/Ligatabelle gibt,
wird der Endplatz ebenfalls aus der Kaderstärke abgeleitet. Sobald
echte Tabellenstände existieren, kann ``final_rank`` in
``evaluate_goal_for_club`` daraus gespeist werden.
"""

from decimal import Decimal

from django.db.models import Max
from django.utils import timezone

from .models import (
    Club,
    HoenessCoin,
    PlayerSeasonStat,
    PlayerStrengthProfile,
    SeasonGoal,
)

TIER_ORDER = [
    SeasonGoal.TIER_MEISTER,
    SeasonGoal.TIER_TOP4,
    SeasonGoal.TIER_INTERNATIONAL,
    SeasonGoal.TIER_MITTELFELD,
    SeasonGoal.TIER_KLASSENERHALT,
]

TIER_LABELS = dict(SeasonGoal.TIER_CHOICES)

COIN_REWARD = 1


def current_season_number():
    """Aktuelle Saison = höchste vorhandene PlayerSeasonStat.season_number."""
    return PlayerSeasonStat.objects.aggregate(m=Max('season_number'))['m'] or 1


def club_squad_strength(club):
    """Summe der base_strength der 11 stärksten Spieler eines Vereins."""
    profiles = (
        PlayerStrengthProfile.objects
        .filter(player__club=club)
        .order_by('-base_strength')[:11]
    )
    return sum((p.base_strength for p in profiles), Decimal('0.00'))


def rank_clubs_in_league(league):
    """Vereine der Liga nach Kaderstärke absteigend sortiert.

    Rückgabe: Liste von (Club, strength) in Rang-Reihenfolge (Rang 1 zuerst).
    """
    clubs = list(Club.objects.filter(league=league))
    scored = [(c, club_squad_strength(c)) for c in clubs]
    scored.sort(key=lambda cs: (-cs[1], cs[0].name))
    return scored


def tier_bands(league_size):
    """Obergrenzen-Rang je Ziel-Kategorie, skaliert mit der Ligagröße.

    Bei 18 Teams: Meister=1, Top4=4, International=8, Mittelfeld=14, Klassenerhalt=18.
    """
    return {
        SeasonGoal.TIER_MEISTER: 1,
        SeasonGoal.TIER_TOP4: max(2, round(0.22 * league_size)),
        SeasonGoal.TIER_INTERNATIONAL: max(3, round(0.44 * league_size)),
        SeasonGoal.TIER_MITTELFELD: max(4, round(0.78 * league_size)),
        SeasonGoal.TIER_KLASSENERHALT: league_size,
    }


def tier_for_rank(rank, league_size):
    """Ziel-Kategorie für einen Kaderstärke-Rang."""
    bands = tier_bands(league_size)
    for tier in TIER_ORDER:
        if rank <= bands[tier]:
            return tier
    return SeasonGoal.TIER_KLASSENERHALT


def required_max_rank(tier, league_size):
    """Maximal erlaubter Endplatz, um die Ziel-Kategorie zu erfüllen."""
    return tier_bands(league_size).get(tier, league_size)


def _rank_and_strength(ranked, club):
    """Rang (1-basiert) und Stärke eines Vereins aus einer rank_clubs-Liste."""
    for idx, (c, strength) in enumerate(ranked):
        if c.id == club.id:
            return idx + 1, strength
    return len(ranked) or 1, Decimal('0.00')


def project_goal_for_club(club, season_number=None):
    """Berechnet (ohne zu speichern) das voraussichtliche Saisonziel.

    Praktisch für die Live-Vorschau auf der Präsidenten-Seite, bevor das
    Ziel offiziell verkündet wurde.
    """
    season_number = season_number or current_season_number()
    ranked = rank_clubs_in_league(club.league)
    league_size = len(ranked) or 1
    rank, strength = _rank_and_strength(ranked, club)
    tier = tier_for_rank(rank, league_size)
    return {
        'season_number': season_number,
        'rank_in_league': rank,
        'league_size': league_size,
        'squad_strength': strength,
        'goal_tier': tier,
        'goal_tier_label': TIER_LABELS.get(tier, tier),
        'required_max_rank': required_max_rank(tier, league_size),
    }


def declare_goal_for_club(club, season_number=None, force=False):
    """Verkündet (speichert) das Saisonziel eines Vereins.

    Idempotent: Existiert bereits ein Ziel für (Verein, Saison), wird es
    unverändert zurückgegeben — ein einmal verkündetes (und ggf. bereits
    ausgewertetes) Saisonziel darf nicht überschrieben werden.
    Mit ``force=True`` wird das Ziel neu berechnet und der Auswertungsstand
    zurückgesetzt (nur für administrative Korrekturen via CLI gedacht).
    """
    season_number = season_number or current_season_number()
    existing = SeasonGoal.objects.filter(
        club=club, season_number=season_number
    ).first()
    if existing and not force:
        return existing

    p = project_goal_for_club(club, season_number)
    goal, _created = SeasonGoal.objects.update_or_create(
        club=club,
        season_number=p['season_number'],
        defaults={
            'goal_tier': p['goal_tier'],
            'rank_in_league': p['rank_in_league'],
            'league_size': p['league_size'],
            'squad_strength': p['squad_strength'],
            'required_max_rank': p['required_max_rank'],
            'final_rank': None,
            'achieved': None,
            'evaluated_at': None,
        },
    )
    return goal


def evaluate_goal_for_club(club, season_number=None, coin_reward=COIN_REWARD):
    """Prüft das Saisonziel gegen den (abgeleiteten) Endplatz.

    Bei Erfolg wird dem Manager des Vereins ein Hoeneß-Coin gutgeschrieben.
    Gibt das ausgewertete SeasonGoal zurück oder None, wenn keins existiert.
    """
    season_number = season_number or current_season_number()
    try:
        goal = SeasonGoal.objects.get(club=club, season_number=season_number)
    except SeasonGoal.DoesNotExist:
        return None

    ranked = rank_clubs_in_league(club.league)
    final_rank, _strength = _rank_and_strength(ranked, club)
    was_already_met = goal.achieved is True

    goal.final_rank = final_rank
    goal.achieved = final_rank <= goal.required_max_rank
    goal.evaluated_at = timezone.now()
    goal.save()

    # Coin nur einmal gutschreiben (nicht bei wiederholter Auswertung)
    if goal.achieved and not was_already_met and club.managed_by_id:
        coin, _ = HoenessCoin.objects.get_or_create(manager=club.managed_by)
        coin.amount += coin_reward
        coin.save()

    return goal
