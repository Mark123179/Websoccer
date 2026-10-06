# T1: tatsächlich umgesetztes Schema

Migration: game/migrations/0187_import_rebuild_n28_n31.py

Quelle: Django-Migrationszustand 0186 → aktive Modelle und PostgreSQL-Katalog.
Keine Pakete importiert. Temporäre Schutz-Sicherungen sind keine fachlichen neuen Modelle.

| Tabelle | Spalte | Änderung | PostgreSQL-Typ | Nullable |
|---|---|---|---|---|
| game_club | official_name | neu | character varying | YES |
| game_club | nickname | neu | character varying | YES |
| game_club | motto | neu | character varying | YES |
| game_club | color_tertiary | neu | character varying | YES |
| game_club | import_state | neu | character varying | NO |
| game_clubexternalid | external_id | geändert | character varying | YES |
| game_clubexternalid | status | neu | character varying | NO |
| game_clubexternalid | checked_at | neu | date | YES |
| game_clubrecord | value_numeric | geändert | numeric | YES |
| game_clubrecord | basis | neu | character varying | YES |
| game_clubrecord | evidence_status | neu | character varying | YES |
| game_clubrecord | opponent_tm_id | neu | bigint | YES |
| game_clubrecord | evidence | neu | jsonb | NO |
| game_clubrecord | searched | neu | jsonb | NO |
| game_clubrecord | package_id | neu | bigint | YES |
| game_clubtrophy | origin | neu | character varying | NO |
| game_clubtrophy | category | neu | character varying | YES |
| game_clubtrophy | competition_fm_id | neu | bigint | YES |
| game_clubtrophyentry | id | neu (neue Tabelle) | bigint | NO |
| game_clubtrophyentry | club_id | neu (neue Tabelle) | bigint | NO |
| game_clubtrophyentry | competition_name | neu (neue Tabelle) | character varying | NO |
| game_clubtrophyentry | competition_fm_id | neu (neue Tabelle) | bigint | YES |
| game_clubtrophyentry | season | neu (neue Tabelle) | character varying | NO |
| game_clubtrophyentry | category | neu (neue Tabelle) | character varying | NO |
| game_clubtrophyentry | origin | neu (neue Tabelle) | character varying | NO |
| game_clubtrophyentry | source_url | neu (neue Tabelle) | character varying | YES |
| game_clubtrophyentry | package_id | neu (neue Tabelle) | bigint | YES |
| game_clubtrophyentry | source_row_key | neu (neue Tabelle) | character varying | NO |
| game_historiccoach | fm_inside_id | geändert | character varying | YES |
| game_historiccoach | person_kind | neu | character varying | NO |
| game_historiccoach | linked_player_id | neu | bigint | YES |
| game_importissue | id | neu (neue Tabelle) | bigint | NO |
| game_importissue | package_id | neu (neue Tabelle) | bigint | NO |
| game_importissue | entity | neu (neue Tabelle) | character varying | NO |
| game_importissue | entity_ref | neu (neue Tabelle) | character varying | NO |
| game_importissue | field | neu (neue Tabelle) | character varying | NO |
| game_importissue | severity | neu (neue Tabelle) | character varying | NO |
| game_importissue | note | neu (neue Tabelle) | text | NO |
| game_importissue | external_reference | neu (neue Tabelle) | jsonb | NO |
| game_importissue | proposed_tm_id | neu (neue Tabelle) | bigint | YES |
| game_importissue | resolved_at | neu (neue Tabelle) | timestamp with time zone | YES |
| game_importissue | resolved_by_id | neu (neue Tabelle) | integer | YES |
| game_importissue | resolution_status | neu (neue Tabelle) | character varying | NO |
| game_player | display_name | neu | character varying | YES |
| game_player | selection_evidence | neu | jsonb | NO |
| game_player | squad_team | neu | character varying | YES |
| game_player | owner_club_id | neu | bigint | YES |
| game_player | owner_club_tm_id | neu | bigint | YES |
| game_player | owner_club_original_name | neu | character varying | YES |
| game_player | loan_club_id | neu | bigint | YES |
| game_player | loan_club_tm_id | neu | bigint | YES |
| game_player | loan_club_original_name | neu | character varying | YES |
| game_player | import_lock | neu | boolean | NO |
| game_player | import_lock_reasons | neu | jsonb | NO |
| game_playerexternalid | player_id | geändert | bigint | YES |
| game_playerexternalid | external_id | geändert | character varying | YES |
| game_playerexternalid | status | neu | character varying | NO |
| game_playerexternalid | checked_at | neu | date | YES |
| game_playerexternalid | person_id | neu | bigint | YES |
| game_playerexternalid | identity_kind | neu | character varying | NO |
| game_playerexternalid | match_evidence | neu | jsonb | NO |
| game_playermarketvaluesnapshot | origin | neu | character varying | NO |
| game_playermarketvaluesnapshot | package_id | neu | bigint | YES |
| game_playermarketvaluesnapshot | source_row_key | neu | character varying | YES |
| game_playermarketvaluesnapshot | club_id | neu | bigint | YES |
| game_playermarketvaluesnapshot | club_tm_id | neu | bigint | YES |
| game_playermarketvaluesnapshot | club_original_name | neu | character varying | YES |
| game_playermarketvaluesnapshot | is_start_value | neu | boolean | NO |
| game_playersourceratingsnapshot | payload_hash | neu | character varying | NO |
| game_playertransferhistory | origin | neu | character varying | NO |
| game_playertransferhistory | package_id | neu | bigint | YES |
| game_playertransferhistory | source_row_key | neu | character varying | YES |
| game_playertransferhistory | is_loan | neu | boolean | NO |
| game_playertransferhistory | from_tm_id | neu | bigint | YES |
| game_playertransferhistory | from_original_name | neu | character varying | YES |
| game_playertransferhistory | to_tm_id | neu | bigint | YES |
| game_playertransferhistory | to_original_name | neu | character varying | YES |
| game_playertransferhistory | fee_text | neu | character varying | YES |
| game_sourceimportrun | source | geändert | character varying | NO |
| game_sourceimportrun | format | neu | character varying | YES |
| game_sourceimportrun | package_type | neu | character varying | YES |
| game_sourceimportrun | format_version | neu | smallint | YES |
| game_sourceimportrun | data_sha256 | neu | character varying | YES |
| game_sourceimportrun | collected_at | neu | timestamp with time zone | YES |
| game_sourceimportrun | titles_through_season | neu | character varying | YES |
| game_sourceimportrun | source_versions | neu | jsonb | NO |
| game_sourceimportrun | position_window | neu | jsonb | NO |
| game_sourceimportrun | manifest | neu | jsonb | NO |
| game_sourceimportrun | package_data | neu | jsonb | NO |
| game_sourceimportrun | club_id | neu | bigint | YES |
| game_sourceimportrun | target_league_id | neu | bigint | YES |
| game_sourceimportrun | status | neu | character varying | NO |
| game_sourceimportrun | applied_at | neu | timestamp with time zone | YES |
| game_stadium | nord_standing | geändert | integer | YES |
| game_stadium | nord_seating | geändert | integer | YES |
| game_stadium | nord_vip | geändert | integer | YES |
| game_stadium | ost_standing | geändert | integer | YES |
| game_stadium | ost_seating | geändert | integer | YES |
| game_stadium | ost_vip | geändert | integer | YES |
| game_stadium | sued_standing | geändert | integer | YES |
| game_stadium | sued_seating | geändert | integer | YES |
| game_stadium | sued_vip | geändert | integer | YES |
| game_stadium | west_standing | geändert | integer | YES |
| game_stadium | west_seating | geändert | integer | YES |
| game_stadium | west_vip | geändert | integer | YES |
| game_stadium | home_end | neu | character varying | YES |
| game_stadium | main_stand | neu | character varying | YES |
| game_stadium | map_lat | neu | numeric | YES |
| game_stadium | map_lng | neu | numeric | YES |
| game_stadium | source_tier | neu | smallint | YES |
| game_stadium | real_capacity_national | neu | integer | YES |
| game_stadium | real_total_standing | neu | integer | YES |
| game_stadium | real_total_seating_incl_vip | neu | integer | YES |
| game_stadium | real_total_vip | neu | integer | YES |
| game_stadium | real_total_standing_basis | neu | character varying | YES |
| game_stadium | real_total_seating_incl_vip_basis | neu | character varying | YES |
| game_stadium | real_total_vip_basis | neu | character varying | YES |
| game_stadium | real_nord_standing | neu | integer | YES |
| game_stadium | real_nord_standing_basis | neu | character varying | YES |
| game_stadium | real_nord_seating | neu | integer | YES |
| game_stadium | real_nord_seating_basis | neu | character varying | YES |
| game_stadium | real_nord_vip | neu | integer | YES |
| game_stadium | real_nord_vip_basis | neu | character varying | YES |
| game_stadium | real_ost_standing | neu | integer | YES |
| game_stadium | real_ost_standing_basis | neu | character varying | YES |
| game_stadium | real_ost_seating | neu | integer | YES |
| game_stadium | real_ost_seating_basis | neu | character varying | YES |
| game_stadium | real_ost_vip | neu | integer | YES |
| game_stadium | real_ost_vip_basis | neu | character varying | YES |
| game_stadium | real_sued_standing | neu | integer | YES |
| game_stadium | real_sued_standing_basis | neu | character varying | YES |
| game_stadium | real_sued_seating | neu | integer | YES |
| game_stadium | real_sued_seating_basis | neu | character varying | YES |
| game_stadium | real_sued_vip | neu | integer | YES |
| game_stadium | real_sued_vip_basis | neu | character varying | YES |
| game_stadium | real_west_standing | neu | integer | YES |
| game_stadium | real_west_standing_basis | neu | character varying | YES |
| game_stadium | real_west_seating | neu | integer | YES |
| game_stadium | real_west_seating_basis | neu | character varying | YES |
| game_stadium | real_west_vip | neu | integer | YES |
| game_stadium | real_west_vip_basis | neu | character varying | YES |

## Zusammenfassung
- Neue fachliche Tabellen: game_clubtrophyentry, game_importissue.
- Neue Spalten insgesamt (einschließlich neuer Tabellen): 123.
- Geänderte Felddefinitionen: 18.
- Physisch entfernte Spalten: 0.
- Nicht angelegt: real_loan_status, real_loan_club_id, real_loan_until, package_file.
- league_id bleibt NOT NULL. Kein nur_verweis-Zustand.
- Legacy-Spalten bleiben für Altleser physisch vorhanden; kein vorgezogener DROP.

## Constraint-Änderungen
- RemoveConstraint: playerexternalid.unique_external_player_id_per_source
- RemoveConstraint: playermarketvaluesnapshot.unique_player_market_value_snapshot
- RemoveConstraint: playersourceratingsnapshot.unique_player_source_rating_snapshot
- AddConstraint: club.club_import_state_valid
- AddConstraint: clubexternalid.clubexternalid_status_valid
- AddConstraint: clubtrophy.club_trophy_origin_valid
- AddConstraint: player.player_squad_team_valid
- AddConstraint: playerexternalid.unique_typed_external_person_id
- AddConstraint: playerexternalid.unique_person_external_id_per_source
- AddConstraint: playerexternalid.external_id_exactly_one_owner
- AddConstraint: playerexternalid.playerexternalid_status_valid
- AddConstraint: playermarketvaluesnapshot.unique_market_value_fact
- AddConstraint: playermarketvaluesnapshot.playermarketvaluesnapshot_origin_valid
- AddConstraint: playersourceratingsnapshot.unique_versioned_source_snapshot
- AddConstraint: playertransferhistory.playertransferhistory_origin_valid
- AddConstraint: playertransferhistory.unique_transfer_fact
- AddConstraint: clubtrophyentry.unique_club_title_fact
- AddConstraint: clubtrophyentry.club_title_origin_valid
- AddConstraint: importissue.import_issue_severity_valid
