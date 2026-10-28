---
name: Datenpakete zwischen Aufgaben und Workspace
description: Ignorierte Paketdateien und Library-Metadaten nach einem Aufgabenmerge auseinanderhalten.
---

Eine erfolgreiche Paketabnahme und ein gemergter Bericht beweisen nicht,
dass die ignorierte Lieferdatei im Haupt-Workspace lokal vorhanden ist.
Library-Metadaten sind ein Verweis auf ein Asset, kein lokaler Dateinachweis.

**Why:** Nach einem Aufgabenmerge lagen Quellcode, Prüfsummen und Asset-Metadaten
vor, aber weder die Liefer-ZIP noch ihre ursprünglichen Eingangsdateien.
Das registrierte Asset konnte am lokalen Pfad nicht erneut geöffnet werden.

**How to apply:** Vor einer weiterführenden Prüfung genau die Datei und ihre
Prüfsumme nachweisen. Falls ein neuer Snapshot des verfügbaren Teilbestands
verwendet wird, dessen Umfang und neue Prüfsummen klar vom früheren Vollpaket
trennen. Nicht einen Bericht als tatsächlichen neuen Backend-Nachweis ausgeben.
