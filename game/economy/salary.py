"""Log-progressive Gehaltsformel (Spec Kap. 4).

Jahresgehalt(Spieler) = MW × (BASIS + PROGRESSION × log10(MW / MEDIAN_ANKER)) / 100
Gehalt_pro_Pflichtspiel = Jahresgehalt / GEHALT_DIVISOR
Untergrenze Prozentsatz: GEHALT_PROZENT_MIN (12 %).

MW wird vor der Rechnung auf MW_MINIMUM (50.000 €) geklemmt — auch vor dem
log10, damit Kleinst-MW nie negative Prozentsätze erzeugen. Der MEDIAN_ANKER
kommt aus dem SeasonEconomySnapshot (gedämpfter MW-Median der Sim).
"""
from decimal import Decimal
from math import log10

from .params import get_decimal


def load_salary_params(saison=None) -> dict:
    """Lädt alle Gehalts-Regler einmalig (für Kader-Schleifen)."""
    return {
        'basis': get_decimal('GEHALT_BASIS', saison),
        'progression': get_decimal('GEHALT_PROGRESSION', saison),
        'divisor': get_decimal('GEHALT_DIVISOR', saison),
        'prozent_min': get_decimal('GEHALT_PROZENT_MIN', saison),
        'mw_minimum': get_decimal('MW_MINIMUM', saison),
    }


def jahresgehalt(marktwert, anker, p) -> Decimal:
    """Jahresgehalt eines Spielers nach Spec Kap. 4.

    Args:
        marktwert: Spieler-MW (None/0 wird auf MW_MINIMUM geklemmt).
        anker: MEDIAN_ANKER (SeasonEconomySnapshot.gehalts_anker).
        p: Parameter-Dict aus load_salary_params().
    """
    mw = Decimal(str(marktwert or 0))
    if mw < p['mw_minimum']:
        mw = p['mw_minimum']
    anker = Decimal(str(anker))
    if anker <= 0:
        anker = p['mw_minimum']

    prozent = p['basis'] + p['progression'] * Decimal(str(log10(float(mw / anker))))
    if prozent < p['prozent_min']:
        prozent = p['prozent_min']

    return (mw * prozent / Decimal('100')).quantize(Decimal('0.01'))


def gehalt_pro_pflichtspiel(marktwert, anker, p) -> Decimal:
    """Gehalt pro Pflichtspiel = Jahresgehalt / GEHALT_DIVISOR."""
    return (jahresgehalt(marktwert, anker, p) / p['divisor']).quantize(Decimal('0.01'))
