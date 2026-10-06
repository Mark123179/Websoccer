# Nachtrag 12: Korrektur der offenen Reste R1–R3

- R1: „11 Pflichtspielsiege in Folge“ bleibt unverändert; die zusätzliche Einheit „Spiele“ entfällt im Vereins- und Trainerraum.
- R2: Suche, Transfer-Wappen und Vereinsnachrichten verwenden URL-Namen mit dem Pilot-Präfix. Die gleichen Links bleiben im Altmodus unverändert ohne Präfix.
- R3: Millionenbeträge der Highlights erhalten im Paketmodus eine Nachkommastelle ohne überflüssige Null. Enzo dos Santos wird mit „1,5 Mio. €“ angezeigt; sein gespeicherter Marktwert bleibt 1.500.000 €. Die bisherige Rundung im Altmodus bleibt erhalten.

Prüfung: alle elf Tests in `game.tests.test_package_display` bestanden (22,288 Sekunden), einschließlich neuer Präfix- und Rundungsprüfungen. Dies ist kein neuer Gesamtlauf der vollständigen Suite.

Zusätzlich wurden Übersicht, Vereinsraum und Vereinsseite mit echten Pilotdaten in einer schreibgeschützten Transaktion gerendert. Alle 144 Game-Fachtabellen stimmen mit dem zuletzt gelieferten Pilotstand überein. Keine Anmeldung, Sitzung oder Kontozuordnung wurde angelegt oder verändert.

Maschinenbeleg: `n12-rest-fixes-verification.json`. Der Pilot bleibt auf v2 mit 156 Arbeitslisteneinträgen, davon 128 offen und 28 durch Paket erledigt. Kein v3-Import oder weiterer freigegebener Folgeschritt wurde ausgeführt.

Die früher gelieferten Bildschirmfotos dokumentieren den damaligen Stand; für diese drei Korrekturen wurden keine neuen Fotos aufgenommen.

## Ergänzung R4: Creator → Spieler → Source

Im Paketmodus liest der Source-Tab die kanonischen externen IDs. Kobel zeigt Transfermarkt-ID 257814, FMInside-ID 98040383 und CMTracker-ID 235073, jeweils schreibgeschützt und mit Profil-Link.

Gespeicherte Profiladressen haben Vorrang. Fehlende Adressen werden ausschließlich für die Anzeige aus vorhandenen IDs abgeleitet und als „Aus ID abgeleitet · nicht gespeichert“ gekennzeichnet. Fehlende IDs bleiben fehlend; alte Spiegel- und Ratingfelder werden dafür nicht ausgewertet. Unsichere URL-Schemata werden nicht als anklickbare Links ausgegeben.

Abgeleitete FMInside-/CMTracker-Links öffnen die aktuelle Quell-Datenbank. Sie aktualisieren keine importierten Ratings und behaupten keine Übereinstimmung mit dem historischen Datenbankstand. Ein Source-Formular-Save schreibt im Paketmodus keine dieser Adressen in die Datenbank; das bisherige Altmodus-Verhalten bleibt bestehen.

Prüfung: alle 14 gezielten Tests bestanden (22,986 Sekunden), einschließlich kanonischer IDs, Vorrang gespeicherter Adressen, fehlender IDs, Altmodus und Schutz vor Adress-Rückschreiben. Kein neuer vollständiger Gesamtlauf.

Zusätzlich wurde die komplette echte Pilot-Creatoransicht für Kobel in einer schreibgeschützten Transaktion gerendert. Alle 144 Game-Fachtabellen bleiben identisch zum gelieferten v2-Stand. Maschinenbeleg: `n12-r4-verification.json`; Testprotokoll: `n12-r4-tests.log`. Keine Sitzung, Kontoänderung oder neue Bildschirmaufnahme. Der vereinbarte Halt gilt weiterhin.
