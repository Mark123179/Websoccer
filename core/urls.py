from django.contrib import admin
from django.urls import path, re_path, include
from game.views_media import serve_media
from game.club_import.static_assets import serve as package_static

urlpatterns = [
    re_path(r'^static/(?P<name>.+)$', package_static),
    re_path(r'^assets/(?P<name>.+)$', package_static, {"asset": True}),
    path('creator/packages/', include('game.club_import.package_views')),
    path('admin/', admin.site.urls),
    re_path(r'^media/(?P<name>.+)$', serve_media, name='serve_media'),
    path('', include('game.urls')),
    path('', include('showauction.urls')),
    path('', include('stadium_editor.urls')),
]
