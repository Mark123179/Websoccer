from django.contrib import admin

from .models import ShowAuction, ShowAuctionBid, ShowAuctionPreset, ShowAuctionWatch


@admin.register(ShowAuctionPreset)
class ShowAuctionPresetAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'color_hex', 'is_active', 'sort_order')
    list_filter = ('is_active',)
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}


class ShowAuctionBidInline(admin.TabularInline):
    model = ShowAuctionBid
    extra = 0
    readonly_fields = ('club', 'manager', 'amount', 'is_active', 'is_leading',
                       'coin_charged', 'reservation_ref', 'created_at')
    can_delete = False


@admin.register(ShowAuction)
class ShowAuctionAdmin(admin.ModelAdmin):
    list_display = ('id', 'type_name', 'player', 'status', 'starts_at',
                    'ends_at', 'winner_club', 'winning_amount')
    list_filter = ('status', 'preset')
    search_fields = ('player__first_name', 'player__last_name', 'type_name')
    readonly_fields = ('config_snapshot', 'hidden_target', 'hidden_width',
                       'market_value_snapshot', 'player_prev_pool_status',
                       'settled_at', 'created_at', 'updated_at')
    inlines = [ShowAuctionBidInline]


@admin.register(ShowAuctionWatch)
class ShowAuctionWatchAdmin(admin.ModelAdmin):
    list_display = ('auction', 'club', 'source', 'created_at')
    list_filter = ('source',)
