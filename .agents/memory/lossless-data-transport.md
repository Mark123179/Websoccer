---
name: Verlustfreie Datenübertragung
description: Zeitstempelpräzision bei Feldparität zwischen PostgreSQL und SQLite.
---

Bei verlustfreien Datenübergaben Zeitstempel mit allen sechs
Mikrosekundenstellen übertragen, nicht mit Djangos Standard-JSON-Encoder.

**Why:** DjangoJSONEncoder kürzt auf Millisekunden. Sub-Millisekundenwerte
werden dabei zu `.000`, das nach erneutem Parsen ganz verschwindet.
Damit entstehen sowohl echte Präzisionsverluste als auch Paritätsfehler.

**How to apply:** Für Datentransport eine verlustfreie kanonische
Zeitstempelkodierung verwenden und Werte unter einer Millisekunde ausdrücklich
im Roundtrip prüfen. Normale UI-JSON-Antworten brauchen diese Regel nicht.

Bei isolierten Transport-/Zusammenführungsprüfungen auch Löschsignale beachten,
nicht nur `save()`-Hooks. Bereits nachgepflegte Werte haben Vorrang vor
überlappenden älteren Quelldatensätzen.

**Why:** Das Löschen von Quellratings kann über Django-Signale Stärkeprofile
neu berechnen oder entfernen. Ein unverändertes fachliches Rating garantiert
damit noch keinen verlustfreien Transport der aktuellen Spielerdaten.

**How to apply:** Baseline-Feldparität separat nachweisen, bevor der kombinierte
Stand exportiert wird. Rohoperationen ohne Signale ausschließlich in der
ausdrücklich isolierten Prüfkopie verwenden; keine solche Ausnahme für normale
Workspace- oder Live-Schreibpfade übernehmen.
