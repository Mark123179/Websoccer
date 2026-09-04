---
name: KPI-Selbstcheck im Nullzustand
description: Dokumentiert den Widerspruch zwischen KPI-Prüfskript und verbindlichem Trophäen-Nullzustand.
---

Bei einem Manager ohne persönliche Trophäen ist der KPI-Nullzustand korrekt, wenn der Wert `0` und keine Wettbewerbslogos erscheinen. Das gelieferte Browser-Selbstprüfskript meldet in diesem Zustand dennoch einen Fehler, weil es mindestens ein Logo verlangt.

**Why:** Die Zustandsvorgabe verlangt ausdrücklich „Trophäen: Wert 0, keine Logos“, während der Logo-Check des Skripts ausschließlich 1–6 Logos akzeptiert. Alle übrigen Messungen können vollständig bestehen.

**How to apply:** Den Original-Selbstcheck für Geometrie und Typografie verwenden. Den Logo-Check nur in einem echten Trophäen-Zustand als verbindlich behandeln; im Nullzustand ist 0 Logos die korrekte Ausnahme und darf nicht durch Demo-Daten oder ein Platzhalterlogo umgangen werden.