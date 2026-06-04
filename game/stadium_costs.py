"""
Kostentabelle für den Stadionausbau.

Preise pro Sitzplatz (in €) basierend auf der aktuellen Gesamtkapazität.
11 Stufen × 3 Typen (Stehplatz / Sitzplatz / VIP).
"""
from decimal import Decimal

# Stufen: (max_kapazität_grenze, preis_steh, preis_sitz, preis_vip)
# Gilt für: aktuelle_kapazität < grenze
KOSTENSTUFEN = [
    (10_000,  Decimal('120'),  Decimal('280'),  Decimal('1_200')),
    (20_000,  Decimal('150'),  Decimal('340'),  Decimal('1_500')),
    (30_000,  Decimal('190'),  Decimal('420'),  Decimal('1_900')),
    (40_000,  Decimal('240'),  Decimal('520'),  Decimal('2_400')),
    (50_000,  Decimal('300'),  Decimal('650'),  Decimal('3_000')),
    (60_000,  Decimal('370'),  Decimal('800'),  Decimal('3_700')),
    (70_000,  Decimal('450'),  Decimal('980'),  Decimal('4_500')),
    (80_000,  Decimal('550'), Decimal('1_200'), Decimal('5_500')),
    (90_000,  Decimal('670'), Decimal('1_450'), Decimal('6_700')),
    (100_000, Decimal('800'), Decimal('1_750'), Decimal('8_000')),
    (120_001, Decimal('980'), Decimal('2_100'), Decimal('9_800')),
]

SEAT_TYPE_INDEX = {
    'STEH': 0,
    'SITZ': 1,
    'VIP':  2,
}

MAX_KAPAZITAET = 120_000


def get_expansion_cost(aktuelle_kapazitaet: int, sitztyp: str, anzahl: int) -> Decimal:
    """
    Berechnet die Gesamtkosten eines Ausbau-Auftrags.

    :param aktuelle_kapazitaet: Aktuelle Gesamtkapazität des Stadions
    :param sitztyp: 'STEH', 'SITZ' oder 'VIP'
    :param anzahl: Anzahl neuer Plätze
    :return: Gesamtkosten als Decimal (€)
    """
    typ_idx = SEAT_TYPE_INDEX.get(sitztyp.upper(), 1)

    for grenze, preis_steh, preis_sitz, preis_vip in KOSTENSTUFEN:
        if aktuelle_kapazitaet < grenze:
            preise = (preis_steh, preis_sitz, preis_vip)
            return preise[typ_idx] * Decimal(anzahl)

    # Fallback: höchste Stufe
    _, preis_steh, preis_sitz, preis_vip = KOSTENSTUFEN[-1]
    preise = (preis_steh, preis_sitz, preis_vip)
    return preise[typ_idx] * Decimal(anzahl)


def get_preis_pro_platz(aktuelle_kapazitaet: int, sitztyp: str) -> Decimal:
    """Gibt den Preis pro Sitzplatz zurück (für die Live-Kostenberechnung im Frontend)."""
    typ_idx = SEAT_TYPE_INDEX.get(sitztyp.upper(), 1)
    for grenze, preis_steh, preis_sitz, preis_vip in KOSTENSTUFEN:
        if aktuelle_kapazitaet < grenze:
            return (preis_steh, preis_sitz, preis_vip)[typ_idx]
    return KOSTENSTUFEN[-1][typ_idx + 1]


def get_kostenmatrix(aktuelle_kapazitaet: int) -> dict:
    """
    Gibt ein Dict zurück: {'STEH': preis_pro_platz, 'SITZ': ..., 'VIP': ...}
    Wird im Template per JSON an den JS-Kostenrechner übergeben.
    """
    for grenze, preis_steh, preis_sitz, preis_vip in KOSTENSTUFEN:
        if aktuelle_kapazitaet < grenze:
            return {
                'STEH': float(preis_steh),
                'SITZ': float(preis_sitz),
                'VIP':  float(preis_vip),
            }
    return {
        'STEH': float(KOSTENSTUFEN[-1][1]),
        'SITZ': float(KOSTENSTUFEN[-1][2]),
        'VIP':  float(KOSTENSTUFEN[-1][3]),
    }
