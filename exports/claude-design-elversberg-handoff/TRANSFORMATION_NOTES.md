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

Der Server-Serializer behandelt entsprechend `quad[2]` und `quad[3]` immer als
spielfeldnahe Rasterkante und `quad[0]` und `quad[1]` als äußere Kante. Nur die
Links-/Rechtsrichtung dieser Kanten wird aus der Lage zum Spielfeld bestimmt.
Eine Radius-Sortierung darf die Kanten-Zugehörigkeit nicht überschreiben.

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

Als Referenzen für die Dachform sind festgelegt:

- die gelieferte orthogonale Draufsicht `elversberg_blaupause.png` für die
  Außenkontur und Segmentgrenzen,
- die datierten Baufortschritts- und Seitenaufnahmen auf
  `https://stadiumdb.com/constructions/ger/ursapharm_arena` für Dachneigung
  und Höhenwirkung,
- die offizielle Stadionseite
  `https://sv07elversberg.de/ursapharm-arena/daten-fakten` zur Kontrolle von
  Spielfeldmaß und stadionseitiger Dachbeleuchtung.

Die Runtime-Scene verwendet 26 explizite Dachquads. Ihre Grundflächen stammen
ausschließlich aus den gelieferten Außenkanten der 26 Oberrangblöcke und deren
pitch-seitigen Kanten; weder Blocknamen noch `rows`/`seats` bestimmen die Form.
Die Z-Werte sind an die gelieferten Blockhöhen `z0`/`z1` gebunden. Damit bleibt
die asymmetrische, pitch-zentrierte Kontur erhalten, ohne eine generische
Ringfläche im Renderer zu erzeugen.
