# PostgreSQL-Nachweis des aktuell vorhandenen Importstands

Stand 28.10.2026. **Lokaler Prüftransport erfolgreich; kein Live-Import,
kein Live-Reset und keine Produktionsfreigabe.**

## Nachgewiesener Umfang

Der aktuelle Workspace wurde ausschließlich lesend als Datenpaket exportiert:

| Größe | Stand |
| --- | ---: |
| Vereine / Ligen | 94 / 5 |
| Spieler / Spielersperren | 4.624 / 61 |
| Marktwertpunkte | 53.305 |
| Transferhistorien | 28.393 |
| Übertragene Tabellen / Zeilen | 25 / 146.002 |

Geprüft auf **PostgreSQL 16.10**, nicht nur SQLite:

- Echte Projektmigrationen auf einem neu angelegten lokalen Prüfserver.
- Separater Server ohne TCP-Listener, ausschließlich über einen privaten
  Unix-Socket in einem neuen temporären Verzeichnis.
- Unabhängige Prüfung von tatsächlichem Datenverzeichnis, Datenbank, Benutzer
  und Port **vor Migrationen**, vor Entfernen der dortigen Migrations-Testdaten
  und nochmals vor dem eigentlichen Einspielen.
- Neue Ziel-IDs ab 10.000.001 statt Wiederverwendung von Workspace-IDs.
- Inhalt und Feldvertrag aller 25 Tabellen identisch; Fremdschlüsselprüfung
  bestanden; PostgreSQL-Sequenzen an die neu erzeugten IDs angepasst.
- Keine Konten übertragen, keine Modell-Save-Signale zur Neuberechnung
  importierter Werte ausgelöst.
- Prüfserver nach erfolgreichem Lauf gestoppt und entfernt.

Jobe, eindeutig über TM-ID 796297:
HP ZM/DM, NP OM, 13 Marktwertpunkte, vier Transferhistorien.

## Konkretes geprüftes Paket

```text
generated-artifacts/live-restart/postgres-baseline-2026-10-28.zip
SHA-256 e4be8844c196974d2ace175d9fdee38d0ecb54e2ab35756fd0d4f6e4214a58f0
```

Prüfbericht:

```text
generated-artifacts/live-restart/postgres-current-verification-2026-10-28.json
```

Kanonischer Inhaltshash der erneut gelesenen Zieltabellen:

```text
713e8f22ea71d5c2c7024d0e69b3b5e38bc3abd61dff9748433203681ec88245
```

Der ausführliche Bericht und das Datenpaket sind generierte Dateien, nicht
Git-Bestandteile. Die lesbare Zusammenfassung hier ist dauerhaft im Code.
Ein Library-Eintrag allein beweist nicht, dass eine Datei in einem späteren
Workspace noch lokal existiert; vor Verwendung Datei und Prüfsumme prüfen.

## Reproduktion – niemals auf einer bestehenden Datenbank

Voraussetzungen: native PostgreSQL-Werkzeuge `initdb`, `pg_ctl`, `createdb`,
`postgres`, vorhandene Python-Projektpakete, normaler Nicht-root-Benutzer.
Es werden weder Docker noch DB-Passwörter benötigt.

```bash
python scripts/verify_restart_postgres.py \
  --package generated-artifacts/live-restart/postgres-baseline-2026-10-28.zip \
  --expected-sha256 e4be8844c196974d2ace175d9fdee38d0ecb54e2ab35756fd0d4f6e4214a58f0 \
  --report generated-artifacts/live-restart/NEUER-POSTGRES-BERICHT.json
```

Die Kennzeichnung und tatsächliche Identität des neuen lokalen Clusters
werden geprüft. Weder `DATABASE_URL` noch eine Serververbindung aus Secrets
bestimmt das Ziel. Ein abweichendes Paket oder vorhandene Ergebnisdateien
führen zum Abbruch. Fehlerberichte bleiben als lokale Diagnose erhalten.
Bei ungeklärtem Server-Stopp wird dessen privates Verzeichnis nicht gelöscht.

Die zugelassenen Verifikations-Settings sind ausschließlich für diesen
Wegwerf-Cluster gedacht, **niemals für Web, Worker oder reguläre Workflows**.
Es gibt keinen `--live`, `--reset`, frei wählbaren DB-Host oder
Produktionsimport-Schalter.

34 gezielte Tests für Transport, Datenbankschutz, Inventar, Szenensicherung und
Reset-Vorschau erfolgreich. Das ersetzt keinen grünen Projekt-Gesamtlauf.

## 94 Vereine sind nicht das frühere 106-Vereine-Paket

Der zusammengeführte Abschlussbericht dokumentiert eine gesonderte Lieferung
mit zwölf zusätzlichen Schweizer Vereinen und insgesamt 5.248 Spielern.
Dessen Library-Metadaten sind vorhanden, die eigentliche Liefer-ZIP und
Schweizer Quelldatei waren nach dem Merge hier jedoch nicht lokal verfügbar.
Die registrierte Datei ließ sich nicht erneut aus dem lokalen Pfad öffnen.

**Deshalb wurde hier bewusst ein neuer Snapshot des tatsächlich verfügbaren
94-Vereine-Stands geprüft**, nicht ein angeblich identisches 106-Vereine-Paket.
Der neue Export ersetzt dessen frühere Prüfsummen und Belege nicht.

Sobald die vollständige Lieferung wieder als Datei vorliegt:

1. Äußere Lieferung gegen den dokumentierten Hash prüfen.
2. Nur den darin enthaltenen Datenbestand `complete-current-state.zip`
   gegen seinen eigenen dokumentierten Hash prüfen.
3. Diesen Datenbestand mit dem PostgreSQL-Prüfer unter einem neuen
   Berichtsnamen nachweisen. Nicht die äußere Beleg-ZIP als Datenpaket einlesen.
4. Das Ergebnis dem 106-Vereine-Bericht getrennt zuordnen.

## Was vor Live weiterhin fehlt

- Private Live-Sicherung samt echter Wiederherstellungsprüfung auf Hetzner:
  [Server-Sicherungsprüfung](server-sicherungspruefung-2026-10-27.md).
- Gesamtübernahme auf der isolierten **Server-Wiederherstellung** erproben:
  Konten/Rechte/Kataloge und Vereinsszenen erhalten, Konflikte sichtbar machen.
  Der lokale Prüfer ist kein produktiver Importer und schreibt ausdrücklich
  nicht in eine Server-Prüfkopie.
- Reset und vollständige Initialisierung später als eine rückrollbare
  Einheit absichern; keine separat committete leere Live-Datenbank.
- Offene Gesamttest-/Sicherheitsbefunde einordnen und erforderliche Korrekturen
  prüfen. Dieser PostgreSQL-Nachweis macht die alten roten Workflows nicht grün.
- Konkrete Lösch-/Schutzliste und Ausführung separat freigeben.

Nicht allein aufgrund dieses Berichts Live leeren, den Paketmodus wechseln,
neue Saisons starten oder Worker/Simulationsjobs aktivieren.
