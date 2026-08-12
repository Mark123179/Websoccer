from django.urls import path
from .views import (
    claim_club,
    club_detail,
    club_list,
    club_match_preview,
    club_match_report,
    match_report_by_id,
    club_news,
    club_news_delete,
    club_news_detail,
    club_news_publish,
    public_manager_profile,
    club_professional_squad,
    club_table,
    club_tactics,
    club_youth_squad,
    squad_assign_shirt,
    squad_move_to_youth,
    home,
    league_detail,
    simulate_matchday_view,
    close_matchday_view,
    manager_profile,
    set_trainer_type,
    update_manager_profile,
    upload_profile_image,
    reset_profile_image,
    save_career_station,
    delete_career_station,
    submit_timeline_entry,
    player_detail,
    player_graph_data,
)
from .views_auth import auth_login, auth_register, auth_logout
from .views_notifications import notifications_page
from .views_ai import ai_chat
from .views_notes import notizen_api
from .views_transfer_v2 import (
    transfer_market,
    transfer_market_bid,
    transfer_market_buy_now,
    transfer_market_pin,
    transfer_rumor_react,
)
from .views_scouting import (
    transfer_scouting,
    scouting_start,
    scouting_bid,
    forced_auction_bid,
    scouting_watch,
    scouting_withdraw,
    scouting_upgrade,
    scouting_reject,
    transfer_watchlist,
    scouting_watchlist_add,
    scouting_watchlist_remove,
    scouting_community_submit,
    creator_scouting_overview,
    creator_moderate_submission,
    creator_timeline_overview,
    creator_moderate_timeline,
)
from .views_management import (
    management_hub,
    stadium_detail,
    stadium_set_prices,
    stadium_expand,
    stadium_cost_api,
    stadium_record_revenue,
    facility_upgrade,
    president_office,
    coin_shop_purchase,
    management_sportgericht,
    sportgericht_ticket_submit,
    management_finanzen,
    management_sponsor_choose,
    management_sponsoring,
    management_sponsoring_accept,
    management_sponsoring_push,
    management_halloffame,
    management_job_offers,
    management_stadionumfeld,
    stadionumfeld_save,
)
from .views_creator import (
    creator_index,
    creator_simulation_diagnostics,
    creator_system_diagnostics,
    creator_search,
    creator_club_edit,
    creator_upload_stadium,
    creator_upload_city,
    creator_upload_kit,
    creator_upload_crest,
    creator_player_edit,
    creator_player_recalculate_strength,
    creator_player_fetch_rl_form,
    creator_player_search_api_football,
    creator_player_save_rl_mapping,
    creator_player_delete,
    creator_new_player,
    creator_save_stammdaten,
    creator_save_infrastruktur,
    creator_save_source_ids,
    creator_add_trophy,
    creator_delete_trophy,
    creator_edit_trophy,
    creator_add_sponsor,
    creator_delete_sponsor,
    creator_toggle_sponsor,
    creator_sponsoring_deactivate,
    creator_sponsoring_slot_reset,
    creator_sponsoring_risk_mode,
    creator_add_goal,
    creator_delete_goal,
    creator_league_edit,
    creator_league_save_stammdaten,
    creator_league_spielplan_generate,
    creator_league_season_reset,
    creator_league_fixture_save,
    creator_upload_league_logo,
)
from .views_creator import (
    creator_manager_list,
    creator_manager_edit,
    creator_save_manager_profil,
    creator_save_manager_club,
    creator_add_career_station,
    creator_delete_career_station,
    creator_save_coins,
    creator_save_satisfaction,
    creator_add_satisfaction,
    creator_import_hub,
    creator_sofifa_import,
    creator_fmid_csv_import,
    creator_club_csv_import,
    creator_vereinslose,
    creator_competition_create,
    creator_cup_generate_dummies,
    creator_cup_season_create,
    creator_cup_season_reset,
    creator_cup_draw_first_round,
    creator_cup_simulate_round,
    creator_cup_advance,
    creator_cup_schedule_preview,
    creator_cup_schedule_apply,
    cup_tree_view,
    creator_season_end,
    creator_freie_vereine,
    creator_import_index,
    creator_import_create,
    creator_import_detail,
    creator_import_status,
    creator_import_candidate_update,
    creator_import_bulk,
    creator_import_confirm,
)
from .views_creator import (
    creator_media_outlets,
    creator_finanzanalyse,
    creator_finance_gap_retry,
    creator_kalibrierung,
    creator_media_outlet_delete,
    creator_ki_angebote,
    creator_ki_transferzentrale,
    creator_sportgericht,
    creator_referee_list,
    creator_referee_edit,
    creator_referee_save,
    creator_referee_delete,
)
from .views_importer_api import (
    importer_next_job,
    importer_claim_job,
    importer_heartbeat,
    importer_progress,
    importer_candidates,
    importer_complete,
    importer_fail,
)
from .views_transfermarkt import (
    squad_set_sale_status,
    transfer_place_bid,
    transfer_accept_counter,
    transfer_cancel_negotiation,
    ai_offer_accept,
    ai_offer_reject,
)


urlpatterns = [
    path(
        '',
        home,
        name='home'
    ),

    path(
        'clubs/',
        club_list,
        name='club_list'
    ),

    path(
        'clubs/<int:club_id>/claim/',
        claim_club,
        name='claim_club'
    ),

    path(
        'clubs/<int:club_id>/',
        club_detail,
        name='club_detail'
    ),

    path(
        'clubs/<int:club_id>/squad/',
        club_professional_squad,
        name='club_professional_squad'
    ),

    path(
        'clubs/<int:club_id>/youth/',
        club_youth_squad,
        name='club_youth_squad'
    ),

    path(
        'clubs/<int:club_id>/tactics/',
        club_tactics,
        name='club_tactics'
    ),

    path(
        'clubs/<int:club_id>/table/',
        club_table,
        name='club_table'
    ),

    path(
        'clubs/<int:club_id>/matches/next/',
        club_match_preview,
        name='club_match_preview'
    ),

    path(
        'clubs/<int:club_id>/matches/last/',
        club_match_report,
        name='club_match_report'
    ),

    path(
        'matches/<int:sm_id>/report/',
        match_report_by_id,
        name='match_report_by_id'
    ),

    path(
        'clubs/<int:club_id>/news/',
        club_news,
        name='club_news'
    ),

    path(
        'clubs/<int:club_id>/news/<int:news_id>/',
        club_news_detail,
        name='club_news_detail'
    ),

    path(
        'clubs/<int:club_id>/news/publish/',
        club_news_publish,
        name='club_news_publish'
    ),

    path(
        'clubs/<int:club_id>/news/<int:news_id>/delete/',
        club_news_delete,
        name='club_news_delete'
    ),

    path(
        'clubs/<int:club_id>/squad/assign-shirt/',
        squad_assign_shirt,
        name='squad_assign_shirt'
    ),

    path(
        'clubs/<int:club_id>/squad/move-to-youth/',
        squad_move_to_youth,
        name='squad_move_to_youth'
    ),

    path(
        'clubs/<int:club_id>/squad/sale-status/',
        squad_set_sale_status,
        name='squad_set_sale_status'
    ),

    path(
        'transfers/bid/',
        transfer_place_bid,
        name='transfer_place_bid'
    ),

    path(
        'transfers/accept-counter/',
        transfer_accept_counter,
        name='transfer_accept_counter'
    ),

    path(
        'transfers/cancel/',
        transfer_cancel_negotiation,
        name='transfer_cancel_negotiation'
    ),

    path(
        'transfers/ki-angebot/annehmen/',
        ai_offer_accept,
        name='ai_offer_accept'
    ),

    path(
        'transfers/ki-angebot/ablehnen/',
        ai_offer_reject,
        name='ai_offer_reject'
    ),

    path(
        'players/<int:player_id>/',
        player_detail,
        name='player_detail'
    ),

    path(
        'players/<int:player_id>/graph-data/',
        player_graph_data,
        name='player_graph_data'
    ),

    path('manager/profil/', manager_profile, name='manager_profile'),
    path('manager/set-type/', set_trainer_type, name='set_trainer_type'),
    path('manager/update-profile/', update_manager_profile, name='update_manager_profile'),
    path('manager/upload-image/', upload_profile_image, name='upload_profile_image'),
    path('manager/reset-image/', reset_profile_image, name='reset_profile_image'),
    path('manager/career-station/save/', save_career_station, name='save_career_station'),
    path('manager/career-station/delete/', delete_career_station, name='delete_career_station'),
    path('manager/timeline-entry/save/', submit_timeline_entry, name='submit_timeline_entry'),
    path('manager/<str:username>/', public_manager_profile, name='public_manager_profile'),

    path('auth/login/', auth_login, name='auth_login'),
    path('auth/register/', auth_register, name='auth_register'),
    path('auth/logout/', auth_logout, name='auth_logout'),

    path('ai/chat/', ai_chat, name='ai_chat'),

    path('api/notizen/', notizen_api, name='notizen_api'),

    path(
        'liga/<int:league_id>/',
        league_detail,
        name='league_detail',
    ),
    path(
        'liga/<int:league_id>/simulate-spieltag/',
        simulate_matchday_view,
        name='simulate_matchday',
    ),
    path(
        'liga/<int:league_id>/close-spieltag/',
        close_matchday_view,
        name='close_matchday',
    ),

    path('management/', management_hub, name='management_hub'),
    path('management/stadionumfeld/', management_stadionumfeld, name='management_stadionumfeld'),
    path('management/stadionumfeld/speichern/', stadionumfeld_save, name='stadionumfeld_save'),
    path('management/stadion/', stadium_detail, name='stadium_detail'),
    path('management/stadion/preise/', stadium_set_prices, name='stadium_set_prices'),
    path('management/stadion/ausbau/', stadium_expand, name='stadium_expand'),
    path('management/stadion/kosten-api/', stadium_cost_api, name='stadium_cost_api'),
    path('management/stadion/einnahmen/', stadium_record_revenue, name='stadium_record_revenue'),
    path('management/stadion/einrichtung-ausbauen/', facility_upgrade, name='facility_upgrade'),

    path('management/praesident/', president_office, name='president_office'),
    path('management/praesident/kaufen/', coin_shop_purchase, name='coin_shop_purchase'),

    path('management/sportgericht/', management_sportgericht, name='management_sportgericht'),
    path('management/sportgericht/ticket/', sportgericht_ticket_submit, name='sportgericht_ticket_submit'),

    path('management/finanzen/', management_finanzen, name='management_finanzen'),
    path('management/finanzen/sponsor/', management_sponsor_choose, name='management_sponsor_choose'),
    path('management/sponsoring/', management_sponsoring, name='management_sponsoring'),
    path('management/sponsoring/annehmen/', management_sponsoring_accept, name='management_sponsoring_accept'),
    path('management/sponsoring/verhandeln/', management_sponsoring_push, name='management_sponsoring_push'),
    path('management/finanzen/sponsoring/', management_sponsoring, name='management_sponsoring_finanzen_compat'),
    path('management/finanzen/sponsoring/annehmen/', management_sponsoring_accept, name='management_sponsoring_accept_compat'),
    path('management/finanzen/sponsoring/verhandeln/', management_sponsoring_push, name='management_sponsoring_push_compat'),
    path('management/halloffame/', management_halloffame, name='management_halloffame'),
    path('management/job-angebote/', management_job_offers, name='management_job_offers'),

    # Transfersystem v2 — Transfermarkt (Task #820)
    path('transfers/markt/', transfer_market, name='transfer_market'),
    path('transfers/markt/gebot/', transfer_market_bid, name='transfer_market_bid'),
    path('transfers/markt/sofortkauf/', transfer_market_buy_now, name='transfer_market_buy_now'),
    path('transfers/markt/pin/', transfer_market_pin, name='transfer_market_pin'),
    path('transfers/markt/geruecht/', transfer_rumor_react, name='transfer_rumor_react'),

    # Scouting-System (Task #594)
    path('transfers/scouting/', transfer_scouting, name='transfer_scouting'),
    path('transfers/scouting/auftrag/', scouting_start, name='scouting_start'),
    path('transfers/scouting/gebot/', scouting_bid, name='scouting_bid'),
    path('transfers/scouting/beobachten/', scouting_watch, name='scouting_watch'),
    path('transfers/scouting/zurueckziehen/', scouting_withdraw, name='scouting_withdraw'),
    path('transfers/zwangsversteigerung/gebot/', forced_auction_bid,
         name='forced_auction_bid'),
    path('transfers/scouting/ausbauen/', scouting_upgrade, name='scouting_upgrade'),
    path('transfers/scouting/ablehnen/', scouting_reject, name='scouting_reject'),
    path('transfers/beobachtungsliste/', transfer_watchlist, name='transfer_watchlist'),
    path('transfers/beobachtungsliste/hinzufuegen/', scouting_watchlist_add, name='scouting_watchlist_add'),
    path('transfers/beobachtungsliste/entfernen/', scouting_watchlist_remove, name='scouting_watchlist_remove'),
    path('transfers/scouting/community/', scouting_community_submit, name='scouting_community_submit'),
    path('creator/scouting/', creator_scouting_overview, name='creator_scouting_overview'),
    path('creator/scouting/<int:submission_id>/moderieren/', creator_moderate_submission, name='creator_moderate_submission'),
    path('creator/antraege/', creator_timeline_overview, name='creator_timeline_overview'),
    path('creator/antraege/<int:entry_id>/moderieren/', creator_moderate_timeline, name='creator_moderate_timeline'),

    path('creator/medien/', creator_media_outlets, name='creator_media_outlets'),
    path('creator/finanzen/', creator_finanzanalyse, name='creator_finanzanalyse'),
    path('creator/finanzen/nachholen/', creator_finance_gap_retry, name='creator_finance_gap_retry'),
    path('creator/kalibrierung/', creator_kalibrierung, name='creator_kalibrierung'),
    path('creator/ki-angebote/', creator_ki_angebote, name='creator_ki_angebote'),
    path('creator/ki-transferzentrale/', creator_ki_transferzentrale, name='creator_ki_transferzentrale'),
    path('creator/sportgericht/', creator_sportgericht, name='creator_sportgericht'),
    path('creator/medien/<int:outlet_id>/loeschen/', creator_media_outlet_delete, name='creator_media_outlet_delete'),
    path('creator/simulation-diagnostics/', creator_simulation_diagnostics, name='creator_simulation_diagnostics'),
    path('creator/system-diagnostics/', creator_system_diagnostics, name='creator_system_diagnostics'),
    path('creator/', creator_index, name='creator_index'),
    path('creator/search/', creator_search, name='creator_search'),
    path('creator/clubs/<int:club_id>/', creator_club_edit, name='creator_club_edit'),
    path('creator/clubs/<int:club_id>/upload/stadium/', creator_upload_stadium, name='creator_upload_stadium'),
    path('creator/clubs/<int:club_id>/upload/city/', creator_upload_city, name='creator_upload_city'),
    path('creator/clubs/<int:club_id>/upload/kit/<str:kit_type>/', creator_upload_kit, name='creator_upload_kit'),
    path('creator/clubs/<int:club_id>/upload/crest/', creator_upload_crest, name='creator_upload_crest'),
    path('creator/players/vereinslose/', creator_vereinslose, name='creator_vereinslose'),
    path('creator/players/<int:player_id>/', creator_player_edit, name='creator_player_edit'),
    path('creator/players/<int:player_id>/recalculate-strength/', creator_player_recalculate_strength, name='creator_player_recalculate_strength'),
    path('creator/players/<int:player_id>/fetch-rl-form/', creator_player_fetch_rl_form, name='creator_player_fetch_rl_form'),
    path('creator/players/<int:player_id>/search-api-football/', creator_player_search_api_football, name='creator_player_search_api_football'),
    path('creator/players/<int:player_id>/save-rl-mapping/', creator_player_save_rl_mapping, name='creator_player_save_rl_mapping'),
    path('creator/players/<int:player_id>/delete/', creator_player_delete, name='creator_player_delete'),
    path('creator/clubs/<int:club_id>/players/new/', creator_new_player, name='creator_new_player'),
    path('creator/clubs/<int:club_id>/stammdaten/', creator_save_stammdaten, name='creator_save_stammdaten'),
    path('creator/clubs/<int:club_id>/infrastruktur/', creator_save_infrastruktur, name='creator_save_infrastruktur'),
    path('creator/clubs/<int:club_id>/source-ids/', creator_save_source_ids, name='creator_save_source_ids'),
    path('creator/clubs/<int:club_id>/trophies/add/', creator_add_trophy, name='creator_add_trophy'),
    path('creator/clubs/<int:club_id>/trophies/<int:trophy_id>/delete/', creator_delete_trophy, name='creator_delete_trophy'),
    path('creator/clubs/<int:club_id>/trophies/<int:trophy_id>/edit/', creator_edit_trophy, name='creator_edit_trophy'),
    path('creator/clubs/<int:club_id>/sponsors/add/', creator_add_sponsor, name='creator_add_sponsor'),
    path('creator/clubs/<int:club_id>/sponsors/<int:sponsor_id>/delete/', creator_delete_sponsor, name='creator_delete_sponsor'),
    path('creator/clubs/<int:club_id>/sponsors/<int:sponsor_id>/toggle/', creator_toggle_sponsor, name='creator_toggle_sponsor'),
    path('creator/clubs/<int:club_id>/sponsoring/slot-reset/', creator_sponsoring_slot_reset, name='creator_sponsoring_slot_reset'),
    path('creator/sponsoring/deactivate/', creator_sponsoring_deactivate, name='creator_sponsoring_deactivate'),
    path('creator/sponsoring/risk-mode/', creator_sponsoring_risk_mode, name='creator_sponsoring_risk_mode'),
    path('creator/clubs/<int:club_id>/goals/add/', creator_add_goal, name='creator_add_goal'),
    path('creator/clubs/<int:club_id>/goals/<int:goal_id>/delete/', creator_delete_goal, name='creator_delete_goal'),

    # Liga-Editor
    path('creator/leagues/<int:league_id>/', creator_league_edit, name='creator_league_edit'),
    path('creator/leagues/<int:league_id>/stammdaten/', creator_league_save_stammdaten, name='creator_league_save_stammdaten'),
    path('creator/leagues/<int:league_id>/spielplan/generate/', creator_league_spielplan_generate, name='creator_league_spielplan_generate'),
    path('creator/leagues/<int:league_id>/season/reset/', creator_league_season_reset, name='creator_league_season_reset'),
    path('creator/leagues/<int:league_id>/fixtures/save/', creator_league_fixture_save, name='creator_league_fixture_save'),
    path('creator/leagues/<int:league_id>/upload/logo/', creator_upload_league_logo, name='creator_upload_league_logo'),

    # Manager-Profile-Editor
    path('creator/managers/', creator_manager_list, name='creator_manager_list'),
    path('creator/managers/<int:manager_id>/', creator_manager_edit, name='creator_manager_edit'),
    path('creator/managers/<int:manager_id>/profil/', creator_save_manager_profil, name='creator_save_manager_profil'),
    path('creator/managers/<int:manager_id>/verein/', creator_save_manager_club, name='creator_save_manager_club'),
    path('creator/managers/<int:manager_id>/karriere/add/', creator_add_career_station, name='creator_add_career_station'),
    path('creator/managers/<int:manager_id>/karriere/<int:station_id>/delete/', creator_delete_career_station, name='creator_delete_career_station'),
    path('creator/managers/<int:manager_id>/coins/', creator_save_coins, name='creator_save_coins'),
    path('creator/managers/<int:manager_id>/satisfaction/<int:sat_id>/', creator_save_satisfaction, name='creator_save_satisfaction'),
    path('creator/managers/<int:manager_id>/satisfaction/add/', creator_add_satisfaction, name='creator_add_satisfaction'),

    # Schiedsrichter
    path('creator/referees/', creator_referee_list, name='creator_referee_list'),
    path('creator/referees/new/', creator_referee_edit, name='creator_referee_new'),
    path('creator/referees/new/save/', creator_referee_save, name='creator_referee_new_save'),
    path('creator/referees/<int:referee_id>/', creator_referee_edit, name='creator_referee_edit'),
    path('creator/referees/<int:referee_id>/save/', creator_referee_save, name='creator_referee_save'),
    path('creator/referees/<int:referee_id>/delete/', creator_referee_delete, name='creator_referee_delete'),

    # Geführter Import-Hub
    path('creator/import/hub/', creator_import_hub, name='creator_import_hub'),

    # CMTracker-CSV-Import
    path('creator/import/sofifa/', creator_sofifa_import, name='creator_sofifa_import'),
    path('creator/import/fmids/', creator_fmid_csv_import, name='creator_fmid_csv_import'),
    path('creator/import/club-csv/', creator_club_csv_import, name='creator_club_csv_import'),

    # Vereins-/Spielerimport (Creator-Mode Oberfläche)
    path('creator/import/', creator_import_index, name='creator_import_index'),
    path('creator/import/create/', creator_import_create, name='creator_import_create'),
    path('creator/import/<int:job_id>/', creator_import_detail, name='creator_import_detail'),
    path('creator/import/<int:job_id>/status/', creator_import_status, name='creator_import_status'),
    path('creator/import/<int:job_id>/candidate/<int:candidate_id>/', creator_import_candidate_update, name='creator_import_candidate_update'),
    path('creator/import/<int:job_id>/bulk/', creator_import_bulk, name='creator_import_bulk'),
    path('creator/import/<int:job_id>/confirm/', creator_import_confirm, name='creator_import_confirm'),

    # Wettbewerb anlegen (Pokal / Liga)
    path('creator/competitions/create/', creator_competition_create, name='creator_competition_create'),

    # Pokal-Saison + Auslosung
    path('creator/leagues/<int:league_id>/cup/generate-dummies/', creator_cup_generate_dummies, name='creator_cup_generate_dummies'),
    path('creator/leagues/<int:league_id>/cup/season/create/', creator_cup_season_create, name='creator_cup_season_create'),
    path('creator/leagues/<int:league_id>/cup/season/<int:cup_season_id>/reset/', creator_cup_season_reset, name='creator_cup_season_reset'),
    path('creator/leagues/<int:league_id>/cup/season/<int:cup_season_id>/draw/', creator_cup_draw_first_round, name='creator_cup_draw_first_round'),
    path('creator/leagues/<int:league_id>/cup/round/<int:cup_round_id>/simulate/', creator_cup_simulate_round, name='creator_cup_simulate_round'),
    path('creator/leagues/<int:league_id>/cup/round/<int:cup_round_id>/advance/', creator_cup_advance, name='creator_cup_advance'),
    path('creator/leagues/<int:league_id>/cup/season/<int:cup_season_id>/schedule-preview/', creator_cup_schedule_preview, name='creator_cup_schedule_preview'),
    path('creator/leagues/<int:league_id>/cup/season/<int:cup_season_id>/schedule-apply/', creator_cup_schedule_apply, name='creator_cup_schedule_apply'),

    # Pokalbaum (öffentliche Ansicht)
    path('pokal/<int:league_id>/<path:season>/', cup_tree_view, name='cup_tree'),

    # Saisonverwaltung
    path('creator/season-end/', creator_season_end, name='creator_season_end'),

    # System — Freie Vereine
    path('creator/system/freie-vereine/', creator_freie_vereine, name='creator_freie_vereine'),

    # Benachrichtigungen (Glocke im Header)
    path('benachrichtigungen/', notifications_page, name='notifications_page'),

    # Geschützte Importer-API (Bearer-Token, kein CSRF; Spec §28)
    path('creator-api/import-jobs/next/', importer_next_job, name='importer_next_job'),
    path('creator-api/import-jobs/<int:job_id>/claim/', importer_claim_job, name='importer_claim_job'),
    path('creator-api/import-jobs/<int:job_id>/heartbeat/', importer_heartbeat, name='importer_heartbeat'),
    path('creator-api/import-jobs/<int:job_id>/progress/', importer_progress, name='importer_progress'),
    path('creator-api/import-jobs/<int:job_id>/candidates/', importer_candidates, name='importer_candidates'),
    path('creator-api/import-jobs/<int:job_id>/complete/', importer_complete, name='importer_complete'),
    path('creator-api/import-jobs/<int:job_id>/fail/', importer_fail, name='importer_fail'),
]
