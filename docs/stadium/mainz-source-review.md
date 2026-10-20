# Mainz: erste Quellmodell-Prüfung

Dieser Stand ist eine **isolierte Prüfung**, keine Modellregistrierung und
keine fertige Integration in die aktuellen Editoren.

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
