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

HSV-Nachtrevisionen nur nach ausdrücklicher Nutzerfreigabe als neue
Asset-Version aktivieren; alte Asset-Pakete nicht überschreiben.

**Why:** Der Nutzer verlangt eine separate Freigabe zwischen der geprüften
Nachtstudie und der tatsächlichen Aktivierung sowie den Erhalt des Altstands.

**How to apply:** Eine Studienabnahme nicht als Aktivierungsfreigabe auslegen.
Registry-Wechsel an den erwarteten Ausgangshash binden und keine weiteren
Stadien, Datenbankinhalte oder Produktionsdeployments damit verbinden.

Bei parallel geänderter HSV-Sitzgrafik den freigegebenen Nachtkandidaten nicht
einfach bevorzugen: neue Sitzgrafik erhalten, Kombination neu prüfen und
separat zur Aktivierungsfreigabe vorlegen.

**Why:** Während der Nachtaktivierung wurde im Hauptprojekt bereits eine
neuere Sitzgrafik registriert. Der Nutzer hat ausdrücklich deren Erhalt und
die erneute Prüfung der Kombination gewählt.

**How to apply:** Ein Merge-Konflikt am Versionsfeld ist kein bloßer Textkonflikt.
Ausgangsmanifest, Pakettexturen und Bildbelege müssen dieselbe neue Baseline
verwenden; ein gemischtes Manifest darf nicht unter einer alten Versionskennung
veröffentlicht werden.
