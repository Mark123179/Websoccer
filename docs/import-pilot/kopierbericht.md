# T1 / N22: Kopierbericht der Schutzbereiche

**Status: Kopie abgeschlossen; anschließend HALT vor dem fachlichen Datenmodell.**

Grundlage: Nachtrag 4 (N18–N22), bestätigte N17-Feldliste mit N19-Korrektur und ausdrückliche Entscheidung, Berechtigungen für noch nicht geladene Modelle als Metadaten zu erhalten. Dieser Bericht ersetzt keine Modellplan-, Paketimport- oder Live-Freigabe.

## 1. Quellstand und Ausführung

- Ausschließlich lokale Replit-Entwicklungsdatenbank; kein Hetzner-/Produktionszugriff.
- Neuer gemeinsamer Quellstand: **05.10.2026, 22:35:54.743392 Uhr Europe/Berlin**; PostgreSQL-Snapshot `2800971:2800971:`.
- Alle Schutzbereiche wurden aus derselben schreibgeschützten `REPEATABLE READ`-Transaktion gelesen, nicht aus voneinander unabhängigen Momentaufnahmen.
- Ziel ausschließlich `import_pilot`, direkte Verbindung als `import_pilot_role`; exakt dieser Suchpfad, ohne `public`-Fallback.
- Zieltabellen und Inhalte wurden in einer einzigen Transaktion angelegt und kopiert. Commit: **22:35:56.733162 Uhr Europe/Berlin**.
- Quellzeilen einschließlich Passwort-Hashes wurden ausschließlich intern über einen Speicherpuffer transportiert. Keine Kontodaten, Hashes oder Medienexporte in Berichten, Dateien oder Logs.
- Keine Django-Spielmodelle, Signals, alten Datenmigrationen oder Jobs ausgeführt. Die Pilot-App-Liste bleibt `import_pilot` + `sessions`.

## 2. Gemessene Kopie

| Tabelle | Quellumfang im Snapshot | Im Pilot | Behandlung |
|---|---:|---:|---|
| `game_referee` | 463 | 463 | Katalog vollständig |
| `game_sponsor` | 504 | 504 | Katalog vollständig |
| `auth_user` | 3 | 3 | Alle bestätigten Kontofelder erhalten |
| `game_managerprofile` | 3 | 3 | N19/N21-Startwerte, siehe Abschnitt 4 |
| `auth_group` | 0 | 0 | Tabelle vorhanden, keine Quellgruppen |
| `auth_user_groups` | 0 | 0 | Keine Quellzuordnungen |
| `auth_user_user_permissions` | 0 | 0 | Keine Einzelzuweisungen |
| `auth_group_permissions` | 0 | 0 | Keine Gruppenzuweisungen |
| `django_content_type` | 157 | 157 | Natürlicher Schlüssel, neue Ziel-IDs |
| `auth_permission` | 628 | 628 | Natürlicher Schlüssel, neue Ziel-IDs; Metadaten |
| `game_economyparameter` | 77 | 77 | 1:1 |
| `game_countrynetwork` | 0 | 0 | 1:1, Tabelle vorhanden |
| `game_stadionumfeldconfig` | 1 | 1 | 1:1 |
| `game_datasource` | 5 | 5 | 1:1 |
| `game_strengthformulasettings` | 1 | 1 | 1:1 |
| `game_strengthmodifierrule` | 15 | 15 | 1:1, FK nur innerhalb des Piloten |
| `game_mediaoutlet` | 24 | 24 | 1:1 |
| `showauction_showauctionpreset` | 5 | 5 | Nur Preset-Katalog, keine Auktionen |
| `game_storysettings` | 0 | 0 | 1:1, keine Geschichten |
| `game_neutralvenue` | 0 | 0 | Vollständige Tabelle, hier leer |
| `game_landkoeffizient` | 9 gesamt; 9 für Saison 0 | 9 | Ausschließlich `saison='0'` |

**Elf N16-Tabellen: 137 Zeilen.** Diese Zahl wurde im neuen Snapshot erneut gemessen; sie ist nicht aus dem älteren Bericht übernommen.

21 kopierte Tabellen plus die zwei vorher vorhandenen technischen Tabellen ergeben 23 Pilot-Tabellen. `django_session` bleibt leer. Der eigene Migrationsstand (`sessions/0001_initial`) bleibt unverändert; kein Bestands-Migrationsstand wurde kopiert. Die neuen Tabellen sind Schutzdaten-Speicher, keine vorgezogene Implementierung der B6-Spielmodelle.

## 3. Katalog- und Rechtegrenzen

**Schiedsrichter:** Identität, Katalogattribute und die `vorsaison_*`-Felder bleiben erhalten. Die letztgenannten Felder werden vom Katalogimport/Creator gepflegt; aktuelle Sim-Statistiken werden separat aus `SimulatedMatch.report_data` berechnet. Keine Spielberichte, Einsätze oder Sim-Zähler übernommen.

**Sponsoren:** Ausschließlich `id`, `slug`, `name`, `display_name`, `bereich`, `branche`, `aktiv`, `created_at`, `domain`. Keine Verträge, Angebote oder Erträge.

**Rechte:** Vor der Kontokopie gemeldet und ausdrücklich entschieden: 156 ContentTypes / 624 Berechtigungen verweisen auf derzeit nicht geladene Modelle. Alle 157 ContentTypes und 628 Rechte bleiben als Metadaten erhalten; weder Anmeldung noch Rechteauswertung oder fehlende Spielmodelle wurden im Pilot aktiviert. Auch die vier Session-Rechte sind derzeit nur gespeicherte Katalogeinträge. Späteres Laden von Auth/Rechteauswertung benötigt eine kontrollierte Zuordnung zu den dann vorhandenen Modellen.

Zuordnung über `(app_label, model)` bzw. `(app_label, model, codename)`, nicht durch Gleichsetzung der Quell-IDs. **151 ContentType-IDs und 616 Permission-IDs unterscheiden sich tatsächlich vom Bestand.** Alle Zuordnungstabellen wurden berücksichtigt; im Snapshot sind Gruppen-, Benutzergruppen- und Rechtezuweisungen jeweils leer. Keine Rechte verworfen. Konten und Profile behalten ihre bestätigten IDs und Zuordnungen. **0 Profile ohne Login-Konto.**

## 4. Profilfelder: endgültige Übernahme

Alle 32 tatsächlichen Spalten sind erfasst:

| Feld | Ergebnis |
|---|---|
| `id` | erhalten |
| `user_id` | erhalten, FK auf Pilot-Konto |
| `name` | erhalten |
| `trainer_type` | erhalten |
| `nationality_flag` | erhalten |
| `nationality_name` | erhalten |
| `member_since` | erhalten |
| `birth_date` | erhalten |
| `profile_image` | Referenz erhalten, keine Datei kopiert |
| `name_confirmed` | erhalten |
| `residence` | erhalten |
| `visibility_settings` | erhalten |
| `level` | 1 |
| `xp` | 0 |
| `xp_max` | 800 |
| `highscore` | leerer Anzeigewert `–` |
| `active_title` | NULL |
| `title_progress` | `{}` |
| `season_score` | 0 |
| `previous_season_score` | 0 |
| `inactivity_season_count` | 0 |
| `inactivity_streak` | 0 |
| `transfer_ban_until` | NULL |
| `login_streak` | 0 |
| `login_points_today` | 0 |
| `login_last_date` | NULL |
| `login_day14_awarded` | false |
| `login_day30_awarded` | false |
| `login_day30_money_paid` | false |
| `last_seen` | NULL |
| `favourite_club_id` | NULL; kein FK auf den Bestandsverein |
| `updated_at` | technisch neu erzeugt, nicht aus dem Bestand kopiert |

Keine Coin-Tabelle oder Coin-Buchung übernommen oder erzeugt. Neustart-Guthaben fachlich 0; die spätere Spielstandinitialisierung ist noch nicht umgesetzt.

## 5. Ausgeschlossene Tabellen und Dateien

Die 35 in N17 ausgeschlossenen direkten Konto-/Profilbezüge wurden **nicht angelegt und nicht kopiert**:

- `django_admin_log`
- `game_club`
- `game_clubnewsitem`
- `game_clubplayerimportjob`
- `game_clubrecord`
- `game_clubrecordcorrectionrequest`
- `game_cointransaction`
- `game_communitysubmission`
- `game_creatoractionlog`
- `game_cupfixture`
- `game_forcedauctionbid`
- `game_hoenesscoin`
- `game_inactivitypenalty`
- `game_inactivityrecord`
- `game_managercareerentry`
- `game_managercareerstation`
- `game_managercompetitiontitle`
- `game_managernotes`
- `game_managerseasonscore`
- `game_managerteamphoto`
- `game_managertimelineentry`
- `game_managertitle`
- `game_managervacationblock`
- `game_notification`
- `game_playereditlog`
- `game_playereditrequest`
- `game_presidentsatisfaction`
- `game_scoutingassignment`
- `game_scoutingbid`
- `game_sourceimportrun`
- `game_storyaudit`
- `game_supportticket`
- `game_watchlistentry`
- `showauction_showauction`
- `showauction_showauctionbid`

Auch die ausdrücklich erfassten indirekten Historientabellen fehlen:

- `game_matchevent`
- `game_matchstory`
- `game_matchstoryround`
- `game_friendlyfixture`
- `game_communitytournament`
- `game_communitytournamententry`
- `game_communitytournamentapplication`
- `game_communitytournamentphase`
- `game_communitytournamentround`
- `game_communitytournamentstanding`
- `game_communitytournamentmatch`
- `game_clubrecordbreak`
- `showauction_showauctionwatch`

Alle weiteren Spieler-, Vereins-, Liga-, Stadion-, Spiel-, Transfer- und Finanzzustände sind ebenfalls außerhalb der Kopie. Keine Originaldatei gelöscht, verändert oder kopiert. Profilbildreferenzen bleiben lesbar; Nationencodes, Mappings und Bilddateien bleiben im unveränderten Originalbestand. Keine Dortmund-Szenensicherung und kein Paketimport.

## 6. Verifikation und Aussagegrenzen

- Für jede Kopiertabelle: Zeilenzahl **und vollständiger Datenbank-Inhaltsfingerprint** mit dem erwarteten Snapshot-Ergebnis verglichen. Bei Profilen einschließlich aller bestätigten Transformationen; bei Rechten einschließlich natürlicher Schlüssel; bei Landeskoeffizienten einschließlich Saisonfilter. Alle Vergleiche bestanden.
- Nach Commit erneut verbunden: alle 21 Zeilenzahlen bestätigt; der vollständige Rollen-/Suchpfad-/Public-Schreibschutz-Guard erneut bestanden.
- Zusätzliche Nachprüfung: alle 3 persistierten Profile erfüllen sämtliche bestätigten Startwerte; Pilot-Tabellenliste entspricht exakt der Freigabeliste; alle Pilot-Tabellen und Sequenzen gehören `import_pilot_role`. Pilot-Health antwortet mit HTTP 200. Erneuter Kopieraufruf verweigert den befüllten Zielbestand ohne Schreibwirkung.
- Pilot-FKs ausschließlich innerhalb `import_pilot`; **0 schemaübergreifende FKs**. Keine Default-Verweise auf Public-Sequenzen; neue Identitätssequenzen gehören dem Pilot, Stände an kopierte IDs angepasst.
- Sämtliche PK-/Unique-/Check-Constraints und ergänzenden Indizes der kopierten Tabellen übernommen. Konto-, Gruppen-, Rechte-, Profil- und Regel-FKs geprüft. Der ausgeschlossene Lieblingsverein ist NULL und zusätzlich durch einen Pilot-Check gesichert.
- Neue, unabhängige Quelltransaktion nach der Kopie: **alle 159 Bestandstabellen unverändert** gegenüber dem gemeinsamen Quellstand, einschließlich Inhaltsfingerprints. Public-ACLs, Rollenattribute, Constraints und Sequenzstände ebenfalls unverändert.
- Bestehende Anwendungsdateien (`core`, `game`, `showauction`, `stadium_editor`, `manage.py`, `.replit`) und laufende Runserver-Prozesse unverändert. Kein Neustart und keine Änderung der Anwendungseinstellungen.
- Bestehende Start-/Anmeldeseite nach der Kopie visuell geprüft: lädt weiterhin vollständig. Kein Login-Test mit übernommenen Konten und keine Pilot-Anmeldung durchgeführt.
- Zwei abgebrochene technische Vorläufe wurden vollständig zurückgerollt. Fehlende Public-Leserechte der Pilot-Rolle wurden nicht erweitert; Ziel-DDL wurde stattdessen aus lesend ermittelten Metadaten aufgebaut.

Die Unverändertheitsprüfung bezieht sich auf den Kopierlauf, nicht auf eine dauerhafte Schreibpause der weiterlaufenden Anwendung. Dies ist **kein Nachweis einer funktionsfähigen Pilot-Anmeldung oder der T4-Seiten**; diese wurden nicht implementiert. Die frühere technische Isolation bleibt in `isolationsnachweis.md` dokumentiert, ihre Aussage „nur zwei technische Tabellen“ bezeichnet den damaligen Stand.

**Maschinenbeleg:** `docs/import-pilot/copy-evidence.json`  
**Kopierwerkzeug:** `scripts/copy_import_pilot_protected.py`, verweigert eine Wiederholung in einen bereits befüllten Pilot.

## 7. Halt

Zusammen mit diesem Bericht liegt `modellplan.md` zur Freigabe vor. **Jetzt HALT.** Fachliches Datenmodell erst nach ausdrücklicher Modellplan-Freigabe. T2–T5, Paketimport, Dortmund-Szenensicherung, Live-Reset und Hetzner bleiben gesperrt.
