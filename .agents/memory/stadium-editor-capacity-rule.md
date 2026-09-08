---
name: Stadioneditor-Kapazitätsregel
description: Abgrenzung zwischen stabiler Topologie, ausbauabhängigem Raster und Stadionökonomie.
---

`Stadium` bleibt die alleinige Quelle für alle zwölf Kapazitätswerte und damit
für Ticketumsatz sowie Ausbauten. Die Geometrie liefert nur Form,
Tribünenzuordnung und eine serverseitig berechnete Blockverteilung.

Blockidentität, Tribüne, Rang und Links-rechts-Reihenfolge sind stabile
Topologie. `seats` bleibt die geometrische Blockbreite; `rows` wird für den
V2-Vertrag aus der aktuell zugewiesenen Kapazität berechnet. Ein vollständiges
RLE beschreibt immer das dadurch entstehende Rechteck einschließlich
Grundfarben-Padding.

**Why:** Browserdaten oder eine nicht ausreichend große Visualisierung dürfen
eine bereits gültige finanzielle Kapazitätsänderung nicht manipulieren oder
blockieren.

**How to apply:** Nach jedem Ausbau das gespeicherte Muster auf das neue
effektive Raster projizieren, auch wenn die Rohgeometrie unverändert bleibt.
Topologiewechsel räumlich über Block-Quads projizieren; keine zusätzlichen
Ränge automatisch erzeugen.

Der externe Raumvertrag verwendet Quads immer als
`[vorne-links, vorne-rechts, hinten-rechts, hinten-links]` aus Spielfeldsicht;
RLE läuft zeilenweise ab Reihe 0 vorne und innerhalb jeder Reihe links nach
rechts. Legacy-RLE muss deshalb pro Reihe gespiegelt werden, wenn dessen
interne D→C-Achse rechts→links verläuft.

Ausbaugeometrie wird stets aus unveränderlichen Referenzmaßen abgeleitet:
Vorderkante und `z0` bleiben fest, Hinterkante und `z1` wachsen proportional
zu `effektive rows / reference_rows`.

**Why:** Eine reine Quad-Umordnung spiegelt asymmetrische Sitzmuster; Skalieren
bereits skalierter Quads erzeugt bei wiederholten Ausbauten Geometriedrift.

**How to apply:** Raumwerte serverseitig setzen und Browserwerte strikt
validieren. Kanonische V2-Datensätze nicht erneut spiegeln; Legacy-Datensätze
genau einmal beim Anreichern in die kanonische Sitzachse überführen.