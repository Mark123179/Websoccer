# Claude Design Brief: Stadion-Livemodus

## Auftrag

Erzeuge einen hochwertigen, interaktiven UI-Prototyp für die Stadionansicht
eines Websoccer-Livespiels. Der Prototyp soll das echte Heimstadion des Spiels
aus der mitgelieferten BVB-Live-Scene darstellen und in einen modernen
Spielbericht eingebettet werden können.

Der aktuelle Canvas-Renderer ist eine **funktionierende technische
Ausgangslage**, aber keine gestalterische Endlösung. Verbessere Inszenierung,
Lesbarkeit, Atmosphäre, Kameraführung und responsive Darstellung, ohne die
gelieferte Stadiongeometrie zu verändern oder neu zu erfinden.

## Erwartetes Ergebnis

- Ein eigenständig startbarer Web-Prototyp mit HTML, CSS und JavaScript
- Eine Stadion-Vollansicht und eine Variante im Spielbericht-Kontext
- Desktopansicht für den bestehenden 1440×900-Game-Shell-Rahmen
- Sinnvolle responsive Zustände für Tablet und Smartphone
- Interaktive Kamera:
  - horizontal ziehen = Stadion umrunden
  - Mausrad oder Touch-Geste = zoomen
  - Doppelklick oder Reset-Button = Ausgangsansicht
- Lade-, Fehler- und Leerezustand
- Gute Performance auch bei den vollständigen Sitzrastern
- Keine Backendimplementierung und keine erfundenen API-Antworten

## Priorität der gelieferten Dateien

Bei Widersprüchen gilt diese Reihenfolge:

1. `data/stadion-live-scene.json`
2. Dieses Briefing
3. `contracts/LIVE_SCENE_CONTRACT_CURRENT.txt`
4. `current-live-mode/`
5. `match-report-context/`
6. `visual-references/`
7. `editor-reference/`
8. `legacy-reference/`

Die Dateien in `legacy-reference/` erklären die Vorgeschichte. Sie sind
ausdrücklich **nicht** der aktuelle technische Vertrag.

## Nicht verhandelbarer Live-Scene-Vertrag

Die Datei `data/stadion-live-scene.json` ist die autoritative Runtime-Scene:

- `schema` muss `websoccer.stadium-live-scene` sein.
- `version` muss `1` sein.
- Maßeinheit ist Meter.
- Ursprung ist die Spielfeldmitte.
- `+X` verläuft Tor-zu-Tor, `+Y` Seitenlinie-zu-Seitenlinie, `+Z` nach oben.
- Das Spielfeld misst 105 × 68 Meter.
- Jeder Block besitzt sein eigenes räumliches Viereck.
- Quad-Reihenfolge:
  `[vorne-links, vorne-rechts, hinten-rechts, hinten-links]`
  aus Sicht des Spielfelds.
- `z0` und `z1` sind die echte Vorder- und Hinterkantenhöhe.
- `rows` und `seats` teilen ausschließlich das gelieferte Quad in Rasterzellen.
- `rle` wird zeilenweise dekodiert: vordere Reihe zuerst, innerhalb einer Reihe
  links nach rechts aus Sicht des Spielfelds.
- `sum(rle[*][0])` ist immer `rows * seats`.
- RLE-Farbwerte sind Indizes in `palette`.
- `roof.mode: "explicit"` bedeutet: ausschließlich die gelieferten
  Dachsegmente verwenden.
- Alle 52 Blöcke werden geladen. Kamera und Culling entscheiden nur, was im
  aktuellen Bild sichtbar ist.

## Was ausdrücklich verboten ist

- Keine Tribünengeometrie aus `stand`, `tier`, `order`, `rows` oder `seats`
  ableiten.
- Keine vier generischen Tribünen statt der 52 individuellen Blöcke erzeugen.
- Keine Quads neu sortieren, spiegeln, skalieren oder anhand einer
  Stadion-Silhouette schätzen.
- Kein `axisTheta` einführen; die Scene ist bereits pitch-zentriert.
- `rows` und `seats` niemals als räumliche Breite, Tiefe oder Höhe verwenden.
- Keine Blöcke oder Dächer wegen eigener Plausibilitätsheuristiken verwerfen.
- Den Design-V2-Export nicht mit Raumgeometrie anreichern oder als Ersatz für
  die Live Scene verwenden.
- Die veraltete aggregierte `tribuenen.nord/west/ost/sued`-Idee aus dem
  Legacy-Dokument nicht implementieren.
- Keine Stadiondaten im Browser zurückschreiben.

## Renderinghinweise

### Tribünen

Eine Rasterzelle mit Spalte `seat` und Reihe `row` liegt bilinear im Blockquad:

```text
u0 = seat / seats
u1 = (seat + 1) / seats
v0 = row / rows
v1 = (row + 1) / rows
```

Interpoliert wird zwischen Vorder- und Hinterkante. Die Höhe steigt dazu von
`z0` auf `z1`. `current-live-mode/live_mode.js` enthält eine funktionierende
Referenzimplementierung (`bilinearPoint`, `decodeRle`, `seatItems`).

### Dächer

Die BVB-Beispielscene enthält `roof.mode: "explicit"`. Jedes Segment besitzt
ein Quad und vier zugehörige Höhen. Diese Segmente sind verbindlich. Ein
generischer Ring ist für diese Scene nicht nötig.

### Kamera und Culling

Die Scene liefert immer das vollständige Stadion. Der Client darf Flächen
ausblenden, die direkt hinter der Kamera liegen, darf aber die Scene nicht
dauerhaft reduzieren. Beim Drehen müssen zuvor ausgeblendete Seiten wieder
erscheinen.

### Performance

Der technische Referenzrenderer baut aktuell jede Rasterzelle als eigenes
Zeichenobjekt. Claude darf dies optimieren, etwa durch:

- Offscreen-Canvas oder vorgerenderte Blocktexturen
- Caching pro Block und Zoomstufe
- nur sichtbare Rasterflächen rendern
- reduzierte Detailstufen auf kleinen Viewports

Die RLE und die räumliche Zuordnung der Farben müssen dabei visuell erhalten
bleiben.

## Gestalterische Richtung

- Dunkle, hochwertige Matchday-Atmosphäre statt heller Dashboard-Optik
- Cyan bleibt funktionale Akzentfarbe
- Vereinsfarben stammen aus der Scene-Palette und dürfen die UI nicht
  überstrahlen
- Spielfeld und Stadion sind die Hauptdarsteller
- Overlays sparsam und gut lesbar
- Keine verschachtelten Karten um das Stadion
- Keine grellen Hintergründe, übermäßigen Verläufe oder generischen
  Glassmorphism-Look
- Steuerung muss mit Maus, Touch und Tastatur verständlich sein
- Kontrast, Fokuszustände und reduzierte Bewegung berücksichtigen

## Spielbericht-Kontext

`match-report-context/match_report.html` enthält die bestehende Einbettung in
der Übersicht des Spielberichts. Relevant ist der Abschnitt
`data-stadium-live-mode`; das übrige Template zeigt den verfügbaren Platz und
die angrenzenden Match-Komponenten.

Die Stadionansicht:

- verwendet immer das Heimstadion der Begegnung,
- liegt oberhalb des Overview-Grids,
- hat desktopabhängig eine Höhe von 260–460 px,
- wird auf Tablet auf 320 px und mobil auf 250 px reduziert.

Claude darf eine bessere Anordnung vorschlagen, muss jedoch eine kompakte
Einbettungsvariante und eine eigenständige Vollansicht liefern.

## Template-Platzhalter

Die gelieferten HTML-Dateien sind Django-Templates. Für einen eigenständigen
Prototyp dürfen folgende Werte durch statische Beispieldaten ersetzt werden:

- `{{ club.name }}` → `Borussia Dortmund`
- `{{ stadium.name }}` → `Signal Iduna Park`
- `{{ scene_url }}` oder `{% url 'stadium_live_scene' ... %}` →
  lokaler Pfad zu `data/stadion-live-scene.json`
- `{% static '...' %}` → relativer Dateipfad im Prototyp

Andere Matchdaten dürfen als eindeutig erkennbare Beispieldaten dargestellt
werden. Die Stadiongeometrie selbst darf niemals gemockt werden.

## Abnahmekriterien

- Die lokale Beispielscene lädt ohne Datenumbau.
- Alle 52 Block-IDs sind im Renderprozess vorhanden.
- Alle 28 expliziten Dachsegmente werden verarbeitet.
- Die Südtribüne bleibt als `homeStand: "SUED"` erkennbar.
- Block 10 bleibt ein normaler Sitzblock mit 16 × 52 Rasterzellen.
- Choreografiefarben stimmen mit den Palettenindizes der RLE überein.
- Orbit, Zoom und Reset funktionieren.
- Desktop-, Tablet- und Mobilansicht sind ohne horizontalen Overflow nutzbar.
- Fehlerhafte oder nicht ladbare JSON zeigt einen sichtbaren Fehlerzustand.
- Das Ergebnis enthält keine neue, parallel gepflegte Stadiongeometrie.
