from django.contrib import admin
from .models import League, Club, Player


class PlayerInline(admin.TabularInline):
    model = Player
    extra = 0
    fields = (
        'first_name',
        'last_name',
        'position',
        'age',
        'strength',
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