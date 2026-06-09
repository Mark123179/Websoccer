"""
Dünner API-Client für API-Football v3 (v3.football.api-sports.io).
API-Key kommt aus settings.API_FOOTBALL_KEY (Env-Secret API_FOOTBALL_KEY).
Kein eigenes Caching — Budget-Steuerung liegt beim Aufrufer.
"""

import requests
from django.conf import settings

API_BASE = 'https://v3.football.api-sports.io'
DEFAULT_TIMEOUT = 15


def _headers():
    return {
        'x-rapidapi-key': settings.API_FOOTBALL_KEY,
        'x-rapidapi-host': 'v3.football.api-sports.io',
    }


def get_team_fixtures(team_id, last=10):
    """Letzte `last` abgeschlossene Spiele eines Teams.

    Returns list[dict] – rohe response-Einträge der API.
    Raises requests.HTTPError bei 4xx/5xx.
    """
    resp = requests.get(
        f'{API_BASE}/fixtures',
        headers=_headers(),
        params={
            'team':   team_id,
            'last':   last,
            'status': 'FT,AET,PEN',
        },
        timeout=DEFAULT_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json().get('response', [])


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
