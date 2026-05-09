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
        'first_name',
        'last_name',
        'position',
        'age',
        'potential',
        'market_value',
    )


class ClubAdmin(admin.ModelAdmin):
    inlines = [
        PlayerInline,
    ]


admin.site.register(League)
admin.site.register(Club, ClubAdmin)
admin.site.register(Player)
admin.site.register(PlayerStrengthProfile)