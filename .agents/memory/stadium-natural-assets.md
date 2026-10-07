---
name: Natürliche Stadionumgebung – Assetauswahl
description: Vom Nutzer bestätigte Grafikquellen für das übertragbare natürliche Live-Ticker-Umfeld.
---

Als Grundlage verwenden: EZ-Tree Oak Medium, Oak Large, Ash Medium und Aspen Small; Poly Haven Shrub 03; ambientCG Asphalt 006, Paving Stones 136 und Grass 001; Poly Haven Brick Wall 02 und Overcast Soil (Pure Sky).

**Why:** Nach der konkreten Quellenauswahl bestätigte der Nutzer „Auswahl verwenden (empfohlen)“ als Grundlage für den Umsetzungsplan. Die Auswahl wurde noch nicht in der Stadionansicht auf Bildqualität oder Leistung abgenommen.

**How to apply:** Gemeinsame, einmal vorbereitete Assets von der geografischen Anordnung pro Stadion trennen. Diese Auswahl ist die Grafikgrundlage, kein Nachweis realer Baumarten oder Fassadenmaterialien; Lizenzen, Baumtexturherkunft und Exportmöglichkeiten bei Übernahme erneut prüfen. Ein reiner Himmel darf keine fremde Landschaft an die Stelle der realen Umgebung setzen. Die getrennten Regeln für Admin-Test und produktiven Neon-Editor bleiben bestehen.

Die umgesetzte natürliche Testansicht ist visuell nicht abgenommen und darf nicht als bestätigte Qualitätsreferenz für weitere Stadien verwendet werden.

**Why:** Der Nutzer lehnte die gezeigte Darstellung am 2026-10-07 ab: „Sieht aus wie auf einem Gamboy Pocket aus 1990.“ Die bestätigte Assetauswahl war keine Bestätigung der erzielten Bildqualität.

**How to apply:** Technische Funktionsprüfungen nicht mit visueller Abnahme gleichsetzen. Vor einer Übertragung auf weitere Stadien die gewünschte Bildqualität anhand einer tatsächlich gerenderten Ansicht klären.

Tree Small 02 war nur ein frühes Quellenbeispiel und ist nicht ausgewählt.

**Why:** Die Detailprüfung ergab eine afrikanische Baumart und ein sehr schweres Ausgangsmodell; für den Dortmunder Standardsatz wurden stattdessen die genannten Laubbaumvorlagen vorgeschlagen und bestätigt.

**How to apply:** Frühere Erwähnungen dieses Beispiels nicht als Freigabe behandeln.

Vorbereitete gzip-Assetdateien können vom Webserver bereits mit `Content-Encoding: gzip` ausgeliefert werden; `fetch` liefert dann schon entpackte Bytes.

**Why:** Django versah die komprimierte Baumdatei automatisch mit diesem Header. Eine zusätzliche bedingungslose Browser-Dekompression scheiterte, obwohl der Download korrekt war.

**How to apply:** Tatsächliche gzip-Signatur vor einer manuellen Dekompression prüfen und beide Auslieferungsarten testen; Serverheader nicht mit dem Zustand des von `fetch` gelieferten Bodys gleichsetzen.
