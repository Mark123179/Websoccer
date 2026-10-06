# Nachtrag 12: Korrektur der offenen Reste R1–R3

- R1: „11 Pflichtspielsiege in Folge“ bleibt unverändert; die zusätzliche Einheit „Spiele“ entfällt im Vereins- und Trainerraum.
- R2: Suche, Transfer-Wappen und Vereinsnachrichten verwenden URL-Namen mit dem Pilot-Präfix. Die gleichen Links bleiben im Altmodus unverändert ohne Präfix.
- R3: Millionenbeträge der Highlights erhalten im Paketmodus eine Nachkommastelle ohne überflüssige Null. Enzo dos Santos wird mit „1,5 Mio. €“ angezeigt; sein gespeicherter Marktwert bleibt 1.500.000 €. Die bisherige Rundung im Altmodus bleibt erhalten.

Prüfung: alle elf Tests in `game.tests.test_package_display` bestanden (22,288 Sekunden), einschließlich neuer Präfix- und Rundungsprüfungen. Dies ist kein neuer Gesamtlauf der vollständigen Suite.

Zusätzlich wurden Übersicht, Vereinsraum und Vereinsseite mit echten Pilotdaten in einer schreibgeschützten Transaktion gerendert. Alle 144 Game-Fachtabellen stimmen mit dem zuletzt gelieferten Pilotstand überein. Keine Anmeldung, Sitzung oder Kontozuordnung wurde angelegt oder verändert.

Maschinenbeleg: `n12-rest-fixes-verification.json`. Der Pilot bleibt auf v2 mit 156 Arbeitslisteneinträgen, davon 128 offen und 28 durch Paket erledigt. Kein v3-Import oder weiterer freigegebener Folgeschritt wurde ausgeführt.

Die früher gelieferten Bildschirmfotos dokumentieren den damaligen Stand; für diese drei Korrekturen wurden keine neuen Fotos aufgenommen.
