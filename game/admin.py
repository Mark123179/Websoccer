from django.contrib import admin
from .models import (
    League,
    Club,
    Player,
    PlayerStrengthProfile
)


class PlayerInline(admin.TabularInline):
    model = Player
    extra = 0

    fields = (
        'fm_inside_id',
        'first_name',
        'last_name',
        'position',
        'age',
        'potential',
        'market_value',
    )


class ClubAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'short_name',
        'league',
        'fm_inside_id',
        'budget',
    )
    search_fields = (
        'name',
        'short_name',
        'fm_inside_id',
    )

    inlines = [
        PlayerInline,
    ]


admin.site.register(League)
admin.site.register(Club, ClubAdmin)


class PlayerAdmin(admin.ModelAdmin):
    list_display = (
        'first_name',
        'last_name',
        'position',
        'club',
        'fm_inside_id',
        'market_value',
    )
    search_fields = (
        'first_name',
        'last_name',
        'fm_inside_id',
    )
    list_filter = (
        'club',
        'position',
    )


admin.site.register(Player, PlayerAdmin)
admin.site.register(PlayerStrengthProfile)
