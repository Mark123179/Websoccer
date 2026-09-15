from django.contrib import admin

from .models import StadiumDesign, StadiumGeometry


@admin.register(StadiumGeometry)
class StadiumGeometryAdmin(admin.ModelAdmin):
    list_display = ('stadium', 'schema_version', 'source', 'updated_at')
    search_fields = ('stadium__name', 'stadium__club__name')
    readonly_fields = ('updated_at',)
    fields = (
        'stadium', 'geometry', 'steckbrief', 'schema_version', 'source',
        'attribution', 'last_warning', 'updated_at',
    )


@admin.register(StadiumDesign)
class StadiumDesignAdmin(admin.ModelAdmin):
    list_display = ('stadium', 'blickrichtung', 'updated_at')
    search_fields = ('stadium__name', 'stadium__club__name')
    readonly_fields = ('updated_at',)