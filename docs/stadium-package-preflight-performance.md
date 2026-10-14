# Große Gelände-Paketprüfungen

## Vertrag und Umsetzung

Die Offline-Prüfung verarbeitet **jedes** Quellobjekt in der Reihenfolge
Grünflächen, Wasser, Straßen, Gebäude, Bäume. Fehler stoppen nur das betroffene
Objekt; spätere Objekte bleiben prüfbar. Quellindizes, Meldungen und die
informative Behandlung vollständig innenliegender Flächen bleiben erhalten.
Es gibt keine Stichprobe, automatische Löschung, Registrierung oder Uploads.

`createSurroundingsChecks` in `dortmund_surroundings.js` wird vom produktiven
Renderer **und** der Vorprüfung verwendet. Gemeinsam sind:

- der unveränderte Koordinatentransform einschließlich aller acht Achsenpaare;
- Polygonabschluss, Mindestpunktzahl und die originale Three.js-Triangulierung,
  auch für ungültige Flächen außerhalb der Aussparung;
- Gebäudehöhen und Baumpositionsprüfung;
- die tatsächlich gezeichnete Straßen-Halbbreite `w * 1.25`, Streifen und
  achteckige Verbindungen, auch bei Einzelpunkten und Null-Längen-Segmenten;
- Aussparungsrelationen einschließlich Randkontakt, konkaver Konturen,
  umschließender Flächen, Winding und unveränderter EPS-Regeln.

Die Aussparung wird einmal validiert. `createGroundCutoutChecks` bereitet ihre
Kanten einmal vor und benutzt dieselben geometrischen Prädikate wie die
öffentlichen Einzelfunktionen. Es gibt weder eine zweite Konfliktimplementierung
noch eine vereinfachende Bounding-Box-Abnahme.

Im Offline-Pfad werden keine Gruppen, Meshes, Materialien, Instanzmatrizen,
Boden- oder Baumgeometrien erzeugt. Transformierte Punkte und Triangulierungen
leben nur für das aktuelle Objekt; Straßen-Footprints werden nacheinander
geliefert. Die eigentliche 3D-Live-Szene wurde nicht optimiert. Ihre
Geometrieausgabe bleibt bytegleich.

## Ressourcen und Fehler

Der Python-Aufruf behält sein **120-Sekunden-Limit**. Node erhält
`--max-old-space-size=512`. Zusätzlich gilt ein **128-MiB-Eingabelimit**, sowohl
beim Python-JSON-Aufruf als auch beim direkten stdin-Einlesen. UTF-8 wird nach
Bytes und nicht nach Zeichen gezählt.

Ein zu großes Paket, Timeout oder ein abgebrochener Node-Prozess liefert
`ok: false` / `checker_failed`, niemals ein erfolgreiches Teilergebnis.
Der direkte Node-Aufruf gibt bei einem Einlese-/Ausführungsfehler Status 2 aus.
Die Grenzen sind Schutzschranken, keine Objektbegrenzung.

512 MiB begrenzen den alten V8-Heap, **nicht** den gesamten Prozess-RSS oder den
Python-Aufrufer. Quell-JSON, geparste Daten und Befunde benötigen weiterhin
linearen Speicher. Die Messungen unten enthalten deshalb den tatsächlichen
Spitzen-RSS; der automatisierte Belastungstest läuft zusätzlich mit 256 MiB
V8-Heap und verlangt weniger als 512 MiB RSS.

## Reproduzierbare Belastungskataloge

`stadium_editor/tests_js/fixtures/surroundings_catalog.mjs` erzeugt die Daten
deterministisch im Speicher: Bäume im Meter-Raster, Grünpolygone mit 32 Punkten,
Wasserpolygone mit 48 Punkten, Gebäude mit 8 Punkten und Höhen von 6–40 m,
Straßen mit 16 Punkten und Breiten von 1–5. Alle regulären Objekte liegen
außerhalb der Aussparung. **Am Ende jeder Liste** steht ein zusätzlicher
Konflikt beziehungsweise Flächenhinweis, dessen ursprünglicher Index geprüft
wird. Große generierte JSON-Dateien werden nicht eingecheckt.

```sh
# Jeweils eigener Prozess, damit der Spitzen-RSS nicht vom Vorlauf stammt:
node --max-old-space-size=512 scripts/benchmark_surroundings_preflight.mjs --legacy
node --max-old-space-size=512 scripts/benchmark_surroundings_preflight.mjs
node --max-old-space-size=512 scripts/benchmark_surroundings_preflight.mjs --large --max-cutout
node --max-old-space-size=512 scripts/benchmark_surroundings_preflight.mjs --huge --max-cutout
```

`--legacy` ist ausschließlich ein Benchmark-Vergleich: Er baut weiterhin
für jedes Objekt die vollständige Produktionsumgebung auf und entsorgt sie.
Das ist kein zusätzlicher Produktionspfad. Die reguläre Messung enthält auch
die Katalogerzeugung; `checkMs` isoliert die eigentliche Prüfung.

Messung im Entwicklungscontainer (Laufzeiten/RSS sind hardware-, GC- und
lastabhängig):

| Strategie / Katalog | Objekte | Aussparungspunkte | Prüfzeit | Gesamtzeit | Spitzen-RSS |
| --- | ---: | ---: | ---: | ---: | ---: |
| Renderer je Objekt | 11.105 | 4 | 3,324 s | 3,340 s | 106,7 MiB |
| Gemeinsame CPU-Prüfung | 11.105 | 4 | 0,056 s | 0,071 s | 113,3 MiB |
| Gemeinsame CPU-Prüfung, groß | 115.005 | 256 | 8,992 s | 9,118 s | 163,2 MiB |
| Gemeinsame CPU-Prüfung, sehr groß | 1.037.505 | 256 | 23,980 s | 24,387 s | 327,3 MiB |

Der sehr große Katalog enthält 1.000.001 Bäume, 25.001 Grünflächen, 2.501
Wasserflächen, 5.001 Straßen und 5.001 Gebäude. Alle fünf letzten Befunde
wurden gefunden. Eine zusätzliche Messung über den **echten Python→Node-Pfad**
mit diesem Katalog ergab **26,994 s** für `inspect_package`, **408,0 MiB**
Node-Spitzen-RSS und dieselben fünf Befundpfade. Das kompakte Quell-JSON war
46.989.207 Bytes groß.

Dieser Messpfad lässt sich ohne Dateien wiederholen:

```sh
node --max-old-space-size=512 --input-type=module -e '
import {surroundingsCatalog, appendLateConflicts}
  from "./stadium_editor/tests_js/fixtures/surroundings_catalog.mjs";
console.log(JSON.stringify(appendLateConflicts(surroundingsCatalog({
  trees:1000000, surfaces:25000, roads:5000, buildings:5000, cutoutVertices:256
}))));
' | python -c '
import json, sys, time, resource
from stadium_editor.package_preflight import inspect_package
package = json.load(sys.stdin)
start = time.monotonic()
report = inspect_package(package)
expected = ["green[25000]", "water[2500]", "roads[5000]", "buildings[5000]", "trees[1000000]"]
assert [f["path"] for f in report["findings"]] == expected, report
print({"seconds": time.monotonic() - start,
       "nodePeakRssMiB": resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss / 1024,
       "findings": expected})
'
```

## Paritäts- und Regressionsevidenz

- Die ursprüngliche Renderer-/Vorprüfungsfassung wurde vor Abschluss separat
  aus Git geladen. **32 vollständige Berichte** (acht Achsenpaare × zwei
  Rahmen × konvexe/konkave Aussparung) stimmen einschließlich aller Meldungen
  und Indizes überein. Hinzu kommen **8.000 Prädikatvergleiche** gegen die
  ursprünglichen Funktionen, einschließlich umgekehrter Konturen.
- **16 Bytevergleiche** der ursprünglichen Renderer-Geometrie über acht
  Achsenpaare und zwei Rahmen waren identisch. Zwei daraus gesicherte
  SHA-256-Goldens bleiben automatisierte Regressionstests: Positionen,
  Normalen, UVs, Indizes, Instanzmatrizen und die letzte 2π-Fan-Ecke.
- Die Tests vergleichen vollständige Befundobjekte mit dem Renderer-Orakel,
  nicht nur `ok`. Abgedeckt sind Randkontakte, der reine Einzelpunkt-Join,
  doppelte Straßenpunkte, Kurvenverbindungen, ungültige Höhen/Flächen,
  späte Fehler und unveränderte Quelldaten.
- Der automatische Großkatalogtest prüft alle 115.005 Objekte mit der maximalen
  256-Punkt-Aussparung in einem separaten Prozess, begrenztem Heap,
  Laufzeit- und RSS-Obergrenze.
- Python-Tests sichern Pfadprojektion, einen serialisierten 100.003-Baum-Katalog,
  Zeitüberschreitung, Prozessabbruch und Eingabeüberschreitung ab.

```sh
node --test \
  stadium_editor/tests_js/test_surroundings_preflight.mjs \
  stadium_editor/tests_js/test_surroundings_ground.mjs \
  stadium_editor/tests_js/test_dortmund_surroundings.mjs \
  stadium_editor/tests_js/test_surroundings_axes.mjs \
  stadium_editor/tests_js/test_dortmund_editor_scene.mjs \
  stadium_editor/tests_js/test_stadium_stage_adapter.mjs
python manage.py test game.tests.test_stadium_package_preflight --verbosity=1
```

Abnahme dieser Prüfungen: **42 JavaScript-Tests und 9 Python-Tests bestanden**.
