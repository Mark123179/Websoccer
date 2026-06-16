"""Namens- und Vereinsnormalisierung (Spec §15).

Berücksichtigt Groß-/Kleinschreibung, überflüssige Leerzeichen, Bindestriche,
Apostrophe, Akzente/diakritische Zeichen und unterschiedliche Unicode-Formen.

Konsistent mit der bestehenden SoFIFA-Import-Normalisierung, damit Spieler über
beide Importwege gleich erkannt werden.
"""

import html
import re
import unicodedata


def normalize_name(value):
    """Normalisiert einen Namen für robusten Vergleich.

    Entfernt HTML-Entities, diakritische Zeichen (NFKD → ASCII) und alle
    Nicht-Buchstaben (Leerzeichen, Bindestriche, Apostrophe, Punkte) und gibt
    das Ergebnis in Kleinbuchstaben zurück.
    """
    value = html.unescape(value or '')
    value = unicodedata.normalize('NFKD', value)
    value = value.encode('ASCII', 'ignore').decode('ASCII')
    return re.sub(r'[^a-zA-Z]', '', value).lower()


def normalize_club_name(value):
    """Normalisiert einen Vereinsnamen für Dedup/Matching (gleiche Regeln)."""
    return normalize_name(value)
