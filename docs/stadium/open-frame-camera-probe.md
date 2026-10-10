# Offener Stadionrahmen: gemeinsame Kameraprobe

## Freigegebener Prüfumfang

Die Feldnähe grundsätzlich beibehalten, aber zurückzoomen, damit Dortmund
als große Referenz vollständig im Bild liegt. Beide Dachzustände prüfen.
Der offene Rahmen bleibt erhalten: Die kameraseitige Tribüne wird nicht
wieder eingeblendet. Keine Integration in Spielansicht oder Admin-Test.

## Verfahren

`scripts/export_stadium_frame_probe.mjs` nutzt unveränderte Studienmodule
und echte Originalgeometrie. Indexierte Dreiecke werden mit ihren tatsächlichen
Material-Schnittebenen geschnitten; auch neue Schnittpunkte werden gemessen.
Der Dach-an-Zustand von Dortmund bestimmt genau eine gemeinsame Kamera.

Eine reine Vergrößerung des Bildwinkels erwies sich als ungünstig. Die
gelieferte Probe behält deshalb Brennweite und 44°-Neigung bei und bewegt
die Kamera entlang der bisherigen Position vom Feldzentrum zurück.
Eine binäre Suche ermittelt den kleinsten Rückzugsfaktor, bei dem sämtliche
gemessenen Rahmenpunkte mindestens 32 Pixel vom Bildrand entfernt liegen.
Der Rahmen wird vertikal zentriert; die horizontale Feldmitte bleibt unverändert.

Elversberg und beide Dachzustände erhalten diese Kamera unverändert.
Elversberg wird nur gegen die gemeinsame Kamera geprüft, nicht separat eingepasst.

## Ergebnis und Grenzen

Format: 1880 × 940; Spielkoordinaten: 105 × 68 Meter.
Kameraposition der Probe: etwa (0, 190,35, 213,66), verglichen mit (0, 98, 110).
Der notwendige Rückzugsfaktor beträgt etwa 1,94.

Der vollständige große Rahmen verlangt damit mehr als einen kleinen Rückzug:
Die nahe Feldkante hat etwa 47 % ihrer bisherigen Bildbreite, die Feldhöhe
etwa 50 %. Dies ist noch keine abgenommene neue Spielkamera. Die Anforderung
„gesamter sichtbarer Rahmen“ steht in dieser Komposition im Konflikt mit
einem nahezu unverändert großen 2D-Feld.

Die Prüfung bestätigt exakt identische Projektionsmatrizen, Posen und vier
Feldeckpunkte für alle vier Zustände. Die Dach-aus-Zustände enthalten keine
sichtbaren registrierten Dachmeshes. Alle vier Rahmen liegen innerhalb des
gemeinsamen Bildes. Das lässt sich nicht pauschal auf jedes künftige Stadion
oder jeden Ausbau übertragen.

Die Bilder verwenden den neutralen Studienhintergrund. Sie sind
Kamera-/Modellproben, keine fertigen geografischen Hintergrundbilder.

Ausgabe und Prüfprotokoll liegen unter dem ignorierten Verzeichnis
`generated-artifacts/stadium-frame-probe/`.

## Näherer Mittelweg (als gemeinsame Kamerabasis bestätigt)

Nach der Gesamtansicht hat der Nutzer das größere Feld priorisiert und einen
Mittelweg angefragt. `node scripts/export_stadium_frame_probe.mjs --middle`
erstellt dafür vier neue Ansichten unter
`generated-artifacts/stadium-middle-probe/`, ohne die Gesamtprobe zu überschreiben.

Dieser Versuch behält die ursprüngliche Kameraposition und Neigung bei,
reduziert die Brennweite auf 75 % und hält die nahe Feldkante auf ihrer
bisherigen Bildhöhe. Damit haben Feldbreite und Feldhöhe exakt 75 % der
ursprünglichen Nahansicht. Äußere Dortmunder Stadionränder und obere Teile
der Dachaufbauten sind bewusst angeschnitten; eine vollständige
Stadion-Einpassung wird hier nicht behauptet.

Der Nutzer hat diese Ansicht mit „Diesen Mittelweg beibehalten“ und
„Beibehalten“ als gemeinsame Kamerabasis ausgewählt. Fertige Umfelder und
eine Integration in die Anwendung sind damit nicht abgenommen.

Alle vier Feldeckpunkte müssen weiterhin vollständig im Bild liegen.
Die identische Projektion und Pose aller Vereine/Dachzustände sowie der
vollständige Dach-aus-Schalter werden unverändert geprüft. Spielkoordinaten,
Anwendungsansicht, Kamera-Presets und Vereinsdaten bleiben unverändert.

## Haupttribüne hinten (ausgewähltes Darstellungsprinzip)

Der Nutzer hat „Haupttribüne hinten sichtbar“ gewählt. Die neue isolierte
Probe entsteht mit:

`node scripts/export_stadium_frame_probe.mjs --middle --main-stand-back`

Ausgabe: `generated-artifacts/stadium-main-stand-back-probe/`.
Die bisherigen Kameraproben werden nicht überschrieben.

Nur die Stadionmodelle werden um 180° gedreht. Dortmund zeigt damit West
hinten, Süd links und Nord rechts; die vordere Ostseite bleibt ausgeschnitten.
Elversberg zeigt die Modellseite Süd hinten, Ost links und West rechts;
die vordere Modellseite Nord wird ausgeblendet. Geografisch liegt die
Elversberger Kameraseite ungefähr nordöstlich, die Haupttribüne südwestlich.

Elversbergs Anpassung erfolgt an einer isolierten Kopie der Eingabedaten,
einschließlich des Filters für die kameraseitige Tribüne. Es werden keine
Dachsegmente hinzugefügt. Die zuvor diskutierte Dachhälfte gehört jetzt
zur ausgeblendeten Vorderseite; ihr Datenstand bleibt unverändert.

Projektionsmatrix, Kamerapose und vier Feldeckpunkte werden in allen vier
Zuständen exakt gegen das Prüfprotokoll der bestätigten 75%-Probe verglichen.
Beide Dach-aus-Zustände müssen ohne sichtbare registrierte Dachmeshes sein.
Dies ist keine produktive Integration oder Vermessung der Stadionmodelle.

Die Dortmunder Umfeldregistrierung aus der bisherigen Westansicht ist für
die neue Ostansicht nicht unverändert verwendbar. Der Kartenadapter muss
die Modellhalbwendung mit berücksichtigen, bevor neue Umfeldvorlagen
als passend ausgegeben werden.


## Originaldaten-Sichtbarkeitsprüfung der neuen Blickrichtung

Die aktuelle vierteilige Probe wurde mit
`--middle --main-stand-back` neu gerendert. Ihre frischen geometrischen
Verdeckungsmasken berücksichtigen Dachzustand, echte Materialschnitte und
Mesh-Instanzen. `export_dortmund_geo_probe.mjs` übernimmt jetzt ausschließlich
die exakt geprüften Matrizen dieser Probe; es setzt nicht mehr die alte
Nahkamera ein.

Der Kartenadapter berücksichtigt die Halbwendung um den Feldmittelpunkt:
`scene X=-u, scene Z=v`. Originalkartenpositionen bleiben unverändert.
Dortmunds geografischer Kamerapunkt liegt östlich (82,003° ab Nord),
Elversbergs nordöstlich (41,129°).

Sichtbarer Boden **außerhalb** der OSM-Stadiongrenze, jeweils Prozent
des gesamten Bildes:

| Verein | Dach an | Dach aus |
|---|---:|---:|
| Dortmund | 0,0042 % (nur 74 Randpixel) | 0,8497 % |
| Elversberg | 40,2234 % | 42,9131 % |

Freier Boden innerhalb der Grenze wird gesondert in ausgeblendete
Tribünenfläche und übrigen Innenboden getrennt. Insbesondere Dortmunds
offener Vordergrund ist damit kein frei verfügbarer Stadtvorplatz.
Elversbergs Geländegrenze und parametrische Modell-Nordtribüne sind keine
vermessen belegten Gebäudegrundrisse.

Projektionsmatrix, Pose, vier Feldpunkte **und alle geschützten Feldpixel**
stimmen in allen vier Zuständen exakt mit der bestätigten 75%-Probe überein.
Die Kamera bleibt unverändert; kein neues Umfeldbild und keine Integration
wurden erstellt. Geprüft ist Bodenprojektion, nicht die Sichtbarkeit
aufrechter Fassaden oder Baumkronen.

Quellen, Messmethode, differenzierte Zahlen und Reproduktionsbefehle:
[`dortmund-orthophoto-feasibility.md`](dortmund-orthophoto-feasibility.md).
Alle Bilder und Prüfprotokolle bleiben unter
`generated-artifacts/stadium-main-stand-back-probe/`.
## Nachtprobe nach der Halbwendung

Derselbe Befehl `node scripts/export_stadium_frame_probe.mjs --middle --main-stand-back`
exportiert jetzt 14 echte 1880×940-WebGL-Render in dasselbe isolierte
Ausgabeverzeichnis. Pro Verein/Dachzustand entstehen Tag (`*_roof.png`,
`*_no_roof.png`), Nacht mit angefordertem Flutlicht (`*_night.png`) und
Nacht mit ausgeschaltetem Flutlicht (`*_night_off.png`). Dortmund erhält
zusätzlich zwei Kontrollansichten (`*_night_sources.png`).
Die bestätigte Mittelweg-Probe wird nicht überschrieben.

### Quellen und Transformationsprüfung

- Dortmund: `study_assets/dortmund_lights.json` enthält 64 geprüfte Unity-
  Spot-Leuchten mit Komponentenposition, Richtung, Lampenmesh-ID und Material.
  Die unveränderte Auswahl verwendet sechs reale Quellen (je drei auf den
  zwei belegten Modellseiten), keine Gruppenmittelpunkte. Die vorhandene
  Browserkalibrierung bleibt unverändert: Quellintensität × 8 ×
  `min(4, sqrt(repräsentierte Leuchten))`. Sie ist keine Messung realer Lux-Werte.
- Die Beleuchtung wird **vor** der Halbwendung erstellt. Anschließend erfolgt
  die Drehung des Modells und die erneute Zustandsanwendung. Für jede aktive
  Quellposition, jedes Ziel und jede Richtung muss `(x,y,z) → (-x,y,-z)` gelten.
  Damit wird ausdrücklich geprüft, dass keine alte Weltposition stehen bleibt.
- Zusätzlich prüft `inspectAlignment()` die tatsächlich geladenen indexierten
  Lampenvertices des deklarierten Meshes und Materials. Lokaler Abstand muss
  mit dem Quellexport übereinstimmen, Weltabstand nach Transformation unter
  einem Meter bleiben. Gemessen: maximal 0,236865 m lokal und 0,235514 m in
  der skalierten Welt. Ursprungs-/Zielfehler sind null. Fehlendes Mesh,
  fehlendes Material oder falsche Ausrichtung brechen den Export ab.
- Alle Nacht-, Dach- und Flutlichtwechsel behalten diese Ausrichtung.
  Die Kontrollansicht zeigt alle 64 deklarierten Montagepunkte in Cyan,
  die sechs ausgewählten Punkte in Gelb sowie deren Lichtkegel. Diese
  Kontrollmarkierungen gehören nicht zu den normalen Nachtbildern.
- Elversberg: Es gibt weiterhin **keine bestätigten Leuchtenpositionen und
  Richtungen**. Beide Nacht-Dachvarianten werden wirklich gerendert, bleiben
  mit dem schwachen vorhandenen Nachtambiente aber fast schwarz. Angefordertes
  Flutlicht erzeugt dort null Quellen, genauso wie Flutlicht-aus. Das Protokoll
  meldet die fehlenden Quellen ausdrücklich; kein generischer Mast, Dachlicht,
  unsichtbares Fülllicht oder Materialleuchten ersetzt den fehlenden Nachweis.

### Ergebnis und Aussagegrenzen

Alle 14 Zustände vergleichen Projektionsmatrix, Kamerapose und vier Feldecken
exakt mit `stadium-middle-probe/verification.json`. Bei Dach-an sind 33
registrierte Dortmunder bzw. 11 Elversberger Dachmeshes sichtbar, bei Dach-aus
jeweils null. Keine Dachflächen wurden ergänzt. Vereinsdaten, Originalmodelle
und produktive Kamera-Presets bleiben unverändert.

`verification.json` enthält Quellenbezüge, Geometrie-/Quellhashes, Vorher-/
Nachher-Positionen und Ziele, Material-/Mesh-Abstände, Schaltzustände sowie
Kameravergleiche. Der Export prüft auch Browserfehler. Die ergänzten Tests in
`study.test.mjs` erkennen stehen gebliebene Positionen/Ziele und falsche
Lampengeometrie-Zuordnungen.

Die Bilder wurden mit Chromium ANGLE/SwiftShader (Software-WebGL) gerendert.
Dies sind echte Render zur visuellen Beurteilung, **keine Nutzerabnahme und
kein FPS- oder Hardwareleistungsnachweis**. Die bisherige Studie verwendet
keine Schattenberechnung (`castShadow=false`); Dach-an belegt daher nicht
die photometrische Abschattung durch das Dach. Die Lichtausrichtung und
Dach-aus-Parität sind davon getrennte geometrische Prüfungen. Himmel und
Umfeld bleiben neutrale Studienkulissen, nicht fertige Ortsansichten.


## Gesonderte Originaldach-Schattenprobe

Die oben beschriebene Standard-Nachtprobe bleibt schattenfrei. Nur der
explizite Aufruf

```sh
node scripts/export_stadium_frame_probe.mjs --middle --main-stand-back --roof-shadows
python scripts/analyze_stadium_roof_shadows.py
```

aktiviert die separate Instrumentierung aus `study_shadows.js`. Ausgabe:
`generated-artifacts/stadium-roof-shadow-probe/`; frühere Proben werden nicht
überschrieben. Produktive Szenen, Kameras, Vereinsdaten, Originalgeometrie,
Leuchtenauswahl und Intensitätskalibrierung werden nicht geändert.


### Grenzen

Elversberg besitzt weiterhin keine bestätigten realen Leuchten: Im Protokoll
steht ausdrücklich, dass dafür kein Abschattungstest möglich ist. Die
separate Nachlieferungsaufgabe bleibt nötig; Dunkelheit ohne Quellen ist
kein Nachweis eines Dachschattens.

Dies ist eine visuelle Raster-Schattenprobe des vorhandenen Originalmodells,
keine photometrische Messung, Nutzerabnahme oder Freigabe zur Integration.
Indirektes Licht, Mehrfachreflexionen und reale Lux-Verteilungen werden
nicht berechnet. Schattenränder können durch Kartenauflösung, Filter und
Bias beeinflusst sein. Chromium ANGLE/SwiftShader ist Software-WebGL:
Die gewählte Schattenqualität, erfolgreiche Exporte und Renderdauer
sind **kein FPS-/Hardwareleistungsnachweis**.

### Sichtbares Ergebnis

Der Vergleich mit unverändert sichtbarem Dach zeigt zusätzliche Abschattung
auf der hinteren Tribüne, insbesondere an Sitzflächen und den gelben
vertikalen Sitzstreifen. Das Spielfeld bleibt in dieser Leuchtenausrichtung
weitgehend direkt beleuchtet; ein großflächiger Dachschatten auf dem Rasen
ist in dieser Probe **nicht** erkennbar. Dach-aus legt vorher verdeckte
Tribünenflächen frei; diesen Bildunterschied allein nicht als Lichtgewinn
interpretieren.

Im Vollbild beträgt die mittlere absolute Differenz zwischen Dachschatten
an/aus rund 2,43/2,57/2,22 je RGB-Kanal. Innerhalb des projizierten
Spielfeldpolygons liegt sie nur bei 0,032/0,079/0,044; die maximale
Kanaldifferenz dort beträgt 3 von 255. Diese Werte beziehen sich auf
8-bit-sRGB nach ACES, nicht auf Lux oder die reale Beleuchtungsleistung.
Das Bildpolygon ist außerdem keine separate Oberfläche-ID-Messung.
Die exakten Werte stehen in `pixel-comparison.json`.
`roof-shadow-controlled-comparison.png` zeigt zwei unveränderte Ausschnitte
der hinteren Tribüne, jeweils mit außerhalb des Renderbilds gesetzter
Beschriftung. Die fünf vollständigen Originalrender bleiben separat erhalten.


### Kontrollaufbau

Fünf echte 1880×940-Render, immer Dortmund mit denselben sechs realen
deklarierten Quellen nach der Halbwendung:

| Bildsuffix | Originaldach | Schatten |
| --- | --- | --- |
| `roof_night_unshadowed` | sichtbar | aus, bisherige Nachtbasis |
| `roof_night_shadowed` | sichtbar | an, inklusive Originaldach |
| `roof_night_roof_noncasting` | sichtbar | an, nur Dach wirft keinen Schatten |
| `no_roof_night_unshadowed` | alle 33 registrierten Meshes ausgeblendet | aus |
| `no_roof_night_shadowed` | alle 33 registrierten Meshes ausgeblendet | an |

Der sichtbare, nicht schattenwerfende Dachzustand ist der entscheidende
Kontrollvergleich: Das Entfernen des Dachs verändert auch die Verdeckung
gegenüber der Kamera. Dagegen verändert der Kontrollzustand ausschließlich
die Schattenwerfer-Eigenschaft der registrierten Originaldachbaugruppe
(Dachhaut, Tragwerk und registrierte Anbauten), nicht deren Sichtbarkeit.
Die übrigen Schatten bleiben aktiv. Es entstehen keine Ersatzdachflächen
oder zusätzlichen Lichtorte. Lichtquellen bleiben auch bei Dach-aus an
ihren nachgewiesenen Montagepunkten, unabhängig von der Mesh-Sichtbarkeit.

Einstellungen: PCFSoftShadowMap, sechs Karten mit jeweils 2048×2048,
Near 0,25 m, Far entsprechend der deklarierten Leuchtenreichweite,
Bias −0,00005, Normal-Bias 0,02 m. Meshes empfangen und werfen Schatten,
ursprünglich doppelseitige Materialien werfen sie doppelseitig.
`clipShadows=true` berücksichtigt die vorhandenen Schnittebenen im
Schattenpass: Die ausgeblendete vordere Tribüne wird nicht zum unsichtbaren
Schattenwerfer. Die normalen Studienmaterialien und der Schattenzustand
werden bei Freigabe der Probe wiederhergestellt.

Das Renderprotokoll prüft berechnete Schattenkarten, Licht-/Dachzustände,
Quellenausrichtung und exakte Parität von Kamera, Projektion und vier
Feldecken zur bestätigten 75%-Basis. Der Pixelvergleich bestätigt zusätzlich
den SHA-256 des tatsächlichen Originalgeometrie-Binaries gegen den
Leuchtennachweis.
