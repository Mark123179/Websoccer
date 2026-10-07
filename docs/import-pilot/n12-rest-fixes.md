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

## Abschließender Gesamtlauf inklusive R1–R4

Am 06.10.2026 wurde der vollständige aktuelle Stand erneut geprüft:

- Befehl: `python manage.py test game.tests --verbosity=0 --keepdb`.
- **1.682 Tests bestanden, OK, Exit-Code 0.**
- Laufzeit: **433,306 Sekunden** (7 Minuten 13 Sekunden).
- Nur eine Testsuite; keine weiteren Codeänderungen während des Laufs.
- Der getrennte v3-Test bleibt grün: sechs Kategorien geändert, null andere Fachwerte geändert, Wiederholung unverändert.
- Abschließender lesender Vergleich: alle **144 Pilot-Fachtabellen**, die Paket-Hashes und die Arbeitslisten-Status-/Text-Fingerprints unverändert.
- Echter Pilot weiterhin v2: **156 Einträge / 128 offen / 28 paketgeschlossen, 49 Stärken, zwei Einzelsperren**.
- Kein v3-Pilotimport, Reset oder Live-Eingriff.

Dieser Abschluss ersetzt die vorherigen Zwischenstände „kein neuer Gesamtlauf“. Er ersetzt nicht die noch ausstehende Claude-Gegenprüfung oder Live-Freigabe.

Vollständiges Protokoll: `n12-r1-r4-full-tests.log`. Maschinenbeleg: `n12-r1-r4-full-verification.json`.

## Ergänzung: ID-Status, ID-Prüfdatum und vollständiger CMTracker-Abgleich

Der Nutzer hat zwei verbleibende Lücken benannt: fehlende Unterscheidung leerer Source-IDs anhand ihres Status und fehlendes ID-Prüfdatum; außerdem war bisher nur Kobels CMTracker-ID in der gerenderten Source-Ansicht geprüft.

Nun stehen kompakt unter jeder kanonischen ID der Status, die quellenbezogene Sperrwirkung und das ID-Prüfdatum. Ein fehlendes ID-Prüfdatum wird nicht aus Rating- oder Importdaten ergänzt. Vorhandene IDs mit fehlendem Rating zeigen weiterhin die Sperrwirkung der unveränderten bestehenden Sperrregeln. Der Altmodus bleibt unverändert.

**Gardarsson, echter v2-Pilot:**

| Quelle | ID | Status | Quellen-Sperre | ID geprüft |
|---|---|---|---|---|
| FMInside | — | nicht gefunden | sperrt | 05.10.2026 |
| CMTracker | — | dort nicht vorhanden | sperrt nicht | 05.10.2026 |

**Vollständiger Abgleich, keine Stichprobe:**

- Alle **51 echten Pilot-Creatoransichten** wurden ohne Login/Sitzungsänderung in einer schreibgeschützten Transaktion gerendert.
- **153 ID-Blöcke** wurden anhand des v2-Pakets auf ID, Status, ID-Prüfdatum und readonly Eingabefeld geprüft.
- Alle **34 vorhandenen CMTracker-IDs** stimmen zwischen v2-Paket, kanonischer Datenbank und tatsächlich gerendertem Source-Eingabefeld überein: **null Abweichungen**.
- Die Stärkentabelle `n12-staerken-51.csv` enthält jetzt TM-, FMInside- und CMTracker-ID, jeweils mit Status, ID-Prüfdatum und Quellen-Sperre. Alle 51 CSV-Zeilen wurden gegen das Paket geprüft.
- Einzelbeleg je CMTracker-ID: `n12-cmtracker-id-abgleich-34.csv`.
- Maschinenbeleg: `n12-source-id-status-verification.json`.
- **17 gezielte Tests bestanden**, 21,887 Sekunden. Testprotokoll: `n12-source-id-status-tests.log`.
- Alle **144 Pilot-Fachtabellen**, Paket-Hashes und Arbeitslisten-Status-/Text-Fingerprints unverändert; weiterhin v2, 156/128/28 Einträge, 49 Stärken, zwei Einzelsperren.

Diese CSV-Erweiterung ersetzt den vorherigen Export mit ausschließlich TM-ID; frühere CSV-Hashes beziehen sich auf diesen vorherigen Export. Der zuletzt dokumentierte vollständige Lauf mit 1.682 Tests war **vor dieser Ergänzung**; er wird nicht als Prüfung der neuen Metadatenanzeige ausgegeben. Kein neuer Gesamtlauf, Paketimport, Reset oder Live-Eingriff. Der vereinbarte Halt gilt weiterhin.
