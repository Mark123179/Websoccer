---
name: Managerprofil KPI-Abnahme
description: Verbindliche Abnahmeregeln für KPI-Leiste und Trophäendarstellung im Managerprofil.
---

Die Managerprofil-KPI darf nicht per Augenmaß abgenommen werden. Das mit dem Design-Handoff gelieferte `kpi_selfcheck.js` muss gegen die tatsächlich gerenderte, authentifizierte Seite ohne FAIL durchlaufen.

**Why:** Eine visuell ähnliche Fassung hatte trotz Sichtprüfung eine 168-px-Zeile statt höchstens 145 px sowie falsche Bildrollen. Die KPI verlangt Wettbewerbslogos; nur die Vitrine zeigt Pokalabbildungen.

**How to apply:** Bei Änderungen an Header, Identitätskarte oder KPI immer den Selfcheck im Browser ausführen und die gemeinsame Höhe messen. Vitrine zusätzlich auf `scrollHeight > clientHeight` prüfen; eine äußere Scrollbar ist nicht vorgesehen.

Der Header darf für die Zeile unter der KPI kein `1fr` verwenden. In der skalierten Game-Shell kann dieser Track auf den verfügbaren Rest wachsen und einen großen Leerraum zwischen KPI und Navigation erzeugen. Beide Header-Zeilen müssen inhaltsbasiert (`max-content`) sein und der Header selbst darf nicht flexibel wachsen.