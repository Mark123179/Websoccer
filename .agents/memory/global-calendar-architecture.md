---
name: Global Calendar Architecture
description: Der Kalender (ws-game-header) ist ein globales Component in base.html, manager-gebunden via context_processors.py
---

## Regel
Der `ws-game-header` wird EINMAL in `base.html` via `{% include 'game/partials/game_header.html' %}` gerendert — direkt in `<main class="container">`, vor `{% block content %}`. Er ist NICHT mehr in einzelnen Seiten-Templates.

## Kalender-Daten: context_processors.py
`current_manager()` berechnet zusätzlich `global_calendar` (calendar_days, previous_offset, next_offset) basierend auf dem echten Manager-Verein aus der DB. `game_header.html` liest `global_calendar.*`.

## game_header-Partial: nur noch Metadaten
`build_game_header(title, subtitle, back_url)` gibt nur noch diese 3 Felder zurück. Kein club/opponent/calendar_offset mehr. Jede View übergibt nur den Seiten-Titel.

**Why:** Manager ohne Verein → überall leerer Kalender. Manager mit Verein → überall seine Spiele. Kein Page-spezifischer Kalender möglich.
