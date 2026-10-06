# T1-Bericht – Import-Neuaufbau

**Stand 06.10.2026 · HALT nach T1.** N28–N31 eingearbeitet; kein Paketimport, kein Creator-Upload, keine Dortmund-Szenensicherung, kein T2–T5 und kein Hetzner-Zugriff.

**Abnahme-Einschränkung:** Der komplette Bytegleichheitsnachweis für public ist nicht grün. Bei identischen Zeilenzahlen änderte sich der Fingerprint von game_managerprofile. Kein Rückschreiben und kein Verbergen dieser Abweichung; Details Punkt 7.

## 1. Tatsächliche Migration und Modelländerungen

**Migration:** game/migrations/0187_import_rebuild_n28_n31.py. 216 reguläre Migrationseinträge im Pilot, keine offenen Migrationen und kein --fake/--fake-initial.

Neu: genau zwei fachliche Tabellen (game_clubtrophyentry, game_importissue). 123 neue Spalten einschließlich deren Spalten; 18 geänderte Felddefinitionen; 0 physische Spaltenlöschungen. **Die vollständige Einzelspalten-/Typ-/Nullbarkeitsliste und Constraints stehen in t1-schema-spalten.md.**

Erweitert: Club, Stadium, Player, PlayerExternalId, ClubExternalId, HistoricCoach, PlayerSourceRatingSnapshot, PlayerMarketValueSnapshot, PlayerTransferHistory, ClubRecord, ClubTrophy und SourceImportRun. Pflicht-Liga bleibt erhalten; import_state nur spielbar/nicht_spielbar. Zwölf reale Seitenkapazitäten mit zwölf Kennzeichen getrennt von zwölf nullable aktuellen Seitenkapazitäten; zusätzlich belegte nationale/aggregierte Gesamtwerte.

Nicht angelegt: drei Real-Leihspalten und package_file. Archiventscheidung: ausschließlich JSON (package_data + manifest), nicht zusätzlich eine Datei. N29 erforderte vier zusätzliche operative TM-/Originalname-Spalten für Stamm-/Leihverein. Das sind die freigegebenen Auflagen, keine neuen Tabellen.

**Übergangsaktivierung:** IMPORT_REBUILD_SCHEMA schaltet dieselben bestehenden Game-Klassen mit ihren gemeinsamen Erweiterungen ein: im Pilot an, im noch nicht migrierten Bestandsdienst standardmäßig aus. Gemeinsame Migration, kein Pilotmodellset und keine kopierte Formel. Ein späterer Live-Cutover muss das neue Schema und die Aktivierung zusammen freigeben; T1 verändert die public-Struktur nicht.

## 2. Null-Zeilen-Nachweis

**Alle 138 aktiven Geschäftstabellen haben 0 Zeilen.** Vollständige Tabelle-zu-Zeilenzahl-Liste:

| Tabelle | Zeilen |
|---|---:|
| django_admin_log | 0 |
| game_aibuyerrun | 0 |
| game_aitransferoffer | 0 |
| game_apifootballdailyusage | 0 |
| game_buybackclause | 0 |
| game_club | 0 |
| game_clubcmtprofile | 0 |
| game_clubexternalid | 0 |
| game_clubfinancialtransaction | 0 |
| game_clubnewsitem | 0 |
| game_clubpartnership | 0 |
| game_clubplayerimportjob | 0 |
| game_clubpublicprofile | 0 |
| game_clubrecord | 0 |
| game_clubrecordbreak | 0 |
| game_clubrecordcorrectionrequest | 0 |
| game_clubsponsor | 0 |
| game_clubstadionumfeldstate | 0 |
| game_clubtmprofile | 0 |
| game_clubtrophy | 0 |
| game_clubtrophyentry | 0 |
| game_cointransaction | 0 |
| game_communitysubmission | 0 |
| game_communitytournament | 0 |
| game_communitytournamentapplication | 0 |
| game_communitytournamententry | 0 |
| game_communitytournamentmatch | 0 |
| game_communitytournamentphase | 0 |
| game_communitytournamentround | 0 |
| game_communitytournamentstanding | 0 |
| game_creatoractionlog | 0 |
| game_cupfixture | 0 |
| game_cupround | 0 |
| game_cupseason | 0 |
| game_cupseason_participants | 0 |
| game_dayweather | 0 |
| game_dealrequest | 0 |
| game_dealrequestplayer | 0 |
| game_facilityconstruction | 0 |
| game_financematchdayrun | 0 |
| game_financereservation | 0 |
| game_financetransaction | 0 |
| game_forcedauction | 0 |
| game_forcedauctionbid | 0 |
| game_friendlyfixture | 0 |
| game_gameseasonstate | 0 |
| game_historiccoach | 0 |
| game_hoenesscoin | 0 |
| game_importissue | 0 |
| game_inactivitypenalty | 0 |
| game_inactivityrecord | 0 |
| game_insolvencycase | 0 |
| game_league | 0 |
| game_leaguenews | 0 |
| game_leagueseasonstate | 0 |
| game_leaguestandings | 0 |
| game_listingpin | 0 |
| game_loan | 0 |
| game_loanlisting | 0 |
| game_managercareerentry | 0 |
| game_managercareerstation | 0 |
| game_managercompetitiontitle | 0 |
| game_managernotes | 0 |
| game_managerseasonscore | 0 |
| game_managerteamphoto | 0 |
| game_managertimelineentry | 0 |
| game_managertitle | 0 |
| game_managervacationblock | 0 |
| game_matchdayrevenue | 0 |
| game_matchevent | 0 |
| game_matchresult | 0 |
| game_matchstory | 0 |
| game_matchstoryround | 0 |
| game_notification | 0 |
| game_pendingtransfer | 0 |
| game_player | 0 |
| game_playerawardtitle | 0 |
| game_playerclubhistory | 0 |
| game_playercmtattributeprofile | 0 |
| game_playercmtprofile | 0 |
| game_playereditlog | 0 |
| game_playereditrequest | 0 |
| game_playerexternalid | 0 |
| game_playerfmiprofile | 0 |
| game_playerformsnapshot | 0 |
| game_playerimportcandidate | 0 |
| game_playerinjuryrecord | 0 |
| game_playermarketvaluesnapshot | 0 |
| game_playerrlformprofile | 0 |
| game_playerseasonstat | 0 |
| game_playersourcerating | 0 |
| game_playersourceratingsnapshot | 0 |
| game_playerstrengthprofile | 0 |
| game_playerstrengthsnapshot | 0 |
| game_playersuspensionrecord | 0 |
| game_playertmprofile | 0 |
| game_playertransferhistory | 0 |
| game_playerweightedratingsnapshot | 0 |
| game_positionbarometer | 0 |
| game_presidentsatisfaction | 0 |
| game_rumornews | 0 |
| game_scoutingassignment | 0 |
| game_scoutingbid | 0 |
| game_scoutingdepartment | 0 |
| game_scoutingfind | 0 |
| game_seasoneconomysnapshot | 0 |
| game_seasonfinancestate | 0 |
| game_seasonfixture | 0 |
| game_seasongoal | 0 |
| game_sellonclause | 0 |
| game_simulatedmatch | 0 |
| game_sourceimportrun | 0 |
| game_sponsorcontract | 0 |
| game_sponsoroffer | 0 |
| game_squadlimitnote | 0 |
| game_squadoffer | 0 |
| game_stadium | 0 |
| game_stadiumexpansion | 0 |
| game_storyaudit | 0 |
| game_supportticket | 0 |
| game_tacticsetup | 0 |
| game_tactictemplate | 0 |
| game_transferbid | 0 |
| game_transferlisting | 0 |
| game_transferlock | 0 |
| game_transfernegotiation | 0 |
| game_transferrecord | 0 |
| game_transferrecordplayer | 0 |
| game_transferreport | 0 |
| game_tvpot | 0 |
| game_vereinkoeffizient | 0 |
| game_watchlistentry | 0 |
| game_youthlevypayment | 0 |
| showauction_showauction | 0 |
| showauction_showauctionbid | 0 |
| showauction_showauctionwatch | 0 |
| stadium_editor_stadiumdesign | 0 |
| stadium_editor_stadiumgeometry | 0 |

Damit sind insbesondere Clubs, Spieler, Stadionanker/Geometrie/Design/Ausbauten, Ligen/Saisons, Wettbewerbe/Turniere/Pokale, Spiele/Ticker/Geschichten, Finanzbuchungen, Transfer-/Leih-/Scoutingzustände, Real-Historien/Rekorde/Titel und Paketläufe/Arbeitsliste leer. Keine Fachzeile aus dem BVB-Paket wurde übernommen.

Ausgenommen sind ausschließlich die bestätigten Schutz-/Parametertabellen, technische Migrationen/Sessions und 21 temporäre Schutz-Sicherungen t1_saved_*. Diese enthalten keine kopierten Clubs/Spieler/Stadien; sie bleiben bis zur Abnahme bestehen.

## 3. Schutzdaten, Profile und Rechte

**Alle 21 Original-Schutzmengen zurückgeführt und fingerprint-identisch.** MD5 ist hier ein Inhaltsvergleich über sortierte Zeilenhashes, keine kryptografische Signatur. Keine Konten-/Passwort-/Profilwerte werden im Bericht ausgegeben.

| Schutztabelle | Originalzeilen | Gesamt jetzt | Fingerprint vorher = nachher |
|---|---:|---:|---|
| django_content_type | 157 | 159 | 4910ea92b1c91cc77553b08f37e528b5 |
| auth_permission | 628 | 636 | ce2a5d31f89f9020b7640433319cb05b |
| auth_user | 3 | 3 | 743eef91094802ebb01789bb37492518 |
| auth_group | 0 | 0 | d41d8cd98f00b204e9800998ecf8427e |
| auth_user_groups | 0 | 0 | d41d8cd98f00b204e9800998ecf8427e |
| auth_user_user_permissions | 0 | 0 | d41d8cd98f00b204e9800998ecf8427e |
| auth_group_permissions | 0 | 0 | d41d8cd98f00b204e9800998ecf8427e |
| game_managerprofile | 3 | 3 | 4cc7b1695c4353c9268f763b3fc4ef66 |
| game_referee | 463 | 463 | c2b6e0c9e1a46c3eda7bb3809a822a20 |
| game_sponsor | 504 | 504 | df2dc25b8364e752142bb27ff760f6ef |
| game_economyparameter | 77 | 77 | 1049b38a456aba10702d21f2118f8402 |
| game_countrynetwork | 0 | 0 | d41d8cd98f00b204e9800998ecf8427e |
| game_stadionumfeldconfig | 1 | 1 | 82b4aad46484cee321d27b769e9857ff |
| game_datasource | 5 | 5 | c4ca6be4075cfea715ecfd18047bb375 |
| game_strengthformulasettings | 1 | 1 | 5c264eedffdb9520cb3a661d31717363 |
| game_strengthmodifierrule | 15 | 15 | 908f1ab28e9cb2c8f71c3b763bc24afe |
| game_mediaoutlet | 24 | 24 | f6cd30c4a824a08649c6ba7aebdb9fd7 |
| showauction_showauctionpreset | 5 | 5 | 54f3470ecc3fe713e3205027b693e2c6 |
| game_storysettings | 0 | 0 | d41d8cd98f00b204e9800998ecf8427e |
| game_neutralvenue | 0 | 0 | d41d8cd98f00b204e9800998ecf8427e |
| game_landkoeffizient | 9 | 9 | 2252c0cdc04f38c7b02357226296435e |

Profilstart: level=1, xp=0, xp_max=800; 0 abweichende Profile. Favoritenverein und aktiver Titel NULL. Auch alle übrigen bereits freigegebenen N19-Resetwerte sind durch den vollständigen Zeilenfingerprint erhalten.

Login-/Gruppen-/Rechtezuordnungen sind erhalten; Permissions über (app_label, model, codename) aufgelöst. Zusätzliche ContentTypes/Standardrechte gehören nur zu den zwei neuen Modellen. Bestehende Rechte wurden nicht gelöscht oder Personen zugeordnet, neue Rechte wurden nicht eigenmächtig vergeben.

Migrationen erzeugten zunächst ihre regulären historischen Seeds. Danach wurden alle aktiven Fach-/Katalogtabellen gemeinsam bereinigt und nur die bestätigten Original-Schutzdaten plus neue technische Modellrechte wieder eingesetzt. Ein Sequenz-Abgleich ging zunächst von id-Spalten aus und stoppte bei einem anderen Primärschlüssel; die Bereinigungstransaktion rollte zurück. Fortsetzung erst nach erneuter Sicherungs-Fingerprintprüfung, ohne erneute Seed-/Migrationsausführung.

## 4. Reparaturen aus Abschnitt 6

Erledigt in T1:
- Snapshot-save im aktivierten neuen Schema: keine verdeckte MW-/Gehalts-/PSR-Aktualisierung, keine Zehn-Snapshot-Kürzung. Legacy-Bestandsmodus bleibt unverändert.
- Versions-/Payload-Eindeutigkeit für Quellstände; Herkunft und stabile Faktenschlüssel für MW-/Transferfakten; NULL-ID-/Personen-XOR-/typisierte-ID-Constraints.
- Neue Importzustände und Import-Einzelsperre am Player; allgemeine HistoricCoach-Personen, nullable Rekordwert und strukturierte Belege.
- Kapazitätssummen bleiben bei unbekannten Einzelwerten NULL, nicht erfundene 0 oder TypeError; belegte Nullen summieren sich weiterhin zu 0.
- Alle sechs Dortmund-PK-Stellen verwenden FMI 907; Live-Link verwendet die tatsächlich aufgelöste Club-ID. Keine Szene gelesen/gesichert/importiert.
- Pilot lädt vollständige game/showauction/stadium_editor-Apps und gemeinsame Originalseiten; HTTP-Mutationen bleiben bis weiterer Freigabe gesperrt.

Noch nicht umgesetzt, bewusst T2–T4:
- Zentraler validierter Paketweg, Positiv-/Uploadmaske einschließlich E35-Grenze, idempotente Projektionen/Initialisierung und explizite Rating-/Stärke-/Gehaltspfade.
- ID-Spiegel, Person↔Player-Zuordnung ohne Namensfallback, Quellen-/Attributnormalisierung und lücken-/konfliktbezogene Arbeitslisten mit Ein-Klick-Bestätigung.
- Kader-/U21-/Leihpool-/Scouting-/Aufstellungsfilter und spielbezogene Sperr-Gates. Die modelseitige Poolkennung allein ersetzt diese noch nicht.
- TM-basierte FK-Nachträge (E69) bei späterem Import: Entscheidung **FK-Backfill beim Import**, nicht Lookup beim Anzeigen. Historische IDs/Namen unverändert; auch nach Ligastart erlaubt.
- Stadion-/Profil-Spiegel, NULL-Nutzungsgates, Registry/offene Rekordschlüssel, Personenbilder, vollständige Historien-/Titel-/Rekord-/Kaderanzeigen und Creator-Vorschau/-Upload/-Nachpflege.

Legacy-Platzhalter-/Namens-/CSV-Wege wurden nicht zum neuen Paketweg umgebaut; sie sind im T1-Pilot nicht per HTTP aufrufbar. Kein behaupteter fertiger Importer.

## 5. Stärkenparität und technische Prüfungen

**96 identische Eingabesätze vorher/nachher**, inklusive TW/IV/ZM/ST, FM/CMT/einer/keiner Quelle, fehlendem/vorhandenem Potential und drei Frischewerten. Aufruf derselben compute_strength_for_player-Funktion im Bestands- und Pilot-Modellkontext, ohne ORM-Spielerdaten oder Paketimport.

Identischer Ergebnis-SHA256: 01715d53dd9961107b0110935c3df2602b8d10595de436caddf051699663d416.
strength_service.py und strength_engine.py sind bytegleich zur Vorhermessung; Hashes in t1-strength-before.json und t1-strength-after.json.

Zusätzliche Rollbacktests: je 12 MW-/Ratingpunkte am selben Datum bleiben bestehen, ohne aktuelle MW-/Gehalts-/Rating-Schreibwirkung. Kein Testdatensatz persistiert. Gleiche externe ID in getrenntem Spieler-/Trainerraum zulässig; genau ein FK-Besitzer per DB-Constraint erzwungen; NULL-Kapazität von belegter 0 unterschieden. 397 aktive Feldlisten-Ziele und alle 384 Paketpfade besitzen ihren SQL-Zielanker; die vier späteren Jugendbewerbungsfelder bleiben ausdrücklich außen vor. Django system check ohne Fehler; makemigrations --check ohne Drift; keine offenen Migrationen; health=200 und POST gesperrt=403; Nullbestand und Schutz-Fingerprints nach allen Tests nochmals gleich.

Das ist ein Eingabe-/Code-Paritätsnachweis, kein neuer Saison-Balancinglauf und keine T2-Importabnahme.

## 6. real_life_club: Leser und Vorschlag

- game/views_scouting.py: _find_card, _search_players, transfer_scouting (Verein/Wappen/Liga in Karten, Suche, Such-/Watchlistdaten).
- game/views.py: player_detail (select_related und Wappenquelle).
- game/admin.py: Player-Form/Querysets/Filter/Feldlisten; _league_coefficient und _dynamic_league_median_rating lesen Verein/Liga für die bestehende Stärkevorschau. PlayerDataReviewAdmin lädt den FK ebenfalls.
- game/club_import/fmid_csv_service.py: _apply_row prüft bestehende real_life_club-Zuordnung vor Ergänzung. Weitere Legacy-Schreiber: club_import/import_service.py und economy/severance.py.
- Historische Migrationen/Testdateien bleiben historische Verweise. CMT-Quellprofile mit gleichnamigem Textfeld sind nicht dieser Player-FK.

**Vorschlag: vorerst abgeleiteter Spiegel von owner_club_id, später entfernen.** Kein eigener Paket-Eingang, kein unabhängiger Editorwert. Beim nicht importierten Stammverein bleibt der Spiegel NULL; Anzeige nutzt owner_club_tm_id/Originalname. T2 führt owner/loan/club/loan_until und aktualisiert real_life_club sowie loan_status/loan_partner_club nur über einen expliziten gemeinsamen Spiegelweg. T4 stellt obige Leser auf die kanonischen Beziehungen um. T1 hat die Legacy-Leser nicht heimlich semantisch umgeschrieben.

## 7. public und Betriebsgrenzen

Vorher/nachher: **158/159 Tabellen fingerprint-identisch**; alle Sequenzstände und alle geprüften Rollen-/Schema-/Objekt-ACL-/Constraint-Metadaten identisch. Abweichende Tabelle: game_managerprofile (Zeilenzahl unverändert).

**Keine pauschale Bestätigung vollständiger Unverändertheit möglich.** Der Bestandsdienst wurde nicht für den Vergleich eingefroren; dessen LastSeenMiddleware schreibt bei authentifizierten Requests last_seen und führt Login-Belohnungslogik aus. Dieser Pfad erklärt mögliche parallele Profilaktivität, ist aber ohne Vorherwerte pro Spalte kein beweisbarer Ausschluss anderer Profiländerungen. Es wurden bewusst keine alten Werte geraten oder nach public zurückgeschrieben.

Alle Schema-/Bereinigungs-/Rückführungswrites erfolgten über direkte import_pilot_role-Verbindung mit genau search_path=import_pilot. Der Guard verweigert public-Schreibrechte, Rollenerhöhung und fremde Suchpfade. Die public-Prüfverbindungen waren read-only. Keine public-Migration, kein Truncate/Update/Delete, keine Änderung bestehender Rollen oder ACLs. Kein Hetznerzugriff, keine Worker/Beat-Jobs, keine Änderung von Produktionssecrets. Keine bestehenden Prozesse/Workflows wurden manuell neu gestartet oder gestoppt. Nur ein kurzlebiger lokaler Pilot-HTTP-Testserver wurde gestartet, geprüft und wieder beendet; sein Healthcheck zeigte t1-full-game-no-import. Der zusätzliche 404-Request war das nicht vorhandene favicon.ico; der Nullbestand blieb erhalten. Kein Broker-Eingriff.

**HALT.** Schutz-Sicherungen bleiben bis Abnahme erhalten. T2–T5 werden nicht begonnen; keine Aussage zu fehlenden Spielern beim Vorstart-Reupload oder Rückkehr zu einem nicht importierten Stammverein vorweggenommen.
