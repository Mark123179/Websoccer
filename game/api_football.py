"""
Dünner API-Client für API-Football v3 (v3.football.api-sports.io).
API-Key kommt aus settings.API_FOOTBALL_KEY (Env-Secret API_FOOTBALL_KEY).
Kein eigenes Caching — Budget-Steuerung liegt beim Aufrufer.
"""

import requests
from django.conf import settings

API_BASE = 'https://v3.football.api-sports.io'
DEFAULT_TIMEOUT = 15
DAILY_LIMIT = 100
WARN_THRESHOLD = 80


def _headers():
    return {
        'x-rapidapi-key': settings.API_FOOTBALL_KEY,
        'x-rapidapi-host': 'v3.football.api-sports.io',
    }


def record_api_call(count=1):
    """Zählt `count` verbrauchte Requests für heute in der DB."""
    try:
        from .models import ApiFootballDailyUsage
        ApiFootballDailyUsage.record(count)
    except Exception:
        pass


def get_today_usage():
    """Gibt den heutigen Request-Verbrauch zurück (int, 0 falls keine DB-Einträge)."""
    try:
        from .models import ApiFootballDailyUsage
        return ApiFootballDailyUsage.today_count()
    except Exception:
        return 0


_FINISHED_STATUSES = {'FT', 'AET', 'PEN'}


def get_team_fixtures(team_id, season, last=10):
    """Letzte `last` abgeschlossene Spiele eines Teams in einer Saison.

    Der Free-Plan von API-Football unterstützt den `last`-Parameter und
    komma-separierte `status`-Werte nicht. Stattdessen werden alle Fixtures
    der Saison abgerufen, clientseitig nach abgeschlossenen Spielen gefiltert
    und die neuesten `last` Einträge zurückgegeben.

    Args:
        team_id:  API-Football-Team-ID.
        season:   Saison-Startjahr (z. B. 2024 für Saison 2024/25).
        last:     Maximale Anzahl zurückgegebener Spiele (default 10).

    Returns list[dict] – rohe response-Einträge (neueste zuerst).
    Raises requests.RequestException bei Netzwerk-/HTTP-Fehlern.
    """
    resp = requests.get(
        f'{API_BASE}/fixtures',
        headers=_headers(),
        params={'team': team_id, 'season': season},
        timeout=DEFAULT_TIMEOUT,
    )
    resp.raise_for_status()
    all_fixtures = resp.json().get('response', [])
    finished = [
        f for f in all_fixtures
        if f.get('fixture', {}).get('status', {}).get('short') in _FINISHED_STATUSES
    ]
    finished.sort(key=lambda f: f['fixture']['date'], reverse=True)
    return finished[:last]


def get_fixture_player_stats(fixture_id, team_id):
    """Spielerstatistiken für ein einzelnes Spiel (nach team gefiltert).

    Returns list[dict] – je Eintrag:
        {
            'player': {'id': int, 'name': str},
            'statistics': [{'games': {'minutes': int|None, 'rating': str|None, ...}}]
        }
    Raises requests.HTTPError bei 4xx/5xx.
    """
    resp = requests.get(
        f'{API_BASE}/fixtures/players',
        headers=_headers(),
        params={'fixture': fixture_id, 'team': team_id},
        timeout=DEFAULT_TIMEOUT,
    )
    resp.raise_for_status()
    payload = resp.json().get('response', [])
    for block in payload:
        if block.get('team', {}).get('id') == int(team_id):
            return block.get('players', [])
    return []


def search_player(name, season=2024):
    """Sucht Spieler bei API-Football per Name (min. 3 Zeichen).

    Args:
        name:    Suchbegriff (Spielername, mind. 3 Zeichen).
        season:  Saison-Jahr (default 2024 = Saison 2024/25).

    Returns list[dict] – rohe response-Einträge der API, je Eintrag:
        {
            'player': {'id': int, 'name': str, 'nationality': str, ...},
            'statistics': [{'team': {'id': int, 'name': str}, 'league': {'season': int, ...}}]
        }
    Raises requests.HTTPError bei 4xx/5xx.
    """
    resp = requests.get(
        f'{API_BASE}/players',
        headers=_headers(),
        params={'search': name, 'season': season},
        timeout=DEFAULT_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json().get('response', [])


def extract_player_stats(player_entry):
    """Aus einem get_fixture_player_stats-Eintrag die Kerndaten extrahieren.

    Returns dict:
        api_football_player_id  int
        name                    str
        minutes_played          int (0 wenn None)
        rating                  float|None
        is_substitute           bool
    """
    stats = player_entry.get('statistics', [{}])[0]
    games = stats.get('games', {})
    raw_rating = games.get('rating')
    try:
        rating = float(raw_rating) if raw_rating is not None else None
    except (TypeError, ValueError):
        rating = None
    return {
        'api_football_player_id': player_entry['player']['id'],
        'name':                   player_entry['player'].get('name', ''),
        'minutes_played':         games.get('minutes') or 0,
        'rating':                 rating,
        'is_substitute':          bool(games.get('substitute', False)),
    }
