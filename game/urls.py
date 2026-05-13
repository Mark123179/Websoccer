from django.urls import path
from .views import home, club_list, club_detail, player_detail, player_graph_data


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
