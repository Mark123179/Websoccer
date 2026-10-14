---
name: Gelände-Paketvorprüfung
description: Entscheidung zur Renderer-Parität und Grenze zwischen Prüfbericht und Paketübernahme.
---

Für räumliche Paketprüfungen den produktiven Renderer als rein lokales
CPU-Prüforakel bevorzugen, statt eine zweite Implementierung seiner
Straßenstreifen, Verbindungen und Konfliktregeln aufzubauen.

**Why:** Die Aufgabe verlangt identische Transformation und Konfliktprüfung.
Eine separate Polygonprüfung könnte die tatsächlich gezeichnete Straßenbreite
oder Verbindungen übersehen. Einzelobjektprüfung sammelt mehrere Quellfehler,
ohne beim ersten Konflikt abzubrechen.

**How to apply:** Bei späterer Beschleunigung diese Parität erhalten und
Produktionsrenderer gegen Vorprüfung vergleichen. Vollständig innenliegende
Grün-/Wasserflächen bleiben Hinweise, weil nur die Darstellung sie auslässt.
Kein Prüfer darf daraus eine automatische Quellbereinigung oder Freigabe
für Registrierung, Upload oder Datenübernahme ableiten.
