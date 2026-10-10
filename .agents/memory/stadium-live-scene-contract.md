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

## Nutzerforderung: Editor-/Ticker-Parität mit Umgebung

„Die 3D Ansicht im Liveticker muss natürlich identisch sein mit dem 3D
Stadioneditor und dem 2D Stadioneditor.“

**Why:** Der Nutzer verlangt nach dem nicht überzeugenden Elversberger
Blueprint-Vergleich ausdrücklich Verbesserung und Umgebung direkt in 3D,
einschließlich Spielansicht und Liveticker. Das ist keine weitere reine
Bildstudie; die frühere Offline-/Admin-only-Grenze gilt für diesen Auftrag
nicht mehr.

**How to apply:** Gemeinsamen Stadion- und Umfeldbestand verwenden, nicht
getrennte Editor-, Ticker- und Exportkulissen. Die 2D-Projektion und
3D-Geometrie müssen dieselben Ortsobjekte und denselben aktuellen Ausbau
darstellen; unterschiedliche Kameras sind kein abweichender Bestand.
Die Freigabe betrifft Elversberg, nicht einen automatischen Vereins-Rollout.

## Verbindliche Stadionabnahme je Verein

Der Nutzer verlangt: „Für jeden Verein möchte ich die Abnahme der 5 Bilder
machen. 2D, 3D Editor, LiveTicker, LiveTicker ohne Dach und bei Nacht.“

**Why:** Der Nutzer hat dieses Abnahmeformat ausdrücklich für jeden Verein
vorgegeben.

**How to apply:** Je Verein diese fünf aktuellen Ansichten vorlegen. Die
Abnahme eines anderen Vereins nicht übertragen; fehlende oder blockierte
Aufnahmen offen benennen und nicht durch unmarkierte ältere Bilder ersetzen.

Die Tagesgestaltung des 3D-Editors und Livetickers ist vom Nutzer bestätigt:
„3D Editor super, LiveTicker ebenfalls“. Der 2D-Editor wirkt ihm dagegen
zu weit entfernt; er möchte den Zoom selbst festlegen und merken. Die sichtbaren
Lichtmasten wurden ausdrücklich hinterfragt, nicht als echte Leuchten
freigegeben; ihre vorläufige schematische Darstellung ist anschließend
ausdrücklich erlaubt worden (siehe Flutlicht-Laufzeitvertrag).

**Why:** Der Nutzer hat die räumlichen Tagesansichten bestätigt, aber weder
den großen anfänglichen 2D-Umgebungsrahmen noch die Herkunft der Lichtmasten.

**How to apply:** Die bestätigte 3D-Gestaltung erhalten. 2D-Zoom als
Ansichtseinstellung behandeln, nicht durch Änderungen an Ortsbestand oder
Stadiongeometrie lösen. Generierte Masten nicht als nachgewiesene
Modellleuchten ausgeben.

Der Nutzer hat den Elversberger Stand einschließlich 2D-Zoom und der
Nachtansicht mit schematischem Flutlicht vorerst abgenommen:
„okay, alles erstmal abgesegnet.“

**Why:** Ausdrückliche Abnahme nach Lieferung der Zoom-Bedienung und
Nachtaufnahme; die Masten bleiben bewusst schematisch.

**How to apply:** Den abgenommenen Stand erhalten. Die Abnahme ist keine
Freigabe realer Leuchtenpositionen oder eines automatischen Vereins-Rollouts.

## Kamera- und Sichtwechsel

Orbit-Kameraänderungen dürfen die Stadiongeometrie nicht neu erzeugen. Eine
ausgeblendete WebGL-Bühne muss ihre Layoutgröße behalten.

**Why:** Große Sitzgeometrien machen jeden Rebuild während Slider-, Drag- oder
2D/3D-Wechseln sichtbar langsam.

**How to apply:** Kamera-Matrizen direkt aktualisieren; nur Scene-, Licht-,
Kameraart- oder echte Größenänderungen dürfen einen Rebuild auslösen.

## Abgeleitete Ansichtsgrenzen

Runtime-Ansichten dürfen optionale Legacy-Metadaten wie `meta.maxR` nicht
voraussetzen; Ansichtsgrenzen werden aus der Live-Scene-Kontur abgeleitet.

**Why:** Kanonische Live Scenes enthalten die Geometrie, aber nicht zwingend
alte Editor-Hilfswerte. Ein fehlender Radius machte die 2D-Skalierung zu `NaN`.

**How to apply:** Explizite gültige Metadaten verwenden, sonst Mittelpunkt und
maximalen Konturradius aus `outline` berechnen.

## Editor- und Scene-Identitäten

Der Stadioneditor verwendet fortlaufende lokale Blockindizes für Interaktion
und Undo. Kanonische Speicher-IDs und flüchtige Vorschau-IDs bleiben davon
getrennt.

**Why:** Kanonische Block-IDs müssen eindeutig, aber nicht fortlaufend sein.
Ausbauvorschauen können zusätzliche Blöcke erzeugen; eine gemeinsame ID würde
bei Lücken kollidieren und 2D-Auswahl, 3D-Scene oder Designexport vertauschen.

**How to apply:** Persistierte Blöcke behalten eine separate kanonische ID.
Nur temporäre Vorschau-Blöcke erhalten eine eigene Renderer-ID und werden nie
als Geometrie oder Kapazität gespeichert.

## Elversberger Haupttribüne und unveränderte Feldkamera

Die freigegebene Spielkamera bleibt einschließlich ihrer Kameraseite und
Feldeckenprojektion unverändert. Die Orientierung des Elversberger Modells
wird im gemeinsamen Szenenrahmen angepasst, nicht durch einen Wechsel der
Kameraseite. Der vordere Stadionteil wird nur für die Spielansicht ausgeblendet.

**Why:** Eine gegenüberliegende Kameraseite kann die Haupttribüne scheinbar
richtig zeigen, dreht aber die Feldprojektion und damit den gemeinsamen
2D-Spielablauf um. Das verletzt die ausdrücklich freigegebene feste Feldkamera.

**How to apply:** Kameravergleiche mit identischem Rahmen, Dach-/Lichtzustand
und aktuellen gespeicherten Daten durchführen. Gebäude und Vegetation folgen
derselben Modelltransformation; sie dürfen nicht unabhängig umgeordnet werden.