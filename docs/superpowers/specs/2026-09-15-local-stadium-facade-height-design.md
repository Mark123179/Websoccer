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
2. Wenn an dieser Stelle ein Dach vorhanden ist, ergibt sich die lokale
   Zielhöhe aus der Unterkante des nächstliegenden Dachsegments. Nur ohne
   lokales Dach wird die Blockoberkante plus Fassadenaufschlag verwendet.
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
- Benachbarte Dachsegmente verwenden an gemeinsamen Übergängen dieselben
  gemittelten XY-Punkte und Höhen. Dadurch öffnen sich beim unterschiedlichen
  Wachstum angrenzender Sektoren keine breiten Dachspalten.
- Die Nahtangleichung betrifft nur tatsächlich benachbarte Segmentpunkte
  innerhalb einer kleinen geometrischen Toleranz; gegenüberliegende oder
  getrennte Dachflächen werden nicht miteinander verbunden.
- Texturkoordinaten verwenden weiterhin den horizontalen Fassadenlauf; die
  vertikale Skalierung orientiert sich an der lokalen Maximalhöhe.
- Pylone, Bodenöffnung, Dachsegmente und Blockgeometrie werden durch diese
  Korrektur nicht verändert.

## Schutzregeln

- Ohne simulierte Erweiterung bleibt das bisherige Fassadenbild unverändert.
- Eine unveränderte Stadionseite darf nicht die Maximalhöhe einer entfernten
  ausgebauten Seite übernehmen.
- Die lokale Fassadenhöhe endet an der lokalen Dachunterkante. Ohne Dach liegt
  sie knapp oberhalb des zugeordneten äußeren Blocks, aber nie pauschal oberhalb
  des höchsten Blocks im Stadion.
- Dachsegmente dürfen nach der transienten Verschiebung nicht sichtbar
  schweben; gemeinsame Segmentnähte bleiben geschlossen beziehungsweise werden
  gegenüber dem aktuellen Zustand verkleinert.
- Bestehende Fassadensegmente und die transient verschobene Außenkontur bleiben
  die geometrische Grundlage.

## Tests

- NORD und SÜD ausbauen: WEST und OST bleiben unter ihren lokalen Dächern.
- Nur eine Tribüne ausbauen: ausschließlich diese Seite und kurze
  Eckübergänge werden höher.
- Gegenüberliegende Seiten mit stark unterschiedlichen Höhen erzeugen keine
  senkrechten Wandkeile.
- Die Fassadenoberkante berührt an mehreren Punkten die jeweilige lokale
  Dachunterkante.
- Gemeinsam angrenzende Dachsegmente behalten nach NORD-/SÜD-Ausbau deckungsgleiche
  Nahtpunkte; der maximale Spalt wächst nicht gegenüber dem Ausgangszustand.
- Stadion ohne Ausbau rendert dieselben Fassadenhöhen wie zuvor.
- Bestehende Ausbau-, Dach-, Undo-/Redo- und Cache-Ketten-Tests bleiben grün.

## Relevante Dateien

- `stadium_editor/static/stadium_editor/stage/stadium_stage.js`
- `stadium_editor/static/stadium_editor/stadium_stage_adapter.js`
- `stadium_editor/tests_js/test_stadium_stage_adapter.mjs`
- `stadium_editor/tests.py`