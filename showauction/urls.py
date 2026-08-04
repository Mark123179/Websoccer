from django.urls import path

from . import views, views_creator

urlpatterns = [
    # Manager-Seiten (Bühne + Detail)
    path('transfers/auktionen/', views.stage, name='showauction_stage'),
    path('transfers/auktionen/<int:pk>/', views.detail, name='showauction_detail'),
    path('transfers/auktionen/<int:pk>/status.json', views.status_json, name='showauction_status'),
    path('transfers/auktionen/<int:pk>/bieten/', views.bid, name='showauction_bid'),
    path('transfers/auktionen/<int:pk>/zuschlag/', views.buy, name='showauction_buy'),
    path('transfers/auktionen/<int:pk>/beobachten/', views.watch, name='showauction_watch'),

    # Creator (TV-Redaktion)
    path('creator/auktionen/', views_creator.creator_auctions, name='showauction_creator'),
    path('creator/auktionen/neu/', views_creator.creator_auction_new, name='showauction_creator_new'),
    path('creator/auktionen/<int:pk>/', views_creator.creator_auction_edit, name='showauction_creator_edit'),
    path('creator/auktionen/<int:pk>/aktion/', views_creator.creator_auction_action, name='showauction_creator_action'),
    path('creator/auktionen/spielersuche.json', views_creator.creator_player_search, name='showauction_creator_player_search'),
    path('creator/auktionen/presets/', views_creator.creator_presets, name='showauction_creator_presets'),
    path('creator/auktionen/presets/<int:pk>/', views_creator.creator_preset_edit, name='showauction_creator_preset_edit'),
]
