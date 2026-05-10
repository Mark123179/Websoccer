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
        'transfermarkt_id',
        'first_name',
        'last_name',
        'position',
        'primary_position',
        'date_of_birth',
        'nationalities',
        'age',
        'potential',
        'market_value',
        'salary_per_match',
        'contract_until',
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
        'transfermarkt_id',
        'date_of_birth',
        'market_value',
        'salary_per_match',
        'contract_until',
    )
    search_fields = (
        'first_name',
        'last_name',
        'fm_inside_id',
        'transfermarkt_id',
    )
    list_filter = (
        'club',
        'position',
    )


admin.site.register(Player, PlayerAdmin)
admin.site.register(PlayerStrengthProfile)
