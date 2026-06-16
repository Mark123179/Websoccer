"""Vereins-/Spielerimport-Engine (Creator-Mode).

Reine Logikdienste (Saison-ID, Positions-Mapping, HP/NP-Algorithmus,
Normalisierung, Wert-Parsing), DB-Matching bestehender Spieler sowie der
serverseitige, verbindliche Datenbankimport. Diese Schicht enthält keinen
Web-Scraper und keine HTTP-Oberfläche — darauf bauen API und UI auf.
"""

from .season import get_current_tm_season_id, season_label
from .positions import compute_positions, map_tm_position, TM_POSITION_MAP
from .normalization import normalize_name, normalize_club_name
from .parsing import (
    parse_height,
    parse_market_value,
    parse_foot,
    parse_nationalities,
)
from .matching import find_existing_player

__all__ = [
    'get_current_tm_season_id',
    'season_label',
    'compute_positions',
    'map_tm_position',
    'TM_POSITION_MAP',
    'normalize_name',
    'normalize_club_name',
    'parse_height',
    'parse_market_value',
    'parse_foot',
    'parse_nationalities',
    'find_existing_player',
]
