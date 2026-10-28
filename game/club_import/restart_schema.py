"""Versioned positive list for the data-only restart handoff.

No account, image, simulation, finance-ledger or editor tables belong here.
Changes to this contract require a new package version and parity evidence.
"""
from game import models as m


FORMAT = "WS_RESTART_CURRENT_STATE_V1"


def fields(text):
    return tuple(text.split())


FIELDS = {
    "League": fields("""
        name country level api_football_id strength_coefficient coefficient_source
        cl_spots el_spots conference_spots relegation_spots competition_type max_teams is_playable
    """),
    "Club": fields("""
        fm_inside_id api_football_id transfermarkt_id cmtracker_id transfermarkt_profile_url
        is_import_placeholder import_name_provisional name short_name color_primary
        color_secondary founded_year league official_name nickname motto color_tertiary import_state
    """),
    "Player": fields("""
        first_name last_name fm_inside_id transfermarkt_id api_football_id
        transfermarkt_profile_url transfermarkt_market_value_url date_of_birth nationalities
        nt_nationality age height_cm strong_foot shirt_number position primary_position
        source_positions main_position_1 main_position_2 main_position_3
        secondary_position_1 secondary_position_2 secondary_position_3 potential market_value
        contract_until club real_life_club loan_status loan_partner_club loan_until
        pool_status scouting_category wsc_conflict is_callable admin_reviewed display_name
        selection_evidence squad_team owner_club owner_club_tm_id owner_club_original_name
        loan_club loan_club_tm_id loan_club_original_name import_lock import_lock_reasons review_pool
    """),
    "DataSource": fields("code name base_url notes"),
    "SourceImportRun": fields("""
        source version imported_at dry_run total_rows count_new count_updated count_unchanged
        count_unmatched count_error format package_type format_version data_sha256
        collected_at titles_through_season source_versions position_window
        club target_league status applied_at
    """),
    "HistoricCoach": fields("fm_inside_id name nationality birth_date notes person_kind linked_player"),
    "PlayerExternalId": fields("""
        player source external_id profile_url is_primary notes db_slug source_url
        created_at updated_at last_seen_at status checked_at person identity_kind match_evidence
    """),
    "ClubExternalId": fields("""
        club source external_id db_slug source_url created_at updated_at last_seen_at status checked_at
    """),
    "ClubPublicProfile": fields("""
        club stadium_name stadium_capacity average_attendance city_name city_country
        map_lat map_lng partner_club
    """),
    "ClubTMProfile": fields("""
        club tm_club_id tm_club_url squad_source_url imported_at fetched_at
        last_imported_at last_verified_at data_quality_flags missing_required_fields
    """),
    "ClubCMTProfile": fields("""
        club db_slug team_id league_id name league_name nation country foundation_year
        popularity domestic_prestige international_prestige profitability payload_hash
        imported_at fetched_at last_imported_at last_verified_at source_priority
        data_quality_flags missing_required_fields
    """),
    "PlayerTMProfile": fields("""
        player tm_player_id tm_club_id market_value market_value_date tm_position_raw
        tm_position_calculated_websoccer source_url imported_at fetched_at
        last_imported_at last_verified_at data_quality_flags missing_required_fields
    """),
    "PlayerFMIProfile": fields("""
        player fmi_id fmi_overall fmi_potential fmi_attributes fmi_version imported_at
        fetched_at last_imported_at last_verified_at data_quality_flags missing_required_fields
    """),
    "PlayerCMTProfile": fields("""
        player db_slug database_version cmt_player_id first_name last_name known_as display_name
        nationality second_nationality date_of_birth overall potential height_cm weight_kg
        preferred_foot body_type emotion real_life_club on_loan_from_club playstyles
        playstyles_plus roles role_plus role_plus_plus payload_hash imported_at fetched_at
        last_imported_at last_verified_at source_priority data_quality_flags missing_required_fields
    """),
    "PlayerCMTAttributeProfile": fields("""
        player db_slug pac sho pas dri def_rating phy acceleration sprint_speed agility balance
        jumping stamina strength reactions aggression composure interceptions positioning vision
        ball_control crossing dribbling finishing freekick_accuracy heading_accuracy
        long_passing short_passing marking shot_power long_shots standing_tackle sliding_tackle
        volleys curve penalties gk_diving gk_handling gk_kicking gk_reflexes gk_positioning
        raw_attributes imported_at fetched_at payload_hash
    """),
    "PlayerSourceRating": fields("""
        player source rating potential tempo ausdauer kraft technik dribbling passspiel flanken
        abschluss kopfball zweikampf defensivstellung uebersicht teamwork ecken freistoss
        elfmeter tw_reflexe tw_fangsicherheit tw_eins_gegen_eins tw_stellungsspiel tw_passen
        source_url source_version checked_at notes created_at updated_at
    """),
    "PlayerStrengthProfile": fields("player base_strength form_modifier freshness final_strength updated_at"),
    "PlayerSourceRatingSnapshot": fields("""
        player source recorded_at rating potential source_url source_version update_current
        raw_payload notes created_at payload_hash
    """),
    "PlayerMarketValueSnapshot": fields("""
        player source recorded_at value_eur profile_url source_version update_current
        raw_payload notes created_at origin package source_row_key club club_tm_id club_original_name is_start_value
    """),
    "PlayerTransferHistory": fields("""
        player transfer_date season from_club to_club fee_eur notes created_at origin package
        source_row_key is_loan from_tm_id from_original_name to_tm_id to_original_name fee_text
    """),
    "ClubRecord": fields("""
        club record_key custom_label source value_numeric value_display holder_name
        holder_player holder_coach opponent_name opponent_club context_line record_date
        period_from period_to season competition source_note is_anonymized updated_at
        basis evidence_status opponent_tm_id evidence searched package
    """),
    "ClubTrophy": fields("""
        club competition_name count trophy_asset_id sort_order origin category competition_fm_id
    """),
    "ClubTrophyEntry": fields("""
        club competition_name competition_fm_id season category origin source_url package source_row_key
    """),
    "ImportIssue": fields("""
        club package last_seen_package subkey manual_value entity entity_ref field severity
        note external_reference proposed_tm_id resolved_at resolution_status
    """),
}

# Stadium's physical/current capacity and imported real-world distribution are
# data, not the separately protected geometry/design or operating prices.
FIELDS["Stadium"] = fields("""
    club name city nord_standing nord_seating nord_vip ost_standing ost_seating ost_vip
    sued_standing sued_seating sued_vip west_standing west_seating west_vip home_end main_stand
    map_lat map_lng source_tier real_capacity_national real_total_standing
    real_total_seating_incl_vip real_total_vip real_total_standing_basis
    real_total_seating_incl_vip_basis real_total_vip_basis
""") + tuple(
    f"real_{side}_{kind}{suffix}"
    for side in ("nord", "ost", "sued", "west")
    for kind in ("standing", "seating", "vip")
    for suffix in ("", "_basis")
)

# This order is also the insert order. Foreign keys are connected in a second
# pass, including cycles (Player -> Club -> League, persons -> players).
MODELS = {name: getattr(m, name) for name in FIELDS}
ANCHORS = {"League", "Club", "Player", "DataSource", "HistoricCoach", "SourceImportRun"}


def structure():
    """Physical type/nullability/precision contract, excluding surrogate IDs."""
    return {
        name: {
            field: {
                "type": model._meta.get_field(field).get_internal_type(),
                "null": model._meta.get_field(field).null,
                "related": (model._meta.get_field(field).related_model.__name__
                            if model._meta.get_field(field).is_relation else None),
                "max_length": model._meta.get_field(field).max_length,
                "max_digits": getattr(model._meta.get_field(field), "max_digits", None),
                "decimal_places": getattr(model._meta.get_field(field), "decimal_places", None),
            }
            for field in FIELDS[name]
        }
        for name, model in MODELS.items()
    }


def exclusions():
    """Every omitted column is visible for inspection, not silently dropped."""
    return {
        name: [f.name for f in model._meta.fields if f.name not in FIELDS[name]]
        for name, model in MODELS.items()
    }
