from django.urls import path

from .views import (
    stadium_editor,
    stadium_editor_design,
    stadium_editor_geometry,
    stadium_editor_save_design,
)


urlpatterns = [
    path('management/stadion/editor/', stadium_editor, name='stadium_editor'),
    path('management/stadion/editor/geometry/', stadium_editor_geometry, name='stadium_editor_geometry'),
    path('management/stadion/editor/design/', stadium_editor_design, name='stadium_editor_design'),
    path('management/stadion/editor/design/save/', stadium_editor_save_design, name='stadium_editor_save_design'),
]