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
    home,
    player_detail,
    player_graph_data,
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
        'players/<int:player_id>/',
        player_detail,
        name='player_detail'
    ),

    path(
        'players/<int:player_id>/graph-data/',
        player_graph_data,
        name='player_graph_data'
    ),
]
