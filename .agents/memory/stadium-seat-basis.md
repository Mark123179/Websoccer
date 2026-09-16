---
name: Stadionsitz-Basis
description: Rechtshändige Sitzorientierung und belastbare visuelle Prüfung instanzierter Stadionsitze.
---

Sitzachsen, die an `Quaternion.setFromRotationMatrix()` gehen, müssen eine reine rechtshändige Rotation mit Determinante +1 bilden. Wenn die berechnete Hochachse nach unten zeigt, die symmetrische Sitz-Querachse umkehren und die Hochachse neu berechnen; niemals nur die Hochachse spiegeln. Die Lehnenachse bleibt dabei die geometrische Richtung von der Blockvorderkante zur Blockhinterkante, also weg vom Spielfeld.

**Why:** Eine gespiegelte Basis mit Determinante −1 kann als Zahlenwert plausibel aussehen (Lehne nach außen, Hochachse positiv), ist aber keine gültige Rotationsmatrix. Three.js-Quaternionen daraus richten Instanzen falsch aus oder machen sie praktisch unsichtbar. Zusätzlich können Setzstufen Sitze vollständig verdecken; ein echter WebGL-Nahprüfstand muss Fassade und Umgebung getrennt ausschalten können.

**How to apply:** Bei Änderungen an Sitzorientierung alle vier Tribünenseiten plus gedrehte Stadionachsen prüfen und `dot(cross(right, up), back) ≈ +1` erzwingen. Farben, Instanzzahl und sichtbare Zwischenräume zusätzlich in einem direkten WebGL-Harness kontrollieren.