---
name: Stadion-Blaupause V2
description: Dauerhafte Sicherheits- und Datenregeln für OSM-basierte V2-Stadionimporte und spätere Ausbauten.
---

V2-Geometrie verwendet ein physisches Raster: Reihen bilden 0,8 m Tiefe und Sitze 0,5 m Breite ab. Die wirtschaftliche Kapazität bleibt ausschließlich im Stadium-Modell und wird separat auf Blöcke verteilt. Bestehende Altgeometrien dürfen durch diese Regel nicht umgedeutet werden.

**Why:** Kapazitätsbasierte Neuberechnung von `rows` würde die physische Form und alle RLE-Designs verändern. Die gelieferte Blaupause erzeugt dagegen bereits kanonische Pitch-Frame-Szenen, während die Persistenz die historische Quad-Reihenfolge erwartet.

**How to apply:** Neue V2-Importe markieren das physische Raster ausdrücklich, wandeln Scene-Quads verlustfrei in die Speicherreihenfolge um und ordnen Quellen nur über eine geprüfte Club-ID-Tabelle zu. Vor jedem schreibenden Import: Dry-Run, Referenzvergleich und vollständiges Geometrie-/Design-Backup. Kapazitätsausbauten nutzen freie Rasterzellen stadionweit, bevor Geometrie wächst; einzelne Rasterzellen sind keine wirtschaftlichen Sitzplätze. Fehler der Visualisierung dürfen einen wirtschaftlichen Ausbau nie zurückrollen.