---
name: SoFIFA matching + importer browser resilience
description: Why SoFIFA extracted nothing and how the CFM importer recovers from a dead browser.
---

# SoFIFA-Matching im CFM-Importer

SoFIFA-Trefferlisten zeigen oft **Kurz-/Abkürzungsnamen** (z. B. „L. Messi").
`normalize.normalize_name` reduziert auf reine Buchstaben (Spiegel der
Server-Engine) — wichtig: **Umlaute werden zu u, nicht zu ue** (ü→u, NFKD-ASCII).
Ein reiner Gleichheitsvergleich scheitert daher an Kurznamen → das Profil wird
nie geöffnet → für ALLE Spieler bleibt SoFIFA leer.

**Lösung/Regel:** zweistufig matchen — toleranter Namens-Vorfilter (gleicher
Nachname + verträglicher Vorname/Initiale; Einzeltoken/Mononyme matchen gegen
Vor- ODER Nachnamen) und danach **Bestätigung über das Geburtsdatum**. Lesbares,
aber abweichendes DOB → verwerfen (kein Raten). DOB nicht lesbar + genau ein
Namenstreffer → mit Warnung „bitte prüfen" übernehmen (SoFIFA ist optional und
wird in der Kontrollphase gesichtet).

**Why:** kein Raten, aber SoFIFA als optionale Quelle darf nicht an reiner
Namensstrenge scheitern; die Kontrollphase fängt Restunsicherheit ab.

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
