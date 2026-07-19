"""Ledger-Integritätsprüfung (Spec Kap. 12.1 / 15).

Der Kontostand (Club.budget) ist nur ein Performance-Cache — die Wahrheit
ist die Summe des Ledgers. Dieser Check vergleicht beide je Verein und
meldet Abweichungen (Admin-Alarm; Exit-Code ≠ 0 im Management-Command).
"""
from decimal import Decimal


def check_ledger_integrity(fix: bool = False) -> dict:
    """Vergleicht Ledger-Summe vs. Club.budget für alle Vereine.

    Args:
        fix: True = Konto-Cache aus dem Ledger neu setzen (Reparatur).

    Returns:
        {'checked': int, 'mismatches': [{'club', 'club_id', 'budget',
         'ledger', 'diff'}, ...], 'fixed': int}
    """
    from django.db.models import Sum
    from game.models import Club, FinanceTransaction

    ledger_sums = dict(
        FinanceTransaction.objects
        .values_list('club_id')
        .annotate(s=Sum('betrag'))
        .values_list('club_id', 's')
    )

    mismatches = []
    fixed = 0
    clubs = list(Club.objects.all().only('id', 'name', 'budget'))
    for club in clubs:
        ledger = ledger_sums.get(club.pk, Decimal('0.00')) or Decimal('0.00')
        budget = club.budget if club.budget is not None else Decimal('0.00')
        diff = (budget - ledger).quantize(Decimal('0.01'))
        if diff != 0:
            mismatches.append({
                'club': club.name,
                'club_id': club.pk,
                'budget': budget,
                'ledger': ledger,
                'diff': diff,
            })
            if fix:
                Club.objects.filter(pk=club.pk).update(budget=ledger)
                fixed += 1

    return {'checked': len(clubs), 'mismatches': mismatches, 'fixed': fixed}
