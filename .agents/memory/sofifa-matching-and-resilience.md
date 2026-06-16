---
name: SoFIFA-Werte kommen per CSV, nicht per Live-Scraping + Importer-Resilience
description: Warum der CFM-Importer SoFIFA NICHT mehr live ausliest, und wie er einen toten Browser übersteht.
---

# SoFIFA-/EA-Ratings: nur noch per CSV-Export

**Entscheidung (Nutzer-bestätigt):** Der CFM-Importer liest SoFIFA/EA-Ratings
(Stärke/Potenzial/Attribute) **NICHT mehr live**. Der frühere Live-Adapter
(`adapters/sofifa.py`) inkl. zweistufigem Namens-/DOB-Matching wurde entfernt.
Diese Werte kommen ausschließlich über den **CMTracker-/SoFIFA-CSV-Export** in
die DB: `game/sofifa_import.py` (Voll-Export `.local/tmp/sofifa_uploads/*.csv`
und CMTracker-API-Export) → `PlayerSourceRating(source=SOURCE_EA)`.

**Why:** Sowohl `sofifa.com` ALS AUCH `cmtracker.net` liefern serverseitig
Cloudflare-403 — nicht verifizierbar/zuverlässig scrapebar. Live-Scraping im
Importer war fragil und konnte leere Werte übertragen.

**How to apply:** Server-Ingestion bleibt tolerant — `candidate.sofifa_raw` ist
`JSONField(default=dict, blank=True)`, `_store_candidate` nutzt
`raw.get('sofifa')` (→ None wenn fehlt), `review.py`/`import_service.py` nutzen
`... or {}`. Ein Candidate ohne `sofifa`-Key ist also unkritisch; die
serverseitige `sofifa_raw`/`sofifa_id`-Verarbeitung NICHT entfernen (würde nur
eine Migration/Risiko ohne Nutzen bringen). SoFIFA-Werte immer über den
CSV-Pfad nachpflegen.

# safe_goto verpackt Browser-Tod als PageError

`adapters/base.py:safe_goto` fängt Navigations-/Timeout-Exceptions (inkl.
„…has been closed") und wirft sie als generischen `PageError`. Die per-Spieler-
Schleife im Runner fängt `PageError` als „Spieler überspringen". Folge eines
toten Browsers: jeder Spieler scheitert still → Lauf „komplett" ohne Daten.

**Regel:** Browser-Verlust muss an **beiden** Stellen erkannt werden —
`except PageError` UND `except Exception` rufen `is_closed_error(exc)` und lösen
über `_BrowserGone` einen `Browser.restart()` aus (persistentes Profil bleibt,
Cloudflare-Freigabe gilt weiter), Wiederaufnahme über `JobState`. Begrenzung:
`Runner.MAX_BROWSER_RELAUNCH`.

**How to apply:** Bei jeder neuen Quelle/jedem neuen Aufrufpunkt, der
`safe_goto` nutzt, dieselbe is_closed_error-Promotion einbauen — sonst frisst
die generische Fehlerbehandlung den Browser-Tod. (Folgeidee: dedizierter
`BrowserClosedError` aus safe_goto statt Text-Marker.)
