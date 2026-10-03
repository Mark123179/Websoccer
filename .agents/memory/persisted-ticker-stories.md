---
name: Persistierte Tickertexte und Erzählerversionen
description: Warum Erzähler-Paketwechsel gespeicherte Geschichten nicht automatisch neu erzeugen dürfen.
---

Bei einem Erzähler-Paketwechsel keine vollständige Neuerzählung gespeicherter Ticker durchführen. Bereits gelesene Texte erhalten; nur ausdrücklich freigegebene Fehlerfälle mit vorherigem vollständigem Export von Geschichte und Ereignissen neu aufbauen.

**Why:** Der Nutzer: „Ein Ticker ist eine gelesene Geschichte. Sobald jemand sie gesehen hat, ist sie Teil seiner Spielerinnerung — ein nachträglich anderer Text für dasselbe Spiel ist schlimmer als eine Kernzahl, die um eins danebenliegt.“

**How to apply:** Ein neuer Paketstandard gilt für neue oder ausdrücklich neu aufgebaute Geschichten. Die Version gehört zur einzelnen Geschichte; alte Texte nicht global auf die neue Version umetikettieren. Backups als exportierte Dateien ablegen, nicht lediglich die alten Zeilen löschen. Widersprüchliche Engine-Eingaben sichtbar diagnostizieren statt still korrigieren.