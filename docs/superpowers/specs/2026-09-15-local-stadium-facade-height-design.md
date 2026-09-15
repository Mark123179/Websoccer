# Lokale Fassadenhöhe bei Stadionausbauten

## Ziel

Ein Ausbau einzelner Tribünen darf die Außenfassade unveränderter Stadionseiten
nicht über deren Dach hinaus erhöhen. Die Fassade soll der lokalen Rang- und
Dachhöhe folgen, statt überall die höchste Blockhöhe des gesamten Stadions zu
verwenden.

## Gewählte Lösung

Der 3D-Renderer bestimmt die Fassadenoberkante getrennt für jeden Endpunkt einer
Fassadenkante:

1. Für jeden Fassadenpunkt werden die räumlich nächstliegenden äußeren
   Tribünenblöcke ermittelt.
2. Die lokale Zielhöhe ergibt sich aus deren Oberkante plus dem bestehenden
   Fassadenaufschlag.
3. Zwischen benachbarten Fassadenpunkten werden unterschiedliche Höhen direkt
   als geneigte oder abgestufte Oberkante verbunden.
4. An gemeinsam genutzten Eckübergängen werden die lokalen Höhen gewichtet
   gemittelt, damit keine dünnen hohen Wandkeile entstehen.

Damit wachsen bei einem Ausbau von NORD und SÜD nur die zugehörigen
Fassadenabschnitte einschließlich ihrer kurzen Eckübergänge. Die mittleren
WEST- und OST-Abschnitte behalten ihre vorherige Höhe.

## Rendering

- Jede Fassadenkante erhält `zTopA` und `zTopB` statt eines globalen `zTop`.
- Die Wandfläche wird als Quad mit zwei möglicherweise unterschiedlichen
  Oberkantenhöhen erzeugt.
- Die obere Abschlussblende folgt derselben geneigten Kante.
- Texturkoordinaten verwenden weiterhin den horizontalen Fassadenlauf; die
  vertikale Skalierung orientiert sich an der lokalen Maximalhöhe.
- Pylone, Bodenöffnung, Dachsegmente und Blockgeometrie werden durch diese
  Korrektur nicht verändert.

## Schutzregeln

- Ohne simulierte Erweiterung bleibt das bisherige Fassadenbild unverändert.
- Eine unveränderte Stadionseite darf nicht die Maximalhöhe einer entfernten
  ausgebauten Seite übernehmen.
- Die lokale Fassadenhöhe liegt knapp oberhalb des zugeordneten äußeren Blocks,
  aber nicht pauschal oberhalb des höchsten Blocks im Stadion.
- Bestehende Fassadensegmente und die transient verschobene Außenkontur bleiben
  die geometrische Grundlage.

## Tests

- NORD und SÜD ausbauen: WEST und OST bleiben unter ihren lokalen Dächern.
- Nur eine Tribüne ausbauen: ausschließlich diese Seite und kurze
  Eckübergänge werden höher.
- Gegenüberliegende Seiten mit stark unterschiedlichen Höhen erzeugen keine
  senkrechten Wandkeile.
- Stadion ohne Ausbau rendert dieselben Fassadenhöhen wie zuvor.
- Bestehende Ausbau-, Dach-, Undo-/Redo- und Cache-Ketten-Tests bleiben grün.

## Relevante Dateien

- `stadium_editor/static/stadium_editor/stage/stadium_stage.js`
- `stadium_editor/static/stadium_editor/stadium_stage_adapter.js`
- `stadium_editor/tests_js/test_stadium_stage_adapter.mjs`
- `stadium_editor/tests.py`