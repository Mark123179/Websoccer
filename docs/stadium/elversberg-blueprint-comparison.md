# Elversberg: räumlicher und flacher Blueprint

## Zweck

Separate Gestaltungstudie nach der Qualitätskritik an den fotografischen
Arbeitsvorlagen. Der gelieferte dunkle 2D-Kartenscreenshot ist die Stilreferenz,
nicht das graue Foto-/Maskenbild. Die Studie liefert vollständige Ansichten
mit echtem Stadion, keine neue Stadt im laufenden Spiel.

Verglichen werden:

- **Räumlich:** dunkle gefüllte Gebäudekörper, unterscheidbare Ober-/Seitenflächen
  und zurückhaltende Konturen. Die realen Grundrisse bleiben erhalten.
- **Flach:** überwiegend bodengebundene Gebäuderinge, Straßen und Grünflächen.
  Weniger räumliche Information, näher am bisherigen 2D-Kartenstil.

Beide Stile verwenden denselben Tageslichtzustand, dasselbe bestehende
Elversberger Modell und jeweils Dach an/aus. Die Haupttribüne liegt hinten,
die kameraseitige Gegentribüne bleibt offen. Stadionmaterialien werden nicht
für einen der Stile nachträglich umgestaltet.

## Feste Vergleichsbasis

- Native Bilder: **1880 × 940 Pixel**.
- Spielfeld: **105 × 68 Meter**, bestätigter **75%-Mittelweg**.
- Kameravertrag: `surroundings-camera.json`.
- Keine zusätzliche Einpassung nach Gebäude, Dach oder Stadiongröße.
- Frische Originalrender je Dachzustand; die beiden Stile teilen denselben
  jeweiligen Originalrender.
- Eigene binäre Feld- und Stadionmasken erhalten die Originalpixel beim
  Zusammensetzen. Diese Kontrollmasken sind keine Gestaltungsvorlagen für
  die Nutzerübergabe.

Die gespeicherte Kamera-`pose` bezeichnet die **inverse Weltmatrix**. Die
Geometrie muss gegen die tatsächlich gerenderte Projektion geprüft werden;
erwartete Kamerawerte lediglich in ein Manifest zu schreiben genügt nicht.

## Quellen und Grenzen

Die Ortslage stammt aus den vorhandenen Elversberger OSM-Daten und den
OSM-Straßen-/Grünflächen des Vereinsblueprints. Das gebäudebezogene
OSM-Rohextrakt allein enthält keine Straßen; das ist kein Beleg, dass im
Projekt keine kartierten Straßen verfügbar sind.

Das Vereinsprofil bleibt maßgeblich für die Einordnung:

- Wasgau: bedingte Höhenhülle bis **9,379 m**.
- TVE: bedingte Höhenhülle bis **14,204 m**; keine bestätigte aktuelle
  Fassade oder Dachform.
- Lidl: Höhe **unbekannt**, keine 6-m-Ersatzhöhe als amtlicher Befund.
- Weitere niedrige Volumen sind gegebenenfalls bewusst **schematische
  Gestaltungsgrößen**, keine nachgemessenen Häuser.
- Gelände bleibt ein gemeinsames flaches Bezugsniveau. Hanglagen und
  Baumkronen sind nicht vermessen. Grünflächen sind keine vollständige
  Waldkanten- oder Baumpositionsquelle.
- Die ausgeblendete Tribünenfläche wird nicht als belegter Vorplatz
  mit neuen Parkplätzen oder Stadtmöbeln ausgestattet.

Quellen: © OpenStreetMap contributors, ODbL 1.0; bedingte Höhenbefunde
© LVGL 2022, dl-de/by-2-0, www.lvgl.saarland.de. Der Vergleich enthält
keine übernommenen historischen Originalfotografien.

Im aktuellen Export sind 345 Gebäudegrundrisse, 132 Straßenlinien und
18 Grünflächen enthalten. 18 Gebäuden konnten bedingte Höhenhüllen bei
mindestens 0,45 Grundriss-IoU zugeordnet werden; die übrigen 327 verwenden
bewusst niedrige 1,7-m-Gestaltungsvolumen. Die im älteren Blueprint enthaltenen
zufällig vergebenen `h`-Werte werden nicht als Höhenbefund übernommen.
Nicht jede im Vereinsprofil genannte Höhe konnte auf diese ältere
Grundrissquelle übertragen werden.

Die Spiegelung des V2-Ortsrahmens wird gegen die kanonischen OSM-Grundrisse
kontrolliert: 149 Grundrisse überschreiten 0,10 IoU, 23 erreichen 0,45 IoU.
Dies unterscheidet die Achsenlage eindeutig von den anderen getesteten
Spiegelungen, ist aber kein vollständiger lagegenauer Abgleich aller
Grundrisse. Straßenbreiten sind schematische 3/5/7-m-Darstellungsbreiten;
Quellwege werden nicht zur Verschönerung neu verlegt.

## Reproduzieren und prüfen

Vom Projektwurzelverzeichnis bei laufendem bestehenden Django-Workflow:

```sh
node scripts/elversberg_blueprint/export.mjs
python scripts/verify_elversberg_blueprint_study.py \
  generated-artifacts/elversberg-blueprint-comparison \
  --output generated-artifacts/elversberg-blueprint-comparison/verification.json
python scripts/test_elversberg_blueprint_study.py
```

Der Export verwendet den vorhandenen proxierten statischen Ursprung,
Chromium/SwiftShader und die bestehenden Studienmodule. Kein eigener Server,
keine neue Workflow-Konfiguration, keine Anmeldung, keine Datenbankänderung.
Die aktuellen Modellrender werden neu erzeugt, nicht aus alten PNGs attestiert.

Die vorhandenen bedingten Höheninputs müssen unter
`generated-artifacts/elversberg-height-visibility/height_inputs.json`
vorliegen. Fehlen sie nach einem Aufgaben-Merge, den dokumentierten
Höhenvorbereitungsablauf aus `reusable-surroundings-workflow.md` verwenden;
keine unbelegten Höhen als stillen Ersatz einsetzen.

Große Render und Vergleichsausgaben liegen ausschließlich im ignorierten
Verzeichnis `generated-artifacts/elversberg-blueprint-comparison/`.
Die vier nativen Entwürfe und `comparison.png` werden einzeln übergeben.
Die Übersicht dient dem Stilvergleich; zum Prüfen von Details die nativen
Bilder öffnen.

Der unabhängige Prüfer kontrolliert vier eindeutige Zustände, native
PNG-Größe und Deckkraft, die exakte gemeinsame Kamera, eine umfassende
Feldmaske, unveränderte geschützte Feldpixel und dieselben Originalrender
für beide Stile. Negative Regressionen umfassen Kameradrift, fehlende
Zustände, Feldveränderung, leere Masken, verkleinerte Bilder, Transparenz
und unzulässige Bildpfade.

Der erzeugte Vergleich wurde geprüft: vier native deckende PNGs, exakt
gemeinsame Kameramatrizen und jeweils **0 veränderte geschützte Feldpixel**.
Die acht Offline-Regressionen des Vergleichsprüfers und die 16 vorhandenen
Geo-Geometrieprüfungen bestanden. Der separate ältere
`test_elversberg_height_probe.py` konnte wegen der hier nicht vorhandenen
ignorierten `height_visibility.json` nicht starten; dieser alte
Sichtlinienbefund wird durch die Gestaltungstudie nicht neu attestiert.

## Beurteilung und nächster Schritt

Die räumliche Fassung stellt Volumen vor zusätzliche Karteninformation;
die flache Fassung stellt Übersichtlichkeit vor Fassadentiefe. In beiden
bleibt das bestehende helle Tagesstadion gegenüber der dunklen Ortskulisse
dominant. Diese bewusste Trennung ist zuerst anhand der Gesamtbilder zu
beurteilen, nicht durch neue Stadionmaterialien zu kaschieren.

Technischer Pixelschutz ist **keine visuelle Nutzerabnahme** und keine
Bestätigung einer vermessenen Ortsrekonstruktion. Die Stilwahl steht nach
der Übergabe beim Nutzer. Nacht, echter Ausbau und eine spätere Integration
benötigen einen gesonderten Auftrag; aus diesen Tagesbildern wird weder
eine fertige Nachtfassung noch eine produktive Laufzeitfreigabe abgeleitet.
