"""
Automatische Helligkeits-Normalisierung für Stadion-Kachelbilder.

Problem: Jeder Verein hat sein eigenes Stadionfoto (stadium_image_static_path),
und diese Fotos unterscheiden sich stark in ihrer natürlichen Belichtung
(Tag/Nacht, Sonnenlicht, Flutlicht). Die anderen Management-Hub-Kacheln nutzen
fest kuratierte, einheitlich dunkel-moody gestimmte Bilder. Damit die
Stadion-Kachel optisch nicht heller/dunkler herausfällt, wird die Ziel-Luminanz
der übrigen Kacheln herangezogen und pro Stadionbild ein CSS-Filter berechnet,
der es auf dasselbe Helligkeitsniveau bringt.

Die eigentliche Messung passiert offline über
`python manage.py build_stadium_brightness_map` und wird als JSON-Datei
persistiert, damit zur Laufzeit keine Bildverarbeitung nötig ist.
"""
import json
import os
from functools import lru_cache

from django.conf import settings

# Ziel-Luminanz (0-255, Graustufen-Mittelwert), kalibriert auf die
# bestehenden kuratierten Hub-Kacheln (sportvorstand/finanzen/sponsoring/...
# liegen im Bereich ~28-48).
TARGET_LUMINANCE = 34.0

# Grenzen für den Helligkeits-Faktor, damit extrem dunkle/helle Fotos nicht
# zu Artefakten (komplett schwarz / ausgewaschen) führen.
MIN_FACTOR = 0.45
MAX_FACTOR = 1.30

BRIGHTNESS_MAP_PATH = os.path.join(
    settings.BASE_DIR, 'game', 'static', 'game', 'data', 'stadium_brightness_map.json'
)

DEFAULT_FILTER = 'brightness(1) contrast(1)'


@lru_cache(maxsize=1)
def _load_map():
    if not os.path.exists(BRIGHTNESS_MAP_PATH):
        return {}
    try:
        with open(BRIGHTNESS_MAP_PATH, 'r', encoding='utf-8') as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError):
        return {}


def get_stadium_tile_filter(static_rel_path):
    """
    Gibt den CSS-Filter-String für ein gegebenes Stadionbild zurück
    (relativer static-Pfad, z.B. 'game/images/stadiums/germany/fc-bayern.jpg').
    Fällt auf einen neutralen Filter zurück, falls das Bild noch nicht in der
    Helligkeits-Map erfasst wurde (z.B. neu hinzugefügtes Bild vor dem
    nächsten `build_stadium_brightness_map`-Lauf).
    """
    if not static_rel_path:
        return DEFAULT_FILTER
    data = _load_map()
    entry = data.get(static_rel_path)
    if not entry:
        return DEFAULT_FILTER
    factor = entry.get('factor', 1.0)
    return f'brightness({factor}) contrast(1.05)'


def compute_factor_from_luminance(luminance):
    if not luminance:
        return 1.0
    factor = TARGET_LUMINANCE / luminance
    factor = max(MIN_FACTOR, min(MAX_FACTOR, factor))
    return round(factor, 3)
