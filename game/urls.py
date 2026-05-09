from django.urls import path
from .views import club_list

urlpatterns = [
    path('clubs/', club_list, name='club_list'),
]