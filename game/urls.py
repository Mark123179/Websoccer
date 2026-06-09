from django.urls import path
from .views import (
    claim_club,
    club_detail,
    club_list,
    club_match_preview,
    club_match_report,
    club_news,
    club_news_detail,
    club_professional_squad,
    club_table,
    club_tactics,
    club_youth_squad,
    squad_assign_shirt,
    squad_move_to_youth,
    home,
    league_detail,
    manager_profile,
    set_trainer_type,
    update_manager_profile,
    upload_profile_image,
    reset_profile_image,
    save_career_station,
    delete_career_station,
    player_detail,
    player_graph_data,
)
from .views_auth import auth_login, auth_register, auth_logout
from .views_ai import ai_chat
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
    management_halloffame,
)
from .views_creator import (
    creator_index,
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
    creator_new_player,
    creator_save_stammdaten,
    creator_save_infrastruktur,
    creator_add_trophy,
    creator_delete_trophy,
    creator_edit_trophy,
    creator_add_sponsor,
    creator_delete_sponsor,
    creator_toggle_sponsor,
    creator_add_goal,
    creator_delete_goal,
    creator_league_edit,
    creator_league_save_stammdaten,
    creator_league_spielplan_generate,
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
    creator_sofifa_import,
    creator_vereinslose,
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

    path('auth/login/', auth_login, name='auth_login'),
    path('auth/register/', auth_register, name='auth_register'),
    path('auth/logout/', auth_logout, name='auth_logout'),

    path('ai/chat/', ai_chat, name='ai_chat'),

    path(
        'liga/<int:league_id>/',
        league_detail,
        name='league_detail',
    ),

    path('management/', management_hub, name='management_hub'),
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
    path('management/halloffame/', management_halloffame, name='management_halloffame'),

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
    path('creator/clubs/<int:club_id>/players/new/', creator_new_player, name='creator_new_player'),
    path('creator/clubs/<int:club_id>/stammdaten/', creator_save_stammdaten, name='creator_save_stammdaten'),
    path('creator/clubs/<int:club_id>/infrastruktur/', creator_save_infrastruktur, name='creator_save_infrastruktur'),
    path('creator/clubs/<int:club_id>/trophies/add/', creator_add_trophy, name='creator_add_trophy'),
    path('creator/clubs/<int:club_id>/trophies/<int:trophy_id>/delete/', creator_delete_trophy, name='creator_delete_trophy'),
    path('creator/clubs/<int:club_id>/trophies/<int:trophy_id>/edit/', creator_edit_trophy, name='creator_edit_trophy'),
    path('creator/clubs/<int:club_id>/sponsors/add/', creator_add_sponsor, name='creator_add_sponsor'),
    path('creator/clubs/<int:club_id>/sponsors/<int:sponsor_id>/delete/', creator_delete_sponsor, name='creator_delete_sponsor'),
    path('creator/clubs/<int:club_id>/sponsors/<int:sponsor_id>/toggle/', creator_toggle_sponsor, name='creator_toggle_sponsor'),
    path('creator/clubs/<int:club_id>/goals/add/', creator_add_goal, name='creator_add_goal'),
    path('creator/clubs/<int:club_id>/goals/<int:goal_id>/delete/', creator_delete_goal, name='creator_delete_goal'),

    # Liga-Editor
    path('creator/leagues/<int:league_id>/', creator_league_edit, name='creator_league_edit'),
    path('creator/leagues/<int:league_id>/stammdaten/', creator_league_save_stammdaten, name='creator_league_save_stammdaten'),
    path('creator/leagues/<int:league_id>/spielplan/generate/', creator_league_spielplan_generate, name='creator_league_spielplan_generate'),
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

    # SoFIFA-CSV-Import
    path('creator/import/sofifa/', creator_sofifa_import, name='creator_sofifa_import'),
]
