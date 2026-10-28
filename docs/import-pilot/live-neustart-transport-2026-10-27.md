# Aktueller Datenübertrag und isolierter Paritätsnachweis

**Historischer Teilnachweis:** Der zwischenzeitliche Schweizer Quellblocker
dieses Berichts wurde am 28.10.2026 durch erneute Lieferung des bytegleichen
Originalarchivs behoben. Maßgeblich ist der
[kombinierte Abschlussnachweis](live-neustart-uebernahmepaket-2026-10-28.md).
Die folgenden Zahlen und Archivprüfsummen beschreiben nur die damalige Basis.

**Status: Teilnachweis des vorhandenen Bestands; vollständige Übergabe noch
blockiert. Kein Live-Zugriff, kein Reset, kein Produktionsimport und keine
Umschaltung des Paketmodus.**

## 1. Tatsächlicher Bestand und fehlende Schweiz

Der aktuelle, wiederholbare Read-only-Snapshot der Workspace-Datenbank enthält
99 angewandte Paketläufe, 94 Vereine aus fünf Ligen, 4.624 Spieler,
53.305 Marktwertpunkte, 28.393 Transferhistorienzeilen und 61 Spielersperren.
Jobe Bellingham wird ausschließlich über TM 796297 geprüft:
HP ZM/DM, NP OM, 13 Marktwertpunkte, vier Transfers.

Für die Schweizer Liga enthält diese Datenbank **keine Vereine**.
Die früheren Berichte beschreiben dagegen zwölf Vereine, 635
Paket-Spielereinträge / 631 unterschiedliche Spieler, 129 Personen,
288 Rekorde und 369 Titel. Diese historischen Lieferzahlen sind
**kein aktueller Datenbanknachweis**.

Beide dokumentierten Schweizer Original-ZIPs sowie die abgeleiteten ZIPs
und der frühere Projektionsbeleg fehlen im aktuellen Dateisystem.
Suche im Workspace und in `/tmp` ergab kein Schweizer Lieferarchiv.
Das erwartete Original hat SHA-256:

```text
4b0ae43e098ab953032ea8fcda679e9cd27ccb41c5a46f616e02e09ffe9b723d
```

Die Quellen-/Entscheidungslage bleibt getrennt verfügbar:

- [Schweizer Importfreigabe](schweiz-2026-10-27.md):
  GC 1:8 gegen Basel am 12.09.2004; Vogels Ligadebüt am 22.07.1992
  mit 15 Jahren / 136 Tagen; keine alten Intertoto-Rekorde.
- [Zürich/Lausanne](schweiz-rekordserien-zuerich-lausanne-2026-10-27.md):
  ungeschlagene Serie bzw. Trainer-Siegesserie weiterhin offen.
- [Luzern/Sion](schweiz-serien-ohne-sieg-quellenpruefung.md):
  jeweils 16 Pflichtspiele ohne Sieg; vollständige Projektionen mit Quellen
  sind zusätzlich in `game/club_import/swiss_winless_20261027.py` verfügbar.
- Zwei ausdrücklich freigegebene Hauptvereins-Eigentümer bleiben zu beachten:
  Koné TM 1133978 → Manchester United TM 985, Leihziel Lausanne TM 527;
  Kristal TM 978438 → Köln TM 3, Leihziel Thun TM 938;
  jeweils bis 30.06.2027.

**Zum Fortsetzen erforderlich:** bytegleiches Schweizer Original erneut
bereitstellen, anschließend ausschließlich auf einer neuen isolierten
Prüfkopie die freigegebenen Projektionen und Eigentümer-Ausnahmen anwenden.
Erst dann das kombinierte Übernahmepaket und dessen Parität nachweisen.
Keine Schweizer Spielerdaten aus Berichten rekonstruieren und keine IDs
ergänzen. Der Workspace wurde nicht nachimportiert.

## 2. Was das vorhandene Übernahmepaket enthält

`game/club_import/restart_schema.py` definiert eine explizite Positivliste
für 25 Tabellen. Das Paket übernimmt den **aktuellen Tabelleninhalt**,
nicht die ursprünglichen Feldwerte aus `SourceImportRun.package_data`.
Die alten Pakete dienen nur zur Auswahl auch vereinsloser Quarantänefälle
und als Provenienz-/Abweichungsbeleg.

| Datenbereich | Übertragene Zeilen |
| --- | ---: |
| Ligen / Vereine / Spieler | 5 / 94 / 4.624 |
| Datenquellen / angewandte Paketläufe | 4 / 99 |
| Historische Personen im Referenzabschluss | 985 |
| Spieler-/Personen-Quellidentitäten / Vereins-Quellidentitäten | 20.114 / 376 |
| Öffentliche Vereinsprofile / Stadionsachwerte | 94 / 94 |
| Aktuelle Quellratings / Stärkeprofile | 7.560 / 4.584 |
| Quellrating-Snapshots | 7.785 |
| Marktwert-Snapshots / Transferhistorien | 53.305 / 28.393 |
| Echte Vereinsrekorde | 2.256 |
| Echte aggregierte Titel / einzelne Titelereignisse | 828 / 2.439 |
| Nachpflege-/Importhinweise samt Bearbeitungsstand | 12.363 |
| TM-/FMI-/CMT-Zusatzprofile und CMT-Attributprofile | jeweils 0 |
| **Gesamt** | **146.002** |

Quellrating- und Marktwert-Rohbelege werden ebenfalls erhalten, einschließlich
des nachgepflegten FM-Identitätsnachweises. JSON-Belege mit nicht freigegebenen
Account-, Bild- oder lokalen Fremdschlüsseln stoppen den Export ausdrücklich.

Die Abweichungsliste `current_vs_archive` weist drei nachträglich ergänzte,
in den letzten Originalständen noch fehlende FM-Identitäten aus:

| Spieler-TM | Aktuelle FM-ID | Aktuelle Sperre |
| --- | --- | --- |
| 1064403 | 2000374246 | nein |
| 1342235 | 2000395283 | nein |
| 1451988 | 2000395286 | ja, „Keine Stärke berechnet“ |

Der aktuelle FM-Potenzialwert dieses letzten Spielers bleibt **NULL**.
Kein Wiederabspielen der ursprünglich fehlenden FM-ID und keine Ersetzung
des NULL-Werts durch einen geschätzten Wert. Alle 61 Sperren, ihre Gründe,
Nachwuchszugehörigkeiten, aktuellen Eigentümer-/Leihziele und Leihenden
werden feldweise verglichen. Die Abweichungsliste ist eine gezielte
FM-/Rating-Diagnose, keine Behauptung einer vollständigen Änderungshistorie.

## 3. Identitäten und bewusst ausgeschlossene Daten

- Vereine/Spieler: vorhandene TM-, sonst FM-, sonst API-Quellidentität;
  fehlt jede belegte Identität, expliziter Abbruch statt Namensschätzung.
- Ligen: bestehender Katalogschlüssel aus Land, Name, Wettbewerbstyp und Stufe.
- Quellen: Quellcode; historische Personen: typisierte externe Quellidentität
  oder vorhandene Spielerreferenz. Bei einem Halter ohne globale Quell-ID
  ausschließlich die bereits persistierte Vereinsrekord-/Paketreferenz,
  niemals eine neue erfundene Personen-ID.
- Paketläufe: Quell- und Zeitstempelidentität mit Vereinsquellreferenz.
- Kindzeilen: kanonischer Inhalt samt stabilen Elternreferenzen; identische
  Zeilen bleiben als Multimenge erhalten.
- Der gesamte ausgewählte Fremdschlüsselabschluss wird aufgelöst.
  Keine Workspace-PKs stehen als Referenzen im Übernahmeinhalt.

Die Spaltenliste und **jede ausgeschlossene Spalte** sind im Paket aufgeführt.
Ausgeschlossen sind Konten, Rechte, Managerverknüpfungen, Bilddateien/-pfade,
Workspace-Spielstände, Kontostände, Ledger, laufende Transfers, persönliche
Editorstände und Geometrien. Bei Titeln bleiben die bestehenden
Katalog-Asset-IDs erhalten; es werden keine Bilddateien transportiert.
Stadion-Sachwerte und die reale Kapazitätsaufteilung sind enthalten, nicht
Betriebspreise oder persönliche 3D-Szenen.

Die Spielbudgetpflichtspalte wird **nur in der isolierten Prüfkopie**
explizit mit 0 angelegt. Dies ist keine Festlegung von Live-Startbudgets.
Die bestehenden Ligenwerte einschließlich `is_playable` werden exakt kopiert,
nicht neu interpretiert. Stärkeformeln und Berechnungskonstanten bleiben
unverändert; beim Replay laufen keine Modell-Save-Hooks oder Signale.

Manifest und Hash des gespeicherten alten JSON-Inhalts sind separate
Provenienzbelege. Deren Hash beweist nicht die ursprünglichen ZIP-/JSON-Bytes.
Die Originalpakete sind **nicht** der aktuelle Übernahmeinhalt.

## 4. Isolierter Nachweis

Vorhandenes, **noch nicht um die Schweiz ergänztes** Paket:

```text
generated-artifacts/live-restart/current-state-with-evidence-2026-10-27.zip
Größe: 21.660.412 Bytes
SHA-256: 54e06c8f9d340f127082cf8ee37cb6aca426eba1a65795b1a006300cf976202b
```

Maschinenlesbare Berichte:

- `generated-artifacts/live-restart/export-with-evidence.json`
- `generated-artifacts/live-restart/parity-with-evidence-2026-10-27.json`

Das ZIP enthält `current-state.json` und eine Prüfsummendatei.
Pro Tabelle sind Zeilenzahl und kanonischer Inhaltshash hinterlegt.
Das Archiv, die SQLite-Prüfdatei und die Rohberichte liegen ausschließlich
im bereits ignorierten Verzeichnis `generated-artifacts/`, nicht in Git
oder im Deployment.

Die neue SQLite-Prüfdatenbank erhielt unabhängig erzeugte IDs ab 10.000.001.
Alle 25 Tabellen wurden erneut gelesen und **alle Feldwerte und aufgelösten
Referenzen** mit dem Paket verglichen; sämtliche Tabellen sind identisch.
Auch leere Tabellen werden geprüft. Fremdschlüsselprüfung bestanden,
keine Konten übertragen, Jobe-Stichprobe identisch.
Der Zeitstempeltransport erhält alle sechs Mikrosekundenstellen.

Kanonischer Inhaltshash aller erneut gelesenen Tabellen:

```text
20a4c0ebe01ed067ced8bed525e1bcb787775ac214b60634d72107882845cb95
```

**Strukturparität** bedeutet hier gleiche freigegebene Django-Feldtypen,
NULL-Eigenschaften, Längen, Dezimalpräzision und Relationsziele plus
erfolgreiche Fremdschlüsselprüfung. Dies ist keine Behauptung identischer
PostgreSQL-/SQLite-DDL oder einer bereits erprobten Server-Wiederherstellung.
Der Bericht setzt `full_restart_ready` ausdrücklich auf `false`.

## 5. Reproduktion ohne Live-Zugriff

Read-only-Export im Workspace, mit einem noch nicht vorhandenen Zielnamen:

```bash
python manage.py live_restart_package \
  --output generated-artifacts/live-restart/NEUER-NAME.zip
```

Auf einer **frischen** Prüfdatei mit der ausschließlich lokalen Konfiguration:

```bash
python manage.py migrate --run-syncdb --noinput \
  --settings=core.live_restart_verify_settings
python manage.py verify_live_restart_package \
  generated-artifacts/live-restart/NEUER-NAME.zip \
  --report generated-artifacts/live-restart/NEUER-BERICHT.json \
  --settings=core.live_restart_verify_settings
```

Der zweite Befehl verweigert PostgreSQL, normale Workspace-Einstellungen,
Pfade außerhalb `generated-artifacts/live-restart/` und bereits befüllte
Prüfdateien. Er ist **kein produktiver Importbefehl**. Eine erneute Prüfung
erfordert eine neue separate Prüfdatei; keine vorhandene DB leeren.

Gezielte Schutztests:

```bash
python manage.py test \
  game.tests.test_live_restart_package \
  game.tests.test_live_restart_inventory \
  game.tests.test_reset_preview \
  --settings=core.package_test_settings --noinput
```

Geprüft werden schreibfreier Export, aktuelle statt alter FM-Werte,
NULL-Potenzial, Quarantäne ohne Vereinszugehörigkeit, historische Halter,
identische Kindzeilen, Ablehnung fehlender aktueller Spieler, Mikrosekunden,
Archivintegrität, verbotene JSON-Daten, neue Ziel-PKs, Replay-Schutz sowie
vollständiger Rollback bei defekter Referenz.
Ergebnis: **16 Tests erfolgreich**, ohne Systemcheck-Fehler;
Protokoll `generated-artifacts/live-restart/targeted-tests-final.log`.
Dies ersetzt weder den projektweiten Test-/Sicherheitsauditstand noch
separate Live-Sicherungen, Wiederherstellungsproben und Reset-Freigaben.

## 6. Offene Abnahme

Die vorhandenen fünf Ligen sind transportiert und inhaltlich nachgewiesen.
Die **vollständige Aufgabenabnahme bleibt gesperrt**, bis das Schweizer
Original erneut vorliegt und die freigegebene Schweizer Projektion in einem
kombinierten isolierten Nachweis enthalten ist. Vorher weder ein angeblich
vollständiges Live-Paket veröffentlichen noch den Neustart freigeben.
