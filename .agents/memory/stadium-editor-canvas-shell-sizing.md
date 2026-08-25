---
name: Stadioneditor-Canvas im Game-Shell
description: Stabile Canvas-Größenmessung für den Stadioneditor innerhalb des transformierten Managementrahmens.
---

Der Stadioneditor braucht für den zentralen Grid-Bereich eine explizite Höhe bzw. Grid-Zeile. Bei der Staff-Ansicht müssen Werkzeugleiste, Canvas und Admin-Spalte außerdem explizit `grid-row: 1` teilen. Nach dem asynchronen Laden der Geometrie muss der Editor zusätzlich nach dem Layout erneut rendern. Ein `ResizeObserver` darf vor dem Laden der Geometrie nur terminieren und keinesfalls rendern.

**Why:** Absolut positionierte Canvas-Layer liefern keine intrinsische Höhe. Im skalierten Game-Shell konnte der Puffer dadurch mit einer Zwischenhöhe erstellt und anschließend über die große CSS-Fläche gestreckt werden; Stadion und Umgebung erschienen nur als winziger Ausschnitt. Weil die Admin-Spalte im DOM vor dem Canvas steht, konnte die Auto-Platzierung den Canvas in eine implizite zweite, leere Grid-Zeile verschieben.

**How to apply:** Bei Änderungen am Managementrahmen oder der Editor-Spaltenstruktur die Stage-Höhe explizit halten und im Dreispaltenlayout alle Rails derselben Grid-Zeile zuweisen. Canvas erst bei vorhandener Geometrie zeichnen und die Darstellung nach dem Layout-Tick erneut vermessen. Staff- und Nicht-Staff-Variante visuell kontrollieren.