"""Transfermarkt-Positions-Mapping (Spiegel der Server-Engine).

Hält dieselbe ``TM_POSITION_MAP`` wie ``game/club_import/positions.py``, damit
das Tool je Positionseinsatz schon eine interne Kennung mitschicken kann
(``mapped_position``). Der endgültige HP/NP-Algorithmus läuft serverseitig —
hier wird NICHT geraten: unbekannte Bezeichnungen ergeben ``None``.
"""

# Transfermarkt-Bezeichnung (kleingeschrieben) -> interne Positionskennung.
TM_POSITION_MAP = {
    'torwart': 'TW',
    'innenverteidiger': 'IV',
    'libero': 'IV',
    'linker verteidiger': 'LV',
    'rechter verteidiger': 'RV',
    'defensives mittelfeld': 'DM',
    'zentrales mittelfeld': 'ZM',
    'linkes mittelfeld': 'LM',
    'rechtes mittelfeld': 'RM',
    'offensives mittelfeld': 'OM',
    'linksaußen': 'LF',
    'rechtsaußen': 'RF',
    'hängende spitze': 'ST',
    'mittelstürmer': 'ST',
    'sturm': 'ST',
}


def map_tm_position(label):
    """Bildet eine TM-Positionsbezeichnung auf die interne Kennung ab.

    Returns interne Kennung (str) oder ``None`` bei unbekannter Bezeichnung.
    """
    if not label:
        return None
    key = ' '.join(str(label).strip().lower().split())
    return TM_POSITION_MAP.get(key)
