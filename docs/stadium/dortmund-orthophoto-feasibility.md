# Echte Umfeldflächen: Ostansicht Dortmund / Nordostseite Elversberg

## Prüfumfang und verbindliche Kamera

Isolierte Originaldaten-Messprobe, keine KI-Bilder, keine verschobenen
Landmarken, keine produktive Integration. Haupttribüne hinten, kameraseitige
Gegentribüne ausgeblendet; beide Dachzustände für beide Vereine.

Die bestätigte 75%-Feldkamera bleibt unverändert: 1880 × 940 Pixel,
105 × 68 Meter, Position `(0, 98, 110)`, 44° Neigung,
Brennweite `1337.4782524186542`, Hauptpunkt
`(940, 681.3221103379157)`.
Projektionsmatrix, Viewmatrix und vier Feldpunkte stimmen exakt mit
`generated-artifacts/stadium-middle-probe/verification.json` überein.
Die **416.792 Feldmaskenpixel** sind in jedem neuen Render und
Originalkarten-Compositing RGB-identisch mit dem jeweils zugehörigen
bestätigten Render, nicht bloß ähnlich positioniert.

## Originalquellen und Kartenadapter

### Dortmund

- Geobasis NRW, WMS NW DOP, `nw_dop_rgb`, EPSG:3857:
  https://www.wms.nrw.de/geobasis/wms_nw_dop
- Datensatz:
  https://open.nrw/dataset/56fb584b-10cf-4009-a405-0bef06bb3e00
- Lizenz: https://www.govdata.de/dl-de/zero-2-0
- Vorhandenes georeferenziertes Raster und BBOX:
  `generated-artifacts/dortmund-site-study/source.json`,
  `orthophoto_north_up.jpg`.
- Originaler örtlicher OSM-Auszug:
  `stadium_editor/blueprints/v2/dortmund.json`;
  © OpenStreetMap contributors, ODbL.
- Feld: Way 17235988; Stadionaußenkontur: Way 17235929;
  Gebäudering mit Innenöffnung: Relation 531985.

Die Kartenachse +u zeigt ungefähr nach Süden (−82,003°).
Der alte Adapter `scene X=u, scene Z=-v` gehörte zur Westansicht.
Die neue Modellhalbwendung erfordert **`scene X=-u, scene Z=v`**.
Rotation um den Feldmittelpunkt; Mittelpunkt, Maßstab und sämtliche
Quellkoordinaten bleiben erhalten. Der Kartenkamerapunkt liegt nun bei
**82,003° ab Nord**, also auf der Ostseite. Die geografische Abbildung wird
gedreht, nicht die Spielkamera. Eine unveränderte Wiederverwendung der alten
Vorlage würde die gegenüberliegende Umgebung fälschlich zuordnen.

Die durchgehende Südterrasse links und die gegliederte Nordseite rechts
stützen die physische Seitenzuordnung. Das ist keine geodätische
Unity-Vermessung. Das Luftbild-Aufnahmedatum bleibt unbekannt;
Dienstaktualisierung ist kein Bildflugdatum.

### Elversberg

- Originaler örtlicher OSM-Auszug:
  `stadium_editor/blueprints/v2/elversberg.json`,
  Datenstand `2026-09-15T09:46:05Z`, ODbL.
- Feld: Way 31339206; Stadiongelände: Way 1154632806.
- Bestandsmodell:
  `stadium_editor/blueprints/v2/elversberg_v2.json`.
- Feldrahmen aus Mittelpunkt und längster OSM-Feldkante, mit demselben
  Verfahren wie der vorhandene Blueprint-Generator.

Die zwei isolierten Modellhalbwendungen heben sich auf. Nach der üblichen
Spielkoordinatenabbildung gilt auch hier `scene X=-u, scene Z=v`.
Der Kamerapunkt liegt geografisch bei **41,129° ab Nord**, also nordöstlich.
Die Modellhaupttribüne Süd steht hinten, geografisch südwestlich.

Elversbergs Bildgrundlage ist eine **schematische Original-OSM-Bodenkarte**,
kein Orthofoto. Häuser und Wege behalten ihre Quellpositionen.
Die OSM-Stadionkontur ist eine Geländegrenze, kein vermessener Gebäudeumriss.
Die Nordtribüne fehlt im OSM-Auszug und ist im bestehenden Modell
parametrisch ergänzt; ihre Grundfläche wird separat als Modellquelle
eingestuft, nicht als kartografisch nachgewiesener Neubau.

## Messverfahren

Die inverse Kameraabbildung schneidet für jedes Pixelzentrum eine horizontale
Bodenebene. Das NRW-Raster beziehungsweise die lokale OSM-Karte wird
deterministisch bilinear abgetastet. Die halbe Modellwendung ist Bestandteil
des Kartenadapters. Die Rasterabdeckung einschließlich des zusätzlichen
Pixels für bilineare Abtastung wird geprüft.

Frische geometrische Verdeckungsmasken entstehen aus dem tatsächlichen
Render: aktuelle Mesh-/Dachsichtbarkeit, Instanzen, Materialseiten und
weltbezogene Schnittebenen bleiben wirksam. Alte Masken aus dem früheren
Kamerapaket werden **nicht** verwendet.
Der gemeinsame Export erhält außerdem die separat ergänzten Nacht- und
Leuchtendiagnosevarianten; die Umfeldmessung filtert ausschließlich die vier
Tagzustände. Leuchtenkegel der Nacht-Diagnose sind keine Stadionverdeckung.

Fünf disjunkte Klassen partitionieren das vollständige Bild:

- Grün: Boden außerhalb der OSM-Stadiongrenze, vom Modell nicht verdeckt.
- Orange: Boden der ausgeblendeten kameraseitigen Tribüne. Dortmund:
  OSM-Gebäudering bei `scene Z > 35`; Elversberg: kartierte Tribünen und
  separat eingeordnete parametrische Modell-Nordtribüne in dieser Schnittzone.
- Violett: anderer freier Boden innerhalb der Grenze, etwa Feldumlauf.
  Diesen Boden nicht pauschal als ausgeblendete Tribüne bezeichnen.
- Dunkel: tatsächlich vom sichtbaren Modell verdeckte Nicht-Feldfläche.
- Hell: geschützte Feldfläche.

Orange und Violett sind unbekannter Stadioninnenboden, **kein Außenumfeld**.
Keine fotografische Bodenrekonstruktion wird behauptet.

## Ergebnis der aktuellen Ost-/Nordostprobe

Alle Prozentwerte beziehen sich auf die **gesamte Bildfläche
(1.767.200 Pixel)**, nicht auf die Nicht-Feldfläche.

| Verein / Dach | Sichtbares Außenumfeld | Ausgeblendete Tribüne | Anderer Innenboden | Modellverdeckung |
|---|---:|---:|---:|---:|
| Dortmund an | 0,0042 % (74 px) | 5,1677 % | 6,1988 % | 65,0444 % |
| Dortmund aus | 0,8497 % (15.016 px) | 5,1677 % | 6,1988 % | 64,1989 % |
| Elversberg an | 40,2234 % (710.828 px) | 0,6165 % | 12,4548 % | 23,1204 % |
| Elversberg aus | 42,9131 % (758.360 px) | 0,6165 % | 13,6545 % | 19,2310 % |

Das Feld nimmt in allen Zuständen 23,5849 % ein.

**Dortmund:** Vor Modellverdeckung lägen 27,9476 % des Bildes außerhalb
des Grundrisses. Dach und Tribünen verdecken diese Flächen aber fast vollständig.
Mit Dach sind die 74 Restpixel nur ein diagnostischer Randrest, keine
belastbare Ortskulisse. Ohne Dach erscheinen schmale obere Randflächen.
99,9632 % beziehungsweise 93,0444 % der tatsächlich freien Nicht-Feldfläche
liegen weiterhin **innerhalb** des Stadiongrundrisses.
Als kartierte Gebäudeflächen treffen die dachlosen Randreste lediglich kleine
Teile von Gartenhäusern (unter anderem Ways 60309238, 60309141, 60309072).
Es gibt keinen Nachweis für eine gut erkennbare große Landmarke.

**Elversberg:** Vor Modellverdeckung liegen 46,1022 % außerhalb der
kartierten Grenze. Auch mit Dach bleiben größere obere und seitliche
Umfeldflächen frei. Kartierte Bodenflächen von Wasgau (30887518),
Lidl (53864241) und TVE-Halle (53864244) werden beispielsweise getroffen,
ohne deren Standorte zu verschieben. Das belegt nur sichtbare
**Grundflächen**, keine Sicht auf aufrechte Fassaden.
24,5265 % mit Dach beziehungsweise 24,9562 % ohne Dach der freien
Nicht-Feldfläche sind Stadioninnenboden und müssen davon getrennt bleiben.

## Grenzen und Folgerung

- Bodenflächenmessung, keine 3D-Sichtbarkeitsanalyse von Bäumen/Fassaden:
  Gebäudehöhen, Geländeparallaxe und gegenseitige Umfeldverdeckung fehlen.
- Elversbergs Geländegrenze ist nicht mit einem vermessenen Baugrundriss
  gleichzusetzen; die vorhandene Modelloutline stimmt mit ihr überein.
- Dortmunder Karten-/Unity-Ausrichtung ist physisch plausibilisiert,
  nicht geodätisch vermessen; sehr kleine Randflächen sind entsprechend
  nicht als verlässliche Landmarkensicht zu interpretieren.
- Weißmaskenschwelle >128 rundet antialiasierte Kanten. Wege werden in
  der OSM-Diagnose mit symbolischer Linienbreite gezeigt, nicht vermessen.
- OSM-Flächen können sich überlagern; ihre sichtbaren Pixel dürfen nicht
  zu einer vermeintlichen Gesamtsichtbarkeit aufsummiert werden.
- Orthofoto-Stadionschatten bleiben erhalten. Schraffur/Klassenfarben und
  harte Masken sind Diagnosehilfen, keine fertigen Hintergrundbilder.
- Alle Zahlen gelten nur für den geprüften Modellzustand, nicht für Ausbau.

Die gemeinsame Kamera wird **nicht** geändert. Dortmund kann unter dieser
festen Komposition keine große belegte Boden-Ortskulisse zeigen.
Elversberg bietet dagegen deutlich mehr kartierte Umfeldfläche.
Weitere Vorlagen müssten diesen Unterschied respektieren; mehr Dortmunder
Ortsbezug darf nicht durch versetzte Landmarken oder erfundene Kulissen
erzwungen werden. Neue Bilder und produktiver Einbau bleiben separat freizugeben.

## Reproduktion und Belege

Voraussetzungen: laufender vorhandener Django-Workflow für unveränderte
Studienmodule, vorhandene bestätigte 75%-Probe, lokales NRW-Raster samt
Georeferenzierung, vorhandenes Chromium/Playwright-Core, NumPy und Pillow.
Die benötigten ignorierten Raster/Kamerabelege werden nicht automatisch
aus Git wiederhergestellt; bei fehlenden Daten scheitert die Probe ausdrücklich.

```sh
node scripts/export_stadium_frame_probe.mjs --middle --main-stand-back
node scripts/export_dortmund_geo_probe.mjs
python scripts/build_dortmund_geo_probe.py
python scripts/test_geo_probe_geometry.py
```

Ausgabe ausschließlich unter
`generated-artifacts/stadium-main-stand-back-probe/`:

- `verification.json`, `camera_exact.json`, `geo_verification.json`.
- Frische vier Modellrender und jeweilige `*_silhouette.png`.
- `visibility_comparison.jpg`: vier farblich getrennte Sichtbarkeitskarten.
- `registered_map_comparison.jpg`: vier Originalkarten-/Modellvergleiche.
- `*_registered_map.png`: Vergleich in voller Auflösung.
- `*_geographic_audit.jpg`: Nord-oben-Karte mit Grenze, Feld, Bodenausschnitt
  und geografischem Kamerapunkt.
- `*_source.json`: Quellen, Frames, BBOX, SHA-256 der Originaldaten.
- Fünf getrennte Klassenmasken pro Zustand; sichtbare OSM-Objekte mit IDs,
  Quelltags und Pixelzahlen im numerischen Bericht.

Fünf unabhängige Geometrieprüfungen testen Halbwendung, Karten-Roundtrip,
Pixelzentrum-/Boden-Roundtrip, Feldpunkte und Elversbergs Nordostseite.
Zusätzlich prüfen die Exporte exakte Kamera-/Feldpixelparität, Dach-aus
und vollständige Klassenpartition.

## Historische Westprobe (nicht mehr aktuelle Registrierung)

Die frühere Nahansicht nutzte die 100%-Kamera und Westseite:
2,11 % Boden außerhalb des Grundrisses vor Verdeckung, praktisch nichts
danach, 77,12 % Modellbelegung der **Nicht-Feldfläche**.
Diese Werte und Masken sind nicht mit den aktuellen Prozentwerten
gleichzusetzen; die alte Studie unter `dortmund-site-study/` bleibt nur
Quellenarchiv und historischer Vergleich, keine aktuelle Kameravorlage.
