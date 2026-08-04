from django.contrib import admin
from django.urls import path, re_path, include
from game.views_media import serve_media

urlpatterns = [
    path('admin/', admin.site.urls),
    re_path(r'^media/(?P<name>.+)$', serve_media, name='serve_media'),
    path('', include('game.urls')),
    path('', include('showauction.urls')),
]
