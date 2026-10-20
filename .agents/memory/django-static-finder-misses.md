---
name: Django Static-Finder-Misses
description: Versionspezifische Falle beim Zusammenspiel eigener Finder mit Djangos Static-Aggregator.
---

Eigene Static-Finder müssen bei Nichttreffern wie Djangos eingebaute Finder eine leere Liste liefern, auch im Einzelmodus. Die öffentliche Aggregator-Funktion liefert anschließend selbst `None`, wenn insgesamt nichts gefunden wurde.

**Why:** Django 6.1 nimmt einen einzelnen Finder-Rückgabewert `None` in die Trefferliste auf. Ohne späteren echten Treffer bleibt `[None]` übrig; die Static-View behandelt diese Liste als Dateipfad und antwortet mit 500. Vorhandene Dateien funktionieren trotzdem, weshalb ein reiner Erfolgsfalltest den Defekt übersieht. Die aktuelle Methodensignatur allein war nicht die Ursache.

**How to apply:** Bei Django-Upgrades oder neuen Static-Findern sowohl vorhandene als auch vollständig fehlende Dateien durch die gesamte Finder-Kette prüfen, im Einzel- und Mehrfachmodus. Fehlende Assets müssen 404 ergeben; daraus nicht ohne separate Prüfung auf eine falsche Bildquelle schließen.
