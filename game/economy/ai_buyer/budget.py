"""Budgetregel des KI-Käufers (Spec Kap. 9.3, Grundsatz).

KI-Vereine geben ausschließlich Überschüsse nach allen Kosten aus:
Puffer ≈ halbe Saison Fixkosten (puffer_spieltage × Fixkosten je
Spieltagslauf), der Rest ist reinvestierbar. Fixkosten je Spieltag =
Kader-Gehälter + Stadion-Unterhalt-Rate + Betriebskosten-Sockelrate
(dieselben Bausteine wie matchday_run — Quote auf Einnahmen bleibt
bewusst außen vor, sie ist einnahmengedeckt).
"""
from decimal import Decimal

from ..params import get_decimal
from ..salary import gehalt_pro_pflichtspiel, load_salary_params
from ..snapshot import ensure_season_snapshot


def fixkosten_puffer(club, saison, params, *, anker=None, salary_params=None):
    """Puffer = Fixkosten je Spieltagslauf × puffer_spieltage (≈ ½ Saison)."""
    from game.models import Player

    spieltage = int(params.get('puffer_spieltage', 17))
    if anker is None:
        anker = ensure_season_snapshot(saison).gehalts_anker
    if salary_params is None:
        salary_params = load_salary_params(saison)

    gehalt = Decimal('0.00')
    for mw in Player.objects.filter(club=club).values_list(
            'market_value', flat=True):
        gehalt += gehalt_pro_pflichtspiel(mw, anker, salary_params)

    unterhalt = Decimal('0.00')
    stadium = getattr(club, 'stadium', None)
    if stadium is not None:
        from ..stadium import unterhalt_rate
        unterhalt = unterhalt_rate(stadium, saison)

    sockel = get_decimal('BETRIEB_SOCKEL', saison)
    divisor = get_decimal('GEHALT_DIVISOR', saison)
    sockel_rate = (sockel / divisor).quantize(Decimal('0.01'))

    fix_je_spieltag = gehalt + unterhalt + sockel_rate
    return (fix_je_spieltag * spieltage).quantize(Decimal('0.01'))


def ueberschuss(club, saison, params, *, puffer=None, anker=None,
                salary_params=None):
    """Reinvestierbarer Überschuss = Kontostand − Fixkosten-Puffer.

    Returns dict: {'konto', 'puffer', 'ueberschuss'}.
    """
    if puffer is None:
        puffer = fixkosten_puffer(
            club, saison, params, anker=anker, salary_params=salary_params,
        )
    konto = Decimal(str(club.budget or 0))
    return {
        'konto': konto,
        'puffer': puffer,
        'ueberschuss': (konto - puffer).quantize(Decimal('0.01')),
    }
