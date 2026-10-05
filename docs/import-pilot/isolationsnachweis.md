# T1: Tatsächlicher Isolationsnachweis

Messstand: Mon Oct 05 2026 22:04:38 GMT+0200 (Europe/Berlin) (Europe/Berlin). Replit-Entwicklung, keine Produktions-/Hetzner-Verbindung.

## Ergebnis und Freigabehalt

Die technische Pilot-Trennung ist eingerichtet und anhand realer Direktverbindungen geprüft. Keine Schutzbereichs-/Kontokopie, kein fachliches Datenmodell, kein Paketimport, keine Szene-Sicherung. T2–T5 wurden nicht begonnen.

Dieser Bericht und die gesonderte N17-Konten-Feldliste werden gemeinsam zur Bestätigung vorgelegt. Danach HALT: Kopie und fachliches Modell erst nach Marks ausdrücklicher Bestätigung.

Wichtige Einschränkung zum Bestand: Die Anwendung lief während der Eingabephase weiter und war nicht eingefroren. Seit der frühen Messung änderte sich der Fingerprint von game_managerprofile bei unverändert drei Profilzeilen. Aus einem aggregierten Fingerprint lässt sich die genaue geänderte Spalte oder Ursache nicht rückwirkend feststellen. Es wird daher NICHT behauptet, dass sämtliche Bestandsinhalte während der gesamten Wartezeit unverändert waren. Im engeren abschließenden Prüfintervall blieben alle 159 Bestandstabellen einschließlich ihrer Inhalts-Fingerprints gleich.

## 1. Reale Pilot-Verbindung

| Merkmal | Gemessener Wert |
|---|---|
| Datenbank | heliumdb |
| current_user | import_pilot_role |
| session_user | import_pilot_role |
| search_path | import_pilot |
| current_schema | import_pilot |
| Schema-Eigentümer | import_pilot_role |
| Schema-ACL | {import_pilot_role=UC/import_pilot_role} |
| Rollen-Suchpfad | search_path=import_pilot |
| LOGIN | ja |
| Superuser / CREATEROLE / CREATEDB / REPLICATION / BYPASSRLS / INHERIT | jeweils nein |
| Rollenmitgliedschaften | 0 |

Keine Superuser-Verbindung mit SET ROLE als Laufzeit-Ersatz: current_user und session_user sind tatsächlich import_pilot_role. Der administrative Zugang wurde nach der Einrichtung geschlossen; Bestandsvergleich nur lesend.

## 2. Pilot → public: effektiver Schreibschutz

| Prüfung der tatsächlichen Pilot-Rolle | Ergebnis |
|---|---|
| CREATE im Schema public | nein |
| Tabellenrechte INSERT/UPDATE/DELETE/TRUNCATE/REFERENCES/TRIGGER | 0 Treffer |
| Spaltenrechte INSERT/UPDATE/REFERENCES | 0 Treffer |
| Sequenzrechte USAGE/UPDATE in public | 0 Treffer |
| Ausführbare SECURITY-DEFINER-Funktionen in public | 0 Treffer |
| Geerbte Rollen / Mitgliedschaften | 0 |
| Pilot-FKs mit Ziel in einem anderen Schema | 0 |

Die effektiven Privilegfunktionen berücksichtigen PUBLIC und Rollenrechte; nicht bloß die direkt sichtbaren Grants. Es wurden keine Testschreibungen in den Bestand durchgeführt. Bestehende Rollen und public-ACLs wurden nicht verändert.

Der eigenständige Datenbank-Backend prüft jede neu eröffnete Pilot-Verbindung und schließt sie bei falscher Identität, falschem Suchpfad, fehlendem Schema, privilegierter Rolle oder public-Schreib-/Eskalationsrechten.

## 3. Reale negative Startprüfungen

| Startbedingung | Ergebnis |
|---|---|
| public_fallback | Start abgewiesen: Pilot requires a direct pilot-role connection and exact pilot schema. |
| user_fallback | Start abgewiesen: Pilot requires a direct pilot-role connection and exact pilot schema. |
| missing_schema | Start abgewiesen: Pilot requires a direct pilot-role connection and exact pilot schema. |
| maintenance_identity | Start abgewiesen: Pilot requires a direct pilot-role connection and exact pilot schema. |
| worker | Start abgewiesen: Pilot workers and schedulers are disabled. |
| beat | Start abgewiesen: Pilot workers and schedulers are disabled. |

public_fallback verwendet import_pilot,public; user_fallback enthält ausdrücklich $user. Der Fehlendes-Schema-Test verwendet eine direkte Pilot-Anmeldung an der lokalen Standarddatenbank postgres, in der import_pilot nicht existiert. Es wurde dafür kein Schema gelöscht oder umbenannt und keine andere Datenbank angelegt. maintenance_identity ist ein reiner Negativtest, keine Pilot-Laufzeitkonfiguration. worker/beat prüfen den ausdrücklichen Startabbruch, ohne einen Worker oder Scheduler zu starten.

## 4. Eigener technischer Zustand

| Pilot-Tabelle | Zeilen |
|---|---:|
| import_pilot.django_migrations | 1 |
| import_pilot.django_session | 0 |

Einzige Migration: sessions / 0001_initial. Eigener Recorder, keine Übernahme von public.django_migrations (dort 215 Zeilen) und keine übernommenen Sitzungen (public.django_session: 442 Zeilen).

Installierte Apps ausschließlich import_pilot.apps.ImportPilotConfig und django.contrib.sessions. core, game, showauction, stadium_editor und celery waren im Prüfprozess nicht importiert. Keine bestehenden Game-Signale, Seeds oder Datenmigrationen wurden aktiviert.

Ein rein synthetischer Pilot-Session-Test wurde gespeichert, erfolgreich gelesen und gelöscht. Nach Cleanup: 0 Pilot-Sitzungen. Keine Anmeldung oder Kontokopie vorgenommen.

Alle fachlichen Pilot-Tabellen für Konten/Profile, Vereine, Spieler, Stadien, Ligen, Wettbewerbe, Spielstände und die elf N16-Bereiche sind NICHT ANGELEGT. Nicht als '0 Zeilen' ausgeben: die Modelle und Tabellen fehlen absichtlich.

## 5. Sitzungen, CSRF, Cache und Dateien

| Bereich | Konfiguration / realer Test |
|---|---|
| Session-Cookie | import_pilot_sessionid |
| CSRF-Cookie-Name | import_pilot_csrftoken |
| CSRF-Speicherung | CSRF_USE_SESSIONS=true: Token in eigener Pilot-Sitzung; normalerweise kein separater CSRF-Cookie nötig |
| Signierung | eigener, zweckgebunden abgeleiteter Pilot-Signierschlüssel; keine Schlüssel-Fallbacks |
| Cache | prozesslokaler LocMemCache, Location websoccer-import-pilot, Prefix import_pilot |
| Uploadziel | .local/import_pilot/uploads/ |
| Originalbilder | vorhandenes ASSETS_ROOT nur über ReadOnlyAssetStorage lesbar |

Die vom Nutzer bereitgestellten Pilot-Eingaben wurden ohne starre 32-Zeichen-Mindestgrenze akzeptiert. Die Sitzungs-Signierung wird mit eigenem Pilot-Kontext abgeleitet. Keine Werte, Signaturen oder Sitzungsschlüssel erscheinen im Bericht. Das Pilot-Datenbankpasswort ist nicht das Wartungspasswort.

Reale Tests: Pilot-Cache setzen/lesen und nur Testschlüssel löschen; kein globaler Flush. Pilot-Upload speichern/lesen/löschen im eigenen Ziel; danach 0 verbleibende Dateien. Ein bestehendes Originalbild erfolgreich lesend geöffnet. save(), delete() und Öffnen im Schreibmodus wurden durch die Originalbild-Storage abgewiesen. Das ist ein Schutz der verwendeten Storage-API, keine behauptete neue Betriebssystem-Sandbox. Bestehende Dateirechte und Originalbilder wurden nicht verändert.

## 6. Bestand → Pilot nach N14

Der Bestand bleibt absichtlich auf seiner bisherigen Rolle und Verbindung. Eine gegenseitige harte ACL-Abschirmung wurde nach N14 NICHT eingerichtet.

| Kontrolle | Befund |
|---|---|
| Bestehende Verbindung | current_user=session_user=postgres |
| Bestehender search_path | "$user", public; enthält import_pilot nicht |
| Laufender Webprozess | core.settings, gleiche bestehende DATABASE_URL; kein Pilot-Verweis |
| Laufende Hauptprozess-PIDs | 128, 306; unverändert vorhanden |
| Bestehender Code / Commands / .replit | keine ausführbaren Pilot-Verweise außerhalb der neuen expliziten Pilot-Infrastruktur |
| Tatsächliche Worker-/Beat-Prozesse | 0 gefunden; kein Pilot-Worker/Beat |
| Pilot-Schedule | leer |
| Pilot-Broker | memory://; keine bestehende Redis/RabbitMQ-Queue |
| Pilot-Webworkflow | keiner angelegt; Bestandsworkflow nicht geändert oder neu gestartet |

Pilot-Einstellungen werden nur ausdrücklich als import_pilot.settings geladen, nicht über core.settings. Der Pilot-Health-Endpunkt wurde im getrennten Django-Prozess mit realer Pilot-DB-Verbindung geprüft: HTTP 200, infrastructure-only. Kein dauerhaft laufender zusätzlicher Dienst oder Scheduler wurde eingerichtet.

## 7. Bestandskontrolle und ihre Grenzen

Frühe Kontrollmessung: 2026-10-05T19:50:12.827535+00:00. Abschließender Prüfstand: 2026-10-05T20:04:38.435383+00:00.

- 159 public-Tabellen; alle Zeilenzahlen gegenüber der frühen Messung gleich.
- 158 Tabellen auch mit unverändertem Inhalts-Fingerprint über den gesamten Zeitraum.
- Einzige Fingerprint-Abweichung gegenüber der frühen Messung: game_managerprofile, weiterhin 3 Zeilen. Ursache/Feld nicht aus dieser Messung bestimmt; keine Bestands-Schreibkorrektur vorgenommen.
- Im abschließenden Vorher/Nachher-Prüfintervall: 159/159 Tabellen mit gleicher Zeilenzahl UND gleichem Inhalts-Fingerprint.
- Bestehende Rollenattribute/Suchpfade, public-Schema-ACL, Objekt-Eigentümer/ACLs und public-Constraints stimmen mit der frühen Kontrollmessung überein.
- SHA-256-Vergleich identisch für core/settings.py, core/__init__.py, core/celery.py, core/urls.py, manage.py, .replit, game/apps.py und game/signals.py.
- Bestandskontrollzahlen: Vereine 28, Spieler 828, Stadien 22, Ligen 5, Pokalsaisons 1, simulierte Spiele 201.

Fingerprints wurden serverseitig berechnet; keine Bestandszeilen, Kontoinhalte oder Passwort-Hashes wurden exportiert. Der Snapshot ist kein eingefrorenes Backup. Vor einer später autorisierten Kopie ist ein neuer konsistenter Quellstand erforderlich.

## 8. N16: bestätigte Schutzliste, weiterhin nicht kopiert

| Quelltabelle | Gemessene Quellzeilen | Pilot |
|---|---:|---|
| game_economyparameter | 77 | nicht angelegt / nicht kopiert |
| game_countrynetwork | 0 | nicht angelegt / nicht kopiert |
| game_stadionumfeldconfig | 1 | nicht angelegt / nicht kopiert |
| game_datasource | 5 | nicht angelegt / nicht kopiert |
| game_strengthformulasettings | 1 | nicht angelegt / nicht kopiert |
| game_strengthmodifierrule | 15 | nicht angelegt / nicht kopiert |
| game_mediaoutlet | 24 | nicht angelegt / nicht kopiert |
| showauction_showauctionpreset | 5 | nicht angelegt / nicht kopiert |
| game_storysettings | 0 | nicht angelegt / nicht kopiert |
| game_neutralvenue | 0 | nicht angelegt / nicht kopiert |
| game_landkoeffizient (nur saison=0) | 9 | nicht angelegt / nicht kopiert |

Die elf Tabellen enthalten in diesem Umfang derzeit zusammen 137 Quellzeilen. Diese Zeilen wurden NICHT in den Pilot übernommen. Bei LandKoeffizient bleiben alle anderen Saisons ausgeschlossen.

## 9. Belege und nächster Freigabehalt

Technische Infrastruktur: import_pilot/ und scripts/setup_import_pilot.py. Reproduzierbarer Prüfer: scripts/verify_import_pilot.py. Messdaten ohne Secrets: docs/import-pilot/evidence.json. Die N17-Liste klassifiziert alle 32 Profilspalten sowie direkte und zusätzliche indirekte Manager-/Kontotabellen.

HALT. Keine Schutzbereichs-/Kontokopie, kein fachliches Datenmodell, kein Paketimport und keine Szene-Sicherung beginnen, bevor Mark den tatsächlichen Nachweis UND die N17-Feldliste ausdrücklich bestätigt hat. Hetzner bleibt unberührt.
