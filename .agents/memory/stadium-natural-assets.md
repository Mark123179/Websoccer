---
name: Natürliche Stadionumgebung – Assetauswahl
description: Verbindliche Quellenkorrektur, szenenbasierter Vertrag und visuelle Abnahme des natürlichen Live-Ticker-Umfelds.
---

Aktuelle Grundlage ist die vom Nutzer angegebene vorbereitete `asset_bibliothek_web.zip`, nicht die eigene Neuaufbereitung der ursprünglichen Modellarchive. Grafikquellen sind die drei Sketchfab-Baumpakete (Realistic Trees Collection, Various Forest Assets Pack, oak trees), Generic passenger car pack sowie die angegebenen Poly-Haven-Himmel, Fernansichts-Bodenmaterialien und Shrub 03. Credits aus der gelieferten README übernehmen.

**Why:** Nach Ablehnung der bisherigen Optik verlangte der Nutzer am 2026-10-08 ausdrücklich die vorbereitete Web-Bibliothek mit korrigierten Materialien, Fahrzeughierarchie und Maßstäben. Diese ersetzt die frühere Auswahl der Standard-Baumvorlagen und Nahaufnahme-Bodentexturen.

**How to apply:** Gemeinsame, einmal vorbereitete Assets von der geografischen Anordnung pro Stadion trennen. Diese Auswahl ist die Grafikgrundlage, kein Nachweis realer Baumarten oder Fassadenmaterialien; Lizenzen, Baumtexturherkunft und Exportmöglichkeiten bei Übernahme erneut prüfen. Ein reiner Himmel darf keine fremde Landschaft an die Stelle der realen Umgebung setzen. Die getrennten Regeln für Admin-Test und produktiven Neon-Editor bleiben bestehen.

EZ-Tree ist nicht verboten. Die Realistic Trees Collection ist selbst ein EZ-Tree-Export. Verboten sind „Laufzeit-Generierung mit Standard-Presets“, „Nahaufnahme-Texturen auf Ferndistanz“ und „Licht ohne Schatten“.

**Why:** Der Nutzer korrigierte die vorherige pauschale Formulierung ausdrücklich: „Das Werkzeug war nie das Problem.“

**How to apply:** Vorbereitete und lizenzierte Modellableitungen nach ihrer tatsächlichen Qualität behandeln, nicht nach dem Namen des Erzeugungswerkzeugs.

Der Renderer muss `surroundings.*`, `geo` und `standsBounds` einer Szene verwenden; das Unity-Modell ist optional. Der Vier-Stadien-Export ersetzt das einzelne Dortmund-Paket. Die Abnahme muss Dortmund **und Elversberg** mit demselben Code zeigen.

**Why:** Der Nutzer machte den zweiten realen Stadionnachweis verbindlich: „sonst ist es nicht multiplizierbar“.

**How to apply:** Quellenunabhängige Szenendarstellung statt Pflicht-Dortmund-Bundle. Nordrichtung aus der jeweiligen Szene lesen, nicht den Dortmunder Nordvektor auf andere Orte übertragen. Südtribüne/Westtribüne gegen das Modell prüfen; Spiegelung nur als kalibrierter Szenenparameter, nie Originalgeometrie ändern. Impostors mindestens 2048, 8×8 Hemi-Oktaeder und alpha-getestete Schatten; Flutlichtpositionen aus dem vorhandenen Steckbrief übertragen. Angemeldete Tag-/Abend-, Dach- und 35°/50°/75°-Nachweise für beide Stadien, Lade-/Schattenkosten und Mobilprofil liefern.

Die umgesetzte natürliche Testansicht ist visuell nicht abgenommen und darf nicht als bestätigte Qualitätsreferenz für weitere Stadien verwendet werden.

**Why:** Der Nutzer lehnte die gezeigte Darstellung am 2026-10-07 ab: „Sieht aus wie auf einem Gamboy Pocket aus 1990.“ Die bestätigte Assetauswahl war keine Bestätigung der erzielten Bildqualität.

**How to apply:** Technische Funktionsprüfungen nicht mit visueller Abnahme gleichsetzen. Vor einer Übertragung auf weitere Stadien die gewünschte Bildqualität anhand einer tatsächlich gerenderten Ansicht klären.

Tree Small 02 war nur ein frühes Quellenbeispiel und ist nicht ausgewählt.

**Why:** Die Detailprüfung ergab eine afrikanische Baumart und ein sehr schweres Ausgangsmodell; für den Dortmunder Standardsatz wurden stattdessen die genannten Laubbaumvorlagen vorgeschlagen und bestätigt.

**How to apply:** Frühere Erwähnungen dieses Beispiels nicht als Freigabe behandeln.

Vorbereitete gzip-Assetdateien können vom Webserver bereits mit `Content-Encoding: gzip` ausgeliefert werden; `fetch` liefert dann schon entpackte Bytes.

**Why:** Django versah die komprimierte Baumdatei automatisch mit diesem Header. Eine zusätzliche bedingungslose Browser-Dekompression scheiterte, obwohl der Download korrekt war.

**How to apply:** Tatsächliche gzip-Signatur vor einer manuellen Dekompression prüfen und beide Auslieferungsarten testen; Serverheader nicht mit dem Zustand des von `fetch` gelieferten Bodys gleichsetzen.
