# Vereinspakete: manuelle Live-Umstellung

> Aktualisierung 27.10.2026: Der Betreiber hat den Live-Altmodus und null
> Importläufe bestätigt und einen Neustart mit dem vollständigen aktuellen
> Importbestand **zur Vorbereitung** gewählt. Vor Ausführung unbedingt
> [den aktuellen Vorbereitungsbericht](live-neustart-vorbereitung-2026-10-27.md)
> beachten. Die historische Nachfüll-Reihenfolge und damalige grüne Tests
> sind keine Freigabe für einen heutigen Reset. Ein aktuelles vollständiges
> Transportpaket einschließlich manueller Nachpflege fehlt noch.
> Für die aktuelle Gesamtübernahme außerdem die
> [Server-Sicherungsprüfung](server-sicherungspruefung-2026-10-27.md) beachten:
> alle Vereinsszenen sichern und Reset/Initialisierung/Schutzprüfung später
> zusammen rückrollbar ausführen. Nicht die unten historische getrennte
> Reset-/Nachfüll-Reihenfolge unverändert ausführen.

Stand 07.10.2026. Maßgeblich: Nachträge 13 und 14. **Diese Anleitung ist Vorbereitung, keine Reset-Freigabe. Replit hat keinen Reset, keine Sicherung auf Hetzner, keinen Push/Pull und keine Umschaltung ausgeführt.**

## Was bereits erledigt ist

- Gegenprüfung abgeschlossen; früherer Halt aufgehoben; BVB-Pilot fachlich abgenommen.
- R1–R4 und Source-ID-Status/Prüfdatum sowie FMI-/CMTracker-ID-Spalten umgesetzt. Nachweise: `n12-r1-r4-full-verification.json`, `n12-source-id-status-verification.json`, `n12-staerken-51.csv`.
- ZIP-Sicherheitsfix und N68 abgeschlossen: siehe `zip-security-report.md`. Dessen Gesamtlauf: **1696 Tests, OK**. Die spätere Vorbereitung hat einen eigenen aktuellen Testnachweis.
- Vorbereitung einschließlich der neuen Vorschau-Tests: **1699 Tests, OK, Exit 0**, frische getrennte Testdatenbank; siehe `live-preparation-report.md` und `live-preparation-full-tests.log`.
- **Pilot bleibt v2.** Keine vorgeschaltete Pilot-Sicherung, kein v3-Pilot-Upload, keine erneute Pilot-Abnahme.
- BVB-v3 bleibt das erste Live-Paket. Nicht stattdessen das neu recherchierte Paket mit ergänzten Vereins-IDs verwenden. Danach weitere Vereine im Chat „Verein Import Praxis“, CMTracker je Liga aus einem Serverlauf.
- Bibliothekswartung bleibt nachgelagert, sofern die Serverbedingungen keine neue Erreichbarkeit eröffnen.

## Grenzen und neue Prüfbefunde

U21-Bezüge sind bei Teilstring-Kollisionen nicht allgemein von externen Vereinsverweisen getrennt; der ZIP-Bericht dokumentiert den reproduzierten Fall. BVB-v3 enthält die neuen U21-Bezüge nicht und wird deshalb nicht neu gebaut. Bei weiteren Paketen diesen Befund berücksichtigen.

Ein Spielerprofil ohne Marktwertverlauf kann über einen bestehenden Fallback abstürzen. Separater Korrekturvorschlag, keine heimliche Änderung während der Vorbereitung.

Die bestehende technische Liga-Startsperre prüft offene `blocking`-Einträge, **nicht die Zahl 18**. Deshalb während des Aufbaus keine Ligastart-/Simulationsaktion ausführen und alle automatischen Simulationsschreiber pausiert lassen. Die vollständige Bundesliga muss separat nachgewiesen werden.

## Lesende Vorschau und Schutzliste

Neu: `python manage.py preview_club_reset`. Kein `--execute`, `--apply` oder anderer Schreibmodus vorhanden. Die Abfragen erfolgen in einem PostgreSQL-Read-only-Snapshot und werden zurückgerollt. `--sql` gibt ausschließlich Text aus; kein SQL-Entwurf wird vom Kommando ausgeführt.

Die lokale Vorschau ist **kein Hetzner-Nachweis**. Auf dem Server nach Migrationen und bei pausierten Schreibern neu erzeugen. Unbekannte Tabellen, nicht klassifizierte Profilspalten, fehlende Schutztabellen oder unerwartete geschützte Fremdschlüssel verhindern die SQL-Ausgabe.

| Aktion | Tabellen/Regel |
|---|---|
| Unverändert erhalten | `auth_user`, `auth_group`, `auth_user_groups`, `auth_user_user_permissions`, `auth_group_permissions`, `auth_permission`, `django_content_type` |
| Technischen Stand erhalten | `django_migrations`; dies ist ein Reset derselben Datenbank, keine Pilot-Datenkopie |
| Kataloge erhalten | `game_referee`, `game_sponsor` |
| Elf Parameter-/Regeltabellen | `game_economyparameter`, `game_countrynetwork`, `game_stadionumfeldconfig`, `game_datasource`, `game_strengthformulasettings`, `game_strengthmodifierrule`, `game_mediaoutlet`, `showauction_showauctionpreset`, `game_storysettings`, `game_neutralvenue`, `game_landkoeffizient` |
| Länderkoeffizienten | ausschließlich Saison `"0"` erhalten; andere Saisonzeilen entfernen |
| Managerprofile | Zeilen und freigegebene persönliche Felder erhalten, Spielwerte nach N17 zurücksetzen |
| Spielbestand entfernen | alle übrigen registrierten Tabellen, einschließlich Clubs, Spieler, Stadien, Spiele/Spielpläne, Berichte, Taktiken, Historien, Importläufe/Arbeitslisten, Finanz-Ledger/Snapshots, Angebote/Verträge, Coins, Notizen, Support-Tickets, Sitzungen, Auktionen und clubgebundener Editor-Geometrie/-Design |
| Dateien | **keine Datei löschen**; komplette Asset-/Medien- und separate Dortmund-Szenensicherung erforderlich |

Profile bleiben: `id`, `user_id`, `name`, `trainer_type`, `nationality_flag`, `nationality_name`, `member_since`, `birth_date`, `profile_image`, `name_confirmed`, `residence`, `visibility_settings`.

Profil-Neustartwerte: level=1, xp=0, **xp_max=800** (nicht Modellstandard 15000), highscore=`–`, active_title=NULL, title_progress={}, season_score=0, previous_season_score=0, inactivity_season_count=0, inactivity_streak=0, transfer_ban_until=NULL, login_streak=0, login_points_today=0, login_last_date=NULL, login_day14_awarded=false, login_day30_awarded=false, login_day30_money_paid=false, last_seen=NULL, favourite_club_id=NULL; updated_at technisch neu.

Keine Rechte-Neuzuordnung anhand anderer IDs: bestehende Login-/Rechtezeilen und PK/FK bleiben in dieser Datenbank unverändert. Keine alten Coin-Guthaben übernehmen; nach dem Löschen keine Coin-Zeile eigenmächtig neu anlegen. Auth-Sitzungen werden geleert, bestehende Konten können sich anschließend neu anmelden.

Der SQL-Entwurf arbeitet mit DELETE, **ohne TRUNCATE CASCADE, DROP, deaktivierte Trigger oder Sequenz-Reset**. Er sperrt die Tabellen in einer Transaktion, bindet den gesamten Datenbestand an den genehmigten Vorschau-Fingerprint und prüft nachher geschützte Zeilen beziehungsweise Profilfelder. Unerwartete Fremdschlüsselverletzungen führen zum Abbruch/Rollback, nicht zum Überspringen eines Schutzes. Auch nicht-deferrierbare zyklische Constraints können einen Entwurf abbrechen; deshalb vor Live nur mit einer ausdrücklich freigegebenen Prüfkopie erproben, nicht „auf gut Glück“ Schutzmechanismen abschalten.

## Die elf Schritte — Mark führt die Serveraktionen aus

### 1. Sicherheitsfix abschließen

Erledigt. Bericht und vollständiges neues Protokoll liegen vor. Nicht mit dem weiterhin roten Bibliotheks-Audit verwechseln.

### 2. Vorbereitung abschließen

Diese Anleitung, lesende Vorschau und Schutzliste übernehmen. Vor einer Ausführung die tatsächlich auf Hetzner erzeugten Dateien prüfen. Private SQL-/Dump-/Szenendateien bleiben auf dem Server; nicht in Git, Chat, Library oder öffentliche Prüfarchive hochladen.

### 3. Stand auf Server, Migrationen im Altmodus

Mark überträgt den freigegebenen Code manuell nach dem bestehenden GitHub-/Serververfahren. Diese Aufgabe führt keinen Push oder Pull aus. In `/opt/websoccer` `.env` **nicht ersetzen**; `IMPORT_PACKAGE_MODE=0` und `RUN_MIGRATIONS=0` beibehalten. `IMPORT_PACKAGE_IMAGE_CHECK_ENABLED=1` kann bereits vorbereitet sein.

Vor Ausführung den tatsächlichen Migrationsplan prüfen. Diese Vorbereitung selbst führt keine neue Migration ein; der bisherige Serverstand ist nicht bekannt.

```bash
cd /opt/websoccer
docker compose build web celeryworker celerybeat
docker compose run --rm --entrypoint python -e IMPORT_PACKAGE_MODE=0 web manage.py showmigrations --plan
# Erst nach Prüfung: bekannte additive Import-Migrationen im Altmodus ausführen.
docker compose run --rm --entrypoint python -e IMPORT_PACKAGE_MODE=0 web manage.py migrate --noinput
docker compose run --rm --entrypoint python -e IMPORT_PACKAGE_MODE=0 web manage.py collectstatic --noinput
```

Bei unbekannten/destruktiven Migrationen stoppen und klären, nicht pauschal alles ausführen. Das alte Spielverhalten bleibt bis zur ausdrücklich späteren Umschaltung erhalten.

### 4. Live-Sicherung und echte Wiederherstellungsprüfung

**Mark, nicht Replit.** Genügend freien Platz prüfen. Beat und externe Cron-/Timerjobs stoppen, aktive Worker-Jobs auslaufen lassen, dann Worker und Web stoppen; auch andere DB-Schreiber ausschließen. Währenddessen Wartungsseite beziehungsweise Nichterreichbarkeit einplanen.

```bash
umask 077
BACKUP="/opt/private-backups/import-$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$BACKUP"
chmod 700 "$BACKUP"
docker compose stop celerybeat
# Vor dem Stop prüfen: keine aktiven Jobs mehr; externe Timer separat pausieren.
docker compose stop celeryworker web
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$BACKUP/db.dump"
docker compose exec -T db pg_restore --list < "$BACKUP/db.dump" > "$BACKUP/db-contents.txt"
tar -C /var/www -czf "$BACKUP/assets.tar.gz" assets
docker compose run --rm -T --no-deps --entrypoint sh web -c 'tar -czf - -C /app media' > "$BACKUP/media.tar.gz"
cp --preserve=mode .env "$BACKUP/server.env"
git rev-parse HEAD > "$BACKUP/code-version.txt"
sha256sum "$BACKUP/db.dump" "$BACKUP/assets.tar.gz" "$BACKUP/media.tar.gz" > "$BACKUP/checksums.txt"
```

Den Altmodus-Code-/Release-Stand und etwaige vor Migrationen vorhandene Sicherung zusätzlich bewahren. Quelle für Medien-/Assetpfade ist die tatsächlich verwendete Compose-Konfiguration; bei abweichenden Mounts anpassen und dokumentieren, nicht einen leeren Pfad als erfolgreiche Sicherung werten. Zertifikate/Serverkonfiguration nach dem bestehenden privaten Server-Sicherungsplan mitführen.

Die **Dortmund-Geometrie und das Design zusätzlich separat exportieren**, siehe Abschnitt unten. Der DB-Dump enthält sie zwar, aber kein Rohdump darf als BVB-Vereinspaket importiert werden.

Prüfkopie mit neuem, noch nicht vorhandenem Namen erzeugen; keine bestehende Datenbank überschreiben:

```bash
CHECK="import_restore_check_$(date -u +%Y%m%d%H%M%S)"
docker compose exec -T db sh -c 'createdb -U "$POSTGRES_USER" "$1"' sh "$CHECK"
docker compose exec -T db sh -c 'pg_restore -U "$POSTGRES_USER" -d "$1" --exit-on-error' sh "$CHECK" < "$BACKUP/db.dump"
docker compose run --rm --entrypoint python -e IMPORT_PACKAGE_MODE=0 web manage.py preview_club_reset > "$BACKUP/live-preview.json"
docker compose run --rm --entrypoint python -e IMPORT_PACKAGE_MODE=0 web manage.py preview_club_reset --restore-check-name "$CHECK" > "$BACKUP/restore-preview.json"
```

`tables`-Inventar beider JSON-Dateien muss gleich sein: Tabellen, Zeilen und vollständige Vorher-Fingerprints, nicht nur Gesamtsumme. Unterschiedliche scope-Felder sind gewollt. Private Prüfdatenbank nicht mit Web/Workern verbinden. Ein erfolgreiches `pg_restore --list` allein ist **keine** Wiederherstellungsprüfung. Archive zusätzlich prüfen und ausschließlich in ein neues isoliertes Prüfverzeichnis entpacken, nie über die laufenden Assets:

```bash
sha256sum -c "$BACKUP/checksums.txt"
tar -tzf "$BACKUP/assets.tar.gz" > "$BACKUP/assets-contents.txt"
tar -tzf "$BACKUP/media.tar.gz" > "$BACKUP/media-contents.txt"
```

Dortmund-Mesh/Seats/Materialien sowie Profilbilder anhand des Inventars prüfen. Die Kopie muss vollständig und lesbar sein. Für den noch nicht ausgeführten Live-Reset-Entwurf fehlt in Replit bewusst eine tatsächliche Ausführungsprobe: Eine solche darf erst separat auf der isolierten Prüfkopie freigegeben werden. Bis dahin kein „Reset bereits getestet“-Versprechen.

### 5. Konkrete Reset-Vorschau prüfen und separat freigeben

```bash
docker compose run --rm --entrypoint python -e IMPORT_PACKAGE_MODE=0 web manage.py preview_club_reset > "$BACKUP/reset-preview.json"
docker compose run --rm --entrypoint python -e IMPORT_PACKAGE_MODE=0 web manage.py preview_club_reset --sql > "$BACKUP/reset-draft.sql"
sha256sum "$BACKUP/reset-preview.json" "$BACKUP/reset-draft.sql" > "$BACKUP/reset-checksums.txt"
```

Nur `blockers=[]` erlaubt einen Entwurf. Die tatsächliche Löschliste enthält auch leere Tabellen und Nebenapps. Alle 139 lokal klassifizierten Lösch-Tabellen sind kein Ersatz für diese **frische Serverliste**; ihr Umfang kann dort abweichen. Betreiber genehmigt genau diese Liste mit Sicherungs-/Wiederherstellungsbelegen und geplantem Profilreset.

**Auswirkung der Freigabe:** Der gesamte alte Spielbestand einschließlich alter Vereinszuordnungen, Geldstände, Spiele, Historien, Verträge und clubgebundener Editordaten entfällt. Nur aufgeführte Konten, Rechte und Schutzdaten bleiben; Dortmund-Szene ist privat gesichert. Die Liga bleibt zunächst unvollständig. Ohne diese konkrete separate Freigabe bei Schritt 5 stoppen.

### 6. Reset — ausschließlich nach dieser Freigabe

Der folgende Befehl ist eine **destruktive manuelle Operatoraktion**, kein Schritt für Replit:

```bash
# NICHT ausführen, bevor Schritt 5 gesondert freigegeben ist.
sha256sum -c "$BACKUP/reset-checksums.txt"
docker compose exec -T db sh -c 'psql -X -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < "$BACKUP/reset-draft.sql"
```

Keine Änderungen zwischen Vorschau und Ausführung. Bei veraltetem Snapshot, Constraint- oder Schutzfehler abgebrochenen Lauf prüfen; niemals Bedingungen aus dem SQL entfernen. Keine FK-/Trigger-Deaktivierung, kein CASCADE. Keine privaten Sicherungen löschen. Keine Sequenzen zurücksetzen; alte Job-/Objekt-IDs sollen nicht neuen Objekten zugeordnet werden.

### 7. Paketmodus aktivieren

Mark ändert in der bestehenden serverlokalen `.env` ausschließlich die betreffenden Schalter:

```text
IMPORT_PACKAGE_MODE=1
IMPORT_PACKAGE_IMAGE_CHECK_ENABLED=1
RUN_MIGRATIONS=0
```

Neue Containerumgebung ist nötig; nur `restart` übernimmt geänderte env_file-Werte nicht sicher:

```bash
docker compose up -d --force-recreate web
```

Alte Celery-Jobs nicht wieder anlaufen lassen. Alte Warteschlangen nach Prüfung gezielt mit dem vorhandenen Celery-Purge-Verfahren bereinigen; **kein Redis FLUSHALL/FLUSHDB**. Beat/Simulationsjobs bleiben bis zur vollständig aufgebauten Liga pausiert. Keine Konten neu anlegen oder Rollen ändern.

### 8. Ausgehende Proxys und Zieladressen prüfen

Mark prüft die **tatsächliche Web- und Worker-Umgebung** auf HTTP_PROXY/HTTPS_PROXY/ALL_PROXY samt Kleinbuchstaben-Varianten sowie ausdrücklich konfigurierte Client-Proxys. Nicht die nginx-HTTPS-Terminierung davor gemeint.

Zieladress-Overrides mit dem bewerteten Code vergleichen; insbesondere `CMTRACKER_BASE_URL` gegenüber dem Standard `https://api.cmtracker.net/api/v1` und andere explizite HTTP-/KI-Client-Basisadressen. Ein abweichender vertrauenswürdiger Anbieter ist nicht automatisch gefährlich, erfordert aber neue Bewertung der bisherigen Annahmen. Keine Schlüssel, Tokens, Passwörter oder Proxy-Adressen mit eingebetteten Zugangsdaten in Chat/Logs ausgeben; nur „gesetzt/abweichend“ und vertraulich geprüftes Ergebnis dokumentieren.

Bei Abweichung vor dem Erstimport stoppen und Erreichbarkeit der aufgeschobenen Bibliotheksbefunde neu bewerten. Ohne Abweichung bleibt die bisherige Code-Einstufung bestehen. Replit hat keine dieser Hetzner-Bedingungen geprüft.

### 9. Bundesliga anlegen, BVB-v3 zuerst importieren

Mark meldet sich mit dem erhaltenen Creator-Konto an, legt die 1. Bundesliga als spielbare Liga an und lädt **bvb_vereinspaket_2026-10-05_v3.zip** über den Import-Knopf hoch. „Spielbar“ ist die richtige Liga-/Pool-Zuordnung, kein Auftrag zum sofortigen Ligastart.

Vorschau prüfen und persönlich bestätigen. Nicht mit v1/v2 initialisieren, keine Pilot-Datenkopie, keine historischen Mini-Clubs nach Namensmatching. Bei Fehlern oder unerwartetem Tabellen-/Sperrenstand nicht erneut blind bestätigen.

### 10. BVB-Erstimport, Szene und Bilder kontrollieren

| Größe | Erstimport-Soll |
|---|---|
| Spieler | 51: 31 Profis, 19 U21, Benkara im Leih-Pool |
| Stärken | 49 |
| Einzelsperren | 2: Takato Yamamoto, Bjarki Gardarsson |
| Paket-Arbeitsliste | 128 offen: 126 Info + 2 Einzelsperren; 0 blocking, 0 erledigt |
| Marktwertpunkte | 637: 631 real + 6 Startwerte |
| Transfers | 322 |
| Rekorde / Titel | 24 / 30 |
| Titel-Kacheln | 8 / 5 / 3 |
| Ø Alter Profis | 24,4 |

Zusätzliche fehlende Bilddateien erzeugen nur Infos oberhalb der 128 Paket-Einträge. Kein Vergleich gegen den Pilot-Reupload-Stand 156/128/28. Bilder auf dem echten Server prüfen, nicht anhand Replits Dateibestand. Gezielten Bildabgleich über den Creator-Knopf durchführen.

Dortmund-Szene anhand des privaten Exports und der Assets erhalten beziehungsweise kontrolliert an das **neu importierte Stadion** zurückzuordnen. Niemals die alte Stadion-ID blind verwenden und keine alten Budget-/Ausbau-/Stärkedaten aus dem Dump zurückladen. Falls die Szene weitere alte FK-/ID-Bezüge enthält, vor dem Wiederherstellen klären. Szenenansichten und Geometrie-/Designwerte mit der Sicherung vergleichen.

### 11. Weitere Vereine nach und nach

Pakete aus dem vorgesehenen Chat in beliebiger Reihenfolge live hochladen, stets Vorschau/Bestätigung. CMTracker-N68 ist bereits korrigiert. Auf neue U21-Verweise und nicht eindeutige Vereinszuordnung achten; gemeldete Abweichungen nicht durch Namensraten lösen.

Erst bei **18 erfolgreich importierten vorgesehenen Vereinen**, null offenen Liga-Startsperren, geprüften Bildern und kontrollierten Betriebsbedingungen den Ligastart separat vornehmen und automatische Jobs kontrolliert aktivieren. Einzelsperren einzelner Spieler verhindern nicht selbst den Ligastart.

## Dortmund-Szenensicherung: getrennt vom Spielbestand

Die Dateien liegen je nach Installation unter `/var/www/assets`, im statischen Codebestand und gegebenenfalls im Medienvolume. Deshalb alle tatsächlich verwendeten Quellen inventarisieren und privat sichern, nicht nur einen angenommenen GLB-Dateinamen.

Die Daten liegen in `stadium_editor.StadiumGeometry` und `stadium_editor.StadiumDesign` an `game.Stadium`. `game.StadionumfeldConfig` ist global geschützt; clubgebundene Umgebungszustände gehören hingegen zum gelöschten Spielbestand und gegebenenfalls zum separat zu sichernden Szenenmaterial.

Beispiel eines **nur lesenden** Exports durch Mark (stdout wird in eine private Datei umgeleitet):

```bash
docker compose run --rm -T --entrypoint python -e IMPORT_PACKAGE_MODE=0 web manage.py shell --verbosity=0 > "$BACKUP/dortmund-scene.json" <<'PY'
import json
from django.apps import apps
from game.models import Club, Stadium
club = Club.objects.get(fm_inside_id=907)
assert club.transfermarkt_id in (None, 16)
stadium = Stadium.objects.get(club=club)
data = {"identity": {"fmi_id": 907, "tm_id": 16},
        "source_club_pk": club.pk, "source_stadium_pk": stadium.pk}
for model_name in ("StadiumGeometry", "StadiumDesign"):
    model = apps.get_model("stadium_editor", model_name)
    data[model_name] = list(model.objects.filter(stadium=stadium).values())
print(json.dumps(data, ensure_ascii=False, default=str))
PY
```

Vor Freigabe prüfen: je ein erwarteter Geometrie-/Designsatz, richtige BVB-Identität, referenzierte Assetdateien vorhanden; fehlenden Designsatz nicht als „gesichert“ ausgeben. Originaldatei unverändert behalten. Die Wiederzuordnung selbst ist **nicht von Replit ausgeführt**: nur geometrische/visuelle Felder in einer kontrollierten Transaktion an das neue Stadion, keine PKs, FK-Altdaten oder alte Spielökonomie kopieren. Weitere per-Club-Szenendaten vor Reset ergänzend exportieren, falls sie zur tatsächlich verwendeten Ansicht gehören.

## Rückkehr zum gesicherten Zustand

Bei Abbruch nach einem Commit: Web, Worker, Beat und externe Schreiber erneut pausieren; neuen vollständigen Diagnose-Dump privat sichern; Sicherungsprüfsummen prüfen. Den getesteten vollständigen Dump in eine **neue** Rückkehrdatenbank wiederherstellen, Schutzdaten und Szene vergleichen. Erst dann die serverlokale Verbindung kontrolliert auf diese DB umstellen; keine teilweise Tabellenrestauration in die beschädigte Datenbank.

Zur gesicherten Datenbank den dazu passenden gesicherten Code-/Altmodus-Stand, `.env` und erforderliche Medien/Assets verwenden. Sicherungen in isolierten Verzeichnissen prüfen, erst nach Zustimmung ersetzen. Nie eine laufende Datenbank mit `pg_restore --clean` überschreiben; nie pauschal `docker compose down -v` verwenden. Container mit passender Umgebung neu erzeugen. Erst nach Prüfung Login/Rechte, Konten-/Profilfelder, Parameterkataloge und Dortmund-Szene wieder freigeben. Alte/private und neue Sicherungen behalten.

## Übergabeprotokoll des Operators

Vor Reset festhalten: Code-/Migrationsstand, Altmodus, pausierte Schreiber, Sicherungsdateien/Prüfsummen, **tatsächlich erfolgreiche Wiederherstellung**, Vergleich der Inventare, Dortmund-Datei-/Szenenprüfung, frische Löschliste/Profilregeln, separate Reset-Freigabe.

Nach Reset festhalten: Transaktionsabschluss und Schutzprüfungen, Paket-/Bildschalter, Proxy-/Zieladressprüfung, BVB-v3-Vorschau/Bestätigung/Sollzahlen, zusätzliche Bildinfos, Szenenprüfung, Anzahl erfolgreich importierter Vereine und Startsperren. Keine privaten Inhalte oder Credentials in ein öffentliches Protokoll aufnehmen.
