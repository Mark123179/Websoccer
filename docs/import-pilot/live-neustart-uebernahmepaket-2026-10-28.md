# Vollständiges Übernahmepaket und Paritätsnachweis

Stand: 28.10.2026. **Datenpaket vollständig erstellt und auf zwei isolierten
Prüfkopien nachgewiesen. Kein Live-Zugriff, kein Reset, kein Produktionsimport,
keine Änderung der vorhandenen Liga-Spielbarkeit oder Stärkeformeln.**

## 1. Ausgangsstand und Schweizer Quelle getrennt

Der schreibfreie PostgreSQL-Snapshot des Workspace enthält weiterhin:
94 Vereine in fünf Ligen, 4.624 Spieler, 53.305 Marktwertpunkte,
28.393 Transferhistorienzeilen und 61 Spielersperren.
Die Schweiz fehlt in dieser Datenbank. Das Paket behauptet **nicht**, dass
die Schweizer Vereine jetzt im Workspace angelegt seien.

Die erneut gelieferte Datei
`attached_assets/0_schweiz_vereinspakete_2026-10-27_1793208044258.zip`
enthält die zwölf erwarteten Vereins-ZIPs und ist bytegleich mit der
freigegebenen historischen Lieferung:

```text
4b0ae43e098ab953032ea8fcda679e9cd27ccb41c5a46f616e02e09ffe9b723d
```

Historische Quellenmenge: 635 Spielereinträge / 631 unterschiedliche Spieler,
129 Personen, 288 Rekorde, 369 Titel. Sieben Spieler sind bereits im
aktuellen Bestand enthalten. Daher entstehen im kombinierten Stand
**624 zusätzliche Spieler**, nicht 631 doppelte Spieler.

Diese Quelle wurde ausschließlich auf einer separaten SQLite-Prüfkopie des
aktuellen Tabellenstands ergänzt. Die bekannten Schweizer Rekordkorrekturen
und Hauptvereins-Eigentümer-Ausnahmen wurden zuvor angewandt; Original und
Projektionsnachweis bleiben getrennt im Lieferpaket erhalten.

## 2. Gelieferter Umfang

| Daten | Kombinierter Stand |
| --- | ---: |
| Ligen / Vereine | 6 / 106 |
| Spieler / gesperrte Spieler | 5.248 / 68 |
| Marktwertpunkte / Transferhistorienzeilen | 58.977 / 31.934 |
| Quellratings / aktuelle Stärkeprofile | 8.535 / 5.205 |
| Rating-Snapshots | 8.774 |
| Historische Personen | 1.108 |
| Spieler-/Personen-Quellidentitäten / Vereins-Quellidentitäten | 22.819 / 424 |
| Echte Vereinsrekorde | 2.544 |
| Aggregierte echte Titel / Titelereignisse | 913 / 2.808 |
| Nachpflege-/Importhinweise | 13.909 |
| Öffentliche Vereinsprofile / Stadion-Sachwerte | 106 / 106 |
| Angewandte Quellpaketläufe | 111 |
| **Freigegebene Tabellen / gesamte Zeilen** | **25 / 163.637** |

Bundesliga 18, zweite Bundesliga 18, Premier League 20, Ligue 1 18,
LaLiga 20, Schweizer Super League 12. Nur die bereits spielbare Bundesliga
bleibt spielbar; die fünf zusätzlichen Ligen bleiben nicht spielbar.
Keine neue Saison, Spielplanerzeugung oder Simulation.

TM-/FMI-/CMT-Zusatzprofile und CMT-Attributprofile sind im Vertrag enthalten,
haben in diesem Bestand jedoch jeweils null Zeilen. Auch leere Tabellen
wurden im Struktur-/Inhaltsvergleich berücksichtigt.

## 3. Vorrang der aktuellen Nachpflege

Der Workspace wird **nicht** aus alten `SourceImportRun.package_data` oder
Original-ZIPs neu aufgebaut. Maßgeblich sind die aktuellen Tabellenwerte.
Alte Paket-JSONs werden zusätzlich als Provenienz archiviert, nicht als
aktuelle Werte angewandt.

Die drei nachträglich bestätigten FM-Identitäten bleiben erhalten:

| Spieler-TM | Aktuelle FM-ID | Aktueller Zustand |
| --- | --- | --- |
| 1064403 | 2000374246 | entsperrt |
| 1342235 | 2000395283 | entsperrt |
| 1451988 | 2000395286 | FM-Potenzial NULL; Sperre bleibt |

Alle ursprünglichen Quarantänen, Sperrgründe, Positionsfelder, Ratingattribute,
Stärkeprofile, Nachwuchszuordnungen, manuell bearbeiteten Hinweise und
Historien bleiben erhalten. Das gilt insbesondere auch dann, wenn ein
Spieler zwar in alten Quellen vorkommt, aktuell aber ohne Verein in der
Quarantäne steht: Die Auswahl berücksichtigt zusätzlich belegte Paket-TM-IDs,
übernimmt jedoch keine fehlenden aktuellen Werte aus dem Archiv.

Der Schweizer Quellimport überschreibt zunächst auch sieben schon vorhandene
Spieler. Deshalb wird vor dem finalen Export die gesamte aktuelle Baseline
noch einmal gegen den eingefrorenen Transportstand geschützt, ohne
Modell-Save-/Delete-Signale oder Stärkeneuberechnung.
Der separate Nachweis umfasst **146.002 Baseline-Zeilen**.

Zugelassen sind ausschließlich **819 einzelne Feldauflösungen** zuvor
fehlender Vereinsreferenzen anhand bereits gespeicherter TM-IDs sowie die
daraus folgende Leihanzeige. Darunter fallen auch Vereinsbezüge in
Marktwertpunkten, Transfers und Gegnerbezüge in Rekorden. Jede andere
Abweichung führt zum Abbruch.

Leih-Ausnahmen bleiben erhalten:

- Koné TM 1133978: Eigentümer Manchester United TM 985, Leihziel Lausanne
  TM 527, bis 30.06.2027; Nachwuchszuordnung des aktuellen Bestands bewahrt.
- Kristal TM 978438: Eigentümer Köln TM 3, Leihziel Thun TM 938,
  bis 30.06.2027; Nachwuchszuordnung des aktuellen Bestands bewahrt.
- Die zuvor bestätigten spanischen Hauptvereins-/Leih-Ausnahmen bleiben
  unverändert Teil der Baseline; keine pauschale Gleichsetzung von B-Teams.

Die alten Rohbelege der Eigentümer-Abweichungen bleiben als Quellen erhalten.
Redundante lokale `owner_club_id`-Werte aus alten Bearbeitungsnotizen werden
in der Exportprojektion durch die bereits daneben belegte TM-Identität
ersetzt, nicht auf das Zielsystem übertragen. Der Workspace wird dabei
nicht geändert. Andere unbekannte lokale FK- oder Bild-/Account-Daten in
JSON-Belegen stoppen den Export ausdrücklich.

## 4. Schweizer Rekorde

- GC: 1:8 gegen Basel am 12.09.2004; Johann Vogels Ligadebüt am
  22.07.1992 mit 15 Jahren / 136 Tagen.
- Luzern: 16 Pflichtspiele ohne Sieg, 29.11.1942–23.05.1943.
- Sion: 16 Pflichtspiele ohne Sieg, 24.11.2001–04.05.2002.
- Zürichs ungeschlagene Serie und Lausannes Trainer-Siegesserie bleiben
  ausdrücklich NULL / `nicht_belegt`. Keine erfundenen Ersatzwerte.
- Vaduz bleibt im Vereinsprofil Liechtenstein zugeordnet.

Die Recherchebelege und sechs Original-/Projektionsvergleiche sind im
Paketmanifest und in `swiss-source-projection.json` enthalten.
Vertiefung: [Schweizer Freigabe](schweiz-2026-10-27.md),
[Zürich/Lausanne](schweiz-rekordserien-zuerich-lausanne-2026-10-27.md),
[Luzern/Sion](schweiz-serien-ohne-sieg-quellenpruefung.md).

## 5. Identitäten, Schema und Ausschlüsse

Der Vertrag steht in `game/club_import/restart_schema.py`.
Vereine/Spieler werden durch vorhandene TM-, sonst FM-, sonst API-Identitäten
verknüpft; Quellen durch ihren Code, Ligen durch ihren Katalogschlüssel.
Historische Personen bleiben über typisierte Quellidentitäten, vorhandene
Spielerverknüpfungen oder bereits persistierte Rekord-/Quellreferenzen
zugeordnet. Keine erfundenen globalen IDs und kein Namens-Raten.

Kindzeilen bleiben einschließlich echter Duplikate als Multimenge erhalten.
Jede Relation im ausgewählten Datenbestand wird im Referenzabschluss
aufgelöst. Die Prüfkopien erzeugen eigene IDs ab 10.000.001; Workspace-PKs
werden nicht als Ziel-IDs oder Fremdschlüssel übernommen.

Explizit ausgeschlossen: Konten/Rechte, Managerbezüge, Bilddateien/-pfade,
Workspace-Kontostände, Ledger, laufende Transfers, Simulationshistorie,
persönliche Stadionentwürfe und Geometrien. Titel-Katalog-Asset-IDs sind
Sachreferenzen, keine transportierten Bilddateien. Stadion-Sachwerte und reale
Kapazitätsverteilungen sind enthalten; persönliche 3D-Szenen nicht.

Alle ausgeschlossenen Spalten sind sichtbar im Manifest aufgeführt.
Die Pflichtspalte `Club.budget` erhält ausschließlich in der Prüfkopie 0;
dies ist weder ein übernommener Workspace-Kontostand noch eine Festlegung
späterer Live-Startbudgets.

Strukturparität meint gleiche freigegebene Django-Feldtypen, NULL-Regeln,
Längen, Dezimalpräzision und Relationsziele plus erfolgreiche
Fremdschlüsselprüfung. Keine Behauptung identischer PostgreSQL-/SQLite-DDL.
Die Zeitstempel behalten sämtliche sechs Mikrosekundenstellen.

## 6. Gelieferte Dateien und Prüfsummen

**Vollständiges Lieferpaket**, einschließlich Nachweisen und Schweizer Original:

```text
generated-artifacts/live-restart/uebernahmepaket-2026-10-28.zip
30.400.749 Bytes
SHA-256 ff2e73ff08c32cea5db5ec215382c0a29cf425d69d03a9fef214f28426fd58f0
```

Darin ist **`complete-current-state.zip` der maßgebliche Datenbestand**:

```text
29.642.709 Bytes
SHA-256 836842fc60cb48e7dd928acb9d6c5290bd9f8bb998b24576ef764d64c4419228
```

Kanonischer Hash aller erneut gelesenen Tabellen auf der zweiten Prüfkopie:

```text
c48ab3565eba18a5a08465b0ea8be1f75d0dc4167226cf4c53ae495e43cbcee1
```

Zusätzlich enthalten:

- `README.md` und `SHA256SUMS`;
- `evidence/complete-parity.json`: Vergleich aller 25 Tabellen;
- `evidence/complete-manifest.json`: Felder, Ausschlüsse, Umfang, Quellen;
- `evidence/baseline-preservation.json`: Baseline-Erhalt und 819 erlaubte Auflösungen;
- `evidence/base-parity.json`: eigenständiger Basisübertrag;
- `evidence/swiss-source-projection.json`: Schweizer Quellenkorrekturen;
- `evidence/targeted-tests.log`: 25 erfolgreiche Schutz-/Quellentests;
- `sources/swiss-original.zip`: bytegleiches Original, nur Quellenbeleg.

Keine SQLite-Dateien, Rohdumps, Zugangsdaten oder internen Scratch-ID-Protokolle
werden ausgeliefert. Große Dateien und Prüfkopien bleiben in den bereits
ignorierten `generated-artifacts/`, außerhalb Git und Deployment.
Die Lieferdatei wird separat als herunterladbares Asset bereitgestellt.

Die archivierten alten Paket-JSONs haben jeweils einen eigenen kanonischen
Hash. Dieser ist **nicht** die ursprüngliche `data.json`-Byteprüfsumme.
Für die 94 alten Vereinsarchive werden deshalb keine nicht mehr vorhandenen
Original-ZIP-Bytes behauptet; für das neu gelieferte Schweizer Original
wurde Bytegleichheit tatsächlich geprüft.

## 7. Reproduktion

Zunächst ein neuer schreibfreier Workspace-Snapshot, danach die ausschließlich
isolierte Zusammenstellung in einem noch nicht vorhandenen Unterverzeichnis:

```bash
python manage.py live_restart_package \
  --output generated-artifacts/live-restart/NEUER-BASIS-SNAPSHOT.zip
python -m scripts.assemble_live_restart_handoff \
  --base-package generated-artifacts/live-restart/NEUER-BASIS-SNAPSHOT.zip \
  --swiss-source attached_assets/0_schweiz_vereinspakete_2026-10-27_1793208044258.zip \
  --output-dir generated-artifacts/live-restart/NEUE-PRUEFUNG
python -m scripts.package_restart_delivery \
  generated-artifacts/live-restart/NEUE-PRUEFUNG \
  --output generated-artifacts/live-restart/NEUES-LIEFERPAKET.zip
```

Die Zusammenstellung ist für den hier dokumentierten Workspace ohne Schweiz
bestimmt. Ein bereits schweizerhaltiger Ausgangsstand darf nicht nochmals
additiv damit importiert werden. Das Skript erzwingt vor Django-Start die
isolierte SQLite-Konfiguration, neue Prüfdateien unter dem ignorierten
Prüfpfad und verweigert Überschreiben. Kein produktiver Schreibmodus.
Eine dokumentierte Fortsetzung eines bereits erzeugten isolierten
Zwischenstands ist mit `--resume-assembly` möglich, aber nur bei passenden
Basis-Prüfsummen, Schweizer Quellbytes und weiterhin gültigem Zwischenstand.

Gezielte Tests:

```bash
python manage.py test \
  game.tests.test_live_restart_package \
  game.tests.test_live_restart_inventory \
  game.tests.test_reset_preview \
  game.tests.test_swiss_package_preparation \
  game.tests.test_swiss_winless_evidence \
  --settings=core.package_test_settings --noinput
```

Ergebnis: **25 Tests erfolgreich**, kein Systemcheck-Fehler. Die Schweizer
Standardquelle wird bei neuem Uploadnamen ausschließlich durch die
freigegebene Byteprüfsumme erkannt; kein Vertrauen in einen Dateinamen.
Nach dieser Erkennungsergänzung zusätzlich beide Quellvorbereitungstests
erfolgreich. Paketintegrität, Referenzauflösung, NULL-Werte, verbotene JSON-Daten,
fehlende aktuelle Spieler, Zeitstempel, neue Ziel-IDs, doppelte Kindzeilen und
vollständiger Rollback bei kaputten Referenzen werden abgesichert.

Der Entwicklungsserver startet sauber; die bestehende Login-Seite lädt.
Es wurden keine neuen Ansichten, Anmelde- oder Produktionspfade eingeführt.

## 8. Was ausdrücklich nicht freigegeben ist

Der Datenumfang ist vollständig transportiert und dokumentiert.
`full_restart_ready=false` bleibt trotzdem korrekt:

- keine Verbindung zur Live-Datenbank und kein Produktionsimport;
- kein Live-Reset, Moduswechsel, Saisonstart oder Liga-Umschalten;
- keine private Live-Sicherung oder Server-Wiederherstellungsprobe;
- kein vollständiger PostgreSQL-Server-Probelauf dieses Pakets;
- keine Aussage, dass die allgemeinen Projektprüfungen grün seien.

Die abgerufenen bestehenden Workflows zeigen weiterhin Fehler:
`test` meldete 47 Fehlschläge und 484 Fehler bei 1.922 Tests,
`security-audit` meldete 57 bekannte Schwachstellen,
`datenqualitaet-check` einen Fehler und 637 Warnungen.
Diese Befunde sind keine neue Ausführungsfreigabe und werden durch die
25 gezielten grünen Prüfungen nicht ersetzt. Eine spätere Live-Ausführung
braucht weiterhin die gesonderten Sicherungs-, Wiederherstellungs-,
Sicherheits- und konkreten Reset-Freigaben aus der Vorbereitung.
