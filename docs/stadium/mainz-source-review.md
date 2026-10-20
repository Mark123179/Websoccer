# Mainz: erste Quellmodell-Prüfung

Diese Dokumentation hält die ursprüngliche isolierte Prüfung fest.
Der geprüfte Folge-Stand wird über `python -m scripts.install_mainz_review`
registriert und mit dem vorhandenen Editor-/Spielansichtsvertrag verbunden.
Der Installationsbeleg liegt unter
`generated-artifacts/mainz-study/osm-fresh/integration-check.json`.

## Einbau des geprüften Folge-Stands

Die Registrierung lädt Geometrie und Texturen mit SHA-256-Rückprüfung in
den dauerhaften Assetspeicher. Das Manifest aktiviert den bestehenden
gemeinsamen Unity-Renderer; vereinsbezogener Renderer-Code ist nicht nötig.
Der neue OSM-Auszug ersetzt ausschließlich die Umfeldschichten der
Editor-Geometrie. Fehlt diese wie beim ersten Mainzer Einbau, liefert die
vorhandene Mainz-Blaupause die Editor-Blöcke.
Wirtschaftliche Stadiondaten, Manager-Ausbau und gespeicherte Entwürfe
werden nicht verändert und beim Einbau auf Gleichheit geprüft.
Vorherzustand und Einbaubeleg bleiben im ignorierten Studienverzeichnis.
Dies ist ein Workspace-Einbau, kein Produktions-Deployment.

## Aktueller Folge-Stand: neues OSM-Umfeld

Der Nutzer hat den Neuaufbau mit frischen OSM-Daten gewählt. Die frühere
isolierte Modellprüfung unten bleibt als Herkunft des ersten Stands erhalten;
die aktuelle Umfeldvorschau liegt unter
`generated-artifacts/mainz-study/osm-fresh/`.

- OSM-API: `https://api.openstreetmap.org/api/0.6/map`,
  Bounding Box `8.210,49.9755,8.239,49.993`.
- Spielfeld: Way 91231799. Stadionumriss: Way 91231800.
  Originalstadion-Building: Relation 1338495 / Wikidata Q392494;
  wird nicht noch einmal als generischer Baukörper dargestellt.
- Ortsbezug: Spielfeldpolygon-Mitte, Länge zum Nordosten, Breite zum
  Nordwesten. Keine Skalierung der Originalgeometrie.
- OSM-Pitch enthält Auslauf und misst etwa 118 × 77 m, nicht die
  105 × 68 m der tatsächlich geprüften Originalmarkierungen.
- Die Aussparung schützt jetzt den unter Geländeniveau liegenden
  Sitz-/Spielfeldbereich. Ihre konservative Kontur wird aus den echten
  Crowd-/Pitch-/Field-Dreiecken am Quell-Umlaufniveau geschnitten.
  Die frühere Umlaufplatten-Grenze schloss auch unterirdische Fundamente
  und einen äußeren Rampenbereich ein; sie war keine geeignete
  Bodenaussparung für das gesamte Stadionumfeld.
- Keine OSM-Flächen am Stadion zugeschnitten, keine Straßen verschoben
  oder entfernt und keine Grün-/Wasserflächen durch den Renderer ausgelassen.
  Beschneidung nur an der ausdrücklich dokumentierten Auswahlgrenze
  von ±800 m in Ost-/Nordrichtung.
- 376 verschiedene Gebäudeobjekte, 787 Straßen-/Wegeobjekte,
  728 kartierte Einzelbäume, 267 Grünflächenobjekte und zwei Wasserobjekte.
  Multipart-Geometrien/Höhlen erzeugen mehr Renderer-Polygone als Objekte.
- OSM-Innenringe bleiben erhalten; die Aufteilung in einfache Polygone
  erfolgt durch beschränkte Triangulation mit Flächenerhaltungsprüfung.
- Gebäudehöhen aus vorhandenen OSM-Höhen oder Geschosszahlen, sonst
  schematisch; keine amtliche Vermessung, ebenes Gelände.
- Vier als unterirdisch/innenliegend kartierte Wege werden nicht als
  oberirdische Wege gezeichnet. Drei im API-Kartenausschnitt
  unvollständige Multipolygon-Grenzen bleiben dokumentierte Datenlücken.
- Die gemeinsame Geländeprüfung erkennt die Deklaration ausdrücklich und
  ist fehlerfrei; vier echte Browserrenderings prüfen zusätzlich
  Modell-, Umfeld- und Fehlerzustand.

Reproduktion des Folge-Stands:

1. Erst die Modellprüfung unten reproduzieren, falls ihre ignorierten
   Quellexporte nicht mehr verfügbar sind.
2. `python -m scripts.build_mainz_osm_review --fetch`.
   Ohne `--fetch` wird der schon gespeicherte OSM-Snapshot erneut verwendet.
3. `node scripts/capture_mainz_study.mjs --fresh 3d-editor-dach-an draufsicht ticker-tag-dach-an ticker-nacht-flutlicht`.
4. `python -m scripts.package_mainz_osm_review`.

Der eigenständige HTML-Prüfbericht dokumentiert den Zustand vor dem Einbau.
Seine Vorschaukennzeichnung ist historisch; der separate Einbaubeleg
dokumentiert die anschließende Registrierung. Kapazität und
Manager-Ausbaustand bleiben unverändert.
OSM-Attribution und Grenzen stehen im eigenständigen HTML-Prüfbericht.

## Quellen und unveränderte Grenzen

- Nutzerquellen: `attached_assets/mainz_1792480841090.bundle`,
  gleichnamige Sitz-JSON sowie `mainz_lightmaps_1792480841089.json` und
  `mainz_lightprobes_1792480841089.json`.
- Vereinsidentität: FMI 918 und TM 39; lokale IDs immer erneut auslesen.
- Wirtschaftskapazität aus dem aktuellen Bestand: 33.305, nicht die
  24.894 Sitzpunkte der Unity-Datei oder 33.320 der älteren Blaupause.
- Keine ORM-Schreiboperationen, kein Assetupload, keine Registrierung.
- Originalmesh-Positionen, Indizes und UVs bleiben unverändert.

## Reproduzierbare Ergebnisse

- Alle 750 Quell-MeshFilter inventarisiert; der Modellauszug umfasst
  MAIN, AUDIAREA, PITCH2021 und ausdrücklich EXTRA.
- EXTRA enthält echte Dachhaut und Fassadenflächen. Die zusätzliche
  Gruppe darf nicht pauschal bei jedem anderen Stadion exportiert werden.
- 34 Dachhaut-/Trägermeshes anhand ihrer konkreten Quellidentitäten mit
  `DACH_` bezeichnet; Quellnamen werden erhalten. Feststehende
  Fassadenteile werden nicht aufgrund einer Höhenschwelle ausgeblendet.
- Das vorhandene Spielfeld misst entlang der Linienmittelachsen
  105 × 68 m. Die weißen Linien verwenden ihre Originaldreiecke;
  Unity-Alpha-Feathering wird nicht nachgebildet.
- Der eigene Rasen-Shader liefert die Albedo über `_Base_Texture`.
  Dieser Slot wird ausdrücklich gelesen; eine weiße Ersatzfläche ist
  kein zulässiger stiller Fallback.
- Sitzpositionen passen bei +90° Y-Drehung zu allen sieben
  Crowd-Bereichen. Mittlerer Bounds-Fehler ca. 0,40 m, größter
  Bereichsfehler unter 0,90 m; die anderen Vierteldrehungen deutlich schlechter.
- 125 aktivierte, feldgerichtete Unity-Lichtkomponenten liegen nahe
  tatsächlicher Leuchtengeometrie. Zwölf Originalpositionen werden
  räumlich ausgewählt. Dies ist keine unabhängige Vermessung realer
  Lichtverteilung; Unity-Intensitäten sind zunächst unverändert.
- Lightmaps und Probes bleiben Quellbelege, kein nachgebautes Baked Lighting.

## Noch nicht gelöster Umfeldbefund

Das vorhandene OSM-/Blueprint-Bundle enthält für Mainz 30 Gebäude,
158 Straßen, 31 Grünflächen und eine Wasserfläche.
Die Original-Umlaufplatte liegt bei ungefähr +5,85 m. Ihre tatsächliche
innere Grenze wurde aus den Quelldreiecken abgeleitet, nicht erfunden.
Die gemeinsame Renderer-Prüfung meldet Überschneidungen unter anderem
bei `green[4]` und mehreren Straßen.

Diese Quellen bleiben unverändert erhalten. Die geprüfte Aussparung ist
keine Erlaubnis, Grünflächen oder Straßen zu löschen, auszublenden oder
still zuzuschneiden. Der isolierte Modelldurchgang lädt **das gesamte
geografische Umfeld nicht** und behält stattdessen den Original-Quellboden.
Damit wird kein bereinigtes oder fertiges Umfeld vorgetäuscht.

Die Prüf-API erwartet die eigentliche Runtime-Presentation mit
`surroundings`/`frame`, nicht den äußeren HTTP-Umschlag `{"presentation":…}`.
Bei jedem Prüfbericht `terrainDeclared` gegen die tatsächliche Deklaration
kontrollieren; `ok` für eine nicht erkannte leere Deklaration ist kein Beleg.

## Reproduktion

1. `scripts/export_stadium_model.py` mit expliziten Quellpfaden, FMI 918,
   `--include-root EXTRA`, `--lamp-material lights_d_color` und genau den
   drei zugehörigen JSON-Dateien per `--evidence` ausführen.
2. Ausgabe nach `generated-artifacts/mainz-study/source-export`;
   Ausgangskalibrierung und ungekürzte Inventare bleiben im Studienordner.
3. `python scripts/prepare_mainz_study.py`.
4. `node scripts/capture_mainz_study.mjs 3d-editor-dach-an 3d-editor-dach-aus ticker-tag-dach-an ticker-tag-dach-aus ticker-nacht-flutlicht`.
5. `python scripts/package_mainz_review.py`.

Die Bilder stammen aus dem aktuellen Projekt-Renderer mit echter
Software-WebGL-Ausgabe, nicht aus Montagen oder Unity-Vorschaubildern.
Der vollständige Quellgrundriss ist ausdrücklich keine installierte
2D-Editoransicht. Weltorientierung, Heim-/Gastseite, aktuelles Umfeld und
der Einbau müssen vor einer späteren Freigabe abgeschlossen werden.
