---
name: Native Geodaten-Bibliotheken
description: Warum funktionierende große Skripte fehlende native Abhängigkeiten kleiner Prüfer verdecken können.
---

Geodaten-Werkzeuge müssen auch als eigenständiger Prozess importierbar sein.
Ein erfolgreicher größerer Aufbereitungslauf beweist nicht, dass ein kleiner,
unabhängiger Rasterprüfer dieselben nativen Bibliotheken laden kann.

**Why:** Im Nix-Workspace funktionierte die kombinierte Höhenaufbereitung,
während der separate Rasterio-Prüfer wegen einer fehlenden libexpat scheiterte.
Bereits geladene Bibliotheken können solche Abhängigkeiten durch die
Importreihenfolge verdecken.

**How to apply:** Neue Offline-Geodaten-Einstiegspunkte in einem frischen
Prozess prüfen; native Abhängigkeiten explizit über die Systemkonfiguration
bereitstellen, nicht durch künstliche Zusatzimporte oder stille Ersatzdaten.
