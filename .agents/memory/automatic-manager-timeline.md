---
name: Automatische Manager-Timeline
description: Integritätsregeln für automatisch persistierte Final-, Amtszeitende- und Jugendereignisse.
---

Automatische Timeline-Ereignisse verwenden stabile Quellentypen und Quellschlüssel. Finalereignisse gehören in dieselbe Transaktion wie der verbindliche Wettbewerbsabschluss; Fehler dürfen nicht geschluckt werden.

**Why:** Sonst kann ein Wettbewerb dauerhaft als abgeschlossen gelten, obwohl die zugehörigen Managerereignisse fehlen und der normale Abschlusslauf sie nie erneut erzeugt.

**How to apply:** Manager zum Anpfiff am Spiel speichern. Historische Zuordnung nur aus einer eindeutig passenden Amtszeit ableiten, nie aus dem heutigen Club-Zeiger. Finaltickets behalten für beide Manager dieselbe echte Heim-/Auswärtsorientierung. Unbelegte Daten überspringen statt Datum, Gegner oder Verantwortung zu raten.