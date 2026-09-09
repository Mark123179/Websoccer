---
name: Stadion-Live-Scene-Vertrag
description: Trennung von gespeichertem Stadiondesign und dem vollständigen Runtime-Vertrag für externe Renderer.
---

Das gespeicherte Stadiondesign bleibt ein reiner, managereditierbarer
Farbvertrag ohne Raumgeometrie. Externe Renderer konsumieren stattdessen eine
serverseitig zusammengesetzte Live Scene aus Geometrie und Design.

**Why:** Würden Browser oder getrennte Renderer Raumform aus Rastermaßen,
Tribünennamen oder Blickrichtung rekonstruieren, liefen Editor und Livemodus
zwangsläufig auseinander. Redundant gespeicherte Quads wären außerdem
manipulierbar und könnten nach Ausbauten veralten.

**How to apply:** Neue Stadionverbraucher immer an die Live Scene anbinden. Die
Scene liefert alle Blöcke in Metern, pitch-zentriert und mit kanonischen Quads;
Kamera und Culling bleiben Client-Aufgabe. Geometrie nie aus dem Design
zurückschreiben oder aus `rows`/`seats` schätzen.