# Kleine echte Kölner Bodenbelege (offline)

**Keine Deckhöhen.** DGM1 ist Boden unter den Brücken, keine Fahrbahn.
`way/5229974` (Aachener Straße) und `way/362049118` bleiben
`unresolved_terrain_derivation`, `deckSource: null`. Es gibt keine Glättung,
Layer-Aufschläge, Ersatzwerte oder ausgeschlossenen Brückenalarme.

## Umfang und Herkunft

* Geobasis NRW, DGM1/WCS `nw_dgm`, **Datenlizenz Deutschland – Zero 2.0**:
  <https://www.govdata.de/dl-de/zero-2-0>.
* Lage: **EPSG:25832**, native Rasterweite **1 m**, Pixelzentren.
  Höhe: **DHHN2016 / NHN (EPSG:7837)**, Meter.
* OSM-Geometrien/Tags: © OpenStreetMap contributors, **ODbL 1.0**:
  <https://www.openstreetmap.org/copyright>.
* `ground.json` nennt die vollständigen ursprünglichen Abruf-URLs,
  Abrufzeitpunkte und SHA-256-Hashes aller zwölf nativen Ausgangsraster sowie
  die Eingabe-Hashes des Kontrolllaufs. Diese Ausgangsraster wurden erneut
  geladen und **bytegenau gegen die bereits dokumentierten Hashes** geprüft.
  Das ist keine neue Höhenaufnahme.
* Die winzigen GeoTIFFs sind **unveränderte Pixel-Fenster**, keine neu
  berechneten/geglätteten Höhen und kein herunterskaliertes Raster.
  `mosaicWindow` und `transform` binden jeden Ausschnitt an das native Mosaik.
  Die JSON-Proben enthalten Modell-X/Z, UTM-Koordinaten, OSM-Identität,
  Originalgeometrie der beiden Brücken und benötigte Zellen des echten
  20-m-Anzeigerasters. Das Anzeigeraster ist ausdrücklich kein natives DGM.
* `manifest.json` bindet JSON und alle TIFFs mit SHA-256. Fehlende oder
  beschädigte Belege brechen ab; es gibt keinen Download-Fallback.

## Was die Regression beweist – und was nicht

Beide Brückenprofile sind vollständig: **13/14 Bodenproben, 12/13 Segmente**.
Die Tests vergleichen jede Höhe, Fehlergröße, Steigung und Steigungsänderung
mit dem vollständigen nativen Kontrolllauf. Die tatsächliche JS-
Rendererinterpolation wird auch für die kleinen Anzeigeraster verwendet.
Durch die versetzte Rasterursprungsrechnung sind Rundungsdifferenzen bis
`1e-9` erlaubt (Meter bzw. Prozentpunkte), keine fachliche Fehlertoleranz.

Zusätzlich enthalten die Ausschnitte die echten schlechtesten Belegstellen
der acht Maximalwert-Alarme aus allen drei Kontrollzonen. Der neunte Alarm,
das gemessene Bodenfehler-95%-Quantil, ist durch seine **zwei georeferenzierten
Rangproben**, Populationsgröße, Rangindizes und lineare Interpolation belegt.
Die Offlineprüfung reproduziert dessen dokumentierten Zahlenwert, **nicht
die Rangfolge der vollständigen Population**. Sie berechnet ausdrücklich
kein neues Gesamtquantil aus dem kleinen Ausschnitt.

`fullRun` ist ein historischer Referenzzusammenhang: 975 Profile,
107.928 Bodenproben, 35.191 Segmente, 34.276 Steigungsänderungen,
**neun Alarme / `ok: false`**. Die kleinen Belege ersetzen keinen vollständigen
Flächenvergleich. Sie sichern die tatsächlichen Alarmwerte und Positionen
sowie die vollständigen zwei kritischen Brückenprofile offline ab.
Der Test entfernt außerdem nur die Brückenkennzeichnung und prüft, dass
dadurch **kein einziger** Bodenwert, Kontrollpunkt oder Alarmbeleg entfällt.

## Offline ausführen

Vom Repository-Stamm, mit den vorhandenen Python-Abhängigkeiten und Node:

```sh
python -m unittest game.tests.test_koln_height_profiles game.tests.test_koln_bridge_heights
```

Keine Datenbank, kein laufender Server, kein Netz und kein Inhalt aus
`generated-artifacts/` nötig. Die Regression blockiert HTTP/Socket-Verbindungen.
Die bisherigen synthetischen GeoTIFF-Grenzfalltests bleiben bestehen.

## Belege ausdrücklich neu ausschneiden

Nur bei bewusster Aktualisierung, **nicht** im Testlauf:

```sh
python -m scripts.build_koln_ground_fixture \
  --presentation generated-artifacts/koln-study/osm-fresh/presentation.json \
  --evidence generated-artifacts/koln-study/osm-fresh/evidence.json \
  --sources generated-artifacts/koln-study/heights/sources.json \
  --output generated-artifacts/koln-ground-rebuilt
```

Der Erzeuger lädt nichts herunter und prüft die vollständigen Eingaben mit
dem unveränderten Bodenprüfer. Voraussetzung sind die gehashten originalen
Raster, das zugehörige OSM-`raw.json`/`evidence.json` und die Präsentation.
Fehlt der Präsentation das Anzeigeraster, kann `--reconstruct-display` es
aus den nativen Quellen mit derselben Bodenrechnung wie
`refine_koln_heights.py` neu aufbauen. Dabei entsteht ausschließlich eine
diagnostische Datei `generated-artifacts/koln-study/heights/ground-fixture-presentation.json`;
die Eingabe und Live-/Stadiondaten werden nicht verändert.
Das benötigt keine LoD2-Gebäudedaten. Die Quelldatenbereitstellung selbst
bleibt eine getrennte, ausdrücklich auszuführende Aktion.

Zuerst in einen ignorierten Ausgabeordner erzeugen, dann Hashes, echte
Alarmwerte und Quellbindung prüfen. Erst anschließend bewusst die kleinen
Belege ersetzen. Große Raster und vollständige Berichte bleiben ignoriert.
