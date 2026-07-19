"""Zentrale Buchungsstelle für Vereins-Finanztransaktionen.

Jede Budget-Mutation soll zusätzlich eine Ledger-Zeile
(ClubFinancialTransaction) schreiben — das Ledger ist die Datenbasis für
Manager-Finanzansicht und Creator-Finanzanalyse.

Saison-Konvention: numerische Sim-Saison als String
(GameSeasonState.current_season, z. B. "0", "1"), konsistent mit der
Manager-Finanzansicht (management_finanzen).

Dieser Helper ist bewusst dünn gehalten: Beim späteren Ausbau des
Finanzsystems (Spec Kap. 12, FinanceTransaction-Ledger) ist er die eine
Stelle, an der das Backing-Modell ausgetauscht wird.
"""
from django.utils import timezone


def current_sim_season():
    """Aktuelle Sim-Saison als String ("0", "1", …); leer wenn kein Zustand."""
    from game.models import GameSeasonState
    state = GameSeasonState.objects.only('current_season').first()
    return str(state.current_season) if state else ''


def log_club_transaction(club, category, description, amount,
                         date=None, season=None):
    """Schreibt eine Finanztransaktions-Zeile für einen Verein.

    Args:
        club: Club-Instanz.
        category: Kategorie-Key aus ClubFinancialTransaction.CATEGORY_CHOICES.
        description: Verwendungszweck (wird auf 200 Zeichen gekürzt).
        amount: Betrag — positiv = Einnahme, negativ = Ausgabe.
        date: Buchungsdatum (Default: heute).
        season: Saison-String (Default: aktuelle Sim-Saison).

    Muss innerhalb derselben DB-Transaktion wie die zugehörige
    Budget-Mutation aufgerufen werden, damit Budget und Ledger nie
    auseinanderlaufen.
    """
    from game.models import ClubFinancialTransaction
    return ClubFinancialTransaction.objects.create(
        club=club,
        date=date or timezone.localdate(),
        season=current_sim_season() if season is None else str(season),
        category=category,
        description=(description or '')[:200],
        amount=amount,
    )
