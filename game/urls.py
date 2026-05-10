from django.urls import path
from .views import home, club_list, club_detail


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
]
