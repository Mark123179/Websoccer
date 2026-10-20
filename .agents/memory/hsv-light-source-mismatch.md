---
name: HSV-Leuchten und Lampengeometrie
description: Quellgebundene Grenzen der HSV-Nachtbeleuchtung und Umgang mit der Flächenabstandshypothese.
---

Bei HSV die einseitige Übereinstimmung von Unity-Spotlights und realer
Lampengeometrie nicht durch großzügigere Montageabstände oder Verschieben
von Lichtquellen „reparieren“.

**Why:** Die ursprüngliche LightBillboard-Anordnung passt auf den anderen
Seiten nicht hinreichend zur geprüften Lampenbank. Die exakte Dreiecksprüfung
bestätigte die einseitige Auswahl; die vermeintlich fehlenden Montageorte
waren hier kein Effekt weit entfernter Mesh-Eckpunkte.

**How to apply:** Die belegten Quellen samt Originalwerten erhalten.
Für weitere Seiten passende Original-Montagenachweise beschaffen, statt
das Dach oder Leuchttexturen anderer Materialien still als Ersatz zu nutzen.
Eine bessere Browserhelligkeit ist eine modellspezifische Kalibrierung,
kein Beleg für vollständige reale Flutlichtabdeckung.
