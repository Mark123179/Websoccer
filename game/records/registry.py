"""Zentrale Registry der aktuell verbindlichen Ruhmeshallen-Rekorde.

Die Slot-Zählung ist absichtlich hier und nicht im Frontend hinterlegt. Dadurch
kann ein neuer Rekord später als Registry-Eintrag plus Berechnung ergänzt werden.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class RecordDefinition:
    key: str
    label: str
    room: str
    slot: int
    calculator: str
    seed_capable: bool = True
    image_source: str = 'record'


RECORD_REGISTRY = (
    RecordDefinition('top_scorer', 'Rekordtorschütze', 'player', 1, 'top_scorer'),
    RecordDefinition('top_assists', 'Rekordvorlagengeber', 'player', 2, 'top_assists'),
    RecordDefinition('most_apps_field', 'Meiste Spiele Feldspieler', 'player', 3, 'most_apps_field'),
    RecordDefinition('most_apps_gk', 'Meiste Spiele Torwart', 'player', 4, 'most_apps_gk'),
    RecordDefinition('most_titles_player', 'Meiste Titel Spieler', 'player', 5, 'most_titles_player'),
    RecordDefinition('highest_market_value', 'Höchster Marktwert', 'player', 6, 'highest_market_value'),
    RecordDefinition('longest_tenure', 'Längste Amtszeit', 'coach', 1, 'longest_tenure'),
    RecordDefinition('most_matches_coach', 'Meiste Spiele', 'coach', 2, 'most_matches_coach'),
    RecordDefinition('most_titles_coach', 'Meiste Titel', 'coach', 3, 'most_titles_coach'),
    RecordDefinition('best_ppg_coach', 'Bester Punkteschnitt', 'coach', 4, 'best_ppg_coach'),
    RecordDefinition('most_wins_coach', 'Meiste Siege', 'coach', 5, 'most_wins_coach'),
    RecordDefinition('biggest_win', 'Höchster Sieg', 'club', 1, 'biggest_win'),
    RecordDefinition('biggest_defeat', 'Höchste Niederlage', 'club', 2, 'biggest_defeat'),
    RecordDefinition('longest_win_streak', 'Längste Siegesserie', 'club', 3, 'longest_win_streak'),
    RecordDefinition('longest_unbeaten', 'Längste Serie ohne Niederlage', 'club', 4, 'longest_unbeaten'),
    RecordDefinition('longest_winless', 'Längste Serie ohne Sieg', 'club', 5, 'longest_winless'),
    RecordDefinition('best_season', 'Beste Saison', 'club', 6, 'best_season'),
    RecordDefinition('worst_season', 'Schlechteste Saison', 'club', 7, 'worst_season'),
    RecordDefinition('most_goals_season', 'Meiste Tore in einer Saison', 'club', 8, 'most_goals_season'),
    RecordDefinition('fewest_conceded_season', 'Wenigste Gegentore in einer Saison', 'club', 9, 'fewest_conceded_season'),
    RecordDefinition('championships', 'Meisterschaften', 'club', 10, 'championships', image_source='trophy'),
    RecordDefinition('cup_wins', 'Pokalsiege', 'club', 11, 'cup_wins', image_source='trophy'),
    RecordDefinition('record_signing', 'Teuerster Einkauf', 'club', 13, 'record_signing'),
    RecordDefinition('record_sale', 'Teuerster Verkauf', 'club', 14, 'record_sale'),
)

RECORDS_BY_KEY = {definition.key: definition for definition in RECORD_REGISTRY}


def get_record_definition(record_key):
    return RECORDS_BY_KEY[record_key]


def iter_record_definitions():
    return iter(RECORD_REGISTRY)