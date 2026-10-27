# Aktuellen Importstand für Live vorbereiten: Server-Sicherung

## Umfang

Der Nutzer verlangt mindestens den **aktuell tatsächlich vorhandenen
Workspace-Importstand** auf dem Live-Server. Fehlende Schweizer Daten werden
gesondert ausgewiesen; sie sind kein Grund, den vorhandenen Stand zurückzuhalten
oder ihn durch erfundene beziehungsweise alte Werte zu ersetzen.

Das Übernahmepaket samt manueller Nachpflege wird separat erstellt. Diese
Anleitung ergänzt dessen Übergabe um die serverseitige Sicherung und
Wiederherstellungsprüfung. **Sie importiert nichts und gibt keinen Reset frei.**

Die frühere Anleitung mit separat committetem Reset und anschließendem
Nachfüllen einzelner Vereine ist **nicht der Ausführungsweg für die aktuelle
Gesamtübernahme**. Ein späterer Übernahmelauf muss geschützte Daten prüfen und
Reset plus vollständige Initialisierung als eine rückrollbare Einheit
behandeln. Bei Fehler oder Abbruch darf kein leerer Live-Spielbestand bleiben.

## Was jetzt bereitsteht

- `live_restart_scene_backup`: rein lesender privater Export sämtlicher
  vorhandener Vereinsgeometrien, Sitzdesigns und Vereins-Umgebungszustände,
  nicht nur Dortmund. Enthält stabile TM-/FM-Vereinsidentitäten statt
  ungeprüft wiederverwendbarer lokaler Primärschlüssel.
- PostgreSQL-Sequenzstände werden zusätzlich erfasst.
- `prepare_live_restart_server.sh`: ausschließlich vom Betreiber gestartete
  private Sicherung und Wiederherstellung in eine **neue** Prüf-DB.
- `compare_live_restart_backups.py`: Vergleich vollständiger Tabellen-
  Fingerprints, Schutzregeln, Szenen und Sequenzen. Benötigt auf dem
  Serverhost nur Python 3, keine Django-Installation und keine Zugangsdaten.

Ein Export ist keine automatische Szenen-Rückübertragung. Vor einer späteren
Übernahme werden Szenen anhand ihrer TM-/FM-ID dem neu importierten Verein
zugeordnet. Mehrdeutige oder widersprüchliche Zuordnungen anhalten. Keine
alten Budgets, Kapazitäten, Ausbaustufen oder Managerzuordnungen aus einem
Szenenexport zurückspielen. Geometrie-/Designkonflikte mit dem gelieferten
Workspace-Stand vor Ausführung sichtbar machen, nicht still überschreiben.

## Servervoraussetzungen

**Nur auf Hetzner durch den Betreiber.** Die Schritte wurden hier nicht
auf dem echten Server ausgeführt.

1. Freigegebenen Code über das übliche GitHub-/Serververfahren übernehmen
   und die Images bauen. Es gibt durch diese Sicherungshilfen keine neuen
   Migrationen. Eine Sicherung mit einer zum Datenbankschema unpassenden
   Django-Version nicht als erfolgreich ausgeben.
2. Genug freien Platz für DB-Dump, Asset-/Medienarchive und eine zusätzliche
   vollständige Datenbank vorsehen. Das Skript zeigt den freien Platz, kann
   aber die erforderliche Reserve nicht verbindlich bestimmen.
3. Wartungsfenster einplanen: Nach dem folgenden Stop ist die Anwendung
   vorübergehend nicht erreichbar. Bestehende Konfiguration unverändert
   lassen, insbesondere noch keinen Paketmodus-Wechsel vornehmen.
4. Externe Cronjobs/Timer und andere Schreiber manuell pausieren.
   Beat stoppen, aktive Jobs auslaufen lassen und erst dann Worker/Web stoppen.

```bash
cd /opt/websoccer
docker compose stop celerybeat
# Aktive Jobs und externe Schreiber kontrollieren, dann:
docker compose stop celeryworker web
```

Das Sicherungsskript stoppt oder startet selbst keine Dienste. Es verweigert
den Start, solange `web`, `celeryworker` oder `celerybeat` noch laufen. Das
Flag `--writers-paused` bestätigt zusätzlich die manuell geprüften externen
Schreiber; diese kann das Skript nicht selbst vollständig ermitteln.

## Private Sicherung und echte DB-Wiederherstellung

```bash
bash scripts/prepare_live_restart_server.sh --writers-paused --backup-and-verify
```

Ohne beide Argumente wird nur ein Hinweis ausgegeben. Mit den Argumenten:

1. Neues privates Verzeichnis unter `/opt/private-backups/` anlegen, Modus
   `0700`. Nichts wiederverwenden, keine alten Sicherungen löschen.
2. Vollständige lesende Live-Vorschau und separate Szenensicherung erzeugen.
   Python-Prüfprozesse laufen zusätzlich mit PostgreSQL-Read-only-Voreinstellung.
3. Vollständigen Custom-Format-DB-Dump erstellen.
4. Assets und Medien aus den **tatsächlich konfigurierten Containerpfaden**
   archivieren und die Archive vollständig auf Lesbarkeit prüfen.
5. Serverkonfiguration privat sichern, Codeversion festhalten.
6. Ausschließlich eine noch nicht vorhandene Datenbank mit Präfix
   `import_restore_check_` anlegen. Dump dorthin wiederherstellen;
   **kein** `--clean`, `DROP`, Wiederherstellen über Live oder Abschalten
   von Schutzmechanismen.
7. Die Prüfkopie separat lesen und gegen die Live-Ausgangsfingerprints
   vergleichen. Live erneut lesen, damit zwischenzeitliche Änderungen
   die Prüfung scheitern lassen.
8. Prüfsummen der wesentlichen Sicherungs- und Belegdateien bilden und prüfen.

Die Prüfdatenbank wird nicht an Web/Worker angebunden. Bei Fehlschlag bleiben
Sicherung und Prüf-DB zur Diagnose erhalten; kein automatisches Aufräumen.
Auch bei Erfolg bleiben die Dienste gestoppt. Ein Erfolgssatz ersetzt
**nicht** die noch ausstehende Import-/Schutzprobe oder konkrete Freigabe.

Wenn nach der Sicherungsprüfung zunächst der Altbetrieb fortgesetzt werden
soll, erst den unveränderten Altmodus prüfen. Nur die zuvor benötigten Dienste
wieder starten; externe Timer kontrolliert nachziehen. Dadurch wird die
gesicherte Vorschau für einen späteren Reset veraltet: vor einer wirklichen
Umstellung im Wartungsfenster erneut sichern und prüfen.

## Welche Belege privat bleiben

Das Verzeichnis enthält unter anderem:

- `db.dump`, `server.env`, `assets.tar.gz`, `media.tar.gz`
- Live-/Restore-Fingerprints, alle vorhandenen Vereinsszenen
- Codeversion, Name der neuen Prüf-DB, Prüfsummen und Vergleichsergebnisse

**Keine dieser Dateien in Git, Chat, Library oder einen öffentlichen Download
stellen.** Dem Agenten nur Erfolg/Fehler und nötigenfalls bereinigte
Fehlermeldungen mitteilen. Keine Kontendaten, Dumpinhalte oder `.env` posten.

Assets/Medien wurden bis dahin auf Archivlesbarkeit, nicht durch eine
vollständige visuelle Rückübertragung abgenommen. Besonders Stadiondateien,
Originalmodelle und persönliche Bilder im privaten Inventar kontrollieren.
Für eine vollständige Rückkehr zudem vorhandene Server-/nginx-/TLS-Sicherungen
gemäß dem privaten Betriebsplan erhalten; das Skript sichert nicht das ganze
Hostsystem.

## Lokaler Prüfnachweis und Grenzen

- 16 gezielte Tests für die neuen Sicherungshilfen und vorhandenen
  Inventar-/Reset-Vorschau-Schutzregeln bestanden.
- Der Skriptablauf wurde mit einer **simulierten** Docker-Schnittstelle
  geprüft: Erfolgspfad, Inhaltsabweichung trotz gleicher Zeilenzahl,
  Abbruch bei laufendem Webdienst, private Dateirechte und keine
  Reset-/Import-/Lösch-/Dienststartoperationen.
- Das Vergleichsprogramm läuft auch ohne installierte Django-Pakete.
- Der echte Workspace wurde mit PostgreSQL-Read-only-Voreinstellung gelesen:
  21 Vereine mit Szenendaten, keine ungeklärte TM-/FM-Zuordnung,
  158 Sequenzen. Keine Daten zurückgeschrieben.

**Keine dieser lokalen Prüfungen ist ein echter Hetzner-Restore.**
Die serverseitige Ausführung und das vollständige geprüfte Übernahmepaket
bleiben Voraussetzungen vor einem späteren Umstellen.
