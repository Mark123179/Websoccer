from django.urls import path
from .model_assets import model_asset
from .allianz_pilot import allianz_pilot, allianz_pilot_scene

from .views import (
    stadium_editor,
    stadium_editor_design,
    stadium_editor_visible_design,
    stadium_editor_geometry,
    stadium_editor_save_design,
    stadium_editor_grass_asset,
    stadium_live_mode,
    stadium_live_scene,
    dortmund_preview,
    dortmund_preview_scene,
    dortmund_original_miniature,
)


urlpatterns = [
    path('stadion/allianz/pilot/', allianz_pilot, name='allianz_pilot'),
    path('stadion/allianz/pilot/scene/', allianz_pilot_scene, name='allianz_pilot_scene'),
    path('stadion/model-assets/<int:fmi_id>/<str:version>/<str:name>',
         model_asset,
         name='stadium_model_asset'),
    path('management/stadion/editor/', stadium_editor, name='stadium_editor'),
    path('management/stadion/editor/rasen/<str:name>/', stadium_editor_grass_asset,
         name='stadium_editor_grass_asset'),
    path('management/stadion/editor/geometry/', stadium_editor_geometry, name='stadium_editor_geometry'),
    path('management/stadion/editor/design/', stadium_editor_design, name='stadium_editor_design'),
    path('management/stadion/editor/design/visible/', stadium_editor_visible_design, name='stadium_editor_visible_design'),
    path('management/stadion/editor/design/save/', stadium_editor_save_design, name='stadium_editor_save_design'),
    path('stadion/<int:club_id>/live-scene/', stadium_live_scene, name='stadium_live_scene'),
    path('stadion/<int:club_id>/live/', stadium_live_mode, name='stadium_live_mode'),
    path('stadion/dortmund/vorschau/', dortmund_preview, name='dortmund_preview'),
    path('stadion/dortmund/vorschau/scene/', dortmund_preview_scene, name='dortmund_preview_scene'),
    path('stadion/dortmund/original-miniatur/', dortmund_original_miniature, name='dortmund_original_miniature'),
]