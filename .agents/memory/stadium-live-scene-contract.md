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

Beim deterministischen Dachring gelten zwei verschiedene Zentren: Das
transformierte Umrisszentrum steuert radiale Außenring-Auswahl und
Winkelsortierung; die Dachinnenkante wird dagegen immer um den kanonischen
Spielfeldursprung `[0,0]` geklemmt.

**Why:** Bei asymmetrischen Stadien kann das Umrisszentrum deutlich vom
Spielfeldzentrum abweichen. Ein gemeinsames Zentrum verändert dann die
Dachflächen gegenüber dem Editor.

**How to apply:** Beide Rollen im Scene-Vertrag getrennt halten. Das
Umrisszentrum niemals als Zentrum der Spielfeld-/Laufbahn-Enveloppe verwenden.