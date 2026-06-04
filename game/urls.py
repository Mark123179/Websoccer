from django.urls import path
from .views import (
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
)
from .views_creator import (
    creator_index,
    creator_club_edit,
    creator_upload_stadium,
    creator_upload_city,
    creator_upload_kit,
    creator_player_edit,
    creator_new_player,
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

    path('management/', management_hub, name='management_hub'),
    path('management/stadion/', stadium_detail, name='stadium_detail'),
    path('management/stadion/preise/', stadium_set_prices, name='stadium_set_prices'),
    path('management/stadion/ausbau/', stadium_expand, name='stadium_expand'),
    path('management/stadion/kosten-api/', stadium_cost_api, name='stadium_cost_api'),
    path('management/stadion/einnahmen/', stadium_record_revenue, name='stadium_record_revenue'),
    path('management/stadion/einrichtung-ausbauen/', facility_upgrade, name='facility_upgrade'),

    path('creator/', creator_index, name='creator_index'),
    path('creator/clubs/<int:club_id>/', creator_club_edit, name='creator_club_edit'),
    path('creator/clubs/<int:club_id>/upload/stadium/', creator_upload_stadium, name='creator_upload_stadium'),
    path('creator/clubs/<int:club_id>/upload/city/', creator_upload_city, name='creator_upload_city'),
    path('creator/clubs/<int:club_id>/upload/kit/<str:kit_type>/', creator_upload_kit, name='creator_upload_kit'),
    path('creator/players/<int:player_id>/', creator_player_edit, name='creator_player_edit'),
    path('creator/clubs/<int:club_id>/players/new/', creator_new_player, name='creator_new_player'),
]
