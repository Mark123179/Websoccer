"""Zuordnung Spieler → Scouting-Land (ISO2).

Ein Spieler "gehört" zu seinem Scouting-Land über seine primäre Nationalität
(erste Nationalität in ``Player.nationalities``). Der reale Verein/Liga wird nur
zur Anzeige genutzt, nicht zur Länderzuordnung — so deckt sich das mit dem
Community-System (Manager reichen Spieler eines Landes ein).
"""

import functools


@functools.lru_cache(maxsize=1)
def _name_to_iso():
    """Reverse-Map deutscher Ländername → ISO2 aus den Flag-Stammdaten."""
    from game.models import COUNTRY_FLAG_ASSETS
    mapping = {}
    for name, rec in COUNTRY_FLAG_ASSETS.items():
        code = (rec.get('code') or '').upper()
        if code:
            mapping[name.strip().lower()] = code
    return mapping


def nationality_to_iso2(nationality_name):
    """Deutscher Nationalitätsname → ISO2 (oder '' wenn unbekannt)."""
    if not nationality_name:
        return ''
    return _name_to_iso().get(nationality_name.strip().lower(), '')


def player_country_iso2(player):
    """Primäres Scouting-Land eines Spielers als ISO2-Code (oder '')."""
    raw = (player.nationalities or '').split(',')
    primary = raw[0].strip() if raw else ''
    return nationality_to_iso2(primary)


def player_country_filter_isos(player):
    """Alle ISO2-Codes der Nationalitäten eines Spielers (für Pool-Zählung)."""
    isos = []
    for part in (player.nationalities or '').split(','):
        iso = nationality_to_iso2(part.strip())
        if iso and iso not in isos:
            isos.append(iso)
    return isos
