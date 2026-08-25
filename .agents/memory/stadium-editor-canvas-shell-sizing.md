---
name: Stadioneditor-Canvas im Game-Shell
description: Stabile Canvas-Größenmessung für den Stadioneditor innerhalb des transformierten Managementrahmens.
---

Der Stadioneditor braucht für den zentralen Grid-Bereich eine explizite Höhe bzw. Grid-Zeile. Nach dem asynchronen Laden der Geometrie muss er zusätzlich nach dem Layout erneut rendern. Ein `ResizeObserver` darf vor dem Laden der Geometrie nur terminieren und keinesfalls rendern.

**Why:** Absolut positionierte Canvas-Layer liefern keine intrinsische Höhe. Im skalierten Game-Shell konnte der Puffer dadurch mit einer Zwischenhöhe erstellt und anschließend über die große CSS-Fläche gestreckt werden; Stadion und Umgebung erschienen nur als winziger Ausschnitt.

**How to apply:** Bei Änderungen am Managementrahmen oder der Editor-Spaltenstruktur die Stage-Höhe explizit halten, Canvas erst bei vorhandener Geometrie zeichnen und die Darstellung nach dem Layout-Tick erneut vermessen. Visuell sowohl Stadion als auch Umfeld kontrollieren.