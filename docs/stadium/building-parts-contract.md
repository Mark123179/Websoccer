# Explizite Gebäude-Teilkörper im gemeinsamen Unity-Umfeld

Der optionale Schlüssel `surroundings.buildingParts` ergänzt den gemeinsamen
OSM-/Unity-Renderer. Ohne diesen Schlüssel ändern sich weder Gebäudeformen
noch Höhenlogik oder bestehende Renderer-Fingerprints. Er ist **keine**
Lockerung der Einzelhöhenfreigabe und kein automatischer LoD2-Import.

## Datenschema, Version 1

- `version: 1`, `verticalDatum: "DHHN2016 / NHN (EPSG:7837)"`.
- `referenceNHN`: derselbe endliche Spielfeldbezug wie
  `heightEvidence.terrainReferenceNHN`; `source`: nicht leere Quellenangabe.
- `groundElevation` und `groundLevel` müssen ausdrücklich vorhanden sein.
- `groups`: eindeutige Zuordnungen zu `buildingIndex` und passender
  `buildingIds[index]` als `osm`. Dieser Gesamtgrundriss bleibt in
  `heightEvidence.buildings` **unmeasured_retained_envelope**.
- Je Gruppe `parts` mit eindeutiger `lodId`, `file`, `polygons`, `height`,
  `baseNHN`, `roofNHN`, `sourceAttributes` und
  `srsName: "urn:adv:crs:ETRS89_UTM32*DE_DHHN2016_NH"`.
  `height` ist in Metern, 1–100 m, und muss `roofNHN - baseNHN` entsprechen
  (maximal 0,01 m Rundungsabweichung). Dachquelle muss `1000` (Laserscan),
  Bodenquelle `1100` (DGM) sein. Unterschiedliche Quell-Bodenniveaus bleiben
  getrennt. Das Kölner Aufbereitungsskript akzeptiert nur ebene GroundSurfaces.
- `polygons` sind einfache Ringe **im bisherigen Editor-Koordinatenrahmen**,
  nicht UTM und nicht bereits nach Modell-X/Z gedreht.
  Innenringe werden beim Erstellen in flächentreue, eingeschränkte
  Dreiecke aufgeteilt; es gibt keine verdeckt gefüllten Löcher.
- `residualPolygons` enthalten den nicht eindeutig belegten Rest der
  OSM-Fläche, mit `residualStatus: "unmeasured_retained_envelope"`.
  Die vorherige `buildingHeights[index]` bleibt deren ausdrücklich
  unvermessene Hüllhöhe; sie wird nicht aus den Teilkörpern berechnet.

Zusätzliche Belegfelder der Kölner Daten sind amtlicher GroundSurface-Grundriss
in EPSG:25832 (`officialGroundUTM`), Quellattribute, Überdeckungen,
unteres/oberes Dachniveau, Rest-/Konfliktflächen und Darstellungsquantisierung.
Die Rohdateien sind über `height-evidence.json → sources` mit URL, Zeit und
SHA-256 gebunden.

## Flächen- und Höhenvertrag

Der Renderer und die Paketvorprüfung benutzen dieselbe Prüfung:
Grundrisse müssen einfach und triangulierbar sein; Teilkörper und Rest müssen
den unveränderten OSM-Grundriss flächentreu und ohne Überlappung partitionieren
(numerische Flächentoleranz 0,00001 m²). Außerhalb liegende Flächen, Lücken,
doppelte Quellen, widersprüchliche NHN-Bezüge und ungültige Werte brechen
die Darstellung/Prüfung ab. Keine stille Rückkehr zur Gesamthülle.
Auch Teilflächen werden gegen die Bowl-Aussparung und Rasterabdeckung geprüft.

Die absoluten Niveaus werden **nicht** auf den höchsten Rasterpunkt gesetzt:

```
lokaler Boden = baseNHN - referenceNHN
lokales oberes Dachniveau = roofNHN - referenceNHN
```

Da die Umfeldgruppe bereits um `groundLevel` verschoben wird, wird dieser
Wert innerhalb der Geometrie einmal abgezogen. Wandfüße liegen auf dem
amtlichen Teilkörperboden; die generalisierte DGM-Anzeige und der ebene
Modellvorplatz dürfen davon abweichen. Es wird keine neue Geländeanpassung
um Gebäude vorgenommen.

Ohne `roofSurfaces` wird das obere RoofSurface-Niveau weiterhin als
**horizontale Teilkörperhülle** gezeigt. Der nachfolgende optionale
Dachflächenvertrag ersetzt ausschließlich diese Hülle. Dies ist keine
maximale oder mittlere Höhe für das gesamte OSM-Gebäude.

## Optionale amtliche Dachflächen

Je Teilkörper kann `roofStatus: "official_surfaces"` mit `roofSurfaces`
vorliegen. Jede Dachfläche enthält:

- `lodId` und `file`, identisch mit dem zugeordneten Teilkörper.
- `surfaceId` und `polygonId`: originale GML-IDs. Fehlen diese in CityGML,
  werden ausdrücklich strukturelle Pfade
  `<lodId>/RoofSurface/<index>/Polygon/<index>` verwendet, keine erfundenen
  amtlichen IDs. Indizes beziehen sich auf das unveränderte Quellobjekt.
- `sourceRingsUTM`: unveränderte geschlossene XYZ-Ringe (Außenring, danach
  Innenringe) aus genau diesem RoofSurface-Polygon in EPSG:25832 / NHN.
- `polygons`: geschlossene XYZ-Ringe im bisherigen Editorrahmen; X/Y sind
  horizontal, Z ist **absolutes NHN**, nicht Modellhöhe. Diese Flächen sind
  an der bereits freigegebenen eindeutigen Teilkörperpartition abgeschnitten.

Die horizontalen Dachgrundrisse verwenden dieselbe offengelegte
0,00001-m-Quantisierung wie die GroundSurface-Grundrisse. Höhen werden dabei
nicht quantisiert: neue Schnittpunkte bekommen die Höhe auf der ursprünglichen
projizierten Dachebene. Benachbarte Rechenpunkte unter 0,000000001 m Abstand
werden zusammengeführt, niemals die Originalquellringe. Nach der Quantisierung
wird das GEOS-Präzisionsmodell zurückgesetzt, damit neue Schnittpunkte an der
unquantisierten OSM-Grenze nicht nochmals verschoben werden.

Nur einfache, endliche, nicht vertikale und innerhalb 0,01 m ebene Flächen
sind zulässig. Alle Ringe eines Quellpolygons müssen dieselbe Ebene teilen.
Quellhöhen müssen dem dokumentierten unteren/oberen RoofSurface-Niveau
entsprechen und über dem amtlichen Boden liegen. Die dargestellten
Dachflächen müssen den Teilkörper vollständig, ohne Überlappung und ohne
außerhalb liegende Fläche decken (0,00001 m² Flächentoleranz).
Diese Prüfungen gelten sowohl in der CPU-Paketvorprüfung als auch im Renderer.
Ein beschädigter deklarierter Dachvertrag führt zum Fehler, nicht zu einem
stillen Rückfall auf eine Hülle.

Bei der **Aufbereitung** wird ein nicht nachweisbares Dach dagegen ausdrücklich
ausgeschlossen: `roofStatus: "rejected_retained_envelope"`,
`roofRejection` und `rejectedRoofEvidence` dokumentieren Grund und Originalringe.
`roofSurfaces` darf dann nicht vorhanden sein. Die unabhängig belegte
Teilkörperhöhe und ihre bisherige horizontale Hülle bleiben erhalten.
Es wird keine Dachlücke gefüllt und kein Teil der OSM-Restfläche umverteilt.

Der Renderer zeichnet Dachrand-/Trauflinien in ihrer tatsächlichen Höhe.
Ränder an der OSM-/Konfliktaussparung sind **Schnittkanten**, keine behaupteten
amtlichen Traufen. Geschlossene Wände vom belegten Boden bis zum Dachrand
bleiben ausdrücklich schematisch: keine Fenster, Fassadendetails,
WallSurface-Topologie oder Innenwände unter Firstlinien. Die Umrechnung ist
auch hier `Dachpunkt-NHN - referenceNHN - groundLevel`; die Umfeldgruppe
addiert `groundLevel` genau einmal.

### Kölner Dachpaket und sichere Übernahme

[`koln-roof-evidence.json`](koln-roof-evidence.json) enthält die Dachgeometrie
für jede der elf Quell-IDs, die Rohquellenbindung und den Tag-/Nachtvergleich.
Neun Pakete sind vollständig verwendbar (fünf geneigt, vier eben). Bei
`UUID_bc2041a5-1f32-40b9-9889-ce55ebc8357f` und
`UUID_c89a41fa-2cb6-4b1e-8960-84adeb194d8f` fehlen gegenüber dem eindeutigen
Teilkörpergrundriss rund 0,010 bzw. 0,002 m² Dachdeckung. Beide behalten
bewusst ihre vorherige Hülle; auch solche kleinen **echten** Quelllücken
werden nicht als numerische Toleranz versteckt.

Das Paket bindet die vollständige vorherige Teilkörperdeklaration per SHA-256.
`scripts/install_koln_roofs.py` übernimmt ausschließlich Dachschlüssel,
idempotent und transaktional. Fehlt die bereits freigegebene Teilkörper-/
NHN-Basis oder hat sie sich geändert, bricht es ab; es installiert niemals
ersatzweise alte Gesamtumfelder. Die frühere Gesamthöhenfreigabe, OSM-Reste,
Gelände, Modelle, Stadiondaten und Managerentwürfe werden nicht verändert.

```sh
# Offline-Neuaufbereitung aus den bereits dokumentierten, lokalen Quellen:
python -m scripts.refine_koln_heights
# Gleiche Tag-/Nachtkameras, zuerst alte Hüllen, dann neue RoofSurfaces:
node scripts/capture_koln_study.mjs --roof-study --flat-roofs \
  abel-ost-tag abel-west-tag abel-ost-nacht abel-west-nacht \
  ticker-tag ticker-nacht-flutlicht
node scripts/capture_koln_study.mjs --roof-study \
  abel-ost-tag abel-west-tag abel-ost-nacht abel-west-nacht \
  ticker-tag ticker-nacht-flutlicht
python -m scripts.package_koln_roofs
# Bewusste Übernahme nur auf dem unveränderten, freigegebenen DB-Stand:
python -m scripts.install_koln_roofs --install
```

Der eigenständige Vergleichsbericht liegt unter
`generated-artifacts/koln-study/heights/koln-dachvergleich.html`.
Roh-GML und Bilder bleiben ignoriert; das kleine Geometrie-/Belegpaket
ist versioniert. Kein automatischer Produktionszugriff oder Download durch
die Laufzeit.

## Kölner Auswahl und Erhalt

Nur die explizit benannten Abelbauten werden durch
`scripts/koln_building_parts.py` aufbereitet. Jeder amtliche Teilgrundriss
muss mindestens 85 % innerhalb seines OSM-Gebäudes liegen und die
NHN-/Laserbelege erfüllen. Außerhalb liegende Quellanteile werden für die
Anzeige an der OSM-Grenze abgeschnitten und bleiben im Originalbeleg erhalten.
Überlappende Quellanteile werden **aus allen betroffenen Teilkörpern**
ausgenommen und als unvermessen erhalten; keine Priorität nach Höhe.

Die Teilung wird nach PROJ-Projektion berechnet. Nur die projizierten
amtlichen Grundrisse werden für numerisch stabile Boolesche Operationen
auf ein dokumentiertes 0,00001-m-Raster quantisiert. Der OSM-Grundriss
bleibt unverändert. Nicht darstellbare Rechenrestpolygone bis 0,00000001 m²
werden nicht zu Float32-Flächen; die vollständigen OSM-Quellpolygone bleiben
gespeichert und die Gesamtflächenprüfung bleibt verpflichtend.

Die bisherige eindeutige, symmetrische 85-%-Einzelhöhenprüfung in
`select_height` bleibt unabhängig und unverändert. `buildings`,
`buildingIds`, alle nicht zugehörigen `buildingHeights`, Straßen, Grün,
Wasser, Bäume, Gelände, Modellmanifest, Kapazität und Spieldaten werden
nicht durch den Teilkörpervertrag geändert.

`project_surroundings` erhält die Deklaration aus dem Live-Umfeld auch bei
Legacy-`bg`-Gebäuden. Die 2D-Karte zeigt weiterhin die ursprünglichen
OSM-Gesamtgrundrisse. Die 3D-Darstellung und deren Vorprüfung verwenden
die geprüfte Partition.
