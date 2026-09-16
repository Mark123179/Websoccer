---
name: Sitzansicht-Himmel für 16:9-Fotos
description: Nahtfreie Darstellung gewöhnlicher 16:9-Himmelsfotos in einer frei drehbaren Stadion-Sitzkamera.
---

Gewöhnliche 16:9-Himmelsfotos werden in der Sitzansicht als leicht
überdeckende Fernfläche an die Kamera gehängt. Sie dürfen nicht als
equirektangulare 360°-Textur oder gespiegelte Rundumtextur behandelt werden.

**Why:** Die linken und rechten Bildränder der gelieferten Fotos passen nicht
zusammen. Sowohl normale Rundumprojektion als auch gespiegelte Wiederholung
erzeugen beim Umschauen eine deutlich sichtbare senkrechte Naht.

**How to apply:** Fernfläche nach Kamera-FOV und Seitenverhältnis mit kleinem
Overscan berechnen, Tiefentest und Tiefenschreiben deaktivieren und das
Original-Seitenverhältnis per Cover-Skalierung erhalten. Die Fläche folgt
Yaw/Pitch, erzeugt keine Positionsparallaxe und darf nur in der Sitzansicht
existieren.