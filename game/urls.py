from django.urls import path
from .views import club_list, club_detail


urlpatterns = [
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