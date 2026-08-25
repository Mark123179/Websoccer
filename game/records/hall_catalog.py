"""Shared slot catalogue for the public Hall of Fame and Creator maintenance."""

from dataclasses import dataclass


@dataclass(frozen=True)
class HallRecordSlot:
    key: str
    label: str
    room: str
    slot: int
    custom_label: bool = False


HALL_RECORD_SLOTS = (
    HallRecordSlot('top_scorer', 'Rekordtorschütze', 'player', 1),
    HallRecordSlot('top_assists', 'Rekordvorlagengeber', 'player', 2),
    HallRecordSlot('most_apps_field', 'Meiste Spiele Feldspieler', 'player', 3),
    HallRecordSlot('most_apps_gk', 'Meiste Spiele Torwart', 'player', 4),
    HallRecordSlot('most_titles_player', 'Meiste Titel Spieler', 'player', 5),
    HallRecordSlot('highest_market_value', 'Höchster Marktwert', 'player', 6),
    HallRecordSlot('player_empty_7', 'Schnellstes Tor', 'player', 7),
    HallRecordSlot('player_empty_8', 'Meiste Spieler des Spiels', 'player', 8),
    HallRecordSlot('longest_tenure', 'Längste Amtszeit', 'coach', 1),
    HallRecordSlot('most_matches_coach', 'Meiste Spiele', 'coach', 2),
    HallRecordSlot('most_titles_coach', 'Meiste Titel', 'coach', 3),
    HallRecordSlot('best_ppg_coach', 'Bester Punkteschnitt', 'coach', 4),
    HallRecordSlot('most_wins_coach', 'Meiste Siege', 'coach', 5),
    HallRecordSlot('coach_empty_6', 'Höchster Sieg', 'coach', 6),
    HallRecordSlot('coach_empty_7', 'Längste Siegesserie', 'coach', 7),
    HallRecordSlot('coach_empty_8', 'Beste Saison', 'coach', 8),
    HallRecordSlot('biggest_win', 'Höchster Sieg', 'club', 1),
    HallRecordSlot('biggest_defeat', 'Höchste Niederlage', 'club', 2),
    HallRecordSlot('longest_win_streak', 'Längste Siegesserie', 'club', 3),
    HallRecordSlot('longest_unbeaten', 'Serie ohne Niederlage', 'club', 4),
    HallRecordSlot('longest_winless', 'Längste Serie ohne Sieg', 'club', 5),
    HallRecordSlot('best_season', 'Beste Saison', 'club', 6),
    HallRecordSlot('worst_season', 'Schlechteste Saison', 'club', 7),
    HallRecordSlot('most_goals_season', 'Meiste Tore in einer Saison', 'club', 8),
    HallRecordSlot('fewest_conceded_season', 'Wenigste Gegentore', 'club', 9),
    HallRecordSlot('championships', 'Meisterschaften', 'club', 10),
    HallRecordSlot('cup_wins', 'Pokalsiege', 'club', 11),
    HallRecordSlot('international_titles', 'Internationale Titel', 'club', 12),
    HallRecordSlot('record_signing', 'Teuerster Einkauf', 'club', 13),
    HallRecordSlot('record_sale', 'Teuerster Verkauf', 'club', 14),
    HallRecordSlot('club_empty_15', 'Vereinsrekord', 'club', 15, custom_label=True),
    HallRecordSlot('club_empty_16', 'Vereinsrekord', 'club', 16, custom_label=True),
)

SLOTS_BY_KEY = {slot.key: slot for slot in HALL_RECORD_SLOTS}


def slots_for_room(room):
    return tuple(slot for slot in HALL_RECORD_SLOTS if slot.room == room)
