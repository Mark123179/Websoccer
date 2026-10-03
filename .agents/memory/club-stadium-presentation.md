---
name: Stadionmodell in der Vereinsübersicht
description: Gewünschte Rotation und Unterschied zwischen transparentem Modell und bestehendem Kachelhintergrund.
---

Die Stadion-Kachel in der Vereinsübersicht dreht das Modell automatisch.
Sie soll keine manuelle Drehung ermöglichen und kein Stadionumfeld zeigen.

**Why:** Der Nutzer präzisierte „dreht sich von alleine, kann man selbst nicht
drehen“ und bestätigte diese Darstellung mit „Stark“.

**How to apply:** Keine Maus-/Touchsteuerung für diese Kachel ergänzen.
Diese Vorgabe gilt nicht für die interaktive Stadionansicht im Editor.

Der Hintergrund der WebGL-Darstellung ist transparent, aber der ursprüngliche
Kachelhintergrund bleibt erhalten.

**Why:** Nach dem Wunsch nach Transparenz korrigierte der Nutzer ausdrücklich:
„Das 3D Modell gerne etwas größer zeigen und den alten ‚Kachelnhintergrund‘
wiederherstellen.“

**How to apply:** Modellhintergrund und Kacheldesign getrennt behandeln.
Transparenz darf nicht die bestehende Hintergrundgrafik der Kachel entfernen.