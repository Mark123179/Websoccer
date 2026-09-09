# Transformationsnotizen: Elversberg

## Quelle

`stadium_elversberg.js` enthält eine Konstante `STADIUMS` mit einem
Elversberg-Datensatz:

- 52 Blöcke
- 128 Punkte im Stadionumriss
- Spielfeldzentrum `fieldC`
- Drehwinkel `axisTheta`
- Blockquads, `z0`, `z1`, `rows`, `seats`, `stand`, `tier` und `type`
- Umfelddaten für Gebäude, Straßen, Grün und Wasser

## Koordinatentransformation

Alle Punkte wurden mit `fieldC` auf die Spielfeldmitte verschoben und um
`-axisTheta` in das kanonische Pitch-Koordinatensystem gedreht.

Die Quellquads verwenden:

```text
[außen-links, außen-rechts, innen-rechts, innen-links]
```

Die Live Scene verwendet:

```text
[vorne-links, vorne-rechts, hinten-rechts, hinten-links]
```

Die vier Punkte jedes Blocks wurden nur neu angeordnet. Punktkoordinaten,
Blockformen und Höhen wurden nicht verändert.

## Eckblöcke

Bei den Blöcken 8, 9, 12, 13, 18, 19, 22 und 23 kann eine reine Sortierung
nach Abstand zur Spielfeldmitte die beiden Vorderkantenpunkte nicht zuverlässig
erkennen. Diese Blöcke überspannen jeweils eine breite Ecke.

Für sie wurde daher wie für alle anderen Blöcke die explizite
Quellkonvention verwendet, statt eine radiale Form zu schätzen.

## Kapazität

Die Summe aller gelieferten Raster beträgt:

```text
14.643 = sum(rows × seats)
```

Diese Summe wurde unverändert übernommen. Sie repräsentiert den gelieferten
Ausbau-/Demonstrationsstand und ersetzt nicht automatisch den aktuellen
10.000er-Datenbankstand.

## Design

Die Quelldatei enthält keine RLE-Farbgestaltung. Für die Demonstration wurde
ein zurückhaltendes blau-weißes Design erzeugt:

- Weiß `#f4f7fb`
- Vereinsblau `#1359a6`
- dunkles VIP-Blau `#071a33`
- helles Akzentblau `#79b8f3`

Diese Ebene ist bewusst editierbar. Geometrie, Rastermaße und Höhen bleiben
dagegen autoritativ.

## Dach

Die Quelle nennt ein Ringdach, liefert jedoch keine Dachsegmente. Die Runtime-
Scene verwendet deshalb den bestehenden Vertragsmodus `procedural-ring`.
Explizite Dachquads wurden nicht erfunden.