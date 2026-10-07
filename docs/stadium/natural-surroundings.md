# Natürliches Stadionumfeld

## Umfang

Die natürliche Umgebung ist ausschließlich im Admin-Test unter `/live/test/`
aktiv. Der produktive Editor verwendet weiterhin seinen bisherigen Neon-Renderer.
Ticker, Simulation, Geschichten, Stadionkapazität und Ursprungsgeometrie werden
durch die Umfelddarstellung nicht geändert. Die spiegelverkehrte BORUSSIA-Schrift
ist Bestandteil des unveränderten Ausgangsmodells, nicht hier korrigiert.

Die Darstellung ist eine grafische Annäherung auf vorhandenen Kartendaten,
keine fotogrammetrische Rekonstruktion oder Behauptung einer exakten Übereinstimmung
mit der gelieferten Spielgrafik. Unbekannte Baumarten, Größen und Fassaden bleiben
ausdrücklich angenähert; Geländehöhen werden nicht erfunden.

## Gemeinsame Assetbibliothek

`stadium_editor/static/stadium_editor/natural_assets/provenance.json` enthält
Quellen, Lizenzen, den festgelegten EZ-Tree-Quellstand und SHA-256-Prüfsummen der
lokalen Dateien. MIT-Copyright und Texturherkunft liegen daneben. Die vendorte
Three.js-HDR-Laderdatei hat ihre Lizenz im Vendor-Verzeichnis.

- EZ-Tree: Oak Medium, Oak Large, Ash Medium, Aspen Small, jeweils drei
  vorbereitete Detailstufen. Kein EZ-Tree-Code und keine Baumgenerierung im Browser.
- Rinde: ambientCG Bark001, CC0; Blätter: EZ-Tree-Demotexturen, MIT.
  Die echten Git-LFS-Texturbytes wurden gegen die Zeiger im festgelegten Archiv geprüft.
- Asphalt006, PavingStones136, Grass001 von ambientCG, CC0.
- Brick Wall 02, Overcast Soil (Pure Sky), Shrub 03 von Poly Haven, CC0.
- Shrub 03 liegt als vollständiges Modell einschließlich Ressourcen bereit.
  Dortmund enthält keine belegten Strauchpositionen, deshalb wird es nicht geladen
  oder platziert. Nichtleere Strauchlisten werden derzeit ausdrücklich abgewiesen;
  ihre zukünftige Darstellung braucht einen eigenen Adapter.
- Brick Wall 02 wird nur bei ausdrücklicher Materialzuordnung benutzt, nicht als
  angeblich reale Fassade jedes Hauses. Im Dortmunder Ausgangsmaterial fehlen diese
  Angaben, deshalb bleiben die Wände neutral.
- Der HDR-Himmel enthält keine fremde Landschaft. Er liefert natürliches
  Umgebungslicht, aber keine neue Wetter- oder Tageszeitlogik.

Geometrie ist in einem binären, gzip-komprimierten Paket statt großer JSON-Zahlenlisten
abgelegt. Oberflächen sind auf 512 Pixel vorbereitet; Blatttexturen behalten Alpha.
Der Lader berücksichtigt, dass ein Webserver gzip bereits als HTTP-Encoding
dekomprimieren lassen kann. Detailstufen und Sichtfeldprüfung reduzieren die
gezeichneten Bauminstanzen. Die Szene zeichnet nur bei Bedarf neu.

## Vorbereitung wiederholen

Die Vorbereitung benötigt Netz für die freigegebenen Providerdownloads. Danach
erfolgt die Auslieferung vollständig lokal, ohne OSM-Abfrage oder externen Assetaufruf.
Quellarchiv in einen temporären Ordner entpacken:

`https://codeload.github.com/dgreenheck/ez-tree/tar.gz/9eac30e99696b53a85e425d22e51aa0a7501705a`

Dann im Projekt ausführen:

```sh
node --experimental-vm-modules scripts/prepare_natural_trees.mjs SOURCE_DIR \
  stadium_editor/static/stadium_editor/natural_assets/library.json
python scripts/prepare_natural_assets.py SOURCE_DIR
python scripts/prepare_dortmund_natural_package.py
```

Die Bibliothek wird einmal vorbereitet. Der zweite Schritt erstellt auch das
Lizenz-/Prüfsummenmanifest. Versionswechsel bewusst prüfen, nicht ungeprüft
`main` herunterladen. Die Werkzeuge benutzen vorhandenes Node, Python,
requests und Pillow; keine zusätzlichen Laufzeitpakete sind erforderlich.

## Weiteres Stadion vorbereiten

1. Reale Straßenlinien, Gebäudepolygone/-höhen, Grünflächen, Wasser und
   belegte Baumpositionen mit Herkunft und Datum beschaffen. Fehlende Objekte
   nicht zur Bildverschönerung ergänzen; ODbL-Herkunft und Datenpflichten erhalten.
2. Den Modelladapter einmal gegen das reale Spielfeld kalibrieren. Einheit ist
   Meter, positive Y-Achse im 3D-Modell zeigt nach oben; Z ist längs und X quer
   zum Spielfeld. Andere Modellachsen zuerst normalisieren.
3. Ein Paket mit `schema: websoccer.natural-surroundings`, `version: 1`,
   `units: m`, `id`, `title`, `frame` und `data` erstellen.
   `frame.fieldC` ist das Spielfeldzentrum im Kartenrahmen; `axisTheta` dessen
   Längsachsenwinkel. Nach Abzug und Drehung gilt 3D-X = −v, 3D-Z = u.
4. `data` enthält `roads` (je `p` und `w`), `buildings`, gleich lange
   `buildingHeights`, `green`, `water`, `trees`, `shrubs` sowie
   `sources.geography` und `sources.trees`. Leere Listen explizit angeben.
   Optional `buildingMaterials` mit `neutral` oder `brick`, in gleicher Reihenfolge
   wie die Gebäude. Die bestehenden Straßenstreifen behalten halbe Breite
   `w * 1.25`; diese grafische Breitenkalibrierung ist kein Vermessungswert.
5. Mit `validate_natural_package` validieren und unter
   `stadium_editor/blueprints/natural/` speichern. Das Paket mit
   `buildNaturalSurroundings` an die eigene Modellansicht anbinden; der gemeinsame
   Umfeld-Renderer enthält keine Dortmund-Objektkoordinaten.
6. Ausrichtung, Maßstab und Lage gegen Ortsreferenz überprüfen. Bei fehlenden
   Höhen/Materialien die Annäherung dokumentieren. Ein verschobenes/gedrehtes
   Testpaket bestätigt die Transformation, ersetzt aber keine reale Ortsprüfung.

Der Dortmunder Export kopiert vorhandene Quelle und Baumkalibrierung, verändert
keine Blueprint-, Modell- oder Spielstände. Er enthält 230 Straßen, 148 Gebäude,
67 Grünflächen und 248 Baumrepräsentanten, keine Sträucher und kein Wasser.

## Prüfung und Leistungsnachweise

Nachweise liegen unter `docs/stadium/natural-surroundings-captures/`, einschließlich
Ansichten mit/ohne Dach, Mobilansicht und maschinenlesbarer Messberichte.
Desktop: Browserviewport 1440×1000, Canvas 998×611; Mobil: 390×850.
Die Kameraneigungen 35°, 50° und 75°, Reset und Dach-Rückkehr wurden geprüft.
Nach Reset und erneuter Dachaktivierung ist das Canvasbild bytegenau identisch
mit dem anfänglichen Dachbild. Keine Seitenfehler, fehlenden Assets oder
horizontal überlaufenden Bedienelemente.

Für den fairen Ausgangsvergleich wurde nur im Prüfbrowser die ursprüngliche
Szenenantwort aus Git mit identischer neuer Canvasgröße, Kamera und Ausschnitt
ausgeliefert. Originale App-Dateien wurden dafür nicht zurückgeschrieben.
Die in der Baseline weiter sichtbaren neuen Statuslabels sind nicht Teil der
Baseline-Geometrie; der Bericht misst den tatsächlich gezeichneten Canvas.

| Messung, 50° | Ursprüngliches Neon-Umfeld | Natürliches Umfeld |
|---|---:|---:|
| Geladene Stadion-/Three.js-Ressourcen, kalter Browser | 19.16 MB | 24.70 MB |
| Dreiecke, Dach an | 492,516 | 694,438 |
| Draw Calls, Dach an | 336 | 339 |
| Dreiecke, Dach aus | 418,109 | 620,031 |
| Draw Calls, Dach aus | 303 | 306 |
| CPU-Renderübergabe, Dach aus | 12.2 ms | 20.2 ms |
| Ausstehende GPU-Arbeit, Dach aus | 5.33 s | 6.85 s |

**Grenzen:** Der Browser verwendet ANGLE/SwiftShader ohne Hardware-GPU. Die
GPU-Wartezeit ist eine Synchronisationsmessung der ausstehenden Arbeit, kein
Hardware-FPS-Benchmark. Die natürliche Ansicht hat zusätzlichen Lade- und
Renderaufwand; keine Behauptung allgemeiner Flüssigkeit auf sämtlichen Geräten.
Das Ursprungsmodell stellt allein etwa 17.7 MB Binärgeometrie.
Strauchdateien sind vorbereitet, aber in diesen Ladegrößen nicht enthalten,
weil im Dortmunder Paket keine Sträucher platziert werden.

Prüfungen: 29 gezielte Node-Prüfungen (natürliches Umfeld, gzip, zweite
Kalibrierung, LOD/Sichtfeld, Fehler/Freigabe, Neon, Kamera, Dach) sowie neun
Python-/Django-Prüfungen (Paket-/Quellenparität, Lizenzmanifest, Zugriffsschutz,
Testlauf/Reload/Reset und unveränderte Spielzustände). Die absichtlich erzeugte
Reset-Fehlermeldung im Django-Test ist erwartetes Testverhalten.

Aufnahmeskript: `scripts/capture_natural_surroundings.mjs`. Es benötigt eine
kurzlebige autorisierte Sitzung in einer privaten Datei, ohne Login-Signale oder
Änderungen an Rollen/Passwörtern. Die verwendete Sitzung wurde nach der Prüfung
gelöscht. Den Zeichenpuffer hält ausschließlich der Prüfbrowser für den Export
vor; die Anwendung aktiviert ihn nicht dauerhaft.
