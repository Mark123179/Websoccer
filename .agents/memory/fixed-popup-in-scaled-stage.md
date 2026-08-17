---
name: Fixed-Popup in skaliertem Stage-Container
description: Warum Hover-Popups (z. B. Wetter-Karte) per JS an document.body portiert werden müssen und wie die Skalierung nachgezogen wird.
---

# Fixed-Popup in skaliertem Stage-Container

**Regel:** Popups/Overlays, die aus einer Kachel innerhalb von `.dashboard-scaler` (transform: scale) herausragen sollen, müssen per JS an `document.body` portiert werden (`position: fixed` + eigenes `scale(var(--game-scale))`).

**Why:** `transform` auf einem Vorfahren macht diesen zum Containing Block für `position: fixed` — das Popup bleibt im skalierten Kontext gefangen und wird zusätzlich von `overflow: hidden` der Kacheln (z. B. Kalender-Kacheln) abgeschnitten. Reines CSS (`:hover > .pop`) reicht dort nicht.

**How to apply:** Zwei Fälle: (1) Flex-zentrierte Modal-Backdrops → es gibt ein globales Portal-Script, das Backdrops an `<body>` portiert und den Inhalt mit `--game-scale` nachskaliert; neue Modals dort registrieren statt eigene Portale zu bauen. (2) Positionierte Hover-Popups → Muster in `game/static/game/js/weather.js`:
- Portal beim ersten `mouseover`/`focusin` synchron vor dem Paint; Popup pro Badge cachen (`el.__wxPop`), kein Leak.
- `--game-scale` wird von der Scaler-Logik in `base.html` auf `:root` gesetzt → zur Laufzeit lesen, nie einfrieren.
- Position: über dem Trigger zentrieren, an Viewport-Rändern klemmen, nach unten öffnen wenn oben kein Platz; Scroll (capture-phase, auch innere Container) + Resize nachführen.
- `pointer-events: none` auf dem Popup verhindert Hover-Flackern.
- CSS-`:hover`-Fallback beibehalten (no-JS). Globales `focusout` auf den Trigger-Selektor begrenzen, sonst schließt jedes Fokusereignis das Popup.
- Debug: `?wxdebug=N` öffnet das N-te Popup ohne Hover (für Screenshots).
