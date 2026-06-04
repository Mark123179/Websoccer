"""
Kostentabelle für den Stadionausbau.

Preise pro Platz (in €) basierend auf der Zielkapazitäts-Stufe.
11 Stufen × 3 Typen (Stehplatz / Sitzplatz / VIP).

Beispiel: Stadion bei 75.000 → Tier "bis 80.000" → Stehplatz 5.400 €/Platz.
Wird die Tier-Grenze überschritten, werden Plätze in jedem Tier separat berechnet.
"""
from decimal import Decimal

# Stufen: (kapazitätsgrenze_inkl, preis_steh, preis_sitz, preis_vip)
# "aktuelle Kapazität <= grenze" → dieser Preis gilt für neue Plätze in diesem Tier
KOSTENSTUFEN = [
    ( 20_000, Decimal('1200'),  Decimal('2200'),  Decimal('6000')),
    ( 30_000, Decimal('1600'),  Decimal('3200'),  Decimal('8000')),
    ( 40_000, Decimal('2200'),  Decimal('4500'),  Decimal('11000')),
    ( 50_000, Decimal('3000'),  Decimal('6000'),  Decimal('14500')),
    ( 60_000, Decimal('4000'),  Decimal('7500'),  Decimal('18000')),
    ( 70_000, Decimal('5000'),  Decimal('9500'),  Decimal('22500')),
    ( 80_000, Decimal('5400'),  Decimal('10000'), Decimal('23000')),
    ( 90_000, Decimal('5800'),  Decimal('11000'), Decimal('24000')),
    (100_000, Decimal('6000'),  Decimal('11500'), Decimal('25000')),
    (110_000, Decimal('6200'),  Decimal('12000'), Decimal('27000')),
    (120_000, Decimal('6500'),  Decimal('13000'), Decimal('30000')),
]

SEAT_TYPE_INDEX = {
    'STEH': 0,
    'SITZ': 1,
    'VIP':  2,
}

MAX_KAPAZITAET = 120_000


def _get_preis_fuer_kapazitaet(kapazitaet: int, typ_idx: int) -> Decimal:
    """Gibt den Preis pro Platz für eine gegebene Kapazität zurück."""
    for grenze, p_steh, p_sitz, p_vip in KOSTENSTUFEN:
        if kapazitaet <= grenze:
            return (p_steh, p_sitz, p_vip)[typ_idx]
    # Über 120.000 → höchste Stufe
    return KOSTENSTUFEN[-1][typ_idx + 1]


def get_expansion_cost(aktuelle_kapazitaet: int, sitztyp: str, anzahl: int) -> Decimal:
    """
    Berechnet die Gesamtkosten eines Ausbau-Auftrags.

    Überschreitet der Ausbau eine Tier-Grenze, werden die Plätze aufgeteilt
    und jeder Anteil zum Preis des jeweiligen Tiers berechnet.

    :param aktuelle_kapazitaet: Aktuelle Gesamtkapazität des Stadions
    :param sitztyp: 'STEH', 'SITZ' oder 'VIP'
    :param anzahl: Anzahl neuer Plätze
    :return: Gesamtkosten als Decimal (€)
    """
    typ_idx = SEAT_TYPE_INDEX.get(sitztyp.upper(), 1)

    gesamtkosten = Decimal('0')
    verbleibend  = anzahl
    aktuell      = aktuelle_kapazitaet

    for grenze, p_steh, p_sitz, p_vip in KOSTENSTUFEN:
        if verbleibend <= 0:
            break
        if aktuell >= grenze:
            continue  # Dieser Tier ist bereits überschritten
        preis       = (p_steh, p_sitz, p_vip)[typ_idx]
        platz_im_tier = grenze - aktuell          # Wie viele Plätze bis zur Tier-Grenze
        diesmal     = min(verbleibend, platz_im_tier)
        gesamtkosten += preis * Decimal(diesmal)
        aktuell      += diesmal
        verbleibend  -= diesmal

    # Falls noch Plätze übrig (über 120.000) → höchste Stufe
    if verbleibend > 0:
        preis = KOSTENSTUFEN[-1][typ_idx + 1]
        gesamtkosten += preis * Decimal(verbleibend)

    return gesamtkosten


def get_preis_pro_platz(aktuelle_kapazitaet: int, sitztyp: str) -> Decimal:
    """Gibt den Preis pro Platz für den aktuellen Tier zurück."""
    typ_idx = SEAT_TYPE_INDEX.get(sitztyp.upper(), 1)
    return _get_preis_fuer_kapazitaet(aktuelle_kapazitaet, typ_idx)


def get_kostenmatrix(aktuelle_kapazitaet: int) -> dict:
    """
    Gibt ein Dict zurück: {'STEH': preis_pro_platz, 'SITZ': ..., 'VIP': ...}
    Preise gelten für den aktuellen Kapazitäts-Tier.
    Wird im Template per JSON an den JS-Kostenrechner übergeben.
    """
    return {
        'STEH': float(_get_preis_fuer_kapazitaet(aktuelle_kapazitaet, 0)),
        'SITZ': float(_get_preis_fuer_kapazitaet(aktuelle_kapazitaet, 1)),
        'VIP':  float(_get_preis_fuer_kapazitaet(aktuelle_kapazitaet, 2)),
    }
