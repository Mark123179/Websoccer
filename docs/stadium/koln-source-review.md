# Köln – RheinEnergieSTADION

## Umfang und unveränderte Spieldaten

Aufbereitung der vier vom Nutzer gelieferten Dateien:

- `koln_1792488328918.bundle`
- `koln_1792488328917.json`
- `koln_lightmaps_1792488328917.json`
- `koln_lightprobes_1792488328916.json`

Identität: FMI 916, Transfermarkt 3. Lokale Vereins-/Stadion-IDs beim Einbau
auslesen, niemals aus externen Paketen übernehmen.
Die wirtschaftliche Kapazität von 50.000 wird nicht aus den 46.424
Quell-Sitzpunkten abgeleitet. Stadionwerte, Manager-Ausbau und gespeicherte
Entwürfe werden beim Einbau auf vollständige Gleichheit geprüft.
Dies ist ein Workspace-Einbau, kein Produktions-Deployment.

## Quelle, Dach und Licht

- 743 MeshFilter inventarisiert; ausgewählt sind 304 Meshes aus MAIN,
  AUDIAREA, PITCH2021 und der für Köln ausdrücklich geprüften EXTRA-Gruppe.
- Originalpositionen, Dreiecksindizes und UVs bleiben erhalten.
  Linienmittelachsen: 105 × 68 m. Der OSM-Pitch enthält zusätzlich Auslauf.
- 102 Quelltexturen werden als Browser-WebP bis 1024 px exportiert.
  Browsermaterialien sind keine Rekonstruktion der Unity-Shader.
- 51 konkret benannte `front3_0` bis `front3_51`, ohne `front3_20`,
  bilden die schaltbare Dachgruppe. `front3_20` ist eine bis zum Boden
  reichende Zaunstruktur, `front3_52` ein Ranggeländer. Die `front3_df_*`
  Glas-/Geländerteile bleiben ebenfalls unabhängig vom Dach sichtbar.
  Die dauerhaft stehenden vier Pylone werden nicht pauschal abgeschaltet.
- 64 aktivierte, feldgerichtete Unity-Spotlights sind räumlich gegen das
  Leuchtenmaterial `light_fixture_a_color` geprüft. Zwölf tatsächliche
  Quellpositionen decken sie im Browser ab, ohne erfundene Leuchtenorte.
- Alle acht Sitzgruppen passen bei +90° Y-Drehung zu den Crowd-Meshes.
  Größter mittlerer Bounds-Fehler einer Gruppe: unter 0,38 m.
- Lightmap-Zuordnungen und Probes bleiben gehashte Quellbelege;
  das gebackene Unity-Licht wird nicht als nachgebildet ausgegeben.

## Ortsbezug und frisches Umfeld

Quelle: OSM-API `https://api.openstreetmap.org/api/0.6/map`,
Bounding Box `6.86,50.925,6.89,50.942`. Der unveränderte Roh-Snapshot,
Abrufmetadaten und objektbezogene Herkunft bleiben im Studienverzeichnis.

- Pitch: Way 123127315; Stadion: Way 145246719.
- Die namenlose Gebäude-Relation 271681 ist ausdrücklich als
  `building=stadium` und durch ihre Lage über dem Pitch identifiziert.
  Sie wird nicht zusätzlich zum Unity-Stadion als generisches OSM-Gebäude
  gezeichnet. Ihre Mitglieder werden nicht als einzelne Duplikate eingebaut.
- Die beiden Abelbauten kommen aus OSM, nicht doppelt aus dem Unity-Hintergrund.
  Die exakten Quellmeshes `center2_28`/`center2_29` werden dafür ausgelassen.
  Generische Quellberge, Quellrasen außerhalb des Stadions und Hintergrundbäume
  (`center2_37`, `center2_26`, `center2_38`) weichen dem geografischen Umfeld.
  Das ist keine Löschung kartierter OSM-Objekte.
- Der nordgerichtete Pitchvektor definiert den Ortsplan. Modell +z ist Nord,
  -z Süd, +x Ost und -x West. Die Quellen-Gästecke liegt bei +z/+x.
  Gegenbeleg: offizieller FC-Plan mit Gästecke Nord/Ost und Heimkurve Süd:
  <https://fc.de/club/ueber-den-fc/spiel-und-trainingsstaette/rheinenergiestadion>
- Auswahlgrenze ±800 m in Ost-/Nordrichtung; Multipolygon-Löcher bleiben
  durch flächentreue Triangulation erhalten. Straßenbreiten berücksichtigen
  den 2,5-fachen Breitenfaktor des gemeinsamen Renderers.
- Die Geländeöffnung schützt den Quell-Innenraum unter +2,1 m, aus den
  tatsächlichen Crowd-/Pitch-/Field-Dreiecken abgeleitet. Unterirdische
  Fundamente bestimmen nicht die Öffnungsgröße.
- Keine OSM-Fläche gegen Stadion oder Geländeöffnung abgeschnitten.
  Gemeinsame Vorprüfung verlangt `terrainDeclared=true`, `ok=true`
  und keine Befunde.

Grenzen: flaches Gelände, kein vermessenes DEM; Gebäudehöhen und
Baumkronen teilweise schematisch. Drei im API-Ausschnitt unvollständige
Multipolygon-Relationen bleiben ausdrücklich dokumentierte Datenlücken.
Render-Polygone und Straßenabschnitte sind nicht gleich der Anzahl
unterschiedlicher OSM-Objekte.

## Editor-Basis

**Aktueller Abgleich:** [Offizieller FC-Blockplan 2026/27 und sichere Übernahme](koln-official-blocks.md).
Die nachfolgend beschriebenen 33 Hüllen sind die ursprüngliche, gesicherte
Ausgangstopologie, nicht mehr die angebotenen Blockbezeichnungen.

Für Köln gibt es im vorhandenen Alt-Blaupausenpaket keine Referenz und
beim ersten Einbau keine gespeicherte Editor-Geometrie bzw. keinen Entwurf.
Deshalb wird keine fremde Vereinsblaupause als Ersatz verwendet.

Die acht echten Sitzquellgruppen werden nach Rang und drei tangentialen
Streifen in 33 Editor-Hüllen übersetzt. Alle 46.424 Quell-Sitzpunkte sind
zugeordnet. Die physischen Rasterabstände folgen den Quellangaben
0,8 × 0,5 m, nicht der wirtschaftlichen Kapazität.
Diese Hüllen sind ausdrücklich **keine offiziellen nummerierten Stadionblöcke**
und keine Behauptung einer 1:1-Rekonstruktion jeder Sitzreihe.
Die 3D-Ansicht zeigt unabhängig davon die unveränderten Quell-Crowd-Meshes.
Die bestehenden wirtschaftlichen Sitzart-Buckets werden mit dem vorhandenen
Adapter auf die Hüllen verteilt, ohne die Stadionwerte zu ändern.

Der aktuelle Builder erzeugt daraus 56 mit dem FC-Plan beschriftete
Plansektoren. Die Nord-Gästetrennung folgt den räumlich getrennten
UltraAway-Quellgruppen; die übrigen inneren Trennungen sind schematische
Planprojektionen, keine aus dem Unity-Modell belegten Ganggrenzen.

## Reproduktion und Nachweise

Große Quellen/Exporte bleiben außerhalb von Git. Dauerhafte Browserassets
werden vom vorhandenen Registrierungsprogramm gespeichert und rückgelesen;
das registrierte Manifest wird eingecheckt.

1. `python -m scripts.inspect_koln_source`
2. `python -m scripts.prepare_koln_study --calibration-only`
3. `python scripts/export_stadium_model.py --bundle attached_assets/koln_1792488328918.bundle --seats attached_assets/koln_1792488328917.json --fmi 916 --name RheinEnergieSTADION --out generated-artifacts/koln-study/source-export --calibration generated-artifacts/koln-study/calibration.json --include-root EXTRA --lamp-material light_fixture_a_color --evidence attached_assets/koln_1792488328917.json --evidence attached_assets/koln_lightmaps_1792488328917.json --evidence attached_assets/koln_lightprobes_1792488328916.json`
4. Den ausdrücklich dokumentierten OSM-Snapshot mit JSON-Accept abrufen und
   unter `generated-artifacts/koln-study/osm-fresh/raw.json` samt `fetch.json`
   speichern. Kein stiller Netzabruf im produktiven Renderer.
5. `python -m scripts.build_koln_review`
6. `node scripts/capture_koln_study.mjs`
7. Alle Bilder visuell prüfen, dann `python -m scripts.install_koln_review`.
8. Anwendungsworkflow neu starten, anschließend
   `node scripts/capture_koln_study.mjs --installed ticker-tag ticker-nacht-flutlicht`.
9. `python -m scripts.package_koln_review`.

Nachweise liegen unter `generated-artifacts/koln-study/osm-fresh/`:
Vorprüfung, Objektprovenienz, sieben Quellrenderings, Installationsbackup,
Einbaubeleg und anschließend echte Renderings über die registrierten
Anwendungs-Asset-Endpunkte.
