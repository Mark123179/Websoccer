---
name: Wettersystem V1
description: Globales Tageswetter (DayWeather) + multiplikative Engine-Modifikatoren; Baseline-Schutz und Integrationsregeln.
---

# Wettersystem V1

## Kernregeln
- **Global & unveränderlich**: ein Wurf pro Sim-Tag (`DayWeather`, sim_day = DateField PK) für alle Ligen/Wettbewerbe; `ensure_weather_for_day` nutzt get_or_create, nie update. Echte Randomness via `random.SystemRandom` — bewusst NICHT seedbar.
- **Saisonphasen**: 90-Tage-Rotation, Anker `SEASON_DAY1 = 2026-07-20`; Phasen/Wahrscheinlichkeiten/Temperaturen in `weather_service.py` (PHASES, PHASE_PROBABILITIES, PHASE_TEMPERATURES). Temperatur ist reiner Anzeigewert.
- **Nightly Tick**: `roll_daily_weather` würfelt heute+7; `ensure_weather_window()` füllt idempotent nach; `weather_for_match(date)` würfelt fehlende Tage on-demand (deckt verpasste Ticks ab).

## Engine-Integration (Freeze-kompatibel)
- `_apply_weather_to_compiled()` läuft NACH `compile_tactic()` — die Compiler-Clamps (xg_for 0.80–1.30) würden Wetterfaktoren sonst beschneiden. Bewusst nicht über zone_weights (±7%-Clamp verschluckt zonale Faktoren).
- **`weather=None` oder `'normal'` = strikter No-Op** (early return, keine RNG-Aufrufe) → Regression-Baseline bleibt bit-identisch; `regression_sim` ruft `_simulate_match_minutes` ohne weather auf.
- Schnee ändert den xG-Exponenten als NEUEN Default-Parameter (`exponent=1.25` unverändert); kein Freeze-Konstante angefasst.
- Caller (season_service, play_matchday, cup_service, views-Proben) holen Wetter via try/except — Wetterfehler degradiert zu None, blockiert nie die Simulation.

## Warum
Match Engine V2 ist im Balancing-Freeze; Wetter musste additiv-multiplikativ und abschaltbar sein. Abnahme: gewichtete Saison-Torschnitt-Verschiebung −1,37 % (Kriterium ≤2 %), gemessen paired per `_make_team_v1`-Arme je Wetterart, gewichtet nach Phasenlängen-Verteilung (normal 53 %, regen 18 %, wind 11 %, nebel 8 %, hitze 6 %, schnee 4 %).

## Anwendung
- Neue Wettereffekte: nur Multiplikatoren in `_apply_weather_to_compiled` bzw. explizite Parameter-Threads (Verletzungen, Standards); No-Op-Pfad für None/'normal' NIE aufweichen.
- UI: `partials/weather_icon.html` (Flags show_temp/dimmed/no_popup) + `weather.css`; Popup zeigt Flavor-Text, absichtlich KEINE Taktik-Hinweise. Kalender-Horizont: Vergangenheit gedimmt, heute..+7 voll, ab +8 nichts. Altberichte ohne weather-Key → '–'-Fallback.
- Achtung beim HTML-Verifizieren: erstes „Wetter:“ im Dokument ist das Kalender-aria-label, nicht der Spielbericht-Hero.
