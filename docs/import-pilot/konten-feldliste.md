# N17: Konten-Feldliste zur Bestätigung

Status: VORSCHLAG, keine Kopie ausgeführt. Erfasst anhand der aktuellen SQL-Spalten und der vorhandenen Modelle.

'Wird auf null gesetzt' bezeichnet fachlichen Neustart, nicht pauschal SQL NULL: numerische Zähler 0, boolsche Marker false, JSON {}, nullable Beziehungen/Datum NULL. Kein Nullability-/Schemaumbau im Bestand.

| ManagerProfile-Feld | Aktion | Ziel / Begründung |
|---|---|---|
| id | bleibt | Stabile Profil-ID |
| user_id | bleibt | Zuordnung zum übernommenen Konto |
| name | bleibt | Managername |
| trainer_type | bleibt | Gewählte Profileinstellung; keine Titel-/XP-Freischaltungen kopieren |
| nationality_flag | bleibt | Profilangabe |
| nationality_name | bleibt | Profilangabe |
| member_since | bleibt | Kontozugehörigkeit |
| birth_date | bleibt | Profilangabe |
| profile_image | bleibt | Profilbildreferenz; keine Mannschaftsfotos |
| name_confirmed | bleibt | Namenseinstellung |
| residence | bleibt | Profilangabe |
| visibility_settings | bleibt | Sichtbarkeitseinstellungen |
| xp_max | bleibt | Schwellen-/Darstellungswert, kein erreichter XP-Stand |
| xp | wird auf null gesetzt | 0 |
| level | wird auf null gesetzt | 0 ausdrücklich nach N6, nicht still Modell-Default 1 |
| highscore | wird auf null gesetzt | Leerer Anzeigewert –; Feld ist nicht SQL-nullable |
| active_title | wird auf null gesetzt | SQL NULL |
| title_progress | wird auf null gesetzt | Leeres Objekt {} |
| season_score | wird auf null gesetzt | 0 |
| previous_season_score | wird auf null gesetzt | 0 |
| inactivity_season_count | wird auf null gesetzt | 0 |
| inactivity_streak | wird auf null gesetzt | 0 |
| transfer_ban_until | wird auf null gesetzt | SQL NULL |
| login_streak | wird auf null gesetzt | 0 |
| login_last_date | wird auf null gesetzt | SQL NULL |
| login_points_today | wird auf null gesetzt | 0 |
| login_day14_awarded | wird auf null gesetzt | false |
| login_day30_awarded | wird auf null gesetzt | false |
| login_day30_money_paid | wird auf null gesetzt | false |
| last_seen | wird auf null gesetzt | SQL NULL |
| favourite_club_id | wird auf null gesetzt | SQL NULL: alter Vereinsbezug |
| updated_at | wird nicht kopiert | Bei späterer Übernahme technisch neu erzeugen |

Datenbankbefund: 32 tatsächliche Profilspalten. implizites id ist enthalten. trainer_type und xp_max sind Vorschläge zur Bestätigung: Einstellung/Schwelle bleiben, erreichte Freischaltungen entfallen. Keine Übernahme anhand von Managername; Konto-/Profil-ID-Zuordnung kontrollieren. Club.managed_by und alle sonstigen alten Vereinsbindungen bleiben leer.

Kontotabellen: auth_user id/password/username/first_name/last_name/email/is_superuser/is_staff/is_active/date_joined/last_login vorgeschlagen 'bleibt' (nur vorhandene Passwort-Hashes intern im später autorisierten Kopierprozess, niemals im Bericht). auth_group id/name und Benutzer-Gruppenzuordnung vorgeschlagen 'bleibt'. Rollen und Einzelrechte bleiben fachlich erhalten, ContentTypes/Permissions werden nach (app_label, model, codename) auf die Pilot-Struktur abgebildet; keine zufällige Fremdschlüssel-ID-Gleichheit voraussetzen. django_content_type/auth_permission-IDs werden nicht blind kopiert; technische Zielzeilen erst im späteren Modell-/Kontokopierschritt anlegen. Bestehende django_session und django_migrations werden nicht kopiert.

Die folgenden im tatsächlichen FK-Inventar gefundenen Tabellen werden vorgeschlagen vollständig NICHT kopiert (alle ihre Felder einschließlich IDs, Manager-/Benutzer-FKs, JSON und Dateien); je Tabelle im endgültigen N17-Bericht aufführen:
- django_admin_log: wird nicht kopiert.
- game_club: wird nicht kopiert.
- game_clubnewsitem: wird nicht kopiert.
- game_clubplayerimportjob: wird nicht kopiert.
- game_clubrecord: wird nicht kopiert.
- game_clubrecordcorrectionrequest: wird nicht kopiert.
- game_cointransaction: wird nicht kopiert.
- game_communitysubmission: wird nicht kopiert.
- game_creatoractionlog: wird nicht kopiert.
- game_cupfixture: wird nicht kopiert.
- game_forcedauctionbid: wird nicht kopiert.
- game_hoenesscoin: wird nicht kopiert.
- game_inactivitypenalty: wird nicht kopiert.
- game_inactivityrecord: wird nicht kopiert.
- game_managercareerentry: wird nicht kopiert.
- game_managercareerstation: wird nicht kopiert.
- game_managercompetitiontitle: wird nicht kopiert.
- game_managernotes: wird nicht kopiert.
- game_managerseasonscore: wird nicht kopiert.
- game_managerteamphoto: wird nicht kopiert.
- game_managertimelineentry: wird nicht kopiert.
- game_managertitle: wird nicht kopiert.
- game_managervacationblock: wird nicht kopiert.
- game_notification: wird nicht kopiert.
- game_playereditlog: wird nicht kopiert.
- game_playereditrequest: wird nicht kopiert.
- game_presidentsatisfaction: wird nicht kopiert.
- game_scoutingassignment: wird nicht kopiert.
- game_scoutingbid: wird nicht kopiert.
- game_sourceimportrun: wird nicht kopiert.
- game_storyaudit: wird nicht kopiert.
- game_supportticket: wird nicht kopiert.
- game_watchlistentry: wird nicht kopiert.
- showauction_showauction: wird nicht kopiert.
- showauction_showauctionbid: wird nicht kopiert.

Damit entfallen auch ManagerNotes und SupportTicket als nicht von Konto/Profil/Settings gedeckte Inhalte; dies ist ein sichtbarer Vorschlag, keine bereits genehmigte Löschung. HoenessCoin wird nicht übernommen, neues Guthaben fachlich 0; keine Erzeugung in dieser Aufgabe. Weitere indirekte Manager-/Benutzerbezüge durch Texte, JSON und Reverse-Relationen prüfen und gegebenenfalls ergänzen.

## Konten und Berechtigungen: einzelne Feldentscheidungen

Alle Entscheidungen sind Vorschläge. In dieser technischen Isolationsphase werden keine Auth-, Profil- oder Berechtigungsmodelle installiert und keine Zeilen kopiert.

| Tabelle | Feld(er) | Aktion | Ziel |
|---|---|---|---|
| auth_user | id, password, last_login, is_superuser, username, first_name, last_name, email, is_staff, is_active, date_joined | bleibt | Vorhandenes Login einschließlich internem Passwort-Hash, Rollen und Kontodaten; keine Ausgabe von Werten |
| auth_group | id, name | bleibt | Bestehende Gruppen |
| auth_user_groups | id, user_id, group_id | bleibt | Bestehende Gruppenzuordnungen |
| auth_user_user_permissions | id, user_id | bleibt | Bestehende Konto-Zuordnung |
| auth_user_user_permissions | permission_id | bleibt | Inhaltlich dasselbe Recht; ID nach natürlichem Schlüssel neu zuordnen |
| auth_group_permissions | id, group_id | bleibt | Bestehende Gruppen-Zuordnung |
| auth_group_permissions | permission_id | bleibt | Inhaltlich dasselbe Recht; ID nach natürlichem Schlüssel neu zuordnen |
| auth_permission | id | wird nicht kopiert | Technische Ziel-ID, keine blinde Übernahme |
| auth_permission | name, codename, content_type_id | bleibt | Fachlich erhalten; ContentType-Ziel über app_label/model zuordnen |
| django_content_type | id | wird nicht kopiert | Technische Ziel-ID |
| django_content_type | app_label, model | bleibt | Natürlicher Schlüssel; im später genehmigten Zielmodell neu auflösen |
| django_session | alle Felder | wird nicht kopiert | Eigene Pilot-Sitzungen, keine Anmeldung aus Bestands-Sessions |
| django_migrations | alle Felder | wird nicht kopiert | Eigener Pilot-Migrationsstand |

Die Formulierung 'bleibt' bei Permission-/ContentType-FKs meint gleiche Bedeutung, nicht garantiert gleiche numerische ID. Rechte zu im Ziel noch nicht vorhandenen Modellen dürfen nicht still verworfen werden: dann vor Kontokopie melden und Entscheidung einholen. Ebenso bedürfen Profile ohne verknüpftes Login-Konto einer expliziten Übernahmeentscheidung; diese Feldliste filtert sie nicht eigenmächtig.

## Indirekte Bezüge und Dateien

Die direkt accountbezogenen Tabellen stammen aus den tatsächlichen PostgreSQL-Fremdschlüsseln, nicht nur aus Modellnamen. Zusätzlich wurden benutzer-/managerähnliche Spaltennamen im SQL-Katalog geprüft. JSON- und Freitextfelder sind dadurch nicht pauschal als referenzfrei bewiesen.

- game_matchevent (einschließlich actors-JSON): wird nicht kopiert; Ereignis-/Spielhistorie.
- game_matchstory und game_matchstoryround (einschließlich taktischer Snapshots, state, payloads und source keys): wird nicht kopiert; Spielhistorie, kein Kontoprofil.
- game_friendlyfixture: wird nicht kopiert; managerinitiierte Anfragen und Freundschaftsspielhistorie mit Vereinsbezug.
- game_communitytournament: wird nicht kopiert; managerinitiierte Turniere, Veranstalterverein, Regeln und Preispläne.
- game_communitytournamententry: wird nicht kopiert; Teilnehmervereine, Auslosung und Endplatzierungen.
- game_communitytournamentapplication: wird nicht kopiert; alte Bewerbungen und deren Status.
- game_communitytournamentphase: wird nicht kopiert; alte Wettbewerbsphasen.
- game_communitytournamentround: wird nicht kopiert; alte Wettbewerbsrunden.
- game_communitytournamentstanding: wird nicht kopiert; alte Tabellen und Statistiken.
- game_communitytournamentmatch: wird nicht kopiert; alte Begegnungen und Ergebnisse.
- game_clubrecordbreak: wird nicht kopiert; indirekte Rekord-/Managerhistorie über ClubRecord.
- showauction_showauctionwatch: wird nicht kopiert; alte Beobachtungsliste über Auktion/Verein, keine Kontoeinstellung.
- Alle sonstigen Sim-/Vereins-/Spieler-/Turnier-/Transfer-/Finanzzustände bleiben außerhalb der Kontokopie. Keine FKs, IDs in JSON, URL oder Datei dürfen über ausgelassene Tabellen doch Bestands-Spielstände importieren.
- Profilbildreferenz bleibt vorgeschlagen erhalten, lesender Originalzugriff. Kein Mannschaftsfoto, Support-Anhang, Timeline- oder Karrierebild wird darüber mitkopiert.
- Es werden in dieser Phase weder Originaldateien gelöscht noch Medien oder Profilbilder kopiert. Für später: Zielbilder/Uploads getrennt schreiben, bestehende Originale nicht überschreiben.

## Offene Bestätigungspunkte

Besonders sichtbar zu bestätigen: trainer_type trotz XP/Level-Neustart, xp_max als Schwellenwert, Level ausdrücklich 0 statt Bestandsdefault 1, Zurücksetzen der Loginbelohnungen, kein altes Coin-Guthaben, ManagerNotes/SupportTicket nicht übernehmen, Zeitstempelbehandlung und Rechte-Mapping.

N17 ist keine Kopierfreigabe. Erst gemeinsam mit dem tatsächlichen Isolationsnachweis vorlegen, dann Halt bis Marks ausdrücklicher Bestätigung.

Kontrollstand: Alle 32 tatsächlichen ManagerProfile-Spalten sind genau einmal klassifiziert. Alle 38 Tabellen mit direktem FK auf auth_user oder game_managerprofile sind in dieser Liste berücksichtigt; weitere oben genannte indirekte Historientabellen sind ausdrücklich ausgeschlossen. Tabellen ohne aktuelle Zeilen sind dennoch klassifiziert; ihre Leere ersetzt keine Entscheidung.
