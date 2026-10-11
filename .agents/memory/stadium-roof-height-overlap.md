---
name: Überlappende Dach- und Ranghöhen
description: Eine reine Dach-Höhenschwelle kann bei Originalmodellen echte Tribünengeometrie ausblenden.
---

Bei neuen Originalmodellen die Wirkung des Dachschalters auf alle
Nicht-Crowd-Meshes prüfen. Ein gültiges Manifest und passende Prüfsummen
sind kein Nachweis einer korrekten Dachzuordnung.

**Why:** Beim extern gelieferten Allianz-Arena-Paket überlappen Dachbeginn
und Oberrang-Stufenhöhen. Die dokumentierte 36-m-Schwelle blendet deshalb
auch Rangteile aus; das Anheben der Schwelle lässt wiederum Dachteile stehen.
Die Crowd-Ausnahme schützt Sitzflächen, nicht sämtliche Tribünenbauteile.
Das ist eine Grenze des höhenbasierten Vertrags, keine beschädigte Datei.

**How to apply:** Dach-aus gegen Dach-an geometrisch prüfen, besonders
Treppen und Rangunterbau. Überlappung nicht durch eine willkürliche
Höhenschwelle oder Umdeklaration von Treppen zu Crowd kaschieren.
Eine saubere Trennung oder ausdrückliche Abnahme des Kompromisses braucht
eine eigene Entscheidung; bei einer Paketprüfung nichts automatisch
importieren oder an anderen freigegebenen Stadien ändern.
