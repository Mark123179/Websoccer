# N27: Korrigierter Modellplan als Feldliste

**Stand 06.10.2026 · N28 FREIGEGEBEN mit N29–N31 · T1 umgesetzt, danach HALT.**

Nachtrag 6 (N28–N31) hat Vorrang vor Teil A, B, C und Nachträgen 1–5. **Club, Player und Stadium bleiben die bestehenden Spielanker mit ihren Beziehungen.** Kein paralleles Modellset, kein eigenes Kader-Modell, keine eigenen Pilotseiten unter game/import/. Die Zustands-/Codebeleg-Spalte beschreibt die Änderung gegenüber dem N27-Ausgangsbestand; alte Zeilennummern sind historische Prüfbelege. Die tatsächlichen T1-Spalten stehen im T1-Bericht und dessen maschineller Schemaanlage. Funktionen mit „geplant“ sind weiterhin nicht implementiert: Paketweg, Initialisierung, Nachpflege und Anzeige folgen ausschließlich nach Freigabe von T2–T4. Kein Paketimport, kein Creator-Upload, keine Dortmund-Szenensicherung. Hetzner bleibt unberührt.

## 1. Zeilenprüfung des Ausgangsvorschlags

| B6-Zeile | Am Code geprüft | Korrigierte Zuordnung |
|---|---|---|
| Verein | Club hat Name, Kurzname, Jahr, zwei Farben, IDs, Liga; Stadt/Land/Lat/Lng stehen in ClubPublicProfile. Spitzname, Motto, offizieller Name, dritte Farbe und Importzustand fehlen. | Dieselben Tabellen erweitern. N29: Club.league bleibt erforderlich; nur importierte Vereine, Zustand spielbar/nicht_spielbar. Historische Fremdvereine bleiben TM-ID plus Originalname, keine Verweis-Zeilen. ClubPublicProfile.stadium_name/capacity entfallen als unabhängige Wahrheit. |
| Stadion | Stadium hat bereits zwölf Kapazitätsfelder, Stadt, Name, Preise, Anlagenstufen. Ausbau schreibt aktuelle Plätze; Basiskennzeichen/Seiten/Geodaten fehlen. | Reale Basiswerte plus Kennzeichen am selben Stadium ergänzen; bestehende zwölf aktuelle Kapazitäten bleiben benannte Spielprojektionen. Sonst würde ein Ausbau Echtweltfelder ändern oder Upload den Ausbau löschen. |
| Spieler | Stammdaten weitgehend vorhanden; Künstlername und Mannschaft fehlen. loan_status, loan_partner_club, loan_until und real_life_club bestehen bereits. | Player erweitern, nicht duplizieren. Mannschaft, explizite Sim-Eigentümer-/Leihbeziehungen und Import-Einzelsperre ergänzen. Vorhandene Leihfelder reparieren, nicht als sämtlich neu ausgeben. |
| Externe ID | PlayerExternalId UND ClubExternalId bestehen. Beide haben Quell-/DB-/URL-Metadaten, aber keinen geforderten Status/Prüftag. IDs sind bisher nicht nullable; Spieler-ID-Tabelle verlangt player. | Beide erweitern; PlayerExternalId zusätzlich mit alternativer historischer Person als Besitzer, XOR und getrennten ID-Räumen. Kein Namensabgleich, keine eigene Person-ID-Tabelle nötig. |
| Quellwerte | PlayerSourceRating.source_version/checked_at bestehen bereits. PlayerSourceRatingSnapshot.raw_payload/source_version bestehen; aktuelle PSR enthält 21 normalisierte Attribute, aber kein Rohdatenfeld. | Bestehendes Versionsarchiv reparieren und aktuellen PSR explizit daraus spiegeln. Keine neue Quellwerttabelle, keine Dynamic→Rating/Potential-Ersatzwerte. |
| Person | HistoricCoach ist eine bestehende Trainertabelle; ClubRecord.holder_coach zeigt darauf. Nicht alle historischen Spieler sind aktive Player. | HistoricCoach um person_kind/nullable FMI und ID-Zuordnung erweitern. Derselbe Halter-FK darf allgemeine Personen tragen; bestehende Halteranzeige/Bildwahl muss kind berücksichtigen. Kein zweiter Player für einen historischen Halter. |
| Marktwertpunkt | PlayerMarketValueSnapshot existiert. save schreibt Player.market_value UND salary_per_match und ruft prune_snapshot_history(limit=10). | Beides entfernen; volle Historie, Herkunft, Vereinsreferenz/-originalname und Startwertkennzeichen ergänzen. Aktualisierung des Spiel-MW nur durch expliziten Spielweg. |
| Transfer | PlayerTransferHistory besteht als WS-Historie; fee_eur ist bereits nullable, from_club/to_club bestehen. | Dieselbe Tabelle um real/sim, Leihkennung, externe Vereinsreferenzen und Originalnamen erweitern. Keine neue Transfer-Tabelle, keine unbekannte Ablöse 0. |
| Rekord | ClubRecord hat bereits source=SEED/SIM, Datum/Zeitraum/Saison/Wettbewerb/Gegnertext. value_numeric ist nicht nullable. record_key ist frei, Registry kann trotzdem Schlüssel ausfiltern. | Herkunft übersetzen statt duplizieren; Nullwert, strukturierte Belege/Suche, Gegner-TM-ID ergänzen. Registry und bestehende Ruhmeshalle für neue Schlüssel reparieren. |
| Titel | ClubTrophy enthält nur competition_name/count/Asset/Sortierung; kein Saison-/Herkunftseintrag. PlayerAwardTitle/ManagerCompetitionTitle sind keine Vereinstitel. | Nur ClubTrophyEntry neu; ClubTrophy als explizit abgeleitete Projektion mit Herkunft je Zeile behalten. |
| Kader | Player trägt Spielverein, Rückennummer, Gehalt und viele Spielzustände. Kein echtes Mannschaftsfeld; Alterssplit in game/views.py:2822–2824. | Ausgangsvorschlag bestätigt: KEIN separates Kader-Modell. Ein Player mit Mannschaft, Eigentümer und Spiel-/Leihverein genügt. Poolabfrage erfolgt aus Beziehungen und zählt nicht als Scouting. |
| Paket / Arbeitsliste | SourceImportRun existiert als Importprotokoll. ClubPlayerImportJob/PlayerImportCandidate sind lokale Import-Leases bzw. spielerbezogene Kandidaten, keine allgemeine Lückenliste. | SourceImportRun zum Paketprotokoll erweitern, keine neue Pakettabelle. Nur ImportIssue für allgemeine Lücken/Nacharbeit neu; Spieler-Kandidaten sind keine Vereins-/Stadion-/Rekord-Liste. |

**Nur zwei neue fachliche Tabellen:** game_clubtrophyentry und game_importissue. Alle Anker-, Personen-, ID-, Quell-, Historien-, Profil- und Protokolltabellen werden wiederverwendet. Herkunft ist auf jeder gemischten Fakt-/Projektionszeile Pflicht.

## 2. Schreibrechte und Uploadmaske

- **E:** Echtwelt. Ausschließlich der zentrale Paket-/Korrekturweg apply_package in der bestehenden game/club_import/import_service.py. Genannte sync-Helfer dürfen nur unter diesem kontrollierten Weg bzw. für abgeleitete Spielprojektionen laufen. Creator-Nachpflege nutzt denselben validierten Weg, nicht zusätzliche direkte Stammdaten-Saves. Originalpaket/Prüfmetadaten gehören als technischer Teil zur Import-Echtweltschicht.
- **R:** Real + Sim. Import schreibt nur origin=real (Rekordquelle SEED), Spiel nur origin=sim (Rekordquelle SIM). Keine realen Fakten über Sim-Fakten schreiben. Bestehende DataSource ist Quellenanbieter, nicht Herkunft; neue origin ist daher bei MW/Transfers/Titeln nötig, bei ClubRecord reicht bestehendes source.
- **S:** Spielstand. Nur Spiel-/Creator-Domänendienste schreiben. Das Paket ist Eingabe für initialize_package_game_state vor Ligastart, kein direkter zweiter Eigentümer dieser Felder. Freigegebene Startwerte, Kader, Leihen, Rückennummer, Anfangsgehalt, Stärke und Sperrstatus werden dadurch initialisiert; keine Sim-Vereinsstation aus Player.save. Ein erneuter Vorstart-Upload darf nur bewusst vorgesehene Initialisierung abgleichen, keine Karriere/Finanzbuchungen erfinden.
- **Vor Ligastart:** Echtweltdaten vollständig ersetzen, Real-Historie idempotent übernehmen, fehlende Werte NULL/unbekannt lassen. Der Sonderstartwert 50.000 € nach N10 wird vom Spiel als markierter sim-Punkt erzeugt, nicht als gefälschter TM-Realwert. Sim-Historien bleiben auch bei Vorstartkorrekturen erhalten.
- **Nach Ligastart (N30):** Ü-Stamm = Vereinsname/Kurzname/offizieller Name/Gründungsjahr/Farben/Spitzname/Motto/Stadt/Land/Koordinaten; Spieler-/Personen-Vorname/Nachname/Künstlername/Geburtsdatum/Nationen/Größe/Fuß. Ü-ID = geprüfte ID-Ergänzung/-Korrektur ohne Identitätswechsel; Konflikt → Arbeitsliste. Stadion: ausschließlich Name. Real-Rekorde und Real-Titel dürfen aktualisiert werden, Titel nur bis 2025/26. **Alle Haupt-/Nebenpositionen und Spiegel position/primary_position/source_positions bleiben unberührt**, ebenso Ratings/Quellversionen, MW-/Transferhistorie, Mannschaft/Spielverein/Leihstand/Rückennummer/Gehalt/Einzelsperre, echte und aktuelle Kapazitäten/Ausbau/Preise/Umfeld und sämtliche Spielstände/Sim-Zeilen. Positionsänderungen nur später über E35. Die Maske ist freigegeben; kein pauschales „Stammdaten“-Schreibrecht.
- **Archive nach Ligastart:** Ein neues Originalpaket darf als Auditlauf gespeichert werden; gesperrte Nutzfelder werden NICHT operativ angewendet. Erledigte Arbeitslisteneinträge werden nicht wieder geöffnet. Einzelsperren bleiben beim erneuten Paketupload ebenfalls unberührt. **N31:** Leihstatus/-vereine/-ende stehen operativ nur im Spielstand; der Erhebungsstand bleibt ausschließlich im archivierten Paket. `real_life_club` wird nicht zum zweiten Stammverein. Die vorgeschlagenen Real-Leihspalten entfallen.
- **N29 Verknüpfung:** T2 trägt beim späteren Vereinsimport FKs nach gleicher TM-ID nach; kein Name-Matching, keine zusätzliche Club-Zeile. Historischer TM-Schlüssel und Originalname bleiben unverändert. Dieser FK-Nachtrag ist auch nach Ligastart erlaubt und keine Änderung der Historie. Verliehene an fehlenden Zielverein: `club=NULL`, Eigentümer-FK nur bei importiertem Eigentümer; Eigentümer-/Leihverein-TM-ID und Originalnamen bleiben im Spielstand, nicht scoutbar und nicht im Stammkader. Geliehene: `club=BVB`, Eigentümer-TM-ID/Name, Eigentümer-FK nur falls vorhanden. E69 übernimmt spätere TM-Verknüpfung.
- **Archiventscheidung:** nur JSON in `SourceImportRun.package_data` und `manifest`; keine `package_file`-Spalte und keine zweite archivierte Paketdatei. Historische Quellwert-Snapshots sind Versionsfakten, kein zweites operatives Leihregister.
- Quellenmetadata last_seen_at/created_at/imported_at sind technische Zeiten; checked_at bleibt der recherchierte Prüftag. Alle im Paket vorhandenen Nullwerte, leeren Listen und Rohschlüssel sind in der Anlage einzeln zugeordnet. JSON-Unterfelder sind bewusst als Spalte#Pfad bezeichnet, nicht als vorgetäuschte SQL-Spalten.

## 3. Notwendige Spiegel und Initialwerte

Alle Ja-Zeilen nennen Quelle und Funktion. Neue Funktionsnamen sind ausdrücklich **geplant**, keine Behauptung über vorhandenen Code.

1. Bestehende Club-/Player-ID-Spalten einschließlich FMI für Bilder spiegeln nur die zugeordneten externen IDs. TM-/API-/CMT-Direktspalten sind ebenfalls Altleser und werden nicht als unabhängige Werte gepflegt. HistoricCoach.fm_inside_id ist derselbe Asset-Kompatibilitätsspiegel. Bei Person↔Player-Verbindung wird dieselbe typisierte Identität verwendet, kein Doppel-ID-Besitzer; lokale persons.ref ist kein Matching-Schlüssel.
2. Player.market_value ist Spiel-MW aus dem maßgeblichen Marktwertpunkt. Das Datum plus stabiler Faktenschlüssel bestimmen den letzten Punkt; 0 bleibt 0, NULL bleibt unbekannt. Start-MW aus dem Paket wird als zusätzlicher belegter Stichtagspunkt übernommen, wenn vorhanden; N10 separat sim. salary_per_match ist kein automatisch mitgeschriebener Snapshot-Spiegel, sondern vom Spiel gesetztes Gehalt.
3. Die zwölf aktuellen Stadium-Kapazitäten spiegeln eingefrorene Realbasis plus angewendete Ausbauten. Die Realbasis bleibt unverändert; resolve_due_expansions ist bestehender Spielpfad, die Initialisierung ist geplant. Unbekannte Basis sperrt die betroffene Nutzung, statt aus NULL eine fiktive 0-Kapazität zu machen. Paket-Summen sind externe Belege, nicht weitere aktuelle Kapazitäten.
4. PlayerSourceRating ist aktuelle, normalisierte Lesesicht auf das bestehende vollständige Snapshot-Archiv. Aktuelle Rating/Potential/Attribute/Version/Prüftag sind ausdrücklich Spiegel. Keine Kürzung auf zehn Quellstände, keine versteckten save(update_current)-Schreibwege. Eindeutigkeit der Snapshots wird um Version/Payload-Fingerprint erweitert, damit zwei Stände am selben Datum erhalten bleiben. Rohattribute des Referenzpakets liegen bereits auf der Quellskala; keine neue Stärkeformel oder neue Durchschnittsrechnung. Vorhandene Attributnormalisierung wird verwendet; nicht verwendete Rohattribute bleiben erhalten.
5. Player.position/primary_position/source_positions und age sind Kompatibilitätsableitungen aus HP/NP bzw. Geburtsdatum; kein dritter Stammdaten-Eingang. Player.potential bleibt kompatibler 100er-Rohspeicher, niemals 200er-Enginewert; Dynamic-Quellpotential bleibt NULL. PlayerStrengthProfile wird ausschließlich über den bestehenden Berechnungs-/Spielweg gefüllt.
6. ClubTrophy bleibt abgeleitet aus ClubTrophyEntry. Zähler, Wettbewerb-/Asset-/Sortierdaten sind keine zweite Titelfaktenpflege. Auch Zählzeilen tragen Herkunft; die bestehenden Pokalkacheln gruppieren passend, statt real+sim doppelt anzuzeigen. ClubRecord.holder_name/Wertanzeige bleiben vorhandene Anzeigeprojektionen auf belegten Inhalt; keine frei erfundenen Halter/Nullwerte.
7. owner_club/loan_club/club plus loan_until sind kanonischer Sim-Leihzustand. loan_status/loan_partner_club bleiben nur reparierte Altvertrags-Projektionen. Geliehen/verliehen ist eine Ansicht relativ zum betrachtenden Verein, nicht zwei Player-Zeilen. is_in_loan_pool ist eine Query/Property (Eigentümer ≠ Spielverein bei laufender Leihe), KEINE zusätzliche speicherbare Wahrheit. Ein auswärtiger nur_verweis-Club zählt nicht zur eigenen Kaderbelegung; ein solcher Spieler ist niemals dadurch scoutable.

Originalpaket/Auditkopie und importierte Recherchebelege sind keine zweite aktive Feldpflege. Bestehende PlayerFMIProfile/PlayerCMTProfile/PlayerTMProfile und Club-Quellprofile werden nicht als weitere unabhängige Wahrheiten befüllt: die bestehenden Quellen-/Creator-Seiten lesen das kanonische Snapshot-/ID-/PSR-Material. Die Tabellen bleiben bis zum späteren, modulweisen Leserabbau bestehen; kein zusätzlicher Modellanker.

## 4. Einzelne Tabellen-/Spaltenentscheidungen

Die Tabelle enthält auch vorhandene B6-Spielzustände und notwendige technische Belegfelder, nicht nur Neuanlagen. „neu“ meint bei bestehendem Modell eine **neue Spalte**, nicht eine neue Tabelle. Erweiterungen/Reparaturen betreffen Nullbarkeit, Herkunft, Constraints oder kontrollierte Schreibweise. 397 eindeutige physische Zielspalten für diesen Umbau; FK-Spalten werden mit _id bezeichnet. Vier ausdrücklich spätere Jugend-Antragsfelder stehen separat und sind nicht Teil dieses Umbaus. Paketarrays werden in der Anlage auf jede beobachtete Feldform abgebildet; HP/NP-Zielspalten sind hier jeweils eigene Zeilen.

### Verein

| Tabelle und Spalte | Zustand / Codebeleg | Schicht / Schreiber | Spiegel: Quelle → Funktion | Upload nach Ligastart | Präzisierung |
|---|---|---|---|---|---|
| game_club.name | vorhanden; game/models.py:741 | E / Import: apply_package | nein | überschreiben: Ü-Stamm | — |
| game_club.short_name | vorhanden; game/models.py:742 | E / Import: apply_package | nein | überschreiben: Ü-Stamm | — |
| game_club.founded_year | vorhanden; game/models.py:755 | E / Import: apply_package | nein | überschreiben: Ü-Stamm | — |
| game_club.color_primary | vorhanden; game/models.py:743 | E / Import: apply_package | nein | überschreiben: Ü-Stamm | — |
| game_club.color_secondary | vorhanden; game/models.py:749 | E / Import: apply_package | nein | überschreiben: Ü-Stamm | — |
| game_club.official_name | neu; im Modellbestand nicht vorhanden | E / Import: apply_package | nein | überschreiben: Ü-Stamm | neu am bestehenden Club; fehlende dritte Farbe bleibt NULL |
| game_club.color_tertiary | neu; im Modellbestand nicht vorhanden | E / Import: apply_package | nein | überschreiben: Ü-Stamm | neu am bestehenden Club; fehlende dritte Farbe bleibt NULL |
| game_club.nickname | neu; im Modellbestand nicht vorhanden | E / Import: apply_package | nein | überschreiben: Ü-Stamm | neu am bestehenden Club; fehlende dritte Farbe bleibt NULL |
| game_club.motto | neu; im Modellbestand nicht vorhanden | E / Import: apply_package | nein | überschreiben: Ü-Stamm | neu am bestehenden Club; fehlende dritte Farbe bleibt NULL |
| game_club.import_state | neu gegenüber N27 | E / Import: apply_package | nein | unberührt: N30 | spielbar / nicht_spielbar; kein Verweis-Verein, kein Liga-Platzhalter |
| game_clubpublicprofile.city_name | vorhanden; game/models.py:1096 | E / Import: apply_package | nein | überschreiben: Ü-Stamm | — |
| game_clubpublicprofile.city_country | vorhanden; game/models.py:1097 | E / Import: apply_package | nein | überschreiben: Ü-Stamm | — |
| game_clubpublicprofile.map_lat | vorhanden; game/models.py:1098 | E / Import: apply_package | nein | überschreiben: Ü-Stamm | — |
| game_clubpublicprofile.map_lng | vorhanden; game/models.py:1099 | E / Import: apply_package | nein | überschreiben: Ü-Stamm | — |
| game_club.league_id | vorhanden; game/models.py:783 | S / Spiel | nein | unberührt: gesperrt nach E37 | N29: FK bleibt NOT NULL; Zielliga aus Creator, nicht aus Paket; ausschließlich importierte Vereine |
| game_club.budget | vorhanden; game/models.py:757 | S / Spiel | ja: FinanceTransaction → game.economy.booking.book() | unberührt: gesperrt nach E37 | Kontostand ist Ledger-Cache; auch Startkapital nur buchen, nicht budget direkt setzen |
| game_club.reserved | vorhanden; game/models.py:768 | S / Spiel | ja: FinanceReservation → transfer_v2.escrow.recalc_reserved | unberührt: gesperrt nach E37 | keine Echtweltdaten; Initialisierung ausschließlich Spiel |
| game_club.fan_popularity | vorhanden; game/models.py:776 | S / Spiel | nein | unberührt: gesperrt nach E37 | keine Echtweltdaten; Initialisierung ausschließlich Spiel |
| game_club.managed_by_id | vorhanden; game/models.py:788 | S / Spiel | nein | unberührt: gesperrt nach E37 | keine Echtweltdaten; Initialisierung ausschließlich Spiel |
| game_club.job_availability_type | vorhanden; game/models.py:814 | S / Spiel | nein | unberührt: gesperrt nach E37 | keine Echtweltdaten; Initialisierung ausschließlich Spiel |
| game_club.ai_buyer_paused | vorhanden; game/models.py:826 | S / Spiel | nein | unberührt: gesperrt nach E37 | keine Echtweltdaten; Initialisierung ausschließlich Spiel |
| game_clubpublicprofile.average_attendance | vorhanden; game/models.py:1095 | S / Spiel | nein | unberührt: gesperrt nach E37 | nicht im Paket; Sim-Auswertung statt recherchierten Wert annehmen |
| game_clubpublicprofile.stadium_image_static_path | vorhanden; game/models.py:1100 | E / Import: apply_package | nein | überschreiben: Ü-Stamm | optionale bestehende Assetreferenz, kein Paketbild vorhanden |
| game_clubpublicprofile.city_image_static_path | vorhanden; game/models.py:1101 | E / Import: apply_package | nein | überschreiben: Ü-Stamm | optionale bestehende Assetreferenz, kein Paketbild vorhanden |
| game_clubpublicprofile.partner_club_id | vorhanden; game/models.py:1102 | S / Spiel | nein | unberührt: gesperrt nach E37 | — |

### Externe IDs / Spiegel

| Tabelle und Spalte | Zustand / Codebeleg | Schicht / Schreiber | Spiegel: Quelle → Funktion | Upload nach Ligastart | Präzisierung |
|---|---|---|---|---|---|
| game_club.fm_inside_id | repariert; game/models.py:698 | E / Import: apply_package | ja: ClubExternalId(FM) → sync_external_id_mirrors (geplant) | überschreiben: Ü-ID, kein Identitätswechsel | vorhandener Leser-/Assetvertrag; nicht unabhängig pflegen |
| game_club.transfermarkt_id | repariert; game/models.py:708 | E / Import: apply_package | ja: ClubExternalId(TM) → sync_external_id_mirrors (geplant) | überschreiben: Ü-ID, kein Identitätswechsel | vorhandener Leser-/Assetvertrag; nicht unabhängig pflegen |
| game_club.cmtracker_id | repariert; game/models.py:714 | E / Import: apply_package | ja: ClubExternalId(CMTRACKER) → sync_external_id_mirrors (geplant) | überschreiben: Ü-ID, kein Identitätswechsel | vorhandener Leser-/Assetvertrag; nicht unabhängig pflegen |
| game_club.api_football_id | repariert; game/models.py:703 | E / Import: apply_package | ja: ClubExternalId(API_FOOTBALL) → sync_external_id_mirrors (geplant) | überschreiben: Ü-ID, kein Identitätswechsel | vorhandener Leser-/Assetvertrag; nicht unabhängig pflegen |
| game_player.fm_inside_id | repariert; game/models.py:1946 | E / Import: apply_package | ja: PlayerExternalId(FM) → sync_external_id_mirrors (geplant) | überschreiben: Ü-ID, kein Identitätswechsel | vorhandener Leser-/Assetvertrag; nicht unabhängig pflegen |
| game_player.transfermarkt_id | repariert; game/models.py:1951 | E / Import: apply_package | ja: PlayerExternalId(TM/spieler) → sync_external_id_mirrors (geplant) | überschreiben: Ü-ID, kein Identitätswechsel | vorhandener Leser-/Assetvertrag; nicht unabhängig pflegen |
| game_player.api_football_id | repariert; game/models.py:1956 | E / Import: apply_package | ja: PlayerExternalId(API_FOOTBALL) → sync_external_id_mirrors (geplant) | überschreiben: Ü-ID, kein Identitätswechsel | vorhandener Leser-/Assetvertrag; nicht unabhängig pflegen |

### Stadion

| Tabelle und Spalte | Zustand / Codebeleg | Schicht / Schreiber | Spiegel: Quelle → Funktion | Upload nach Ligastart | Präzisierung |
|---|---|---|---|---|---|
| game_stadium.name | vorhanden; game/models.py:888 | E / Import: apply_package | nein | überschreiben: nur Stadionname | — |
| game_stadium.city | vorhanden; game/models.py:889 | E / Import: apply_package | nein | unberührt: gesperrt nach E37 | — |
| game_stadium.home_end | neu; im Modellbestand nicht vorhanden | E / Import: apply_package | nein | unberührt: gesperrt nach E37 | Quellwerte/Recherche; Gesamtwerte sind Belege, keine zusätzliche aktuelle Sim-Kapazität |
| game_stadium.main_stand | neu; im Modellbestand nicht vorhanden | E / Import: apply_package | nein | unberührt: gesperrt nach E37 | Quellwerte/Recherche; Gesamtwerte sind Belege, keine zusätzliche aktuelle Sim-Kapazität |
| game_stadium.map_lat | neu; im Modellbestand nicht vorhanden | E / Import: apply_package | nein | unberührt: gesperrt nach E37 | Quellwerte/Recherche; Gesamtwerte sind Belege, keine zusätzliche aktuelle Sim-Kapazität |
| game_stadium.map_lng | neu; im Modellbestand nicht vorhanden | E / Import: apply_package | nein | unberührt: gesperrt nach E37 | Quellwerte/Recherche; Gesamtwerte sind Belege, keine zusätzliche aktuelle Sim-Kapazität |
| game_stadium.source_tier | neu; im Modellbestand nicht vorhanden | E / Import: apply_package | nein | unberührt: gesperrt nach E37 | Quellwerte/Recherche; Gesamtwerte sind Belege, keine zusätzliche aktuelle Sim-Kapazität |
| game_stadium.real_capacity_national | neu; im Modellbestand nicht vorhanden | E / Import: apply_package | nein | unberührt: gesperrt nach E37 | Quellwerte/Recherche; Gesamtwerte sind Belege, keine zusätzliche aktuelle Sim-Kapazität |
| game_stadium.real_total_standing | neu; im Modellbestand nicht vorhanden | E / Import: apply_package | nein | unberührt: gesperrt nach E37 | Quellwerte/Recherche; Gesamtwerte sind Belege, keine zusätzliche aktuelle Sim-Kapazität |
| game_stadium.real_total_standing_basis | neu; im Modellbestand nicht vorhanden | E / Import: apply_package | nein | unberührt: gesperrt nach E37 | Quellwerte/Recherche; Gesamtwerte sind Belege, keine zusätzliche aktuelle Sim-Kapazität |
| game_stadium.real_total_seating_incl_vip | neu; im Modellbestand nicht vorhanden | E / Import: apply_package | nein | unberührt: gesperrt nach E37 | Quellwerte/Recherche; Gesamtwerte sind Belege, keine zusätzliche aktuelle Sim-Kapazität |
| game_stadium.real_total_seating_incl_vip_basis | neu; im Modellbestand nicht vorhanden | E / Import: apply_package | nein | unberührt: gesperrt nach E37 | Quellwerte/Recherche; Gesamtwerte sind Belege, keine zusätzliche aktuelle Sim-Kapazität |
| game_stadium.real_total_vip | neu; im Modellbestand nicht vorhanden | E / Import: apply_package | nein | unberührt: gesperrt nach E37 | Quellwerte/Recherche; Gesamtwerte sind Belege, keine zusätzliche aktuelle Sim-Kapazität |
| game_stadium.real_total_vip_basis | neu; im Modellbestand nicht vorhanden | E / Import: apply_package | nein | unberührt: gesperrt nach E37 | Quellwerte/Recherche; Gesamtwerte sind Belege, keine zusätzliche aktuelle Sim-Kapazität |
| game_stadium.real_nord_standing | neu; im Modellbestand nicht vorhanden | E / Import: apply_package | nein | unberührt: gesperrt nach E37 | nullable Quellkapazität; 0 ist belegte Null, NULL ist unbekannt |
| game_stadium.real_nord_standing_basis | neu; im Modellbestand nicht vorhanden | E / Import: apply_package | nein | unberührt: gesperrt nach E37 | belegt / berechnet, fehlend NULL |
| game_stadium.nord_standing | repariert; game/models.py:896 | S / Spiel | ja: real_nord_standing + fertiggestellte Ausbauten → initialize_package_game_state / resolve_due_expansions | unberührt: gesperrt nach E37 | aktueller Sim-Wert; missing Quelle sperrt Nutzung statt stiller 0; Erweiterung nullable bei unbekannter Basis |
| game_stadium.real_nord_seating | neu; im Modellbestand nicht vorhanden | E / Import: apply_package | nein | unberührt: gesperrt nach E37 | nullable Quellkapazität; 0 ist belegte Null, NULL ist unbekannt |
| game_stadium.real_nord_seating_basis | neu; im Modellbestand nicht vorhanden | E / Import: apply_package | nein | unberührt: gesperrt nach E37 | belegt / berechnet, fehlend NULL |
| game_stadium.nord_seating | repariert; game/models.py:897 | S / Spiel | ja: real_nord_seating + fertiggestellte Ausbauten → initialize_package_game_state / resolve_due_expansions | unberührt: gesperrt nach E37 | aktueller Sim-Wert; missing Quelle sperrt Nutzung statt stiller 0; Erweiterung nullable bei unbekannter Basis |
| game_stadium.real_nord_vip | neu; im Modellbestand nicht vorhanden | E / Import: apply_package | nein | unberührt: gesperrt nach E37 | nullable Quellkapazität; 0 ist belegte Null, NULL ist unbekannt |
| game_stadium.real_nord_vip_basis | neu; im Modellbestand nicht vorhanden | E / Import: apply_package | nein | unberührt: gesperrt nach E37 | belegt / berechnet, fehlend NULL |
| game_stadium.nord_vip | repariert; game/models.py:898 | S / Spiel | ja: real_nord_vip + fertiggestellte Ausbauten → initialize_package_game_state / resolve_due_expansions | unberührt: gesperrt nach E37 | aktueller Sim-Wert; missing Quelle sperrt Nutzung statt stiller 0; Erweiterung nullable bei unbekannter Basis |
| game_stadium.real_ost_standing | neu; im Modellbestand nicht vorhanden | E / Import: apply_package | nein | unberührt: gesperrt nach E37 | nullable Quellkapazität; 0 ist belegte Null, NULL ist unbekannt |
| game_stadium.real_ost_standing_basis | neu; im Modellbestand nicht vorhanden | E / Import: apply_package | nein | unberührt: gesperrt nach E37 | belegt / berechnet, fehlend NULL |
| game_stadium.ost_standing | repariert; game/models.py:900 | S / Spiel | ja: real_ost_standing + fertiggestellte Ausbauten → initialize_package_game_state / resolve_due_expansions | unberührt: gesperrt nach E37 | aktueller Sim-Wert; missing Quelle sperrt Nutzung statt stiller 0; Erweiterung nullable bei unbekannter Basis |
| game_stadium.real_ost_seating | neu; im Modellbestand nicht vorhanden | E / Import: apply_package | nein | unberührt: gesperrt nach E37 | nullable Quellkapazität; 0 ist belegte Null, NULL ist unbekannt |
| game_stadium.real_ost_seating_basis | neu; im Modellbestand nicht vorhanden | E / Import: apply_package | nein | unberührt: gesperrt nach E37 | belegt / berechnet, fehlend NULL |
| game_stadium.ost_seating | repariert; game/models.py:901 | S / Spiel | ja: real_ost_seating + fertiggestellte Ausbauten → initialize_package_game_state / resolve_due_expansions | unberührt: gesperrt nach E37 | aktueller Sim-Wert; missing Quelle sperrt Nutzung statt stiller 0; Erweiterung nullable bei unbekannter Basis |
| game_stadium.real_ost_vip | neu; im Modellbestand nicht vorhanden | E / Import: apply_package | nein | unberührt: gesperrt nach E37 | nullable Quellkapazität; 0 ist belegte Null, NULL ist unbekannt |
| game_stadium.real_ost_vip_basis | neu; im Modellbestand nicht vorhanden | E / Import: apply_package | nein | unberührt: gesperrt nach E37 | belegt / berechnet, fehlend NULL |
| game_stadium.ost_vip | repariert; game/models.py:902 | S / Spiel | ja: real_ost_vip + fertiggestellte Ausbauten → initialize_package_game_state / resolve_due_expansions | unberührt: gesperrt nach E37 | aktueller Sim-Wert; missing Quelle sperrt Nutzung statt stiller 0; Erweiterung nullable bei unbekannter Basis |
| game_stadium.real_sued_standing | neu; im Modellbestand nicht vorhanden | E / Import: apply_package | nein | unberührt: gesperrt nach E37 | nullable Quellkapazität; 0 ist belegte Null, NULL ist unbekannt |
| game_stadium.real_sued_standing_basis | neu; im Modellbestand nicht vorhanden | E / Import: apply_package | nein | unberührt: gesperrt nach E37 | belegt / berechnet, fehlend NULL |
| game_stadium.sued_standing | repariert; game/models.py:904 | S / Spiel | ja: real_sued_standing + fertiggestellte Ausbauten → initialize_package_game_state / resolve_due_expansions | unberührt: gesperrt nach E37 | aktueller Sim-Wert; missing Quelle sperrt Nutzung statt stiller 0; Erweiterung nullable bei unbekannter Basis |
| game_stadium.real_sued_seating | neu; im Modellbestand nicht vorhanden | E / Import: apply_package | nein | unberührt: gesperrt nach E37 | nullable Quellkapazität; 0 ist belegte Null, NULL ist unbekannt |
| game_stadium.real_sued_seating_basis | neu; im Modellbestand nicht vorhanden | E / Import: apply_package | nein | unberührt: gesperrt nach E37 | belegt / berechnet, fehlend NULL |
| game_stadium.sued_seating | repariert; game/models.py:905 | S / Spiel | ja: real_sued_seating + fertiggestellte Ausbauten → initialize_package_game_state / resolve_due_expansions | unberührt: gesperrt nach E37 | aktueller Sim-Wert; missing Quelle sperrt Nutzung statt stiller 0; Erweiterung nullable bei unbekannter Basis |
| game_stadium.real_sued_vip | neu; im Modellbestand nicht vorhanden | E / Import: apply_package | nein | unberührt: gesperrt nach E37 | nullable Quellkapazität; 0 ist belegte Null, NULL ist unbekannt |
| game_stadium.real_sued_vip_basis | neu; im Modellbestand nicht vorhanden | E / Import: apply_package | nein | unberührt: gesperrt nach E37 | belegt / berechnet, fehlend NULL |
| game_stadium.sued_vip | repariert; game/models.py:906 | S / Spiel | ja: real_sued_vip + fertiggestellte Ausbauten → initialize_package_game_state / resolve_due_expansions | unberührt: gesperrt nach E37 | aktueller Sim-Wert; missing Quelle sperrt Nutzung statt stiller 0; Erweiterung nullable bei unbekannter Basis |
| game_stadium.real_west_standing | neu; im Modellbestand nicht vorhanden | E / Import: apply_package | nein | unberührt: gesperrt nach E37 | nullable Quellkapazität; 0 ist belegte Null, NULL ist unbekannt |
| game_stadium.real_west_standing_basis | neu; im Modellbestand nicht vorhanden | E / Import: apply_package | nein | unberührt: gesperrt nach E37 | belegt / berechnet, fehlend NULL |
| game_stadium.west_standing | repariert; game/models.py:908 | S / Spiel | ja: real_west_standing + fertiggestellte Ausbauten → initialize_package_game_state / resolve_due_expansions | unberührt: gesperrt nach E37 | aktueller Sim-Wert; missing Quelle sperrt Nutzung statt stiller 0; Erweiterung nullable bei unbekannter Basis |
| game_stadium.real_west_seating | neu; im Modellbestand nicht vorhanden | E / Import: apply_package | nein | unberührt: gesperrt nach E37 | nullable Quellkapazität; 0 ist belegte Null, NULL ist unbekannt |
| game_stadium.real_west_seating_basis | neu; im Modellbestand nicht vorhanden | E / Import: apply_package | nein | unberührt: gesperrt nach E37 | belegt / berechnet, fehlend NULL |
| game_stadium.west_seating | repariert; game/models.py:909 | S / Spiel | ja: real_west_seating + fertiggestellte Ausbauten → initialize_package_game_state / resolve_due_expansions | unberührt: gesperrt nach E37 | aktueller Sim-Wert; missing Quelle sperrt Nutzung statt stiller 0; Erweiterung nullable bei unbekannter Basis |
| game_stadium.real_west_vip | neu; im Modellbestand nicht vorhanden | E / Import: apply_package | nein | unberührt: gesperrt nach E37 | nullable Quellkapazität; 0 ist belegte Null, NULL ist unbekannt |
| game_stadium.real_west_vip_basis | neu; im Modellbestand nicht vorhanden | E / Import: apply_package | nein | unberührt: gesperrt nach E37 | belegt / berechnet, fehlend NULL |
| game_stadium.west_vip | repariert; game/models.py:910 | S / Spiel | ja: real_west_vip + fertiggestellte Ausbauten → initialize_package_game_state / resolve_due_expansions | unberührt: gesperrt nach E37 | aktueller Sim-Wert; missing Quelle sperrt Nutzung statt stiller 0; Erweiterung nullable bei unbekannter Basis |
| game_stadium.lawn_quality | vorhanden; game/models.py:890 | S / Spiel | nein | unberührt: gesperrt nach E37 | nicht im Paket |
| game_stadium.price_standing | vorhanden; game/models.py:912 | S / Spiel | nein | unberührt: gesperrt nach E37 | nicht im Paket |
| game_stadium.price_seating | vorhanden; game/models.py:916 | S / Spiel | nein | unberührt: gesperrt nach E37 | nicht im Paket |
| game_stadium.price_vip | vorhanden; game/models.py:920 | S / Spiel | nein | unberührt: gesperrt nach E37 | nicht im Paket |
| game_stadium.nlz_level | vorhanden; game/models.py:926 | S / Spiel | nein | unberührt: gesperrt nach E37 | nicht im Paket |
| game_stadium.medizin_level | vorhanden; game/models.py:927 | S / Spiel | nein | unberührt: gesperrt nach E37 | nicht im Paket |
| game_stadium.training_level | vorhanden; game/models.py:928 | S / Spiel | nein | unberührt: gesperrt nach E37 | nicht im Paket |
| game_stadium.office_level | vorhanden; game/models.py:929 | S / Spiel | nein | unberührt: gesperrt nach E37 | nicht im Paket |

### Stadionausbau

| Tabelle und Spalte | Zustand / Codebeleg | Schicht / Schreiber | Spiegel: Quelle → Funktion | Upload nach Ligastart | Präzisierung |
|---|---|---|---|---|---|
| game_stadiumexpansion.stadium_id | vorhanden; game/models.py:973 | S / Spiel | nein | unberührt: gesperrt nach E37 | — |
| game_stadiumexpansion.stand | vorhanden; game/models.py:978 | S / Spiel | nein | unberührt: gesperrt nach E37 | — |
| game_stadiumexpansion.seat_type | vorhanden; game/models.py:979 | S / Spiel | nein | unberührt: gesperrt nach E37 | — |
| game_stadiumexpansion.seats_added | vorhanden; game/models.py:980 | S / Spiel | nein | unberührt: gesperrt nach E37 | — |
| game_stadiumexpansion.cost | vorhanden; game/models.py:981 | S / Spiel | nein | unberührt: gesperrt nach E37 | — |
| game_stadiumexpansion.ordered_at | vorhanden; game/models.py:982 | S / Spiel | nein | unberührt: gesperrt nach E37 | — |
| game_stadiumexpansion.completes_at | vorhanden; game/models.py:984 | S / Spiel | nein | unberührt: gesperrt nach E37 | — |
| game_stadiumexpansion.applied | vorhanden; game/models.py:988 | S / Spiel | nein | unberührt: gesperrt nach E37 | — |

### Stadionumfeld

| Tabelle und Spalte | Zustand / Codebeleg | Schicht / Schreiber | Spiegel: Quelle → Funktion | Upload nach Ligastart | Präzisierung |
|---|---|---|---|---|---|
| game_clubstadionumfeldstate.club_id | vorhanden; game/models.py:6819 | S / Spiel | nein | unberührt: gesperrt nach E37 | — |
| game_clubstadionumfeldstate.state | vorhanden; game/models.py:6825 | S / Spiel | nein | unberührt: gesperrt nach E37 | — |
| game_clubstadionumfeldstate.updated_at | vorhanden; game/models.py:6826 | S / Spiel | nein | unberührt: gesperrt nach E37 | — |

### Spieler

| Tabelle und Spalte | Zustand / Codebeleg | Schicht / Schreiber | Spiegel: Quelle → Funktion | Upload nach Ligastart | Präzisierung |
|---|---|---|---|---|---|
| game_player.first_name | vorhanden; game/models.py:1937 | E / Import: apply_package | nein | überschreiben: Ü-Stamm | — |
| game_player.last_name | vorhanden; game/models.py:1938 | E / Import: apply_package | nein | überschreiben: Ü-Stamm | — |
| game_player.date_of_birth | vorhanden; game/models.py:1963 | E / Import: apply_package | nein | überschreiben: Ü-Stamm | — |
| game_player.nationalities | vorhanden; game/models.py:1967 | E / Import: apply_package | nein | überschreiben: Ü-Stamm | Array wird verlustfrei als vorhandene normalisierte Länderliste gespeichert; kein zweites Nationsfeld |
| game_player.height_cm | vorhanden; game/models.py:1982 | E / Import: apply_package | nein | überschreiben: Ü-Stamm | — |
| game_player.strong_foot | vorhanden; game/models.py:1987 | E / Import: apply_package | nein | überschreiben: Ü-Stamm | Paketnull bleibt unbekannt/leer; keine rechte Seite erfinden |
| game_player.display_name | neu; im Modellbestand nicht vorhanden | E / Import: apply_package | nein | überschreiben: Ü-Stamm | bisher full_name ist nur Property, kein Künstlername |
| game_player.age | repariert; game/models.py:1981 | E / Import: apply_package | ja: date_of_birth + Referenzdatum → sync_player_identity_mirrors (geplant) | überschreiben: Ü-Stamm | keine Mannschaftsentscheidung über Alter |
| game_player.main_position_1 | vorhanden; game/models.py:2018 | E / Import: apply_package | nein | unberührt: N30; spätere Änderung nur E35 | TM-Auswertungsfenster; 3. Stelle nur nach erlaubter ROV/ROM/LOV/LOM-Regel |
| game_player.main_position_2 | vorhanden; game/models.py:2024 | E / Import: apply_package | nein | unberührt: N30; spätere Änderung nur E35 | TM-Auswertungsfenster; 3. Stelle nur nach erlaubter ROV/ROM/LOV/LOM-Regel |
| game_player.main_position_3 | vorhanden; game/models.py:2030 | E / Import: apply_package | nein | unberührt: N30; spätere Änderung nur E35 | TM-Auswertungsfenster; 3. Stelle nur nach erlaubter ROV/ROM/LOV/LOM-Regel |
| game_player.secondary_position_1 | vorhanden; game/models.py:2036 | E / Import: apply_package | nein | unberührt: N30; spätere Änderung nur E35 | TM-Auswertungsfenster; 3. Stelle nur nach erlaubter ROV/ROM/LOV/LOM-Regel |
| game_player.secondary_position_2 | vorhanden; game/models.py:2042 | E / Import: apply_package | nein | unberührt: N30; spätere Änderung nur E35 | TM-Auswertungsfenster; 3. Stelle nur nach erlaubter ROV/ROM/LOV/LOM-Regel |
| game_player.secondary_position_3 | vorhanden; game/models.py:2048 | E / Import: apply_package | nein | unberührt: N30; spätere Änderung nur E35 | TM-Auswertungsfenster; 3. Stelle nur nach erlaubter ROV/ROM/LOV/LOM-Regel |
| game_player.position | repariert; game/models.py:2003 | E / Import: apply_package | ja: HP/NP → sync_position_mirrors (geplant) | überschreiben: Ü-Stamm | keine zweite frei bearbeitbare Positionsquelle; CMT/FMI-Positionen nur Beleg |
| game_player.primary_position | repariert; game/models.py:2008 | E / Import: apply_package | ja: HP/NP → sync_position_mirrors (geplant) | überschreiben: Ü-Stamm | keine zweite frei bearbeitbare Positionsquelle; CMT/FMI-Positionen nur Beleg |
| game_player.source_positions | repariert; game/models.py:2013 | E / Import: apply_package | ja: HP/NP → sync_position_mirrors (geplant) | überschreiben: Ü-Stamm | keine zweite frei bearbeitbare Positionsquelle; CMT/FMI-Positionen nur Beleg |
| game_player.real_life_club_id | Altleser; game/models.py:2083 | S / Spiel | Vorschlag: owner_club_id → sync_loan_mirrors (T2) | unberührt: N30 | N31: kein unabhängiger Stammverein; vorerst beibehalten, Spiegel vorgeschlagen, Leser siehe T1-Bericht |
| game_player.selection_evidence | neu; im Modellbestand nicht vorhanden | E / Import: apply_package | nein | unberührt: gesperrt nach E37 | JSON für gem, u21_reason, u21_source, double_listed, position_group; Recherche, nicht aktuelle Mannschaft |
| game_player.transfermarkt_profile_url | vorhanden; game/models.py:1961 | E / Import: apply_package | ja: ID + Paket-/Quell-URL → sync_external_id_mirrors (geplant) | überschreiben: Ü-Stamm | — |
| game_player.transfermarkt_market_value_url | vorhanden; game/models.py:1962 | E / Import: apply_package | ja: ID + Paket-/Quell-URL → sync_external_id_mirrors (geplant) | überschreiben: Ü-Stamm | — |
| game_player.nt_nationality | vorhanden; game/models.py:1971 | E / Import: apply_package | nein | überschreiben: Ü-Stamm | nicht aus raw CMT-Nationalteam raten; bei fehlendem Paketwert unverändert/leer |

### Kader / Spielstand

| Tabelle und Spalte | Zustand / Codebeleg | Schicht / Schreiber | Spiegel: Quelle → Funktion | Upload nach Ligastart | Präzisierung |
|---|---|---|---|---|---|
| game_player.squad_team | neu; im Modellbestand nicht vorhanden | S / Spiel | nein | unberührt: gesperrt nach E37 | first / u21, keine Age-Split-Auswahl |
| game_player.owner_club_id | neu; im Modellbestand nicht vorhanden | S / Spiel | nein | unberührt: gesperrt nach E37 | expliziter Stamm-/Leihverein im Sim-Spielstand |
| game_player.loan_club_id | neu; im Modellbestand nicht vorhanden | S / Spiel | nein | unberührt: gesperrt nach E37 | expliziter Stamm-/Leihverein im Sim-Spielstand |
| game_player.owner_club_tm_id | neu gegenüber N27; game/import_schema.py | S / Spiel | nein | unberührt: N30 | N29: TM-Identität des Stammvereins, auch ohne importierte Club-Zeile; E69-FK-Nachtrag erlaubt |
| game_player.owner_club_original_name | neu gegenüber N27; game/import_schema.py | S / Spiel | nein | unberührt: N30 | Originalname des Stammvereins; kein Name-Matching |
| game_player.loan_club_tm_id | neu gegenüber N27; game/import_schema.py | S / Spiel | nein | unberührt: N30 | N29: TM-Identität des Leihvereins, auch ohne importierte Club-Zeile; E69-FK-Nachtrag erlaubt |
| game_player.loan_club_original_name | neu gegenüber N27; game/import_schema.py | S / Spiel | nein | unberührt: N30 | Originalname des Leihvereins; kein Name-Matching |
| game_player.import_lock | neu; im Modellbestand nicht vorhanden | S / Spiel | nein | unberührt: gesperrt nach E37 | Spiel setzt Sperre aus validierter Pflichtquellenprüfung; nicht identisch mit WS-Rotsperre |
| game_player.import_lock_reasons | neu; im Modellbestand nicht vorhanden | S / Spiel | nein | unberührt: gesperrt nach E37 | Spiel setzt Sperre aus validierter Pflichtquellenprüfung; nicht identisch mit WS-Rotsperre |
| game_player.club_id | repariert; game/models.py:2077 | S / Spiel | nein | unberührt: gesperrt nach E37 | aktiver Spielverein; Stamm-/Leih-Pool nicht durch club=NULL als Scouting tarnen |
| game_player.loan_status | repariert; game/models.py:2110 | S / Spiel | ja: owner_club / loan_club / club → sync_loan_compatibility (geplant) | unberührt: gesperrt nach E37 | Altvertrag für Transfermodule; Anzeige loaned_in/out wird je betrachtendem Verein abgeleitet |
| game_player.loan_partner_club_id | repariert; game/models.py:2119 | S / Spiel | ja: owner_club / loan_club / club → sync_loan_compatibility (geplant) | unberührt: gesperrt nach E37 | Altvertrag für Transfermodule; Anzeige loaned_in/out wird je betrachtendem Verein abgeleitet |
| game_player.loan_until | vorhanden; game/models.py:2127 | S / Spiel | nein | unberührt: gesperrt nach E37 | Paket darf nur initiale Spielinitialisierung anstoßen; erneuter Upload kein Zustandsreset |
| game_player.shirt_number | vorhanden; game/models.py:1997 | S / Spiel | nein | unberührt: gesperrt nach E37 | Paket darf nur initiale Spielinitialisierung anstoßen; erneuter Upload kein Zustandsreset |
| game_player.salary_per_match | vorhanden; game/models.py:2067 | S / Spiel | nein | unberührt: gesperrt nach E37 | Startgehalt im Spiel: 5.000 €/1 Mio. Marktwert; später kein Snapshot.save-Schreibrecht |
| game_player.contract_until | vorhanden; game/models.py:2072 | S / Spiel | nein | unberührt: gesperrt nach E37 | Paket darf nur initiale Spielinitialisierung anstoßen; erneuter Upload kein Zustandsreset |
| game_player.ws_injury_type | vorhanden; game/models.py:2091 | S / Spiel | nein | unberührt: gesperrt nach E37 | Paket darf nur initiale Spielinitialisierung anstoßen; erneuter Upload kein Zustandsreset |
| game_player.ws_injury_days_remaining | vorhanden; game/models.py:2096 | S / Spiel | nein | unberührt: gesperrt nach E37 | Paket darf nur initiale Spielinitialisierung anstoßen; erneuter Upload kein Zustandsreset |
| game_player.ws_suspension_reason | vorhanden; game/models.py:2097 | S / Spiel | nein | unberührt: gesperrt nach E37 | Paket darf nur initiale Spielinitialisierung anstoßen; erneuter Upload kein Zustandsreset |
| game_player.ws_suspension_matches_remaining | vorhanden; game/models.py:2102 | S / Spiel | nein | unberührt: gesperrt nach E37 | Paket darf nur initiale Spielinitialisierung anstoßen; erneuter Upload kein Zustandsreset |
| game_player.is_on_transfer_list | vorhanden; game/models.py:2132 | S / Spiel | nein | unberührt: gesperrt nach E37 | Paket darf nur initiale Spielinitialisierung anstoßen; erneuter Upload kein Zustandsreset |
| game_player.is_on_loan_list | vorhanden; game/models.py:2136 | S / Spiel | nein | unberührt: gesperrt nach E37 | Paket darf nur initiale Spielinitialisierung anstoßen; erneuter Upload kein Zustandsreset |
| game_player.sale_category | vorhanden; game/models.py:2148 | S / Spiel | nein | unberührt: gesperrt nach E37 | Paket darf nur initiale Spielinitialisierung anstoßen; erneuter Upload kein Zustandsreset |
| game_player.sale_visible_to_ai | vorhanden; game/models.py:2156 | S / Spiel | nein | unberührt: gesperrt nach E37 | Paket darf nur initiale Spielinitialisierung anstoßen; erneuter Upload kein Zustandsreset |
| game_player.transfer_locked_until | vorhanden; game/models.py:2164 | S / Spiel | nein | unberührt: gesperrt nach E37 | Paket darf nur initiale Spielinitialisierung anstoßen; erneuter Upload kein Zustandsreset |
| game_player.pool_status | vorhanden; game/models.py:2200 | S / Spiel | nein | unberührt: gesperrt nach E37 | Leih-Pool ungleich Scouting-Pool; Verliehene nicht als scoutable behandeln |
| game_player.scouting_category | vorhanden; game/models.py:2221 | S / Spiel | nein | unberührt: gesperrt nach E37 | Paket darf nur initiale Spielinitialisierung anstoßen; erneuter Upload kein Zustandsreset |
| game_player.wsc_conflict | vorhanden; game/models.py:2229 | S / Spiel | nein | unberührt: gesperrt nach E37 | Paket darf nur initiale Spielinitialisierung anstoßen; erneuter Upload kein Zustandsreset |
| game_player.is_callable | vorhanden; game/models.py:2234 | S / Spiel | nein | unberührt: gesperrt nach E37 | Paket darf nur initiale Spielinitialisierung anstoßen; erneuter Upload kein Zustandsreset |
| game_player.admin_reviewed | vorhanden; game/models.py:2239 | S / Spiel | nein | unberührt: gesperrt nach E37 | Paket darf nur initiale Spielinitialisierung anstoßen; erneuter Upload kein Zustandsreset |
| game_player.wsc_player_id | vorhanden; game/models.py:1939 | S / Spiel | nein | unberührt: gesperrt nach E37 | technische stabile Spiel-ID; nicht externe ID oder Name |
| game_player.market_value | repariert; game/models.py:2057 | S / Spiel | ja: letzter freigegebener Marktwertpunkt → sync_current_market_value (geplant) | unberührt: gesperrt nach E37 | 0≠NULL; initialer N10-Startpunkt 50.000 nur bei fehlendem TM-MW; nie Save-Nebeneffekt |
| game_player.potential | repariert; game/models.py:2055 | S / Spiel | ja: maßgebliche rohe Potentialwerte → vorhandener Stärkepfad, kompatibler 100er-Speicher | unberührt: gesperrt nach E37 | keine 200er-Engine-Stärke in dieses 100er-Feld schreiben; kein Dynamic-Ersatzwert |

### Stärkeprofil

| Tabelle und Spalte | Zustand / Codebeleg | Schicht / Schreiber | Spiegel: Quelle → Funktion | Upload nach Ligastart | Präzisierung |
|---|---|---|---|---|---|
| game_playerstrengthprofile.player_id | vorhanden; game/models.py:3283 | S / Spiel | nein | unberührt: gesperrt nach E37 | bestehendes Profil bleibt; Sperrprüfung muss vor Ersatz 50 / Frische 100 greifen |
| game_playerstrengthprofile.base_strength | repariert; game/models.py:3289 | S / Spiel | ja: strength_service.compute_strength_for_player / calculate_final_strength | unberührt: gesperrt nach E37 | bestehendes Profil bleibt; Sperrprüfung muss vor Ersatz 50 / Frische 100 greifen |
| game_playerstrengthprofile.form_modifier | vorhanden; game/models.py:3294 | S / Spiel | nein | unberührt: gesperrt nach E37 | bestehendes Profil bleibt; Sperrprüfung muss vor Ersatz 50 / Frische 100 greifen |
| game_playerstrengthprofile.freshness | vorhanden; game/models.py:3299 | S / Spiel | nein | unberührt: gesperrt nach E37 | bestehendes Profil bleibt; Sperrprüfung muss vor Ersatz 50 / Frische 100 greifen |
| game_playerstrengthprofile.final_strength | repariert; game/models.py:3309 | S / Spiel | ja: strength_service.compute_strength_for_player / calculate_final_strength | unberührt: gesperrt nach E37 | bestehendes Profil bleibt; Sperrprüfung muss vor Ersatz 50 / Frische 100 greifen |
| game_playerstrengthprofile.updated_at | vorhanden; game/models.py:3315 | S / Spiel | nein | unberührt: gesperrt nach E37 | bestehendes Profil bleibt; Sperrprüfung muss vor Ersatz 50 / Frische 100 greifen |

### Externe IDs

| Tabelle und Spalte | Zustand / Codebeleg | Schicht / Schreiber | Spiegel: Quelle → Funktion | Upload nach Ligastart | Präzisierung |
|---|---|---|---|---|---|
| game_playerexternalid.player_id | erweitert; game/models.py:2660 | E / Import: apply_package | nein | überschreiben: Ü-ID, kein Identitätswechsel | nullable nur mit person_id; genau ein Besitzer |
| game_playerexternalid.source_id | vorhanden; game/models.py:2665 | E / Import: apply_package | nein | überschreiben: Ü-ID, kein Identitätswechsel | — |
| game_playerexternalid.external_id | erweitert; game/models.py:2670 | E / Import: apply_package | nein | überschreiben: Ü-ID, kein Identitätswechsel | nullable für nicht_gefunden / nicht_vorhanden; kein NULL→0 |
| game_playerexternalid.profile_url | vorhanden; game/models.py:2671 | E / Import: apply_package | nein | überschreiben: Ü-ID, kein Identitätswechsel | — |
| game_playerexternalid.is_primary | vorhanden; game/models.py:2672 | E / Import: apply_package | nein | überschreiben: Ü-ID, kein Identitätswechsel | — |
| game_playerexternalid.notes | vorhanden; game/models.py:2673 | E / Import: apply_package | nein | überschreiben: Ü-ID, kein Identitätswechsel | — |
| game_playerexternalid.db_slug | vorhanden; game/models.py:2674 | E / Import: apply_package | nein | überschreiben: Ü-ID, kein Identitätswechsel | — |
| game_playerexternalid.source_url | vorhanden; game/models.py:2679 | E / Import: apply_package | nein | überschreiben: Ü-ID, kein Identitätswechsel | — |
| game_playerexternalid.created_at | vorhanden; game/models.py:2680 | E / Import: apply_package | nein | überschreiben: Ü-ID, kein Identitätswechsel | — |
| game_playerexternalid.updated_at | vorhanden; game/models.py:2681 | E / Import: apply_package | nein | überschreiben: Ü-ID, kein Identitätswechsel | — |
| game_playerexternalid.last_seen_at | vorhanden; game/models.py:2682 | E / Import: apply_package | nein | überschreiben: Ü-ID, kein Identitätswechsel | — |
| game_playerexternalid.status | neu; im Modellbestand nicht vorhanden | E / Import: apply_package | nein | überschreiben: Ü-ID, kein Identitätswechsel | — |
| game_playerexternalid.checked_at | neu; im Modellbestand nicht vorhanden | E / Import: apply_package | nein | überschreiben: Ü-ID, kein Identitätswechsel | — |
| game_clubexternalid.club_id | vorhanden; game/models.py:2710 | E / Import: apply_package | nein | überschreiben: Ü-ID, kein Identitätswechsel | — |
| game_clubexternalid.source_id | vorhanden; game/models.py:2715 | E / Import: apply_package | nein | überschreiben: Ü-ID, kein Identitätswechsel | — |
| game_clubexternalid.external_id | erweitert; game/models.py:2720 | E / Import: apply_package | nein | überschreiben: Ü-ID, kein Identitätswechsel | nullable für nicht_gefunden / nicht_vorhanden; kein NULL→0 |
| game_clubexternalid.db_slug | vorhanden; game/models.py:2721 | E / Import: apply_package | nein | überschreiben: Ü-ID, kein Identitätswechsel | — |
| game_clubexternalid.source_url | vorhanden; game/models.py:2725 | E / Import: apply_package | nein | überschreiben: Ü-ID, kein Identitätswechsel | — |
| game_clubexternalid.created_at | vorhanden; game/models.py:2726 | E / Import: apply_package | nein | überschreiben: Ü-ID, kein Identitätswechsel | — |
| game_clubexternalid.updated_at | vorhanden; game/models.py:2727 | E / Import: apply_package | nein | überschreiben: Ü-ID, kein Identitätswechsel | — |
| game_clubexternalid.last_seen_at | vorhanden; game/models.py:2728 | E / Import: apply_package | nein | überschreiben: Ü-ID, kein Identitätswechsel | — |
| game_clubexternalid.status | neu; im Modellbestand nicht vorhanden | E / Import: apply_package | nein | überschreiben: Ü-ID, kein Identitätswechsel | — |
| game_clubexternalid.checked_at | neu; im Modellbestand nicht vorhanden | E / Import: apply_package | nein | überschreiben: Ü-ID, kein Identitätswechsel | — |
| game_playerexternalid.person_id | neu; im Modellbestand nicht vorhanden | E / Import: apply_package | nein | überschreiben: Ü-ID, kein Identitätswechsel | HistoricCoach als allgemeine historische Person; XOR zu player_id |
| game_playerexternalid.identity_kind | neu; im Modellbestand nicht vorhanden | E / Import: apply_package | nein | überschreiben: Ü-ID, kein Identitätswechsel | TM-spieler / TM-trainer getrennt; eindeutiger Quell-ID-Raum |
| game_playerexternalid.match_evidence | neu; im Modellbestand nicht vorhanden | E / Import: apply_package | nein | überschreiben: Ü-ID, kein Identitätswechsel | Paket match/proof, kein Name/DOB-Matching |

### Historische Person

| Tabelle und Spalte | Zustand / Codebeleg | Schicht / Schreiber | Spiegel: Quelle → Funktion | Upload nach Ligastart | Präzisierung |
|---|---|---|---|---|---|
| game_historiccoach.name | vorhanden; game/models.py:6005 | E / Import: apply_package | nein | überschreiben: Ü-Stamm | bestehende Tabelle zu Personenkatalog erweitern, kein paralleles Person-Modell |
| game_historiccoach.nationality | vorhanden; game/models.py:6006 | E / Import: apply_package | nein | überschreiben: Ü-Stamm | bestehende Tabelle zu Personenkatalog erweitern, kein paralleles Person-Modell |
| game_historiccoach.birth_date | vorhanden; game/models.py:6007 | E / Import: apply_package | nein | überschreiben: Ü-Stamm | bestehende Tabelle zu Personenkatalog erweitern, kein paralleles Person-Modell |
| game_historiccoach.notes | vorhanden; game/models.py:6008 | E / Import: apply_package | nein | überschreiben: Ü-Stamm | bestehende Tabelle zu Personenkatalog erweitern, kein paralleles Person-Modell |
| game_historiccoach.fm_inside_id | erweitert; game/models.py:6000 | E / Import: apply_package | ja: PlayerExternalId(Person,FM) → sync_external_id_mirrors (geplant) | überschreiben: Ü-ID, kein Identitätswechsel | nullable, bleibt für bestehende Bildleser; bei verknüpftem Player dessen kanonische ID |
| game_historiccoach.person_kind | neu; im Modellbestand nicht vorhanden | E / Import: apply_package | nein | überschreiben: Ü-ID, kein Identitätswechsel | spieler / trainer |
| game_historiccoach.linked_player_id | neu; im Modellbestand nicht vorhanden | E / Import: apply_package | nein | überschreiben: Ü-ID, kein Identitätswechsel | nur über externe IDs verbinden; keine Namensauflösung |

### Quellwerte / Archiv

| Tabelle und Spalte | Zustand / Codebeleg | Schicht / Schreiber | Spiegel: Quelle → Funktion | Upload nach Ligastart | Präzisierung |
|---|---|---|---|---|---|
| game_playersourceratingsnapshot.player_id | vorhanden; game/models.py:3685 | E / Import: apply_package | nein | unberührt: gesperrt nach E37 | Versionsarchiv; keine Prune-Kürzung / kein implizites update_current; NULL-Potential bleibt NULL |
| game_playersourceratingsnapshot.source_id | vorhanden; game/models.py:3690 | E / Import: apply_package | nein | unberührt: gesperrt nach E37 | Versionsarchiv; keine Prune-Kürzung / kein implizites update_current; NULL-Potential bleibt NULL |
| game_playersourceratingsnapshot.recorded_at | vorhanden; game/models.py:3695 | E / Import: apply_package | nein | unberührt: gesperrt nach E37 | Versionsarchiv; keine Prune-Kürzung / kein implizites update_current; NULL-Potential bleibt NULL |
| game_playersourceratingsnapshot.rating | vorhanden; game/models.py:3696 | E / Import: apply_package | nein | unberührt: gesperrt nach E37 | Versionsarchiv; keine Prune-Kürzung / kein implizites update_current; NULL-Potential bleibt NULL |
| game_playersourceratingsnapshot.potential | vorhanden; game/models.py:3699 | E / Import: apply_package | nein | unberührt: gesperrt nach E37 | Versionsarchiv; keine Prune-Kürzung / kein implizites update_current; NULL-Potential bleibt NULL |
| game_playersourceratingsnapshot.source_url | vorhanden; game/models.py:3704 | E / Import: apply_package | nein | unberührt: gesperrt nach E37 | Versionsarchiv; keine Prune-Kürzung / kein implizites update_current; NULL-Potential bleibt NULL |
| game_playersourceratingsnapshot.source_version | vorhanden; game/models.py:3705 | E / Import: apply_package | nein | unberührt: gesperrt nach E37 | Versionsarchiv; keine Prune-Kürzung / kein implizites update_current; NULL-Potential bleibt NULL |
| game_playersourceratingsnapshot.update_current | repariert; game/models.py:3706 | E / Import: apply_package | nein | unberührt: gesperrt nach E37 | Versionsarchiv; keine Prune-Kürzung / kein implizites update_current; NULL-Potential bleibt NULL |
| game_playersourceratingsnapshot.raw_payload | vorhanden; game/models.py:3710 | E / Import: apply_package | nein | unberührt: gesperrt nach E37 | Versionsarchiv; keine Prune-Kürzung / kein implizites update_current; NULL-Potential bleibt NULL |
| game_playersourceratingsnapshot.notes | vorhanden; game/models.py:3711 | E / Import: apply_package | nein | unberührt: gesperrt nach E37 | Versionsarchiv; keine Prune-Kürzung / kein implizites update_current; NULL-Potential bleibt NULL |
| game_playersourceratingsnapshot.created_at | vorhanden; game/models.py:3712 | E / Import: apply_package | nein | unberührt: gesperrt nach E37 | Versionsarchiv; keine Prune-Kürzung / kein implizites update_current; NULL-Potential bleibt NULL |
| game_playersourceratingsnapshot.payload_hash | neu; im Modellbestand nicht vorhanden | E / Import: apply_package | nein | unberührt: gesperrt nach E37 | gleicher Tag mit anderer Version/anderen Rohdaten darf keinen vorherigen Stand verdrängen |

### Aktuelle Quellwerte

| Tabelle und Spalte | Zustand / Codebeleg | Schicht / Schreiber | Spiegel: Quelle → Funktion | Upload nach Ligastart | Präzisierung |
|---|---|---|---|---|---|
| game_playersourcerating.player_id | erweitert; game/models.py:3024 | E / Import: apply_package | nein | unberührt: gesperrt nach E37 | source_version und checked_at bereits vorhanden; Rohdaten fehlen hier, aber Snapshot.raw_payload existiert |
| game_playersourcerating.source | erweitert; game/models.py:3029 | E / Import: apply_package | nein | unberührt: gesperrt nach E37 | source_version und checked_at bereits vorhanden; Rohdaten fehlen hier, aber Snapshot.raw_payload existiert |
| game_playersourcerating.rating | erweitert; game/models.py:3033 | E / Import: apply_package | ja: maßgeblicher Snapshot + unveränderte Attributnormalisierung → sync_current_source_ratings (geplant) | unberührt: gesperrt nach E37 | source_version und checked_at bereits vorhanden; Rohdaten fehlen hier, aber Snapshot.raw_payload existiert |
| game_playersourcerating.potential | erweitert; game/models.py:3039 | E / Import: apply_package | ja: maßgeblicher Snapshot + unveränderte Attributnormalisierung → sync_current_source_ratings (geplant) | unberührt: gesperrt nach E37 | source_version und checked_at bereits vorhanden; Rohdaten fehlen hier, aber Snapshot.raw_payload existiert |
| game_playersourcerating.tempo | erweitert; game/models.py:3051 | E / Import: apply_package | ja: maßgeblicher Snapshot + unveränderte Attributnormalisierung → sync_current_source_ratings (geplant) | unberührt: gesperrt nach E37 | source_version und checked_at bereits vorhanden; Rohdaten fehlen hier, aber Snapshot.raw_payload existiert |
| game_playersourcerating.ausdauer | erweitert; game/models.py:3055 | E / Import: apply_package | ja: maßgeblicher Snapshot + unveränderte Attributnormalisierung → sync_current_source_ratings (geplant) | unberührt: gesperrt nach E37 | source_version und checked_at bereits vorhanden; Rohdaten fehlen hier, aber Snapshot.raw_payload existiert |
| game_playersourcerating.kraft | erweitert; game/models.py:3059 | E / Import: apply_package | ja: maßgeblicher Snapshot + unveränderte Attributnormalisierung → sync_current_source_ratings (geplant) | unberührt: gesperrt nach E37 | source_version und checked_at bereits vorhanden; Rohdaten fehlen hier, aber Snapshot.raw_payload existiert |
| game_playersourcerating.technik | erweitert; game/models.py:3063 | E / Import: apply_package | ja: maßgeblicher Snapshot + unveränderte Attributnormalisierung → sync_current_source_ratings (geplant) | unberührt: gesperrt nach E37 | source_version und checked_at bereits vorhanden; Rohdaten fehlen hier, aber Snapshot.raw_payload existiert |
| game_playersourcerating.dribbling | erweitert; game/models.py:3068 | E / Import: apply_package | ja: maßgeblicher Snapshot + unveränderte Attributnormalisierung → sync_current_source_ratings (geplant) | unberührt: gesperrt nach E37 | source_version und checked_at bereits vorhanden; Rohdaten fehlen hier, aber Snapshot.raw_payload existiert |
| game_playersourcerating.passspiel | erweitert; game/models.py:3072 | E / Import: apply_package | ja: maßgeblicher Snapshot + unveränderte Attributnormalisierung → sync_current_source_ratings (geplant) | unberührt: gesperrt nach E37 | source_version und checked_at bereits vorhanden; Rohdaten fehlen hier, aber Snapshot.raw_payload existiert |
| game_playersourcerating.flanken | erweitert; game/models.py:3076 | E / Import: apply_package | ja: maßgeblicher Snapshot + unveränderte Attributnormalisierung → sync_current_source_ratings (geplant) | unberührt: gesperrt nach E37 | source_version und checked_at bereits vorhanden; Rohdaten fehlen hier, aber Snapshot.raw_payload existiert |
| game_playersourcerating.abschluss | erweitert; game/models.py:3080 | E / Import: apply_package | ja: maßgeblicher Snapshot + unveränderte Attributnormalisierung → sync_current_source_ratings (geplant) | unberührt: gesperrt nach E37 | source_version und checked_at bereits vorhanden; Rohdaten fehlen hier, aber Snapshot.raw_payload existiert |
| game_playersourcerating.kopfball | erweitert; game/models.py:3084 | E / Import: apply_package | ja: maßgeblicher Snapshot + unveränderte Attributnormalisierung → sync_current_source_ratings (geplant) | unberührt: gesperrt nach E37 | source_version und checked_at bereits vorhanden; Rohdaten fehlen hier, aber Snapshot.raw_payload existiert |
| game_playersourcerating.zweikampf | erweitert; game/models.py:3088 | E / Import: apply_package | ja: maßgeblicher Snapshot + unveränderte Attributnormalisierung → sync_current_source_ratings (geplant) | unberührt: gesperrt nach E37 | source_version und checked_at bereits vorhanden; Rohdaten fehlen hier, aber Snapshot.raw_payload existiert |
| game_playersourcerating.defensivstellung | erweitert; game/models.py:3092 | E / Import: apply_package | ja: maßgeblicher Snapshot + unveränderte Attributnormalisierung → sync_current_source_ratings (geplant) | unberührt: gesperrt nach E37 | source_version und checked_at bereits vorhanden; Rohdaten fehlen hier, aber Snapshot.raw_payload existiert |
| game_playersourcerating.uebersicht | erweitert; game/models.py:3097 | E / Import: apply_package | ja: maßgeblicher Snapshot + unveränderte Attributnormalisierung → sync_current_source_ratings (geplant) | unberührt: gesperrt nach E37 | source_version und checked_at bereits vorhanden; Rohdaten fehlen hier, aber Snapshot.raw_payload existiert |
| game_playersourcerating.teamwork | erweitert; game/models.py:3101 | E / Import: apply_package | ja: maßgeblicher Snapshot + unveränderte Attributnormalisierung → sync_current_source_ratings (geplant) | unberührt: gesperrt nach E37 | source_version und checked_at bereits vorhanden; Rohdaten fehlen hier, aber Snapshot.raw_payload existiert |
| game_playersourcerating.ecken | erweitert; game/models.py:3108 | E / Import: apply_package | ja: maßgeblicher Snapshot + unveränderte Attributnormalisierung → sync_current_source_ratings (geplant) | unberührt: gesperrt nach E37 | source_version und checked_at bereits vorhanden; Rohdaten fehlen hier, aber Snapshot.raw_payload existiert |
| game_playersourcerating.freistoss | erweitert; game/models.py:3113 | E / Import: apply_package | ja: maßgeblicher Snapshot + unveränderte Attributnormalisierung → sync_current_source_ratings (geplant) | unberührt: gesperrt nach E37 | source_version und checked_at bereits vorhanden; Rohdaten fehlen hier, aber Snapshot.raw_payload existiert |
| game_playersourcerating.elfmeter | erweitert; game/models.py:3117 | E / Import: apply_package | ja: maßgeblicher Snapshot + unveränderte Attributnormalisierung → sync_current_source_ratings (geplant) | unberührt: gesperrt nach E37 | source_version und checked_at bereits vorhanden; Rohdaten fehlen hier, aber Snapshot.raw_payload existiert |
| game_playersourcerating.tw_reflexe | erweitert; game/models.py:3123 | E / Import: apply_package | ja: maßgeblicher Snapshot + unveränderte Attributnormalisierung → sync_current_source_ratings (geplant) | unberührt: gesperrt nach E37 | source_version und checked_at bereits vorhanden; Rohdaten fehlen hier, aber Snapshot.raw_payload existiert |
| game_playersourcerating.tw_fangsicherheit | erweitert; game/models.py:3127 | E / Import: apply_package | ja: maßgeblicher Snapshot + unveränderte Attributnormalisierung → sync_current_source_ratings (geplant) | unberührt: gesperrt nach E37 | source_version und checked_at bereits vorhanden; Rohdaten fehlen hier, aber Snapshot.raw_payload existiert |
| game_playersourcerating.tw_eins_gegen_eins | erweitert; game/models.py:3131 | E / Import: apply_package | ja: maßgeblicher Snapshot + unveränderte Attributnormalisierung → sync_current_source_ratings (geplant) | unberührt: gesperrt nach E37 | source_version und checked_at bereits vorhanden; Rohdaten fehlen hier, aber Snapshot.raw_payload existiert |
| game_playersourcerating.tw_stellungsspiel | erweitert; game/models.py:3136 | E / Import: apply_package | ja: maßgeblicher Snapshot + unveränderte Attributnormalisierung → sync_current_source_ratings (geplant) | unberührt: gesperrt nach E37 | source_version und checked_at bereits vorhanden; Rohdaten fehlen hier, aber Snapshot.raw_payload existiert |
| game_playersourcerating.tw_passen | erweitert; game/models.py:3140 | E / Import: apply_package | ja: maßgeblicher Snapshot + unveränderte Attributnormalisierung → sync_current_source_ratings (geplant) | unberührt: gesperrt nach E37 | source_version und checked_at bereits vorhanden; Rohdaten fehlen hier, aber Snapshot.raw_payload existiert |
| game_playersourcerating.source_url | erweitert; game/models.py:3145 | E / Import: apply_package | ja: maßgeblicher Snapshot + unveränderte Attributnormalisierung → sync_current_source_ratings (geplant) | unberührt: gesperrt nach E37 | source_version und checked_at bereits vorhanden; Rohdaten fehlen hier, aber Snapshot.raw_payload existiert |
| game_playersourcerating.source_version | erweitert; game/models.py:3146 | E / Import: apply_package | ja: maßgeblicher Snapshot + unveränderte Attributnormalisierung → sync_current_source_ratings (geplant) | unberührt: gesperrt nach E37 | source_version und checked_at bereits vorhanden; Rohdaten fehlen hier, aber Snapshot.raw_payload existiert |
| game_playersourcerating.checked_at | erweitert; game/models.py:3150 | E / Import: apply_package | ja: maßgeblicher Snapshot + unveränderte Attributnormalisierung → sync_current_source_ratings (geplant) | unberührt: gesperrt nach E37 | source_version und checked_at bereits vorhanden; Rohdaten fehlen hier, aber Snapshot.raw_payload existiert |
| game_playersourcerating.notes | erweitert; game/models.py:3154 | E / Import: apply_package | ja: maßgeblicher Snapshot + unveränderte Attributnormalisierung → sync_current_source_ratings (geplant) | unberührt: gesperrt nach E37 | source_version und checked_at bereits vorhanden; Rohdaten fehlen hier, aber Snapshot.raw_payload existiert |
| game_playersourcerating.created_at | erweitert; game/models.py:3156 | E / Import: apply_package | nein | unberührt: gesperrt nach E37 | source_version und checked_at bereits vorhanden; Rohdaten fehlen hier, aber Snapshot.raw_payload existiert |
| game_playersourcerating.updated_at | erweitert; game/models.py:3157 | E / Import: apply_package | nein | unberührt: gesperrt nach E37 | source_version und checked_at bereits vorhanden; Rohdaten fehlen hier, aber Snapshot.raw_payload existiert |

### Marktwertpunkt

| Tabelle und Spalte | Zustand / Codebeleg | Schicht / Schreiber | Spiegel: Quelle → Funktion | Upload nach Ligastart | Präzisierung |
|---|---|---|---|---|---|
| game_playermarketvaluesnapshot.player_id | vorhanden; game/models.py:3338 | R / Import nur real; Spiel nur sim | nein | unberührt: gesperrt nach E37 | volle Historie; Save ohne Player.market_value-/Gehaltsupdate und ohne Prune |
| game_playermarketvaluesnapshot.source_id | vorhanden; game/models.py:3343 | R / Import nur real; Spiel nur sim | nein | unberührt: gesperrt nach E37 | volle Historie; Save ohne Player.market_value-/Gehaltsupdate und ohne Prune |
| game_playermarketvaluesnapshot.recorded_at | vorhanden; game/models.py:3348 | R / Import nur real; Spiel nur sim | nein | unberührt: gesperrt nach E37 | volle Historie; Save ohne Player.market_value-/Gehaltsupdate und ohne Prune |
| game_playermarketvaluesnapshot.value_eur | vorhanden; game/models.py:3349 | R / Import nur real; Spiel nur sim | nein | unberührt: gesperrt nach E37 | volle Historie; Save ohne Player.market_value-/Gehaltsupdate und ohne Prune |
| game_playermarketvaluesnapshot.profile_url | vorhanden; game/models.py:3350 | R / Import nur real; Spiel nur sim | nein | unberührt: gesperrt nach E37 | volle Historie; Save ohne Player.market_value-/Gehaltsupdate und ohne Prune |
| game_playermarketvaluesnapshot.source_version | vorhanden; game/models.py:3351 | R / Import nur real; Spiel nur sim | nein | unberührt: gesperrt nach E37 | volle Historie; Save ohne Player.market_value-/Gehaltsupdate und ohne Prune |
| game_playermarketvaluesnapshot.update_current | repariert; game/models.py:3352 | R / Import nur real; Spiel nur sim | nein | unberührt: gesperrt nach E37 | volle Historie; Save ohne Player.market_value-/Gehaltsupdate und ohne Prune |
| game_playermarketvaluesnapshot.raw_payload | vorhanden; game/models.py:3356 | R / Import nur real; Spiel nur sim | nein | unberührt: gesperrt nach E37 | volle Historie; Save ohne Player.market_value-/Gehaltsupdate und ohne Prune |
| game_playermarketvaluesnapshot.notes | vorhanden; game/models.py:3357 | R / Import nur real; Spiel nur sim | nein | unberührt: gesperrt nach E37 | volle Historie; Save ohne Player.market_value-/Gehaltsupdate und ohne Prune |
| game_playermarketvaluesnapshot.created_at | vorhanden; game/models.py:3358 | R / Import nur real; Spiel nur sim | nein | unberührt: gesperrt nach E37 | volle Historie; Save ohne Player.market_value-/Gehaltsupdate und ohne Prune |
| game_playermarketvaluesnapshot.origin | neu; im Modellbestand nicht vorhanden | R / Import nur real; Spiel nur sim | nein | unberührt: gesperrt nach E37 | real / sim zwingend je Zeile |
| game_playermarketvaluesnapshot.club_id | neu; im Modellbestand nicht vorhanden | R / Import nur real; Spiel nur sim | nein | unberührt: gesperrt nach E37 | NULL-Club ohne TM-ID bleibt Name; kein Namensabgleich |
| game_playermarketvaluesnapshot.club_tm_id | neu; im Modellbestand nicht vorhanden | R / Import nur real; Spiel nur sim | nein | unberührt: gesperrt nach E37 | NULL-Club ohne TM-ID bleibt Name; kein Namensabgleich |
| game_playermarketvaluesnapshot.club_original_name | neu; im Modellbestand nicht vorhanden | R / Import nur real; Spiel nur sim | nein | unberührt: gesperrt nach E37 | NULL-Club ohne TM-ID bleibt Name; kein Namensabgleich |
| game_playermarketvaluesnapshot.is_start_value | neu; im Modellbestand nicht vorhanden | R / Import nur real; Spiel nur sim | nein | unberührt: gesperrt nach E37 | N10: 50.000-Spielstartwert ist sim, nicht erfundener TM-Realwert |
| game_playermarketvaluesnapshot.package_id | neu; im Modellbestand nicht vorhanden | R / Import nur real; Spiel nur sim | nein | unberührt: gesperrt nach E37 | NULL-Club ohne TM-ID bleibt Name; kein Namensabgleich |
| game_playermarketvaluesnapshot.source_row_key | neu; im Modellbestand nicht vorhanden | R / Import nur real; Spiel nur sim | ja: normalisierter Faktenschlüssel → make_fact_key (geplant) | unberührt: gesperrt nach E37 | Idempotenz ohne Namensabgleich mit anderen Entitäten; origin Bestandteil |

### Transfer

| Tabelle und Spalte | Zustand / Codebeleg | Schicht / Schreiber | Spiegel: Quelle → Funktion | Upload nach Ligastart | Präzisierung |
|---|---|---|---|---|---|
| game_playertransferhistory.player_id | vorhanden; game/models.py:3483 | R / Import nur real; Spiel nur sim | nein | unberührt: gesperrt nach E37 | — |
| game_playertransferhistory.transfer_date | vorhanden; game/models.py:3488 | R / Import nur real; Spiel nur sim | nein | unberührt: gesperrt nach E37 | — |
| game_playertransferhistory.season | vorhanden; game/models.py:3489 | R / Import nur real; Spiel nur sim | nein | unberührt: gesperrt nach E37 | — |
| game_playertransferhistory.from_club_id | vorhanden; game/models.py:3490 | R / Import nur real; Spiel nur sim | nein | unberührt: gesperrt nach E37 | — |
| game_playertransferhistory.to_club_id | vorhanden; game/models.py:3497 | R / Import nur real; Spiel nur sim | nein | unberührt: gesperrt nach E37 | — |
| game_playertransferhistory.fee_eur | vorhanden; game/models.py:3504 | R / Import nur real; Spiel nur sim | nein | unberührt: gesperrt nach E37 | bereits nullable, unbekannt bleibt NULL |
| game_playertransferhistory.notes | vorhanden; game/models.py:3510 | R / Import nur real; Spiel nur sim | nein | unberührt: gesperrt nach E37 | — |
| game_playertransferhistory.created_at | vorhanden; game/models.py:3511 | R / Import nur real; Spiel nur sim | nein | unberührt: gesperrt nach E37 | — |
| game_playertransferhistory.origin | neu; im Modellbestand nicht vorhanden | R / Import nur real; Spiel nur sim | nein | unberührt: gesperrt nach E37 | eigene Sim-Transfers bleiben unangetastet; Namen ohne TM-ID nur Text |
| game_playertransferhistory.is_loan | neu; im Modellbestand nicht vorhanden | R / Import nur real; Spiel nur sim | nein | unberührt: gesperrt nach E37 | eigene Sim-Transfers bleiben unangetastet; Namen ohne TM-ID nur Text |
| game_playertransferhistory.from_tm_id | neu; im Modellbestand nicht vorhanden | R / Import nur real; Spiel nur sim | nein | unberührt: gesperrt nach E37 | eigene Sim-Transfers bleiben unangetastet; Namen ohne TM-ID nur Text |
| game_playertransferhistory.to_tm_id | neu; im Modellbestand nicht vorhanden | R / Import nur real; Spiel nur sim | nein | unberührt: gesperrt nach E37 | eigene Sim-Transfers bleiben unangetastet; Namen ohne TM-ID nur Text |
| game_playertransferhistory.from_original_name | neu; im Modellbestand nicht vorhanden | R / Import nur real; Spiel nur sim | nein | unberührt: gesperrt nach E37 | eigene Sim-Transfers bleiben unangetastet; Namen ohne TM-ID nur Text |
| game_playertransferhistory.to_original_name | neu; im Modellbestand nicht vorhanden | R / Import nur real; Spiel nur sim | nein | unberührt: gesperrt nach E37 | eigene Sim-Transfers bleiben unangetastet; Namen ohne TM-ID nur Text |
| game_playertransferhistory.fee_text | neu; im Modellbestand nicht vorhanden | R / Import nur real; Spiel nur sim | nein | unberührt: gesperrt nach E37 | eigene Sim-Transfers bleiben unangetastet; Namen ohne TM-ID nur Text |
| game_playertransferhistory.package_id | neu; im Modellbestand nicht vorhanden | R / Import nur real; Spiel nur sim | nein | unberührt: gesperrt nach E37 | eigene Sim-Transfers bleiben unangetastet; Namen ohne TM-ID nur Text |
| game_playertransferhistory.source_row_key | neu; im Modellbestand nicht vorhanden | R / Import nur real; Spiel nur sim | ja: normalisierter Faktenschlüssel → make_fact_key (geplant) | unberührt: gesperrt nach E37 | Idempotenz ohne Namensabgleich mit anderen Entitäten; origin Bestandteil |

### Rekord

| Tabelle und Spalte | Zustand / Codebeleg | Schicht / Schreiber | Spiegel: Quelle → Funktion | Upload nach Ligastart | Präzisierung |
|---|---|---|---|---|---|
| game_clubrecord.club_id | vorhanden; game/models.py:6034 | R / Import nur real; Spiel nur sim | nein | überschreiben: nur real, SIM unberührt | — |
| game_clubrecord.record_key | vorhanden; game/models.py:6039 | R / Import nur real; Spiel nur sim | nein | überschreiben: nur real, SIM unberührt | — |
| game_clubrecord.custom_label | vorhanden; game/models.py:6040 | R / Import nur real; Spiel nur sim | nein | überschreiben: nur real, SIM unberührt | — |
| game_clubrecord.source | vorhanden; game/models.py:6045 | R / Import nur real; Spiel nur sim | nein | überschreiben: nur real, SIM unberührt | real→SEED / sim→SIM; Herkunft besteht bereits |
| game_clubrecord.value_numeric | erweitert; game/models.py:6046 | R / Import nur real; Spiel nur sim | nein | überschreiben: nur real, SIM unberührt | nullable für nicht_belegt; kein 0 erfinden |
| game_clubrecord.value_display | vorhanden; game/models.py:6047 | R / Import nur real; Spiel nur sim | ja: Halter-/Wertbelege → refresh_record_display (geplant) | überschreiben: nur real, SIM unberührt | — |
| game_clubrecord.holder_name | vorhanden; game/models.py:6048 | R / Import nur real; Spiel nur sim | ja: Halter-/Wertbelege → refresh_record_display (geplant) | überschreiben: nur real, SIM unberührt | — |
| game_clubrecord.holder_player_id | vorhanden; game/models.py:6049 | R / Import nur real; Spiel nur sim | nein | überschreiben: nur real, SIM unberührt | — |
| game_clubrecord.holder_coach_id | erweitert; game/models.py:6056 | R / Import nur real; Spiel nur sim | nein | überschreiben: nur real, SIM unberührt | bestehender FK wird allgemeiner Person-FK (Legacyname bleibt); Person.kind steuert Bild/Anzeige |
| game_clubrecord.holder_manager_id | vorhanden; game/models.py:6063 | R / Import nur real; Spiel nur sim | nein | überschreiben: nur real, SIM unberührt | — |
| game_clubrecord.opponent_name | vorhanden; game/models.py:6070 | R / Import nur real; Spiel nur sim | nein | überschreiben: nur real, SIM unberührt | — |
| game_clubrecord.opponent_club_id | vorhanden; game/models.py:6071 | R / Import nur real; Spiel nur sim | nein | überschreiben: nur real, SIM unberührt | — |
| game_clubrecord.context_line | vorhanden; game/models.py:6078 | R / Import nur real; Spiel nur sim | nein | überschreiben: nur real, SIM unberührt | — |
| game_clubrecord.record_date | vorhanden; game/models.py:6079 | R / Import nur real; Spiel nur sim | nein | überschreiben: nur real, SIM unberührt | — |
| game_clubrecord.period_from | vorhanden; game/models.py:6080 | R / Import nur real; Spiel nur sim | nein | überschreiben: nur real, SIM unberührt | — |
| game_clubrecord.period_to | vorhanden; game/models.py:6081 | R / Import nur real; Spiel nur sim | nein | überschreiben: nur real, SIM unberührt | — |
| game_clubrecord.season | vorhanden; game/models.py:6082 | R / Import nur real; Spiel nur sim | nein | überschreiben: nur real, SIM unberührt | — |
| game_clubrecord.competition | vorhanden; game/models.py:6083 | R / Import nur real; Spiel nur sim | nein | überschreiben: nur real, SIM unberührt | — |
| game_clubrecord.source_note | vorhanden; game/models.py:6084 | R / Import nur real; Spiel nur sim | nein | überschreiben: nur real, SIM unberührt | — |
| game_clubrecord.linked_match_id | vorhanden; game/models.py:6085 | R / Import nur real; Spiel nur sim | nein | überschreiben: nur real, SIM unberührt | — |
| game_clubrecord.is_anonymized | vorhanden; game/models.py:6092 | R / Import nur real; Spiel nur sim | nein | überschreiben: nur real, SIM unberührt | — |
| game_clubrecord.updated_at | vorhanden; game/models.py:6093 | R / Import nur real; Spiel nur sim | nein | überschreiben: nur real, SIM unberührt | — |
| game_clubrecord.basis | neu; im Modellbestand nicht vorhanden | R / Import nur real; Spiel nur sim | nein | überschreiben: nur real, SIM unberührt | Suchnachweis/Quellen strukturiert; neue Schlüssel müssen zusätzlich Registry/Seiten tolerieren |
| game_clubrecord.evidence_status | neu; im Modellbestand nicht vorhanden | R / Import nur real; Spiel nur sim | nein | überschreiben: nur real, SIM unberührt | Suchnachweis/Quellen strukturiert; neue Schlüssel müssen zusätzlich Registry/Seiten tolerieren |
| game_clubrecord.opponent_tm_id | neu; im Modellbestand nicht vorhanden | R / Import nur real; Spiel nur sim | nein | überschreiben: nur real, SIM unberührt | Suchnachweis/Quellen strukturiert; neue Schlüssel müssen zusätzlich Registry/Seiten tolerieren |
| game_clubrecord.evidence | neu; im Modellbestand nicht vorhanden | R / Import nur real; Spiel nur sim | nein | überschreiben: nur real, SIM unberührt | Suchnachweis/Quellen strukturiert; neue Schlüssel müssen zusätzlich Registry/Seiten tolerieren |
| game_clubrecord.searched | neu; im Modellbestand nicht vorhanden | R / Import nur real; Spiel nur sim | nein | überschreiben: nur real, SIM unberührt | Suchnachweis/Quellen strukturiert; neue Schlüssel müssen zusätzlich Registry/Seiten tolerieren |
| game_clubrecord.package_id | neu; im Modellbestand nicht vorhanden | R / Import nur real; Spiel nur sim | nein | überschreiben: nur real, SIM unberührt | Suchnachweis/Quellen strukturiert; neue Schlüssel müssen zusätzlich Registry/Seiten tolerieren |

### Titel-Eintrag

| Tabelle und Spalte | Zustand / Codebeleg | Schicht / Schreiber | Spiegel: Quelle → Funktion | Upload nach Ligastart | Präzisierung |
|---|---|---|---|---|---|
| game_clubtrophyentry.club_id | neu; im Modellbestand nicht vorhanden | R / Import nur real; Spiel nur sim | nein | überschreiben: nur real bis Titelschnitt | neue Tabelle nur weil echte Einzeltitel fehlen; kein League-Seed aus Wettbewerbsnamen |
| game_clubtrophyentry.competition_name | neu; im Modellbestand nicht vorhanden | R / Import nur real; Spiel nur sim | nein | überschreiben: nur real bis Titelschnitt | neue Tabelle nur weil echte Einzeltitel fehlen; kein League-Seed aus Wettbewerbsnamen |
| game_clubtrophyentry.competition_fm_id | neu; im Modellbestand nicht vorhanden | R / Import nur real; Spiel nur sim | nein | überschreiben: nur real bis Titelschnitt | neue Tabelle nur weil echte Einzeltitel fehlen; kein League-Seed aus Wettbewerbsnamen |
| game_clubtrophyentry.season | neu; im Modellbestand nicht vorhanden | R / Import nur real; Spiel nur sim | nein | überschreiben: nur real bis Titelschnitt | neue Tabelle nur weil echte Einzeltitel fehlen; kein League-Seed aus Wettbewerbsnamen |
| game_clubtrophyentry.category | neu; im Modellbestand nicht vorhanden | R / Import nur real; Spiel nur sim | nein | überschreiben: nur real bis Titelschnitt | neue Tabelle nur weil echte Einzeltitel fehlen; kein League-Seed aus Wettbewerbsnamen |
| game_clubtrophyentry.origin | neu; im Modellbestand nicht vorhanden | R / Import nur real; Spiel nur sim | nein | überschreiben: nur real bis Titelschnitt | neue Tabelle nur weil echte Einzeltitel fehlen; kein League-Seed aus Wettbewerbsnamen |
| game_clubtrophyentry.source_url | neu; im Modellbestand nicht vorhanden | R / Import nur real; Spiel nur sim | nein | überschreiben: nur real bis Titelschnitt | neue Tabelle nur weil echte Einzeltitel fehlen; kein League-Seed aus Wettbewerbsnamen |
| game_clubtrophyentry.package_id | neu; im Modellbestand nicht vorhanden | R / Import nur real; Spiel nur sim | nein | überschreiben: nur real bis Titelschnitt | neue Tabelle nur weil echte Einzeltitel fehlen; kein League-Seed aus Wettbewerbsnamen |
| game_clubtrophyentry.source_row_key | neu; im Modellbestand nicht vorhanden | R / Import nur real; Spiel nur sim | ja: normalisierter Faktenschlüssel → make_fact_key (geplant) | überschreiben: nur real bis Titelschnitt | Idempotenz ohne Namensabgleich mit anderen Entitäten; origin Bestandteil |

### Titelzählung

| Tabelle und Spalte | Zustand / Codebeleg | Schicht / Schreiber | Spiegel: Quelle → Funktion | Upload nach Ligastart | Präzisierung |
|---|---|---|---|---|---|
| game_clubtrophy.club_id | repariert; game/models.py:1119 | R / Import nur real; Spiel nur sim | ja: ClubTrophyEntry → rebuild_trophy_projection (geplant) | überschreiben: nur real bis Titelschnitt | bestehendes Aggregat nur Lesespiegel, keine zweite Titelfaktenpflege |
| game_clubtrophy.competition_name | repariert; game/models.py:1124 | R / Import nur real; Spiel nur sim | ja: ClubTrophyEntry → rebuild_trophy_projection (geplant) | überschreiben: nur real bis Titelschnitt | bestehendes Aggregat nur Lesespiegel, keine zweite Titelfaktenpflege |
| game_clubtrophy.count | repariert; game/models.py:1125 | R / Import nur real; Spiel nur sim | ja: ClubTrophyEntry → rebuild_trophy_projection (geplant) | überschreiben: nur real bis Titelschnitt | bestehendes Aggregat nur Lesespiegel, keine zweite Titelfaktenpflege |
| game_clubtrophy.trophy_asset_id | repariert; game/models.py:1126 | R / Import nur real; Spiel nur sim | ja: ClubTrophyEntry → rebuild_trophy_projection (geplant) | überschreiben: nur real bis Titelschnitt | bestehendes Aggregat nur Lesespiegel, keine zweite Titelfaktenpflege |
| game_clubtrophy.sort_order | repariert; game/models.py:1127 | R / Import nur real; Spiel nur sim | ja: ClubTrophyEntry → rebuild_trophy_projection (geplant) | überschreiben: nur real bis Titelschnitt | bestehendes Aggregat nur Lesespiegel, keine zweite Titelfaktenpflege |
| game_clubtrophy.origin | neu; im Modellbestand nicht vorhanden | R / Import nur real; Spiel nur sim | ja: ClubTrophyEntry → rebuild_trophy_projection (geplant) | überschreiben: nur real bis Titelschnitt | auch Aggregat hat Herkunft je Zeile; Darstellung gruppiert real+sim, keine doppelten Pokalkacheln |
| game_clubtrophy.category | neu; im Modellbestand nicht vorhanden | R / Import nur real; Spiel nur sim | ja: ClubTrophyEntry → rebuild_trophy_projection (geplant) | überschreiben: nur real bis Titelschnitt | auch Aggregat hat Herkunft je Zeile; Darstellung gruppiert real+sim, keine doppelten Pokalkacheln |
| game_clubtrophy.competition_fm_id | neu; im Modellbestand nicht vorhanden | R / Import nur real; Spiel nur sim | ja: ClubTrophyEntry → rebuild_trophy_projection (geplant) | überschreiben: nur real bis Titelschnitt | auch Aggregat hat Herkunft je Zeile; Darstellung gruppiert real+sim, keine doppelten Pokalkacheln |

### Paketprotokoll

| Tabelle und Spalte | Zustand / Codebeleg | Schicht / Schreiber | Spiegel: Quelle → Funktion | Upload nach Ligastart | Präzisierung |
|---|---|---|---|---|---|
| game_sourceimportrun.source | erweitert; game/models.py:3763 | E / Import: apply_package | nein | überschreiben: neuer unveränderlicher Paketlauf | bestehender Importlauf wird erweitert; keine neue Pakettabelle |
| game_sourceimportrun.version | vorhanden; game/models.py:3768 | E / Import: apply_package | nein | überschreiben: neuer unveränderlicher Paketlauf | bestehender Importlauf wird erweitert; keine neue Pakettabelle |
| game_sourceimportrun.file_name | vorhanden; game/models.py:3773 | E / Import: apply_package | nein | überschreiben: neuer unveränderlicher Paketlauf | bestehender Importlauf wird erweitert; keine neue Pakettabelle |
| game_sourceimportrun.imported_at | vorhanden; game/models.py:3774 | E / Import: apply_package | nein | überschreiben: neuer unveränderlicher Paketlauf | bestehender Importlauf wird erweitert; keine neue Pakettabelle |
| game_sourceimportrun.dry_run | vorhanden; game/models.py:3775 | E / Import: apply_package | nein | überschreiben: neuer unveränderlicher Paketlauf | bestehender Importlauf wird erweitert; keine neue Pakettabelle |
| game_sourceimportrun.created_by_id | vorhanden; game/models.py:3776 | E / Import: apply_package | nein | überschreiben: neuer unveränderlicher Paketlauf | bestehender Importlauf wird erweitert; keine neue Pakettabelle |
| game_sourceimportrun.total_rows | vorhanden; game/models.py:3783 | E / Import: apply_package | nein | überschreiben: neuer unveränderlicher Paketlauf | bestehender Importlauf wird erweitert; keine neue Pakettabelle |
| game_sourceimportrun.count_new | vorhanden; game/models.py:3784 | E / Import: apply_package | nein | überschreiben: neuer unveränderlicher Paketlauf | bestehender Importlauf wird erweitert; keine neue Pakettabelle |
| game_sourceimportrun.count_updated | vorhanden; game/models.py:3785 | E / Import: apply_package | nein | überschreiben: neuer unveränderlicher Paketlauf | bestehender Importlauf wird erweitert; keine neue Pakettabelle |
| game_sourceimportrun.count_unchanged | vorhanden; game/models.py:3786 | E / Import: apply_package | nein | überschreiben: neuer unveränderlicher Paketlauf | bestehender Importlauf wird erweitert; keine neue Pakettabelle |
| game_sourceimportrun.count_unmatched | vorhanden; game/models.py:3787 | E / Import: apply_package | nein | überschreiben: neuer unveränderlicher Paketlauf | bestehender Importlauf wird erweitert; keine neue Pakettabelle |
| game_sourceimportrun.count_error | vorhanden; game/models.py:3788 | E / Import: apply_package | nein | überschreiben: neuer unveränderlicher Paketlauf | bestehender Importlauf wird erweitert; keine neue Pakettabelle |
| game_sourceimportrun.unmatched | vorhanden; game/models.py:3789 | E / Import: apply_package | nein | überschreiben: neuer unveränderlicher Paketlauf | bestehender Importlauf wird erweitert; keine neue Pakettabelle |
| game_sourceimportrun.notes | vorhanden; game/models.py:3790 | E / Import: apply_package | nein | überschreiben: neuer unveränderlicher Paketlauf | bestehender Importlauf wird erweitert; keine neue Pakettabelle |
| game_sourceimportrun.format | neu; im Modellbestand nicht vorhanden | E / Import: apply_package | nein | überschreiben: neuer unveränderlicher Paketlauf | Paketmetadaten/Audit; Archiv ist kein zweiter aktiver Feldspeicher |
| game_sourceimportrun.format_version | neu; im Modellbestand nicht vorhanden | E / Import: apply_package | nein | überschreiben: neuer unveränderlicher Paketlauf | Paketmetadaten/Audit; Archiv ist kein zweiter aktiver Feldspeicher |
| game_sourceimportrun.package_type | neu; im Modellbestand nicht vorhanden | E / Import: apply_package | nein | überschreiben: neuer unveränderlicher Paketlauf | Paketmetadaten/Audit; Archiv ist kein zweiter aktiver Feldspeicher |
| game_sourceimportrun.data_sha256 | neu; im Modellbestand nicht vorhanden | E / Import: apply_package | nein | überschreiben: neuer unveränderlicher Paketlauf | Paketmetadaten/Audit; Archiv ist kein zweiter aktiver Feldspeicher |
| game_sourceimportrun.collected_at | neu; im Modellbestand nicht vorhanden | E / Import: apply_package | nein | überschreiben: neuer unveränderlicher Paketlauf | Paketmetadaten/Audit; Archiv ist kein zweiter aktiver Feldspeicher |
| game_sourceimportrun.titles_through_season | neu; im Modellbestand nicht vorhanden | E / Import: apply_package | nein | überschreiben: neuer unveränderlicher Paketlauf | Paketmetadaten/Audit; Archiv ist kein zweiter aktiver Feldspeicher |
| game_sourceimportrun.source_versions | neu; im Modellbestand nicht vorhanden | E / Import: apply_package | nein | überschreiben: neuer unveränderlicher Paketlauf | Paketmetadaten/Audit; Archiv ist kein zweiter aktiver Feldspeicher |
| game_sourceimportrun.position_window | neu; im Modellbestand nicht vorhanden | E / Import: apply_package | nein | überschreiben: neuer unveränderlicher Paketlauf | Paketmetadaten/Audit; Archiv ist kein zweiter aktiver Feldspeicher |
| game_sourceimportrun.manifest | neu; im Modellbestand nicht vorhanden | E / Import: apply_package | nein | überschreiben: neuer unveränderlicher Paketlauf | Paketmetadaten/Audit; Archiv ist kein zweiter aktiver Feldspeicher |
| game_sourceimportrun.package_data | neu; im Modellbestand nicht vorhanden | E / Import: apply_package | nein | überschreiben: neuer unveränderlicher Paketlauf | Paketmetadaten/Audit; Archiv ist kein zweiter aktiver Feldspeicher |
| game_sourceimportrun.club_id | neu; im Modellbestand nicht vorhanden | E / Import: apply_package | nein | überschreiben: neuer unveränderlicher Paketlauf | Paketmetadaten/Audit; Archiv ist kein zweiter aktiver Feldspeicher |
| game_sourceimportrun.target_league_id | neu; im Modellbestand nicht vorhanden | E / Import: apply_package | nein | überschreiben: neuer unveränderlicher Paketlauf | Paketmetadaten/Audit; Archiv ist kein zweiter aktiver Feldspeicher |
| game_sourceimportrun.status | neu; im Modellbestand nicht vorhanden | E / Import: apply_package | nein | überschreiben: neuer unveränderlicher Paketlauf | Paketmetadaten/Audit; Archiv ist kein zweiter aktiver Feldspeicher |
| game_sourceimportrun.applied_at | neu; im Modellbestand nicht vorhanden | E / Import: apply_package | nein | überschreiben: neuer unveränderlicher Paketlauf | Paketmetadaten/Audit; Archiv ist kein zweiter aktiver Feldspeicher |

### Arbeitsliste

| Tabelle und Spalte | Zustand / Codebeleg | Schicht / Schreiber | Spiegel: Quelle → Funktion | Upload nach Ligastart | Präzisierung |
|---|---|---|---|---|---|
| game_importissue.package_id | neu; im Modellbestand nicht vorhanden | E / Import: apply_package | nein | überschreiben: neue Meldung; keine erledigte Meldung zurücksetzen | neue Tabelle für vereins-/stadion-/personenweite Lücken, bestehende PlayerImportCandidate nur spielerbezogen |
| game_importissue.entity | neu; im Modellbestand nicht vorhanden | E / Import: apply_package | nein | überschreiben: neue Meldung; keine erledigte Meldung zurücksetzen | neue Tabelle für vereins-/stadion-/personenweite Lücken, bestehende PlayerImportCandidate nur spielerbezogen |
| game_importissue.entity_ref | neu; im Modellbestand nicht vorhanden | E / Import: apply_package | nein | überschreiben: neue Meldung; keine erledigte Meldung zurücksetzen | neue Tabelle für vereins-/stadion-/personenweite Lücken, bestehende PlayerImportCandidate nur spielerbezogen |
| game_importissue.field | neu; im Modellbestand nicht vorhanden | E / Import: apply_package | nein | überschreiben: neue Meldung; keine erledigte Meldung zurücksetzen | neue Tabelle für vereins-/stadion-/personenweite Lücken, bestehende PlayerImportCandidate nur spielerbezogen |
| game_importissue.severity | neu; im Modellbestand nicht vorhanden | E / Import: apply_package | nein | überschreiben: neue Meldung; keine erledigte Meldung zurücksetzen | neue Tabelle für vereins-/stadion-/personenweite Lücken, bestehende PlayerImportCandidate nur spielerbezogen |
| game_importissue.note | neu; im Modellbestand nicht vorhanden | E / Import: apply_package | nein | überschreiben: neue Meldung; keine erledigte Meldung zurücksetzen | neue Tabelle für vereins-/stadion-/personenweite Lücken, bestehende PlayerImportCandidate nur spielerbezogen |
| game_importissue.external_reference | neu; im Modellbestand nicht vorhanden | E / Import: apply_package | nein | überschreiben: neue Meldung; keine erledigte Meldung zurücksetzen | neue Tabelle für vereins-/stadion-/personenweite Lücken, bestehende PlayerImportCandidate nur spielerbezogen |
| game_importissue.proposed_tm_id | neu; im Modellbestand nicht vorhanden | E / Import: apply_package | nein | überschreiben: neue Meldung; keine erledigte Meldung zurücksetzen | neue Tabelle für vereins-/stadion-/personenweite Lücken, bestehende PlayerImportCandidate nur spielerbezogen |
| game_importissue.resolved_at | neu; im Modellbestand nicht vorhanden | S / Spiel | nein | unberührt: gesperrt nach E37 | Creator löst über zentralen Importweg; Upload überschreibt keine Erledigung |
| game_importissue.resolved_by_id | neu; im Modellbestand nicht vorhanden | S / Spiel | nein | unberührt: gesperrt nach E37 | Creator löst über zentralen Importweg; Upload überschreibt keine Erledigung |
| game_importissue.resolution_status | neu; im Modellbestand nicht vorhanden | S / Spiel | nein | unberührt: gesperrt nach E37 | Creator löst über zentralen Importweg; Upload überschreibt keine Erledigung |

### Bestehende Finanzen, Spiele, Saison und Sim-Vereinsstationen

Diese B6-Gruppen bleiben Spielstand, ohne neue Tabellen. Ligastart für die Uploadmaske kommt aus dem vorhandenen `GameSeasonState.is_started`, nicht aus erfundenen Paketfeldern. Die realen Stamm-/Leihdaten oben sind Echtwelt; die bestehenden und ergänzten Sim-Leihfelder werden nur initial daraus gesetzt und dürfen danach unabhängig laufen. Diese bewusste Trennung ist kein dauerhaft synchroner Spiegel.

| Tabelle und Spalte | Zustand / Codebeleg | Schicht / Schreiber | Spiegel: Quelle → Funktion | Upload nach Ligastart | Präzisierung |
|---|---|---|---|---|---|
| game_financetransaction.club_id | vorhanden; game/models.py:7010 | S / book() | nein | unberührt | bestehende Club-Beziehung |
| game_financetransaction.saison | vorhanden; game/models.py:7016 | S / book() | nein | unberührt | numerische Sim-Saison, kein TM-Saisonlabel |
| game_financetransaction.spieltag | vorhanden; game/models.py:7017 | S / book() | nein | unberührt | Spielbuchung |
| game_financetransaction.typ | vorhanden; game/models.py:7020 | S / book() | nein | unberührt | Buchungstyp |
| game_financetransaction.betrag | vorhanden; game/models.py:7023 | S / book() | nein | unberührt | keine Importbuchung |
| game_financetransaction.referenz_typ | vorhanden; game/models.py:7029 | S / book() | nein | unberührt | bestehender Buchungsvertrag |
| game_financetransaction.referenz_id | vorhanden; game/models.py:7030 | S / book() | nein | unberührt | bestehender Buchungsvertrag |
| game_financetransaction.referenz_mw | vorhanden; game/models.py:7031 | S / book() | nein | unberührt | historischer Buchungsbeleg, nicht aktueller Marktwert |
| game_financetransaction.beschreibung | vorhanden; game/models.py:7040 | S / book() | nein | unberührt | Buchungsbeleg |
| game_financetransaction.datum | vorhanden; game/models.py:7043 | S / book() | nein | unberührt | Buchungsdatum |
| game_financetransaction.created_at | vorhanden; game/models.py:7044 | S / book() | nein | unberührt | technische Zeit |
| game_gameseasonstate.current_season | vorhanden; game/models.py:4948 | S / Saisonsteuerung | nein | unberührt | bestehender globaler Status |
| game_gameseasonstate.is_started | vorhanden; game/models.py:4952 | S / Saisonsteuerung | nein | unberührt | verbindlicher Startzustand für Uploadmaske |
| game_gameseasonstate.started_at | vorhanden; game/models.py:4956 | S / Saisonsteuerung | nein | unberührt | Startzeit |
| game_gameseasonstate.transfer_window_open | vorhanden; game/models.py:4957 | S / Saisonsteuerung | nein | unberührt | Transferfenster |
| game_gameseasonstate.transfer_window_id | vorhanden; game/models.py:4963 | S / Saisonsteuerung | nein | unberührt | Fensterkennung, keine Fremd-ID |
| game_gameseasonstate.updated_at | vorhanden; game/models.py:4971 | S / Saisonsteuerung | nein | unberührt | technische Zeit |
| game_leagueseasonstate.league_id | vorhanden; game/models.py:5072 | S / season_service | nein | unberührt | bestehende Liga-Beziehung |
| game_leagueseasonstate.season | vorhanden; game/models.py:5078 | S / season_service | nein | unberührt | Sim-Saison |
| game_leagueseasonstate.current_matchday | vorhanden; game/models.py:5079 | S / season_service | nein | unberührt | Spieltagzustand |
| game_leagueseasonstate.is_simulated | vorhanden; game/models.py:5083 | S / season_service | nein | unberührt | bestehender Ablaufzustand |
| game_leagueseasonstate.champion_club_id | vorhanden; game/models.py:5088 | S / season_service | nein | unberührt | abgeschlossener Wettbewerb |
| game_leagueseasonstate.completed_at | vorhanden; game/models.py:5096 | S / season_service | nein | unberührt | Abschlusszeit |
| game_leagueseasonstate.updated_at | vorhanden; game/models.py:5101 | S / season_service | nein | unberührt | technische Zeit |
| game_simulatedmatch.home_club_id | vorhanden; game/models.py:5630 | S / Simulation | nein | unberührt | bestehende Club-Beziehung |
| game_simulatedmatch.away_club_id | vorhanden; game/models.py:5635 | S / Simulation | nein | unberührt | bestehende Club-Beziehung |
| game_simulatedmatch.home_goals | vorhanden; game/models.py:5640 | S / Simulation | nein | unberührt | Spielergebnis |
| game_simulatedmatch.away_goals | vorhanden; game/models.py:5641 | S / Simulation | nein | unberührt | Spielergebnis |
| game_simulatedmatch.report_data | vorhanden; game/models.py:5642 | S / Simulation | nein | unberührt | Sim-Bericht, kein Import-Rohpayload |
| game_simulatedmatch.story_round_id | vorhanden; game/models.py:5646 | S / Simulation | nein | unberührt | bestehender Story-Vertrag |
| game_simulatedmatch.story_source_key | vorhanden; game/models.py:5650 | S / Simulation | nein | unberührt | bestehender Story-Vertrag |
| game_simulatedmatch.story_tactic_snapshot | vorhanden; game/models.py:5651 | S / Simulation | nein | unberührt | Spielzeit-Taktik |
| game_simulatedmatch.match_type | vorhanden; game/models.py:5652 | S / Simulation | nein | unberührt | bestehender Wettbewerbspfad |
| game_simulatedmatch.simulated_at | vorhanden; game/models.py:5658 | S / Simulation | nein | unberührt | Sim-Zeit |
| game_simulatedmatch.season | vorhanden; game/models.py:5659 | S / Simulation | nein | unberührt | Sim-Saison |
| game_simulatedmatch.match_no | vorhanden; game/models.py:5666 | S / Simulation | nein | unberührt | Sim-Spielkennung |
| game_simulatedmatch.referee_id | vorhanden; game/models.py:5672 | S / Simulation | nein | unberührt | Schutzkatalog-FK, kein neuer Schiedsrichterimport |
| game_playerclubhistory.player_id | vorhanden; game/models.py:3530 | S / Transfer-/Karrieredienst | nein | unberührt | Import-Suppress verhindert neue Sim-Station |
| game_playerclubhistory.club_id | vorhanden; game/models.py:3535 | S / Transfer-/Karrieredienst | nein | unberührt | bestehende Club-Beziehung |
| game_playerclubhistory.season | vorhanden; game/models.py:3540 | S / Transfer-/Karrieredienst | nein | unberührt | Sim-Saison |
| game_playerclubhistory.created_at | vorhanden; game/models.py:3543 | S / Transfer-/Karrieredienst | nein | unberührt | technische Zeit |

### Jugend-Antrag: nur die ausdrücklich späteren B6-Felder

**Nicht Teil dieses Umbaus und nicht zur Umsetzung vorgeschlagen.** Die vorhandene `CommunitySubmission` ist eine Scouting-Einreichung, kein U21-Antrag; deshalb wird sie jetzt nicht umgedeutet. Folgende reservierten Zielnamen dienen nur der Vollständigkeit der B6-Feldliste, ohne heutige Modell- oder Migrationsentscheidung.

| Tabelle und Spalte (erst Jugendmodul) | Zustand | Schicht / Schreiber | Spiegel | Upload nach Ligastart | Präzisierung |
|---|---|---|---|---|---|
| game_playerapplication.manager_id | neu, erst später | S / Jugendmodul | nein | unberührt | Antragsteller; endgültiger Tabellenschnitt später |
| game_playerapplication.tm_url | neu, erst später | S / Jugendmodul | nein | unberührt | Antragseingabe, keine ID-Zuordnung durch Namen |
| game_playerapplication.status | neu, erst später | S / Jugendmodul | nein | unberührt | Prüfstand |
| game_playerapplication.rejection_reason | neu, erst später | S / Jugendmodul | nein | unberührt | Ablehnungsgrund |

## 5. Tabellen/Spalten, die entfallen bzw. auslaufen

**Jetzt wird nichts gelöscht.** Der neue Import benötigt keine Löschung einer bestehenden fachlichen Tabelle.

| Bestand | Geplante Ablösung | Zeitpunkt / Schutz |
|---|---|---|
| Club.is_import_placeholder | entfällt als operativer Zustand; N29 verbietet Verweis-Club | Spalte vorerst für Altcode erhalten; der neue Paketweg setzt sie nicht, keine zweite Wahrheit |
| Club.import_name_provisional | ID-/Arbeitslistenstatus | kein eigener vorläufiger Namenszustand mehr; alte Importleser vor physischem Entfernen anpassen |
| ClubPublicProfile.stadium_name | Stadium.name | unabhängige Pflege entfällt; bestehende Vereinsseite sofort auf Stadium umstellen; physische Doppelspalte erst nach Leserprüfung entfernen |
| ClubPublicProfile.stadium_capacity | Stadium.capacity_total | unabhängige Pflege entfällt; reale Summe nicht als aktuelle Sim-Kapazität anzeigen; physische Doppelspalte später |
| PlayerMarketValueSnapshot.update_current | expliziter Spiel-MW-Dienst | Save-Schreibwirkung mit Reparatur abschaffen, Boolspalte nach Leserabbau entfernen |
| PlayerSourceRatingSnapshot.update_current | zentraler PSR-Spiegeldienst | impliziten Save-Schreibweg abschaffen, Boolspalte nach Leserabbau entfernen |
| Platzhalter-Liga / Namens-DOB-Fallback / Age-Split | echte Zielliga, nur ID-Abgleich, squad_team | Verhalten entfällt, keine neue Ersatzliga und kein Names-Matching |
| ClubTrophy.count als manuelle Faktquelle | Einzeltitel-Projektion | Spalte bleibt als benannter Spiegel, wird NICHT gelöscht |
| HistoricCoach / PlayerClubHistory / vorhandene Quellprofile | Personen-Erweiterung / reine Sim-Historie / kanonische Quellenleser | Tabellen bleiben. Kein vorsorgliches Löschen, keine Historie aus Echtweltimport |

„Später“ ist der durch N27 ausdrücklich erlaubte modulweise Abbau redundanter Spalten, kein vorgezogener Löschauftrag. Für Übergangs-Kompatibilität gelten dieselben Ja-Spiegelregeln; nachgezogenes Lesen ist keine neue Pilotseite.

## 6. Reparaturen an bestehenden Wegen und echten Seiten

- Player.save/_track_club_history in game/models.py:2590–2650 muss im zentralen Importweg den bereits vorhandenen Suppress-Vertrag benutzen; kein record_club_stint für Paketinitialisierung. Sim-Transferpfade behalten ihre Historie.
- Marktwert-Snapshot.save und prune_snapshot_history(limit=10) sind reale Codebefunde, keine Annahmen. Marktwert- UND Quellstandhistorie vollständig erhalten; stattdessen stabile Faktenschlüssel/Herkunft, keine Save-Nebeneffekte.
- game/club_import/matching.py hat einen Name+DOB-Fallback; für den neuen Paketweg unzulässig. T2 meldet Identitätskonflikte an die Arbeitsliste, ohne Namensvereinigung. N29: Historien-/Rekord-/Leihvereine bleiben TM-ID plus Originalname, KEINE Club-Zeile und keine NULL-/Platzhalterliga. T2 trägt passende FKs nach späterem Import per TM-ID nach.
- game/views.py:2822–2824 und bestehende Vereins-/Kader-Highlights ersetzen Altersfilter durch squad_team/Leihbeziehungen. U21-Eligibility bei Auswahl bleibt eine andere Regel; jüngere Profis bleiben first. Kein eigenständiger Kader-FK und keine U21-Aufstellfreigabe vor Jugendmodul.
- game/match_readiness.py und _build_team_dict in game/match_engine.py prüfen import_lock, aktive Kaderzugehörigkeit und echte berechenbare Pflichtwerte VOR den vorhandenen 50-/100-Fallbacks, auch Bank/Defaulttaktik/Matchday. Frische 0 darf nicht durch „or 100“ zu voller Frische werden. game/strength_service.py und game/strength_engine.py bleiben derselbe Berechnungspfad mit unveränderten Formeln; keine zweite Engine/Adapter-App.
- Bestehende game/club_profile.py-Leser für Stadium/ClubTrophy und die bestehenden Kader-/Spieler-/Ruhmeshallenseiten werden an die erweiterten Felder angepasst. Kein game/import_views.py, kein game/templates/game/import/, keine abweichende Pilot-UI. Nur Creator-Upload, Vorschau und Arbeitsliste sind später neue Seiten.
- Nachtrag nennt drei Dortmund-Stellen, tatsächlich stehen im aktuellen stadium_editor/views.py **sechs PK-3-Vorkommen**: drei Editor-Bedingungen (68/69/73), zwei Stadium-Lookups (195/211) und Live-Link args=[3] (219). Alle sechs müssen auf club.fm_inside_id=907 bzw. die so gefundene echte Club-PK umgestellt werden; nicht nur die zwei Datenbank-Lookups. Keine Geometrie-/Design-/Szenenänderung in dieser Arbeit.

## 7. Pilot und echte Migrationen: konkrete Zusammenführung

**Nur geplanter Ablauf nach Freigabe; jetzt nicht ausgeführt.** Pilot lädt die vollständige App game und die für bestehende Seiten nötigen Apps/Middleware. Derselbe game-Modellbestand und dieselbe echte neue Django-Migration laufen im Pilot und später live; kein eigener B6-Migrationssatz, keine fiktiven Migrationseinträge.

Die schon kopierten 21 Schutzdatentabellen sind kein vollständiger Auth-/Game-Migrationszustand. Deshalb nicht --fake-initial auf die gesamte Game-Initialmigration anwenden: zahlreiche andere Tabellen fehlen. Entscheidung zur Zusammenführung:

1. Innerhalb des eingeschränkten Pilot-Schemas die kopierten Tabellen samt zugehörigen Index-/Sequenznamen unter eindeutigem Sicherungspräfix isolieren. Bestehende Schutz-FKs bleiben zusammen; Inhalte/Fingerprints sichern. Kein public lesen/schreiben, keine neue Quellkopie, keine Schutzzeile verwerfen.
2. Standard-Django-Migrationen für Auth/ContentTypes/game und benötigte vorhandene Apps normal im Pilot ausführen, einschließlich alter Datenmigrationen und derselben neuen Umbau-Migration. Eigene leere Session-Infrastruktur bleibt erhalten. Hintergrundjobs/Zeitplaner aus, direkte Pilot-Rolle/Suchpfad/Uploads/Cookies unverändert isoliert.
3. Historisch geseedete Vereins-, Spieler-, Stadion-, Liga-, Wettbewerbs-, Karriere-, Spiel- und Sim-Zustände im Pilot kontrolliert bereinigen. Danach gesicherte Schutzdaten in die durch echte Migrationen erzeugten Tabellen zurückführen; ContentTypes/Permissions erneut nach natürlichen Schlüsseln, nicht IDs. Neue Modell-ContentTypes/Rechte aus echten Migrationen dürfen zusätzlich entstehen; alte Rechte nicht verwerfen. Pflicht-Nullbarkeit/FK-Bereinigung aus N19/N21 bleiben erhalten.
4. Vor Freigabe der Pilotseiten/BVB-Import: jede betroffene Spieltabelle mit **0 Zeilen** belegen, auch neue Einzeltitel; Schutzdaten-Fingerprints/zulässige Feldtransformationen, Profilstartwerte und Rechtezuordnung prüfen. Temporäre Sicherungen erst nach erfolgreicher Abnahme entfernen. Bei Fehler kein teilweise freigegebener Pilot; Sicherungen erhalten.

Diese Zielvorbereitung/Schutzdatenrückführung ist kein zweiter fachlicher Migrationsweg: Tabellen entstehen vollständig durch die echten Migrationen. Standard --fake der gesamten App und eigenhändiges Anlegen nur ausgewählter Game-Tabellen sind ausgeschlossen. **T1 tatsächlich ausgeführt:** vollständige Apps/Migrationen, Migration 0187, 138 Geschäftstabellen leer und 21 Schutzkopien zurückgeführt. Temporäre Sicherungstabellen bleiben bis zur Abnahme erhalten. Die gemeinsame Erweiterung wird über IMPORT_REBUILD_SCHEMA aktiviert; im Pilot an, im noch nicht migrierten Bestandsdienst aus. Keine Formelkopie, keine separaten Game-Klassen/Migrationen; der spätere Live-Cutover benötigt gesonderte Freigabe.

## 8. Vollständigkeits- und Codebeleg

Die Paket-Anlage bildet **357 tatsächlich vorkommende data.json-Feldpfade plus 27 manifest.json-Feldpfade = 384 Zeilen** auf Tabelle/Spalte, Zustand, Schicht, Spiegel und Post-Ligastart-Verhalten ab. Union über alle 51 Spieler/11 Personen/24 Rekorde/30 Titel, nicht nur einen Beispielspieler. NULL-/leere-Array-Formen sind zusätzlich zu gefüllten Unterfeldern aufgenommen. Alle 47 FMI- und 34 CMT-Rohattribute haben eigene Zeilen. Arrays sind als [] normalisiert; zusätzliche Rohschlüssel zukünftiger Pakete bleiben im Roharchiv, werden nicht automatisch zu spielwirksamen Feldern.

**Historischer N27-Prüfbeleg vom 05.10.2026:** Die beiden Nachtrag-5-Anhänge sind nach Vereinheitlichung von Zeilenenden/Rand-Leerraum inhaltlich identisch. Paket unverändert im ZIP gelesen, nicht importiert/extrahiert. SHA-256 data.json: 9d2b87c16389caf12693da07d7644df2c5f7d36e1e8c979b8651ead1e951676d; stimmt mit Manifest überein. Feldexistenz/alte Belegzeilen stammen aus statischer AST-Prüfung des damaligen game/models.py (SHA-256 b089d35d6489aed457baa1f48736e140bba22551977c2bb81a6b311935504d0a), ergänzt durch Leser-/Schreiberprüfung. Damals keine Django-App geladen oder DB abgefragt. **T1 am 06.10.2026:** reale Modelle/DB geprüft und Schema migriert; tatsächliche Änderungen, Prüfungen und Einschränkungen siehe t1-bericht.md und t1-schema-evidence.json.

Anlage: feldliste-n27-paketfelder.md. Beide Dokumente bilden gemeinsam die nach N28–N31 freigegebene Feldliste; die frühere Einseitenbegrenzung des N22-Modellplans ist durch die detaillierte N27-Feldliste ersetzt.

**HALT am Ende von T1.** Modell/Migration/Pilot-Schema aufgebaut und berichtet; kein Paketimport, kein Creator-Upload und keine Dortmund-Szenensicherung. T2–T5 bleiben gesperrt, Hetzner unberührt. Das Verhalten fehlender Spieler beim Vorstart-Reupload sowie die Rückkehr zu einem nicht importierten Stammverein bleiben ausdrücklich unentschieden.
