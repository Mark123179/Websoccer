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

Die 120.000er-Grenze ist eine globale Spielregel, **keine** Grenze des
ursprünglichen OSM-Grundrisses oder des Unity-Dachs. Spieler sollen die Tribüne
frei wählen können; auch Vereine mit etwa 14.000 Ausgangsplätzen sollen
grundsätzlich durch größere Bauphasen bis zur Gesamtgrenze wachsen können.
Extrem einseitige Ausbauten sind nicht schon deshalb baulich plausibel und
brauchen einen eigenen, klar als Konzept erkennbaren Rang-/Dach-/Eckentwurf.

**Why:** Der Nutzer hat ausdrücklich klargestellt, dass der alte Grundriss
keine ewige Schranke sein soll. Die Dortmunder Unity-Stuhlpositionszahl ist
zudem nicht die wirtschaftliche Stadionkapazität.

**How to apply:** 120.000 gegen die wirtschaftliche Kapazität prüfen und
Spielentscheidung, neue Bauphase sowie visuelle Machbarkeitsstudie trennen;
keine aus dem alten Mesh abgeleitete Seitenquote als universelle Regel
verwenden. Erst verifizierte Ausbauregeln produktiv machen.