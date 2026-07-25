"""Wettersystem — Würfellogik, Saisonphasen und Anzeige-Metadaten.

Das Wetter gilt global: ein Wurf pro Sim-Tag für alle Ligen, Wettbewerbe
und Spiele. Ein Sim-Tag entspricht dem echten Kalenderdatum (der globale
Kalender läuft auf date.today(), Fixtures haben scheduled_date).

Kernregeln (Spez):
- Echte Randomisierung, kein Seed, kein deterministischer Ablauf.
- Einmal gewürfeltes Wetter ist unveränderlich (get_or_create, nie update).
- Nächtlicher Tick würfelt "heute + 7"; ensure_weather_window() füllt
  idempotent alle fehlenden Tage von heute bis heute + 7 nach (deckt
  Erst-Deploy und verpasste Ticks ab).
- Saisonphasen über 90 Sim-Tage, Abfolge in jeder Saison identisch.
- Temperatur ist reiner Anzeigewert ohne Mechanik.
"""

from __future__ import annotations

import random
from datetime import date, timedelta

# Unabhängige, nicht seedbare Zufallsquelle (echte Randomness laut Spez).
_rng = random.SystemRandom()

# ── Saison-Anker ──────────────────────────────────────────────────────────────
# Tag 1 der 90-Tage-Saisonphasen-Rotation. Saison 1 wurde am 20.07.2026
# eröffnet (finance_season_open, siehe replit.md). Die Phasenfolge wiederholt
# sich alle 90 Tage; der Anker bestimmt nur, wo im Zyklus "heute" liegt.
SEASON_DAY1 = date(2026, 7, 20)

SEASON_LENGTH_DAYS = 90

# Phasen: (erster Tag, letzter Tag, Schlüssel) — Tage 1-basiert.
PHASES = [
    (1, 19,  'spaetsommer'),
    (20, 41, 'herbst'),
    (42, 60, 'winter'),
    (61, 82, 'fruehling'),
    (83, 90, 'fruehsommer'),
]

PHASE_LABELS = {
    'spaetsommer': 'Spätsommer',
    'herbst':      'Herbst',
    'winter':      'Winter',
    'fruehling':   'Frühling',
    'fruehsommer': 'Frühsommer',
}

# Wetterarten in Spez-Reihenfolge: Normal / Regen / Wind / Nebel / Hitze / Schnee
WEATHER_TYPES = ['normal', 'regen', 'wind', 'nebel', 'hitze', 'schnee']

# Wahrscheinlichkeiten in Prozent je Phase (Summe = 100).
PHASE_PROBABILITIES = {
    'spaetsommer': {'normal': 60, 'regen': 12, 'wind': 8,  'nebel': 5,  'hitze': 15, 'schnee': 0},
    'herbst':      {'normal': 48, 'regen': 25, 'wind': 15, 'nebel': 12, 'hitze': 0,  'schnee': 0},
    'winter':      {'normal': 40, 'regen': 15, 'wind': 12, 'nebel': 15, 'hitze': 0,  'schnee': 18},
    'fruehling':   {'normal': 60, 'regen': 20, 'wind': 10, 'nebel': 5,  'hitze': 5,  'schnee': 0},
    'fruehsommer': {'normal': 65, 'regen': 10, 'wind': 5,  'nebel': 0,  'hitze': 20, 'schnee': 0},
}

# Temperaturbereiche (inklusiv, °C) je Phase und Wetterart.
PHASE_TEMPERATURES = {
    'spaetsommer': {'normal': (18, 25), 'regen': (14, 19), 'wind': (15, 21), 'nebel': (12, 17), 'hitze': (29, 36)},
    'herbst':      {'normal': (8, 15),  'regen': (6, 12),  'wind': (7, 13),  'nebel': (4, 9)},
    'winter':      {'normal': (2, 8),   'regen': (3, 7),   'wind': (1, 6),   'nebel': (-1, 4), 'schnee': (-8, 0)},
    'fruehling':   {'normal': (12, 19), 'regen': (9, 15),  'wind': (10, 16), 'nebel': (7, 12), 'hitze': (24, 29)},
    'fruehsommer': {'normal': (19, 26), 'regen': (15, 20), 'wind': (16, 22), 'hitze': (28, 35)},
}

# ── Anzeige-Metadaten (Design-Vorlage, keine Taktik-Hinweise!) ────────────────
WEATHER_META = {
    'normal': {
        'label': 'Normal',
        'flavor': 'Klarer Himmel, trockener Rasen — bestes Fußballwetter. '
                  'Keine Ausreden heute.',
    },
    'regen': {
        'label': 'Regen',
        'flavor': 'Anhaltender Regen macht den Rasen tief und den Ball '
                  'rutschig. Wer heute grätscht, rutscht weit.',
    },
    'wind': {
        'label': 'Starker Wind',
        'flavor': 'Kräftige Böen fegen durchs Stadion. Jeder hohe Ball wird '
                  'heute zum Abenteuer.',
    },
    'nebel': {
        'label': 'Nebel',
        'flavor': 'Dichter Nebel liegt über dem Platz — von der Tribüne sieht '
                  'man nur Schemen. Alles ist möglich.',
    },
    'hitze': {
        'label': 'Hitze',
        'flavor': 'Drückende Hitze flimmert über dem Rasen. Heute werden die '
                  'Beine früher schwer als sonst.',
    },
    'schnee': {
        'label': 'Schnee/Frost',
        'flavor': 'Schneetreiben auf gefrorenem Boden — der Ball verspringt, '
                  'jeder Schritt ist ein Risiko.',
    },
}


def temperature_css_class(temp: int) -> str:
    """Farbcode laut Design: Hitze ≥28 orange, 10–27 neutral, 1–9 kalt, ≤0 Frost."""
    if temp >= 28:
        return 'wx-temp--heat'
    if temp >= 10:
        return 'wx-temp--normal'
    if temp >= 1:
        return 'wx-temp--cold'
    return 'wx-temp--frost'


def day_in_season(sim_day: date) -> int:
    """Tag innerhalb des 90-Tage-Saisonzyklus (1–90)."""
    delta = (sim_day - SEASON_DAY1).days
    return (delta % SEASON_LENGTH_DAYS) + 1


def phase_for_date(sim_day: date) -> str:
    """Saisonphase für ein Kalenderdatum."""
    day = day_in_season(sim_day)
    for start, end, key in PHASES:
        if start <= day <= end:
            return key
    return 'spaetsommer'  # unerreichbar (1–90 vollständig abgedeckt)


def roll_weather(sim_day: date) -> tuple[str, int]:
    """Würfelt Wetterart + Temperatur für einen Sim-Tag (ohne Persistenz).

    Echte Randomness via SystemRandom — kein Seed, kein Kontingent.
    """
    phase = phase_for_date(sim_day)
    probs = PHASE_PROBABILITIES[phase]
    types = [t for t in WEATHER_TYPES if probs.get(t, 0) > 0]
    weights = [probs[t] for t in types]
    weather_type = _rng.choices(types, weights=weights, k=1)[0]
    lo, hi = PHASE_TEMPERATURES[phase][weather_type]
    temperature = _rng.randint(lo, hi)
    return weather_type, temperature


def ensure_weather_for_day(sim_day: date):
    """Stellt sicher, dass für den Tag Wetter existiert (unveränderlich).

    Gibt (DayWeather, created) zurück. Bereits gewürfeltes Wetter wird
    NIEMALS überschrieben.
    """
    from .models import DayWeather

    existing = DayWeather.objects.filter(sim_day=sim_day).first()
    if existing is not None:
        return existing, False
    weather_type, temperature = roll_weather(sim_day)
    obj, created = DayWeather.objects.get_or_create(
        sim_day=sim_day,
        defaults={'weather_type': weather_type, 'temperature': temperature},
    )
    return obj, created


def ensure_weather_window(today: date | None = None, horizon: int = 7) -> int:
    """Füllt fehlende Wettertage von heute bis heute + horizon nach.

    Idempotent — deckt sowohl den nächtlichen Tick (würfelt effektiv
    heute + 7) als auch Erst-Deploy/verpasste Ticks ab.
    Gibt die Anzahl neu gewürfelter Tage zurück.
    """
    if today is None:
        today = date.today()
    created_count = 0
    for offset in range(0, horizon + 1):
        _, created = ensure_weather_for_day(today + timedelta(days=offset))
        if created:
            created_count += 1
    return created_count


def weather_for_match(match_date: date | None = None):
    """Wetter für einen Spieltermin (fehlendes Datum → heute).

    Würfelt fehlendes Tageswetter nach (get_or_create, unveränderlich) —
    damit hat jedes neu simulierte Spiel garantiert Wetter, auch wenn der
    Termin außerhalb des heute+7-Fensters liegt oder der Tick verpasst wurde.
    """
    if match_date is None:
        match_date = date.today()
    dw, _ = ensure_weather_for_day(match_date)
    return dw


def get_weather_for_date(sim_day: date | None):
    """DayWeather für ein Datum oder None (nie automatisch nachwürfeln).

    Spiele ohne Wettereintrag (Altdaten, fehlendes Datum) laufen ohne
    Wettereffekte; die Anzeige zeigt dann kein Icon.
    """
    if sim_day is None:
        return None
    from .models import DayWeather
    return DayWeather.objects.filter(sim_day=sim_day).first()


def weather_context(dw) -> dict | None:
    """Anzeige-Dict für Templates (Icon, Label, Temperatur, Flavor)."""
    if dw is None:
        return None
    return weather_context_from_parts(dw.weather_type, dw.temperature)


def weather_context_from_parts(weather_type, temperature) -> dict | None:
    """Anzeige-Dict aus Rohwerten (z. B. report_data['weather'] alter Spiele)."""
    meta = WEATHER_META.get(weather_type)
    if meta is None or temperature is None:
        return None
    return {
        'type':        weather_type,
        'label':       meta['label'],
        'temperature': int(temperature),
        'temp_class':  temperature_css_class(int(temperature)),
        'flavor':      meta['flavor'],
    }
