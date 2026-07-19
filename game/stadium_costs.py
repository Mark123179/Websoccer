"""
Kostenmodell des Stadionausbaus (Spec Kap. 5.3, Phase 3).

Preis pro Platz nach ZIELkapazitäts-Band (EconomyParameter AUSBAU_BAENDER,
Sitzplatz-Basis) × Kategorie-Faktor (AUSBAU_FAKTOR_KATEGORIE: Steh 0,6 /
Sitz 1,0 / VIP 4,0). Überschreitet ein Ausbau eine Bandgrenze, wird jeder
Platz zum Preis seines Ziel-Bandes berechnet (Splitting).

Beispiel Elversberg: 10.000 → 25.000 Sitzplätze
  = 10.000 × 1.500 € (Band ≤ 20.000) + 5.000 × 2.500 € (Band ≤ 40.000)
  = 27,5 Mio €.

Obergrenze: STADION_MAX (120.000). Alle Werte kommen aus EconomyParameter —
keine Code-Defaults für Balancing-Werte.
"""
from decimal import Decimal

from .economy.params import get_param

SEAT_TYPE_KEY = {
    'STEH': 'steh',
    'SITZ': 'sitz',
    'VIP':  'vip',
}


def _baender(saison: str | None = None) -> list[tuple[int, Decimal]]:
    """AUSBAU_BAENDER als [(Zielkapazitätsgrenze inkl., Sitz-Basispreis €)]."""
    return [
        (int(grenze), Decimal(str(preis)))
        for grenze, preis in get_param('AUSBAU_BAENDER', saison)
    ]


def _kategorie_faktor(sitztyp: str, saison: str | None = None) -> Decimal:
    faktoren = get_param('AUSBAU_FAKTOR_KATEGORIE', saison)
    key = SEAT_TYPE_KEY.get(sitztyp.upper(), 'sitz')
    return Decimal(str(faktoren[key]))


def max_kapazitaet(saison: str | None = None) -> int:
    """Harte Obergrenze der Stadionkapazität (STADION_MAX)."""
    return int(get_param('STADION_MAX', saison))


def _basispreis_fuer_zielplatz(kapazitaet: int, saison: str | None = None) -> Decimal:
    """Sitz-Basispreis des Bandes, in das der NÄCHSTE Platz fällt."""
    baender = _baender(saison)
    for grenze, basis in baender:
        if kapazitaet < grenze:
            return basis
    return baender[-1][1]


def get_expansion_cost(aktuelle_kapazitaet: int, sitztyp: str, anzahl: int,
                       saison: str | None = None) -> Decimal:
    """
    Gesamtkosten eines Ausbau-Auftrags.

    Jeder neue Platz wird zum Basispreis seines ZIEL-Bandes berechnet
    (Splitting an Bandgrenzen) und mit dem Kategorie-Faktor multipliziert.

    :param aktuelle_kapazitaet: Aktuelle Gesamtkapazität des Stadions
    :param sitztyp: 'STEH', 'SITZ' oder 'VIP'
    :param anzahl: Anzahl neuer Plätze
    :return: Gesamtkosten als Decimal (€)
    """
    faktor = _kategorie_faktor(sitztyp, saison)
    baender = _baender(saison)

    gesamtkosten = Decimal('0')
    verbleibend = int(anzahl)
    aktuell = int(aktuelle_kapazitaet)

    for grenze, basis in baender:
        if verbleibend <= 0:
            break
        if aktuell >= grenze:
            continue  # Dieses Band ist bereits ausgeschöpft.
        diesmal = min(verbleibend, grenze - aktuell)
        gesamtkosten += basis * faktor * Decimal(diesmal)
        aktuell += diesmal
        verbleibend -= diesmal

    # Über der letzten Bandgrenze → höchstes Band (Views kappen ohnehin
    # bei max_kapazitaet()).
    if verbleibend > 0:
        gesamtkosten += baender[-1][1] * faktor * Decimal(verbleibend)

    return gesamtkosten


def get_preis_pro_platz(aktuelle_kapazitaet: int, sitztyp: str,
                        saison: str | None = None) -> Decimal:
    """Preis pro Platz im Band des nächsten Ziel-Platzes."""
    basis = _basispreis_fuer_zielplatz(int(aktuelle_kapazitaet), saison)
    return basis * _kategorie_faktor(sitztyp, saison)


def get_kostenmatrix(aktuelle_kapazitaet: int, saison: str | None = None) -> dict:
    """
    {'STEH': preis_pro_platz, 'SITZ': ..., 'VIP': ...} für das Band des
    nächsten Ziel-Platzes — geht ans Template für den JS-Kostenrechner.
    """
    basis = _basispreis_fuer_zielplatz(int(aktuelle_kapazitaet), saison)
    return {
        typ: float(basis * _kategorie_faktor(typ, saison))
        for typ in ('STEH', 'SITZ', 'VIP')
    }
