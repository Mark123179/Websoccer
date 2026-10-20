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

Das obere RoofSurface-Niveau wird als **horizontale Teilkörperhülle** gezeigt.
Geneigte Dachflächen, Trauflinien und Fassadentopologie werden nicht
rekonstruiert. Dies ist keine maximale oder mittlere Höhe für das gesamte
OSM-Gebäude.

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
