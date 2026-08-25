---
name: Stadioneditor-Kapazitätsregel
description: Abgrenzung zwischen Stadionökonomie und visueller Stadiongeometrie.
---

`Stadium` bleibt die alleinige Quelle für alle zwölf Kapazitätswerte und damit
für Ticketumsatz sowie Ausbauten. Die Geometrie liefert nur Form,
Tribünenzuordnung und eine serverseitig berechnete Blockverteilung.

**Why:** Browserdaten oder eine nicht ausreichend große Visualisierung dürfen
eine bereits gültige finanzielle Kapazitätsänderung nicht manipulieren oder
blockieren.

**How to apply:** Nach einem Ausbau die vorhandene Geometrie nur innerhalb von
42 Reihen je Block aktualisieren. Reicht das nicht, bleibt die Geometrie
unverändert und meldet die Warnung; keine zusätzlichen Ränge automatisch
erzeugen.