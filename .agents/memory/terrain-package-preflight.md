---
name: Gelände-Paketvorprüfung
description: Entscheidung zur Renderer-Parität und Grenze zwischen Prüfbericht und Paketübernahme.
---

Für räumliche Paketprüfungen dieselben reinen Prüffunktionen wie im produktiven
Renderer verwenden, statt seine Geometrien je Quellobjekt aufzubauen oder eine
zweite Implementierung der Straßenstreifen, Verbindungen und Konfliktregeln
einzuführen. Der vollständige Renderer bleibt das Vergleichsorakel.

**Why:** Die Aufgabe verlangt identische Transformation und Konfliktprüfung.
Eine separate Polygonprüfung könnte die tatsächlich gezeichnete Straßenbreite
oder Verbindungen übersehen. Geometrieerzeugung je Objekt und wiederholte
Aussparungsvalidierung skalieren bei großen Katalogen unnötig schlecht.
Einzelobjektprüfung sammelt mehrere Quellfehler, ohne beim ersten Konflikt
abzubrechen; Ressourcenüberschreitungen müssen die gesamte Prüfung ablehnen.

**How to apply:** Bei späterer Beschleunigung diese Parität erhalten und
Produktionsrenderer gegen Vorprüfung vergleichen, einschließlich Randkontakt,
Verbindungsflächen und ungültiger Flächen außerhalb der Aussparung.
Vollständig innenliegende
Grün-/Wasserflächen bleiben Hinweise, weil nur die Darstellung sie auslässt.
Kein Prüfer darf daraus eine automatische Quellbereinigung oder Freigabe
für Registrierung, Upload oder Datenübernahme ableiten.
