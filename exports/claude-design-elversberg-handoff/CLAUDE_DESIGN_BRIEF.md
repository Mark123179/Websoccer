# Claude Design Brief: Elversberg als kleines Stadion

## Auftrag

Erzeuge eine zweite, deutlich kleinere Stadion-Demonstration für den
Websoccer-Livemodus. Das Ergebnis soll zeigen, dass derselbe Renderer nicht nur
das Signal Iduna Park, sondern auch die kompakte und asymmetrische
URSAPHARM-Arena an der Kaiserlinde korrekt darstellen kann.

Die Elversberg-Scene ist die verbindliche Datenquelle. Der mitgelieferte
Dortmund-Stand dient ausschließlich als Vergleich für eine bereits
funktionierende Umsetzung.

## Ausbauzustand

Das Projekt führt das Stadion derzeit noch mit 10.000 Plätzen. Die gelieferte
Geometrie bildet einen laufenden Ausbauzustand auf rund 14.000 Plätze ab:

- 52 individuelle Blöcke
- exakt 14.643 Rasterplätze aus `rows × seats`
- 2.313 Stehplätze
- 11.430 Sitzplätze
- 900 VIP-Plätze

Für diesen Demonstrationsprototyp gilt **14.643** als verbindlicher
Geometriestand. Dadurch bleiben alle gelieferten Blöcke und Rastermaße
unverändert. Diese Übergabe verändert nicht die produktive Datenbank.

## Autoritätsreihenfolge

Bei Widersprüchen gilt:

1. `data/elversberg-live-scene-demo.json`
2. Dieses Briefing
3. `contracts/LIVE_SCENE_CONTRACT_CURRENT.txt`
4. `current-live-mode/`
5. `comparison-dortmund/`
6. `source-material/`

Die JavaScript-Quelldatei in `source-material/` ist die Herkunft der
Elversberg-Geometrie, aber nicht mehr der Runtime-Vertrag. Claude soll direkt
die konvertierte Live Scene laden.

## Nicht verhandelbarer Scene-Vertrag

- Schema: `websoccer.stadium-live-scene`
- Version: `1`
- Maßeinheit: Meter
- Ursprung: Spielfeldmitte
- `+X`: Tor-zu-Tor
- `+Y`: Seitenlinie-zu-Seitenlinie
- `+Z`: nach oben
- Spielfeld: 105 × 68 Meter
- Quad-Reihenfolge:
  `[vorne-links, vorne-rechts, hinten-rechts, hinten-links]`
- `rows` und `seats` teilen nur das gelieferte Quad in Rasterzellen.
- `rle` wird vordere Reihe zuerst und je Reihe von links nach rechts gelesen.
- `sum(rle[*][0])` ist immer `rows × seats`.
- RLE-Farbwerte sind Indizes der gelieferten `palette`.
- Alle 52 Blöcke müssen verarbeitet werden.

Claude darf Geometrie niemals aus `stand`, `tier`, `order`, `rows` oder
`seats` ableiten. Diese Felder beschreiben und unterteilen die gelieferten
Quads; sie bestimmen nicht deren räumliche Form.

## Elversberg-spezifische Besonderheiten

### Kompakte, asymmetrische Form

Die Arena ist kein verkleinertes Vier-Tribünen-Schema. Die individuellen
Blockquads bilden Ecken, unterschiedliche Tiefen und die konkrete Außenform
ab. Keine Seite darf durch ein generisches Rechteck ersetzt werden.

### Ober- und Unterrang

Die Scene enthält sowohl `OBER`- als auch `UNTER`-Blöcke mit eigenen Höhen.
Diese müssen räumlich getrennt bleiben. `z0` und `z1` sind verbindlich.

### Heimtribüne

`homeStand` ist `SUED`. Die aktuelle blau-weiße RLE ist ein zurückhaltendes
Demonstrationsdesign und darf gestalterisch verfeinert werden, solange
Blockraster, Palette und Scene-Vertrag erhalten bleiben.

### Dach

Das Quellmaterial liefert keine expliziten Dachsegmente, sondern nur die
Information eines Ringdachs. Deshalb enthält die Scene:

```json
{
  "mode": "procedural-ring"
}
```

Der aktuelle Renderer kann diesen Modus darstellen. Das Dach darf für den
Prototyp atmosphärisch verbessert werden, aber nicht als neue autoritative
Geometrie in die Scene zurückgeschrieben werden. Eine spätere Vermessung
expliziter Dachsegmente wäre ein separater Arbeitsschritt.

### Normalisierte Eckpunkte

Bei acht breiten Eckblöcken war die radiale Näherungsheuristik des aktuellen
Serializers nicht ausreichend. Für die Demo wurden ausschließlich die vier
bereits gelieferten Punkte anhand der dokumentierten Quellkonvention
`außen-links, außen-rechts, innen-rechts, innen-links` in die Runtime-Reihenfolge
überführt. Kein Punkt wurde verschoben, ergänzt oder geschätzt.

## Gewünschte Darstellung

- Gleiche technische Basis wie beim erfolgreichen Dortmund-Prototyp
- Deutlich kompaktere, intimere Stadionwirkung
- Dunkle Matchday-Atmosphäre
- Blau und Weiß als Vereinsfarben
- Spielfeld und Stadion bleiben Hauptdarsteller
- Kein künstliches Hochskalieren auf Dortmund-Dimensionen
- Keine generische Arena-Silhouette über die gelieferten Quads legen
- Eine Vollansicht und eine kompakte Spielbericht-Einbettung

## Interaktion

- Ziehen: Kamera horizontal um das Stadion bewegen
- Mausrad oder Touch-Geste: zoomen
- Doppelklick oder sichtbarer Reset-Button: Ausgangsansicht
- Funktionierende Maus-, Touch- und Tastaturbedienung
- Lade-, Fehler- und Leerezustand
- Responsive Zustände für 1440×900, Tablet und Smartphone

Kamera und Culling dürfen nur die aktuelle Darstellung reduzieren. Beim
Drehen müssen alle 52 Blöcke wieder sichtbar werden können.

## Technische Referenz

`current-live-mode/live_mode.js` enthält:

- Scene-Prüfung
- RLE-Dekodierung
- bilineare Projektion der Rasterzellen
- Kamera, Zoom und Culling
- explizite und prozedurale Dächer

Claude darf Rendering und Performance verbessern, aber keinen zweiten
Geometrievertrag erfinden.

## Dortmund-Vergleich

`comparison-dortmund/` enthält die bereits funktionierende BVB-Scene und einen
Screenshot. Der Vergleich soll insbesondere zeigen:

| Eigenschaft | Elversberg | Dortmund |
|---|---:|---:|
| Kapazitätsstand | 14.643 | 81.365 |
| Blöcke | 52 | 52 |
| Dach | prozeduraler Ring | 28 explizite Segmente |
| Charakter | kompakt/asymmetrisch | groß/geschlossen |

Die Dortmund-Geometrie darf niemals auf Elversberg übertragen werden.

## Abnahmekriterien

- Die Elversberg-JSON wird unverändert als Runtime-Scene geladen.
- Alle 52 eindeutigen Block-IDs werden verarbeitet.
- Die Summe aller Rasterzellen bleibt 14.643.
- Die RLE-Länge stimmt für jeden Block exakt mit `rows × seats` überein.
- Ober- und Unterränge bleiben anhand ihrer gelieferten Höhen unterscheidbar.
- `homeStand: "SUED"` bleibt erhalten.
- Das prozedurale Ringdach wird dargestellt.
- Orbit, Zoom und Reset funktionieren.
- Desktop, Tablet und Smartphone haben keinen horizontalen Overflow.
- Fehlerhaftes oder nicht ladbares JSON zeigt einen sichtbaren Fehlerzustand.
- Es entsteht keine neue parallel gepflegte Stadiongeometrie.
