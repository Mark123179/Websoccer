# Stadionmodell-Registry

Ein weiterer **bereits vorhandener** Verein benötigt für den
Originalmodell-Renderer keine vereinsbezogene Codeänderung:
`models/<fmi>.json` + Assets hochladen + `check_stadium_model`.
Die FMI-ID ist `Club.fm_inside_id`, niemals die Django-Vereins-PK.
Dieses Verfahren legt weder Vereine noch Stadiongeometrien an.

## Manifest-Vertrag

Kanonische Datei: `stadium_editor/blueprints/v2/models/<fmi>.json`.
`model_manifest(fmi)` liefert ein vollständig validiertes Manifest oder
`None`. Ungültige Dateien werden mit Feldnamen als Warnung protokolliert;
sie aktivieren weder Renderer noch Asset-Auslieferung.
`registered_fmi_ids()` liefert die gültigen IDs numerisch sortiert.

| Pflichtfeld | Typ / Bedeutung |
| --- | --- |
| `format` | exakt `unity-mesh-binary-v1` |
| `clubFmiId` | positive ganze Zahl, muss zum Dateinamen passen |
| `stadiumName` | nichtleerer Stadionname |
| `source` | nichtleere Bezeichnung des Original-Bundles |
| `sourceSha256` | SHA-256 des Original-Bundles; 64 kleine Hex-Zeichen |
| `geometrySha256` | SHA-256 von `geometry.bin`, gleich `assetSha256["geometry.bin"]` |
| `assetVersion` | sichere einzelne Pfadkomponente; Version des Asset-Pakets |
| `assetSha256` | Objekt mit SHA-256 für `geometry.bin` und jede Textur |
| `meshes` | nichtleere Liste mit Namen, Vertex-Anzahl, Position-/UV-Offsets und Material-Teilen |
| `textures` | Liste eindeutiger, sicherer Dateinamen; keine Pfade |
| `fixtures` | 1–12 nachgewiesene Lichtquellen: Position, Richtung, Farbe, Reichweite, Winkel, Intensität, Mesh-Abstand ≤ 2 m, `representedIds` |
| `verifiedFixtureCount` | ganze Zahl ≥ Anzahl der Runtime-Leuchten |
| `seatView` | Objekt mit `position: [x,y,z]`; Quellindex und Rahmendrehung dürfen zusätzlich enthalten sein |
| `limits` | Liste ausdrücklich benannter Export-/Darstellungsgrenzen |
| `sourceEvidence` | Objekt je Quell-JSON mit SHA-256 und optionalem Zähler |
| `calibration` | vollständiges Objekt nach folgender Tabelle; keine Standardwerte |

Alle Zahlen müssen endlich sein; boolesche Werte sind keine Zahlen.
Binary-Offsets sind Byte-Offsets, durch vier teilbar. Positionen und UVs
sind Little-Endian Float32, Indizes Little-Endian Uint32; Indexanzahlen
sind positive Vielfache von drei. Jeder Material-Teil enthält `color`
als RGB-Dreierliste und `texture` als registrierten Dateinamen oder `null`.

### Kalibrierung

| Pflichtfeld | Typ / Bedeutung |
| --- | --- |
| `roofMinHeight` | Meter; Dreieck ist Dach, wenn alle drei Vertices mindestens diese Y-Höhe erreichen; Crowd ausgenommen |
| `skipMeshPrefixes` | Liste nichtleerer Präfixe für ausgelassene Quellmeshes |
| `crowdPrefix` | Präfix der Crowd-Meshes |
| `pitchPrefix` | Präfix der Spielfeld-Meshes, vom Front-Schnitt ausgenommen |
| `tickerRotationY` | Grad; Y-Quaternion auf die freigegebene `approved-elversberg`-Pose |
| `tickerFrontCut.normal` | endlicher, nichtnulliger Dreiervektor; THREE.Plane-Konvention |
| `tickerFrontCut.constant` | endliche Ebenenkonstante in Metern |
| `standAxes` | genau `+x`, `-x`, `+z`, `-z`; eindeutige Zuordnung zu NORD/SUED/OST/WEST |
| `orbitDefault.azimuth` | Radiant |
| `orbitDefault.elevation` | Radiant |
| `orbitDefault.distance` | positive Entfernung in Metern |

Tribünenzuordnung: dominante X-/Z-Achse des Crowd-Mesh-Zentrums und deren
Vorzeichen wählen. Bei Gleichstand gewinnt Z; Null verwendet das negative
Vorzeichen. Keine Spiegelung und keine stille Ersatzzuordnung.

Gladbach ist unverändert kalibriert:

```json
{
  "roofMinHeight": 26,
  "skipMeshPrefixes": ["center2_"],
  "crowdPrefix": "C_",
  "pitchPrefix": "st081_pitch_",
  "tickerRotationY": -90,
  "tickerFrontCut": {"normal": [1, 0, 0], "constant": 32},
  "standAxes": {"+x": "SUED", "-x": "NORD", "+z": "OST", "-z": "WEST"},
  "orbitDefault": {"azimuth": 0.95, "elevation": 0.65, "distance": 310}
}
```

Fehlt ein Kalibrierungsfeld oder ist es ungültig, bricht der Browser vor
dem Geometrie-Download mit `Kalibrierung fehlt: <feld>` ab. Er prüft außerdem
Vereins-ID und Bundle-Hash gegen die serverseitige Präsentation.

## Ablage und Integrität

- Registry: `stadium_editor/blueprints/v2/models/<fmi>.json` (kleines Manifest in Git).
- Lokale Assets: `<assets_root()>/stadium-models/<fmi>/<assetVersion>/<name>`.
- Sonst App Storage: `stadium-models/<fmi>/<assetVersion>/<name>`.
- Download-Cache: `/tmp/stadium-model-assets/<fmi>/<assetVersion>/<name>`.
- HTTP: `/stadion/model-assets/<fmi>/<assetVersion>/<name>`.

`manifest.json` kommt ausschließlich aus der Registry, nicht aus einem
alten Storage-Manifest. Nur `manifest.json`, `geometry.bin` und deklarierte
Texturen sind erlaubt. Unregistrierte FMI-ID, falsche Version und fremder
Dateiname ergeben 404. Prüfsummenfehler brechen die Auslieferung ab, auch
bei Cache-Treffern. Lokale Assets haben Vorrang.

Die Präsentations-URL des Manifests enthält einen aus dessen Inhalt
berechneten Revisionsparameter. Damit bleiben Kalibrierungsänderungen
nicht hinter einem früheren unveränderlichen Browser-Cache verborgen;
Geometrie- und Textur-URLs bleiben bei gleichen Assets unverändert.

Die Registry verwendet einen Prozess-Cache. Nach neuen/geänderten Manifesten
alle Web-Worker neu starten; auch ein früheres „nicht registriert“ wird
gecacht. Es ist keine Codeänderung und keine Datenbankmigration erforderlich.

## Übergabe durch Claude / neuer Verein

1. Bestehenden Verein, FMI-ID, Stadion und vorhandene `StadiumGeometry`
   lesend prüfen. Fehlende Grunddaten sind **nicht** Teil der Registrierung.
2. Original-Bundle und alle dazugehörigen Quell-JSONs in einen eigenen
   ignorierten Paketordner legen; nicht andere Stadien dazumischen.
3. Vollständige Kalibrierung als eigene JSON-Datei bereitstellen. Werte
   müssen gegen das jeweilige Modell geprüft sein, nicht von Gladbach kopiert.
4. Offline exportieren:

   ```sh
   python scripts/export_stadium_model.py \
     --bundle <paket/stadion.bundle> \
     --seats <paket/sitze.json> \
     --fmi <FMI_ID> --name "<STADIONNAME>" \
     --out generated-artifacts/<paket>/export \
     --calibration <kalibrierung.json>
   ```

   Der Export schreibt nur in `--out`. Er übernimmt den Kalibrierungsblock
   unverändert, erfasst alle JSON-Dateien neben dem Bundle als Quellbelege
   und validiert das vollständige Manifest. Er verwendet die bisherigen
   Unity-Hierarchien `MAIN`, `AUDIAREA`, `PITCH2021`, `MESH_CROWD`, den
   bisherigen Sitzquellrahmen und den vorhandenen Quellleuchtennachweis.
   Anders strukturierte Bundles müssen kompatibel vorbereitet werden;
   nicht durch erfundene Geometrien oder Leuchten ersetzen.
5. Das exportierte `manifest.json` als `models/<FMI_ID>.json` übernehmen.
   Binary/Texturen unverändert unter `<fmi>/<assetVersion>/` hochladen.
   Upload zuerst, Registry-Freigabe danach. Große Rohassets niemals in Git.
6. Lesen und prüfen:

   ```sh
   python manage.py check_stadium_model --fmi <FMI_ID>
   python manage.py check_stadium_model --fmi <FMI_ID> --assets
   ```

   Der zweite Befehl prüft jeden Hash an den **dauerhaften** Ablageorten,
   ohne Download-Cache und ohne Schreiboperationen. Fehler führen zu einem
   Fehlerstatus; der Feld-/Dateiname wird genannt.
7. Worker neu starten, die fünf Ansichten abnehmen und Bilder gesondert
   übergeben. Kein DB-Import, keine Kapazitäts-, Manager-, Finanz- oder
   Designänderung ist mit der Registrierung verbunden.

Der Dortmund-Pfad (907) hat in `current_live_scene()` weiterhin Vorrang.
Elversberg und `study_camera.js` bleiben unverändert. Gladbach (908) ist
die einzige im Rahmen dieses Umbaus registrierte ID.

## Gladbach-Reproduzierbarkeit

Das bisherige Bundle und Sitz-JSON ergeben mit dem generischen Export
weiterhin:

```text
geometrySha256:
956f33f9f791066b9cce465158ac029adae9c73eeef71f5465178c8d60f1889e
```

Der neu erzeugte Manifest-/Asset-Versionswert kann sich durch ergänzte
Metadaten und die vollständige Quellbelegliste ändern. Der bestehende
Gladbach-Registry-Eintrag behält seine Asset-Version; es wurden keine
Geometrien/Texturen ersetzt oder neu hochgeladen.

Prüfungen:

```sh
python manage.py test stadium_editor.test_model_registry --verbosity=2
node --test stadium_editor/static/stadium_editor/*.test.mjs
python manage.py check_stadium_model --fmi 908 --assets
```

Aufnahmebelege (bewusst nicht in Git):
`generated-artifacts/stadium-registry/before/`,
`generated-artifacts/stadium-registry/after/`,
`generated-artifacts/stadium-registry/pixel-diff.json`.
Alle fünf Nachher-Bilder wurden unter identischen Bedingungen neu
gerendert: 2D/3D jeweils 1000×560, Ticker jeweils 1000×500.
Pixel-Diff gegen die frische Vorher-Serie **und** die abgenommene Serie:
jeweils 0 geänderte Pixel in allen fünf Ansichten.
