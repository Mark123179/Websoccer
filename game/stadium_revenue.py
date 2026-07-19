"""
Spieltags-Zuschauer & Stadioneinnahmen (Spec Kap. 5, Phase 3).

Die Zuschauerzahl kommt aus der vollen Nachfrageformel in
``game.economy.stadium.compute_demand`` (Kader-MW-Basis, Beliebtheits-,
Gegner- und Preisfaktor je Kategorie, kategorieweise Kappung).
Dieses Modul verbucht das Ergebnis: MatchdayRevenue-Eintrag + TICKET-Buchung.
"""
from decimal import Decimal

from django.db import transaction

from .economy.booking import book
from .economy.stadium import compute_demand


def record_matchday_revenue(
    club,
    match_result=None,
    opponent_strength: float | None = None,
    competition_name: str = '',
    saison=None,
    spieltag=None,
    opponent_club=None,
    is_pokal_ko: bool = False,
):
    """
    Berechnet die Spieltags-Einnahmen (volle Nachfrageformel), schreibt sie
    dem Vereinsbudget gut und erstellt einen MatchdayRevenue-Eintrag.

    :param club:              Club-Instanz (Heimverein, muss ein Stadion haben)
    :param match_result:      MatchResult-Instanz oder None (Freundschaftsspiel)
    :param opponent_strength: Gegnerstärke 0–100 (Fallback, wenn kein
                              ``opponent_club`` bekannt ist)
    :param competition_name:  Wettbewerbsname (nur Beschriftung)
    :param opponent_club:     Gegner-Club für den vollen Gegnerfaktor
                              (MW-Verhältnis, Topspiel, Derby)
    :param is_pokal_ko:       True bei Pokal-K.o.-Heimspielen (Attraktivitäts-
                              Zuschlag laut Kap. 5.1)
    :return:                  MatchdayRevenue-Instanz
    :raises ValueError:       wenn dem Verein kein Stadion zugeordnet ist
    :raises RuntimeError:     wenn für dieses MatchResult bereits Einnahmen
                              verbucht wurden
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

    if opponent_club is None and match_result is not None:
        opponent_club = match_result.away_club

    demand = compute_demand(
        club, stadium,
        opponent_club=opponent_club,
        opponent_strength=opponent_strength,
        is_pokal_ko=is_pokal_ko,
        saison=str(saison) if saison is not None else None,
    )
    kat = demand['kategorien']

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
            stadium            = stadium,
            match_result       = match_result,
            match_label        = match_label,
            competition_name   = effective_competition,
            auslastung_pct     = Decimal(str(demand['auslastung_pct'])),
            attendance         = demand['zuschauer_gesamt'],
            attendance_standing = kat['steh']['zuschauer'],
            attendance_seating  = kat['sitz']['zuschauer'],
            attendance_vip      = kat['vip']['zuschauer'],
            revenue_standing   = kat['steh']['einnahmen'],
            revenue_seating    = kat['sitz']['einnahmen'],
            revenue_vip        = kat['vip']['einnahmen'],
            revenue_total      = demand['einnahmen_gesamt'],
        )

        # book() sperrt die Club-Zeile, schreibt die Ledger-Zeile und
        # aktualisiert den Konto-Cache (inkl. der übergebenen Instanz).
        # 0-€-Spieltage (z. B. Kader-MW 0 → Nachfrage 0) erzeugen keine
        # Ledger-Zeile — der MatchdayRevenue-Eintrag dokumentiert sie trotzdem.
        if demand['einnahmen_gesamt'] > 0:
            book(
                club, 'TICKET', demand['einnahmen_gesamt'],
                beschreibung=f'Spieltagseinnahmen {match_label}',
                saison=saison,
                spieltag=spieltag,
                referenz_typ='matchday_revenue',
                referenz_id=entry.pk,
                pflicht=True,
            )

    return entry
