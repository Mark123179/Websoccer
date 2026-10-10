---
name: Borussia-Park source seating frame
description: Verified relation of uploaded seating coordinates to the exported source mesh world frame.
---

Die Borussia-Park-Sitz-JSON benutzt einen anderen Rahmen als die exportierten
World-Meshes. Für die sieben Sitzbereiche stimmt die Y-Drehung um +90°:
`(x,y,z)` wird zu `(z,y,-x)`. Sitzorientierungen brauchen denselben Adapter.

**Why:** Der Vergleich aller sieben Bereichs-Bounds ergab bei +90° eine
mittlere Abweichung von ungefähr 0,38m; ohne Drehung etwa 50m. Dateinamen und
Abschnittsbezeichnungen allein belegten die Zuordnung nicht.

**How to apply:** Native Sitzpositionen vor Erweiterung oder Sitzansicht gegen
die zugehörigen World-Crowd-Meshes prüfen. Beim nächsten Bundle die Prüfung
wiederholen, nicht die Drehung als allgemeines Unity-Gesetz übernehmen.
