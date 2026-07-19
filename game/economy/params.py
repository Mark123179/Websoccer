"""EconomyParameter-Zugriff (Spec Kap. 2).

Saison-Konvention: numerische Sim-Saison als String ("0", "1", …) wie
GameSeasonState.current_season. Parameter werden pro Saison versioniert;
fehlt ein Wert für die angefragte Saison, gilt der jüngste Wert einer
früheren Saison (Snapshot-Semantik ohne Kopierzwang).

Fehlende Keys sind ein harter Fehler — keine stillen Code-Defaults,
Balancing-Werte leben ausschließlich in der Tabelle (Spec: nie hartcodieren).
"""
from decimal import Decimal


class EconomyParameterMissing(Exception):
    """Angefragter EconomyParameter-Key existiert in keiner Saison."""


def current_season() -> str:
    from game.finance import current_sim_season
    return current_sim_season() or '0'


def _season_sort_key(saison: str):
    """Numerische Saisons zuerst (aufsteigend), nicht-numerische dahinter."""
    s = (saison or '').strip()
    return (0, int(s)) if s.lstrip('-').isdigit() else (1, 0)


def get_param(key: str, saison: str | None = None):
    """Gibt den Parameterwert für (saison, key) zurück — mit Saison-Fallback.

    Fallback-Reihenfolge:
      1. exakter Treffer (saison, key)
      2. jüngste numerische Saison ≤ angefragte Saison
      3. jüngste vorhandene Saison überhaupt (z. B. Seed "0")
    """
    from game.models import EconomyParameter

    saison = str(saison) if saison is not None else current_season()

    rows = list(
        EconomyParameter.objects.filter(key=key).values_list('saison', 'value')
    )
    if not rows:
        raise EconomyParameterMissing(
            f'EconomyParameter "{key}" ist in keiner Saison definiert — '
            f'Seed-Migration fehlt oder Key-Tippfehler.'
        )

    by_season = {s: v for s, v in rows}
    if saison in by_season:
        return by_season[saison]

    if saison.lstrip('-').isdigit():
        target = int(saison)
        numeric = [
            (int(s), v) for s, v in rows if s.lstrip('-').isdigit()
        ]
        older = [(n, v) for n, v in numeric if n <= target]
        if older:
            return max(older, key=lambda t: t[0])[1]

    best = max(rows, key=lambda t: _season_sort_key(t[0]))
    return best[1]


def get_decimal(key: str, saison: str | None = None) -> Decimal:
    """Wie get_param, aber als Decimal (für Geldrechnung)."""
    return Decimal(str(get_param(key, saison)))
