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

Breite Eckblöcke dürfen nicht ausschließlich über die zwei radial nächsten
Punkte in Vorder- und Hinterkante zerlegt werden. Wenn die Quellgeometrie eine
explizite Kantenkonvention besitzt, ist diese Konvention autoritativ und die
vier vorhandenen Punkte werden nur in die kanonische Scene-Reihenfolge
überführt.

**Why:** Ein Eckblock kann einen so großen Winkel überspannen, dass ein äußerer
Eckpunkt näher an der Spielfeldmitte liegt als der gegenüberliegende innere
Punkt. Eine reine Distanzsortierung erzeugt dann trotz gültigem Quellquad ein
scheinbar selbstüberschneidendes Runtime-Quad.

**How to apply:** Bei neuen Stadionimporten die Quellreihenfolge dokumentieren
und verlustfrei normalisieren. Niemals Punkte verschieben oder die Form aus
`rows`, `seats`, Tribünenseite oder Kapazität schätzen.

Renderer mit engerem Vertrag dürfen fehlende Live-Scene-Darstellungen nur in
einer flüchtigen Kopie normalisieren; kanonische Scene, Design und Geometrie
bleiben unverändert.

**Why:** Sonst verändern Renderergrenzen dauerhaft den gemeinsamen Datenvertrag.

**How to apply:** Zum Beispiel `procedural-ring` nur für einen Renderer, der
explizite Dachsegmente benötigt, transient auflösen und nie zurückschreiben.