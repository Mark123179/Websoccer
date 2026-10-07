# Ergänzung der bestehenden Source-ID-Anzeige

Freigegeben: Status, quellenbezogene Sperrwirkung und ID-Prüfdatum kompakt unter jeder ID.

- Kanonische externe ID-Zeilen sind die Quelle für IDs, Status und ID-Prüfdatum.
- Die bestehenden Sperrregeln bleiben unverändert und liefern die Sperrwirkung pro Quelle, einschließlich vorhandener IDs mit fehlendem Rating.
- Ein fehlendes ID-Prüfdatum bleibt fehlend; Rating- und Importdatum sind kein Ersatz.
- Die Stärken-CSV erhält alle drei IDs mit Status, ID-Prüfdatum und quellenbezogener Sperrwirkung.
- Abnahme: Gardarsson zeigt FMInside „nicht gefunden / sperrt“ und CMTracker „dort nicht vorhanden / sperrt nicht“, beide geprüft am 05.10.2026.
- Alle 34 vorhandenen CMTracker-IDs werden gegen v2-Paket, kanonische DB-Zeilen und tatsächliches readonly Input im gerenderten Source-Tab verglichen.
- Altmodus, Ratings, Formeln, Quelldaten, Arbeitsliste und aktives Pilotpaket bleiben unverändert. Kein Import, Reset oder Live-Eingriff.
