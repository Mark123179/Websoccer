"""
Spieltags-Auslastung & Stadioneinnahmen

Berechnet die Zuschauerzahl und die Einnahmen für ein Heimspiel basierend auf:
  - Fanbeliebtheit des Vereins (Club.fan_popularity, 1–100)
  - Ticketpreise (Stadium.price_*)
  - Wettbewerb (z. B. Champions League → höhere Auslastung)
  - Gegner-Stärke (0–100)
"""
from decimal import Decimal

from django.db import transaction

from .economy.booking import book

COMPETITION_FACTORS = [
    ('champions league',   1.30),
    ('europa league',      1.18),
    ('conference league',  1.10),
    ('super cup',          1.25),
    ('dfb-pokal',          1.08),
    ('fa cup',             1.08),
    ('copa del rey',       1.08),
    ('coupe de france',    1.08),
    ('coppa italia',       1.08),
    ('bundesliga',         1.00),
    ('premier league',     1.00),
    ('la liga',            1.00),
    ('serie a',            1.00),
    ('ligue 1',            1.00),
    ('eredivisie',         1.00),
    ('primeira liga',      1.00),
]

DEFAULT_COMPETITION_FACTOR = 0.85


def get_competition_factor(competition_name: str) -> float:
    lower = (competition_name or '').lower()
    for keyword, factor in COMPETITION_FACTORS:
        if keyword in lower:
            return factor
    return DEFAULT_COMPETITION_FACTOR


def calculate_auslastung(
    fan_popularity: int,
    price_standing: float,
    price_seating: float,
    competition_factor: float,
    opponent_strength: float,
) -> float:
    """
    Berechnet den Auslastungsfaktor (0.0–1.0) für einen Spieltag.

    :param fan_popularity:     Fanbeliebtheit des Heimvereins (1–100)
    :param price_standing:     Stehplatz-Ticketpreis (€)
    :param price_seating:      Sitzplatz-Ticketpreis (€)
    :param competition_factor: Wettbewerbs-Multiplikator (z. B. 1.30 für CL)
    :param opponent_strength:  Stärke des Gegners (0–100)
    :return:                   Auslastung 0.0–1.0
    """
    fan_base = 0.30 + (min(100, max(1, fan_popularity)) / 100.0) * 0.60

    avg_price = (float(price_standing) + float(price_seating)) / 2.0
    price_factor = max(0.55, min(1.15, 1.0 - (avg_price - 20.0) / 160.0))

    opp_factor = 0.82 + (min(100.0, max(0.0, opponent_strength)) / 100.0) * 0.36

    raw = fan_base * price_factor * opp_factor * competition_factor
    return min(0.99, max(0.05, raw))


def record_matchday_revenue(
    club,
    match_result=None,
    opponent_strength: float = 65.0,
    competition_name: str = '',
    saison=None,
    spieltag=None,
):
    """
    Berechnet die Spieltags-Einnahmen, schreibt sie dem Vereinsbudget gut
    und erstellt einen MatchdayRevenue-Eintrag.

    :param club:             Club-Instanz (Heimverein, muss ein Stadion haben)
    :param match_result:     MatchResult-Instanz oder None (Freundschaftsspiel)
    :param opponent_strength: Stärke des Gegners 0–100 (Standard 65)
    :param competition_name: Wettbewerbsname (überschreibt match_result.competition_name
                             wenn angegeben; bei match_result=None zwingend für korrekten Faktor)
    :return:                 MatchdayRevenue-Instanz
    :raises ValueError:      wenn dem Verein kein Stadion zugeordnet ist
    :raises RuntimeError:    wenn für dieses MatchResult bereits Einnahmen verbucht wurden
    """
    from .models import MatchdayRevenue

    try:
        stadium = club.stadium
    except Exception:
        raise ValueError(f'Verein {club} hat kein Stadion.')

    if match_result is not None and hasattr(match_result, 'matchday_revenue'):
        raise RuntimeError(
            f'Für das Spiel "{match_result}" wurden bereits Einnahmen verbucht.'
        )

    if competition_name:
        effective_competition = competition_name
    elif match_result is not None:
        effective_competition = match_result.competition_name or ''
    else:
        effective_competition = 'Freundschaftsspiel'

    competition_factor = get_competition_factor(effective_competition)

    auslastung = calculate_auslastung(
        fan_popularity=club.fan_popularity,
        price_standing=float(stadium.price_standing),
        price_seating=float(stadium.price_seating),
        competition_factor=competition_factor,
        opponent_strength=opponent_strength,
    )

    att_standing = int(stadium.capacity_standing * auslastung)
    att_seating  = int(stadium.capacity_seating  * auslastung)
    att_vip      = int(stadium.capacity_vip      * auslastung)

    rev_standing = Decimal(att_standing) * stadium.price_standing
    rev_seating  = Decimal(att_seating)  * stadium.price_seating
    rev_vip      = Decimal(att_vip)      * stadium.price_vip
    rev_total    = rev_standing + rev_seating + rev_vip

    if match_result:
        away_name = (
            match_result.away_club.short_name
            if match_result.away_club else '?'
        )
        day_label = match_result.matchday_label or match_result.date_label or ''
        match_label = f'vs {away_name}' + (f' ({day_label})' if day_label else '')
    else:
        match_label = f'Heimspiel ({effective_competition})' if effective_competition else 'Freundschaftsspiel'

    with transaction.atomic():
        entry = MatchdayRevenue.objects.create(
            stadium          = stadium,
            match_result     = match_result,
            match_label      = match_label,
            competition_name = effective_competition,
            auslastung_pct   = Decimal(str(round(auslastung * 100, 1))),
            attendance       = att_standing + att_seating + att_vip,
            revenue_standing = rev_standing,
            revenue_seating  = rev_seating,
            revenue_vip      = rev_vip,
            revenue_total    = rev_total,
        )

        # book() sperrt die Club-Zeile, schreibt die Ledger-Zeile und
        # aktualisiert den Konto-Cache (inkl. der übergebenen Instanz).
        book(
            club, 'TICKET', rev_total,
            beschreibung=f'Spieltagseinnahmen {match_label}',
            saison=saison,
            spieltag=spieltag,
            referenz_typ='matchday_revenue',
            referenz_id=entry.pk,
            pflicht=True,
        )

    return entry
