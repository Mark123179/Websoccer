from django import forms
from django.contrib import admin
from django.contrib import messages
from django.contrib.admin.models import CHANGE, ADDITION, DELETION, LogEntry
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.core.exceptions import ValidationError
from django.templatetags.static import static
from django.utils import timezone
from django.utils.html import format_html, format_html_join
from django.utils.safestring import mark_safe
from datetime import timedelta
from decimal import Decimal
from .models import (
    COUNTRY_FLAG_ASSETS,
    DataSource,
    League,
    Club,
    Player,
    PlayerAwardTitle,
    PlayerDataReview,
    PlayerEditRequest,
    PlayerExternalId,
    PlayerFormSnapshot,
    PlayerInjuryRecord,
    PlayerMarketValueSnapshot,
    PlayerSeasonStat,
    PlayerSourceRating,
    PlayerSourceRatingSnapshot,
    PlayerStrengthProfile,
    PlayerStrengthSnapshot,
    PlayerSuspensionRecord,
    PlayerTransferHistory,
    PlayerWeightedRatingSnapshot,
    StrengthFormulaSettings,
    StrengthModifierRule,
    strength_decimal,
)


NATIONALITY_CHOICES = [
    ('', '---------'),
    *[
        (country, country)
        for country in sorted(COUNTRY_FLAG_ASSETS)
    ],
]


class PlayerNationalityForm(forms.ModelForm):
    club = forms.ModelChoiceField(
        queryset=Club.objects.none(),
        required=False,
        label='WS-Verein',
    )
    real_life_club = forms.ModelChoiceField(
        queryset=Club.objects.none(),
        required=False,
        label='RL-Verein',
    )
    nationality_1 = forms.ChoiceField(
        choices=NATIONALITY_CHOICES,
        required=False,
        label='Nationalitaet 1',
    )
    nationality_2 = forms.ChoiceField(
        choices=NATIONALITY_CHOICES,
        required=False,
        label='Nationalitaet 2',
    )

    class Meta:
        model = Player
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        club_queryset = Club.objects.order_by(
            models.Case(
                models.When(name='Karrierende', then=0),
                models.When(name='Default', then=1),
                default=2,
                output_field=models.IntegerField(),
            ),
            'name',
        )
        self.fields['club'].queryset = club_queryset
        self.fields['real_life_club'].queryset = club_queryset

        nationalities = []
        if self.instance and self.instance.nationalities:
            nationalities = [
                nationality.strip()
                for nationality in self.instance.nationalities.split(',')
                if nationality.strip()
            ][:2]

        if nationalities:
            self.fields['nationality_1'].initial = nationalities[0]

        if len(nationalities) > 1:
            self.fields['nationality_2'].initial = nationalities[1]

    def clean(self):
        cleaned_data = super().clean()
        nationality_1 = cleaned_data.get('nationality_1')
        nationality_2 = cleaned_data.get('nationality_2')

        if nationality_1 and nationality_1 == nationality_2:
            self.add_error(
                'nationality_2',
                'Die zweite Nationalitaet muss sich von der ersten unterscheiden.',
            )

        position_fields = (
            'main_position_1',
            'main_position_2',
            'main_position_3',
            'secondary_position_1',
            'secondary_position_2',
            'secondary_position_3',
        )
        positions = [
            cleaned_data.get(field_name)
            for field_name in position_fields
            if cleaned_data.get(field_name)
        ]
        if len(positions) != len(set(positions)):
            self.add_error(
                'secondary_position_1',
                'Eine Position darf pro Spieler nur einmal vergeben werden.',
            )

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        nationalities = [
            self.cleaned_data[nationality]
            for nationality in ('nationality_1', 'nationality_2')
            if self.cleaned_data.get(nationality)
        ]
        instance.nationalities = ', '.join(nationalities)
        instance.position = self.cleaned_data.get('main_position_1') or ''
        instance.primary_position = self.cleaned_data.get('secondary_position_1') or ''
        instance.source_positions = self.cleaned_data.get('secondary_position_1') or ''

        if commit:
            instance.save()
            self.save_m2m()

        return instance


class PlayerSourceRatingForm(forms.ModelForm):
    notes = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'size': '40'}),
    )

    class Meta:
        model = PlayerSourceRating
        fields = '__all__'


class SingleLineNotesInlineMixin:
    formfield_overrides = {
        models.TextField: {
            'widget': forms.TextInput(attrs={'size': '32'}),
        },
    }


class PlayerInline(admin.TabularInline):
    model = Player
    form = PlayerNationalityForm
    fk_name = 'club'
    extra = 0

    fields = (
        'fm_inside_id',
        'wsc_player_id',
        'transfermarkt_id',
        'first_name',
        'last_name',
        'real_life_club',
        'main_position_1',
        'main_position_2',
        'main_position_3',
        'secondary_position_1',
        'secondary_position_2',
        'secondary_position_3',
        'date_of_birth',
        'nationality_1',
        'nationality_2',
        'age',
        'market_value',
        'salary_per_match',
        'contract_until',
    )


class LeagueAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'country',
        'api_football_id',
        'strength_coefficient',
        'coefficient_source',
    )
    search_fields = (
        'name',
        'country',
    )


class ClubAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'short_name',
        'league',
        'api_football_id',
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


admin.site.register(League, LeagueAdmin)
admin.site.register(Club, ClubAdmin)


class PlayerSourceRatingInline(admin.TabularInline):
    model = PlayerSourceRating
    form = PlayerSourceRatingForm
    verbose_name = 'Source Rating'
    verbose_name_plural = 'Source'
    extra = 0

    fields = (
        'source',
        'rating',
        'potential',
        'source_version',
        'checked_at',
        'source_url',
        'notes',
    )


class PlayerExternalIdInline(SingleLineNotesInlineMixin, admin.TabularInline):
    model = PlayerExternalId
    verbose_name = 'Externe ID'
    verbose_name_plural = 'Externe IDs'
    extra = 0

    fields = (
        'source',
        'external_id',
        'profile_url',
        'is_primary',
        'notes',
    )


class PlayerSourceRatingSnapshotInline(SingleLineNotesInlineMixin, admin.TabularInline):
    model = PlayerSourceRatingSnapshot
    verbose_name = 'Source-Rating-Verlauf'
    verbose_name_plural = 'Source-Rating-Verlauf'
    extra = 0

    fields = (
        'source',
        'recorded_at',
        'rating',
        'potential',
        'source_url',
        'source_version',
        'update_current',
        'notes',
    )


class PlayerWeightedRatingSnapshotInline(SingleLineNotesInlineMixin, admin.TabularInline):
    model = PlayerWeightedRatingSnapshot
    verbose_name = 'Gewichteter Rating-Verlauf'
    verbose_name_plural = 'Gewichteter Rating-Verlauf'
    extra = 0

    fields = (
        'recorded_at',
        'source',
        'fixture_reference',
        'weighted_rating',
        'rating_minutes',
        'match_count',
        'window_label',
        'notes',
    )


class SourceBaseQualityFilter(admin.SimpleListFilter):
    title = 'Quellenstatus'
    parameter_name = 'source_base_quality'

    def lookups(self, request, model_admin):
        return (
            ('complete', 'EA + FM'),
            ('partial', 'nur eine Quelle'),
            ('default', 'Default 40.00'),
        )

    def queryset(self, request, queryset):
        queryset = queryset.annotate(
            ea_source_count=models.Count(
                'source_ratings',
                filter=models.Q(source_ratings__source=PlayerSourceRating.SOURCE_EA),
                distinct=True,
            ),
            fm_source_count=models.Count(
                'source_ratings',
                filter=models.Q(source_ratings__source=PlayerSourceRating.SOURCE_FM),
                distinct=True,
            ),
        )

        if self.value() == 'complete':
            return queryset.filter(ea_source_count__gt=0, fm_source_count__gt=0)

        if self.value() == 'partial':
            return queryset.filter(
                models.Q(ea_source_count__gt=0, fm_source_count=0)
                | models.Q(ea_source_count=0, fm_source_count__gt=0)
            )

        if self.value() == 'default':
            return queryset.filter(ea_source_count=0, fm_source_count=0)

        return queryset


class PlayerDataQualityFilter(admin.SimpleListFilter):
    title = 'Datenqualitaet'
    parameter_name = 'data_quality'

    def lookups(self, request, model_admin):
        return (
            ('complete_sources', 'Vollstaendig EA + FM'),
            ('fmi_only', 'Nur FMI / ohne SoFIFA'),
            ('default_strength', 'Default-Staerke'),
            ('missing_api_id', 'Ohne API-ID'),
            ('missing_image', 'Ohne Spielerbild'),
            ('default_image', 'Mit Defaultbild'),
            ('missing_tm_id', 'Ohne Transfermarkt-ID'),
            ('missing_tm_profile', 'Ohne TM-Profil-Link'),
            ('missing_market_value', 'Ohne Marktwert'),
            ('missing_salary', 'Ohne Gehalt'),
        )

    def queryset(self, request, queryset):
        value = self.value()
        if not value:
            return queryset

        queryset = queryset.annotate(
            ea_source_count=models.Count(
                'source_ratings',
                filter=models.Q(source_ratings__source=PlayerSourceRating.SOURCE_EA),
                distinct=True,
            ),
            fm_source_count=models.Count(
                'source_ratings',
                filter=models.Q(source_ratings__source=PlayerSourceRating.SOURCE_FM),
                distinct=True,
            ),
        )

        if value == 'complete_sources':
            return queryset.filter(ea_source_count__gt=0, fm_source_count__gt=0)

        if value == 'fmi_only':
            return queryset.filter(ea_source_count=0, fm_source_count__gt=0)

        if value == 'default_strength':
            return queryset.filter(ea_source_count=0, fm_source_count=0)

        if value == 'missing_api_id':
            return queryset.filter(api_football_id__isnull=True)

        if value == 'missing_tm_id':
            return queryset.filter(transfermarkt_id__isnull=True)

        if value == 'missing_tm_profile':
            return queryset.filter(transfermarkt_profile_url='')

        if value == 'missing_market_value':
            return queryset.filter(
                models.Q(market_value__isnull=True) |
                models.Q(market_value__lte=0)
            )

        if value == 'missing_salary':
            return queryset.filter(
                models.Q(salary_per_match__isnull=True) |
                models.Q(salary_per_match__lte=0)
            )

        if value in {'missing_image', 'default_image'}:
            matching_ids = [
                player.pk
                for player in queryset
                if player.portrait_static_path == 'game/images/default_player.svg'
            ]
            return queryset.filter(pk__in=matching_ids)

        return queryset


DEFAULT_MINUTE_MODIFIER_RULES = [
    (Decimal('90.00'), Decimal('100.00'), Decimal('4.00'), '90-100 %', ''),
    (Decimal('75.00'), Decimal('89.99'), Decimal('2.50'), '75-89 %', ''),
    (Decimal('60.00'), Decimal('74.99'), Decimal('1.00'), '60-74 %', ''),
    (Decimal('40.00'), Decimal('59.99'), Decimal('-1.00'), '40-59 %', ''),
    (Decimal('20.00'), Decimal('39.99'), Decimal('-3.00'), '20-39 %', ''),
    (Decimal('5.00'), Decimal('19.99'), Decimal('-6.00'), '5-19 %', ''),
    (Decimal('0.00'), Decimal('4.99'), Decimal('-8.00'), '0-4 %', ''),
]

DEFAULT_FRESHNESS_MODIFIER_RULES = [
    (Decimal('90.00'), Decimal('100.00'), Decimal('0.00'), '90-100', 'kein Risiko'),
    (Decimal('85.00'), Decimal('89.99'), Decimal('-0.50'), '85-89', 'kein Risiko'),
    (Decimal('80.00'), Decimal('84.99'), Decimal('-1.00'), '80-84', 'kein Risiko'),
    (Decimal('75.00'), Decimal('79.99'), Decimal('-1.50'), '75-79', 'leichtes Risiko'),
    (Decimal('70.00'), Decimal('74.99'), Decimal('-2.00'), '70-74', 'erhoehtes Risiko'),
    (Decimal('65.00'), Decimal('69.99'), Decimal('-3.00'), '65-69', 'spuerbares Risiko'),
    (Decimal('60.00'), Decimal('64.99'), Decimal('-4.00'), '60-64', 'hohes Risiko'),
    (Decimal('0.00'), Decimal('59.99'), Decimal('-6.00'), 'unter 60', 'deutliches Risiko'),
]


class StrengthModifierRuleInline(admin.TabularInline):
    model = StrengthModifierRule
    extra = 0
    fields = (
        'category',
        'label',
        'min_value',
        'max_value',
        'modifier',
        'risk_label',
        'sort_order',
        'is_active',
    )


class StrengthFormulaSettingsAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'is_active',
        'rating_modifier_factor',
        'default_league_median_rating',
        'default_freshness',
        'updated_at',
    )
    list_filter = ('is_active',)
    fieldsets = (
        (
            'Grundwerte',
            {
                'fields': (
                    'name',
                    'is_active',
                    'rating_modifier_factor',
                    'default_league_median_rating',
                    'default_freshness',
                ),
            },
        ),
        (
            'Notizen',
            {
                'fields': (
                    'notes',
                ),
            },
        ),
    )
    inlines = [StrengthModifierRuleInline]


class PlayerAdmin(admin.ModelAdmin):
    form = PlayerNationalityForm
    change_form_template = 'admin/game/player/change_form.html'
    change_list_template = 'admin/game/player/change_list.html'
    list_display = (
        'portrait_thumbnail',
        'first_name',
        'last_name',
        'club',
        'real_life_club',
        'main_position_1',
        'wsc_player_id',
        'api_football_id',
        'source_strength_badge',
        'source_data_quality_badge',
        'final_strength',
        'fm_inside_id',
        'transfermarkt_id',
        'date_of_birth',
        'height_cm',
        'strong_foot',
        'market_value',
        'salary_per_match',
        'contract_until',
    )
    search_fields = (
        'first_name',
        'last_name',
        'wsc_player_id',
        'fm_inside_id',
        'transfermarkt_id',
    )
    list_filter = (
        PlayerDataQualityFilter,
        'club',
        'real_life_club',
        'main_position_1',
    )
    readonly_fields = (
        'portrait_preview',
        'source_strength_summary',
        'strength_breakdown_preview',
        'strength_chart_preview',
        'market_value_chart_preview',
        'weighted_rating_chart_preview',
        'season_career_admin_preview',
        'transfer_history_admin_preview',
        'history_admin_preview',
    )
    fieldsets = (
        (
            'Spielerprofil',
            {
                'fields': (
                    (
                        'portrait_preview',
                    ),
                    'first_name',
                    'last_name',
                    (
                        'club',
                        'real_life_club',
                    ),
                    (
                        'main_position_1',
                        'main_position_2',
                        'main_position_3',
                    ),
                    (
                        'secondary_position_1',
                        'secondary_position_2',
                        'secondary_position_3',
                    ),
                    (
                        'date_of_birth',
                        'age',
                    ),
                    (
                        'height_cm',
                        'strong_foot',
                    ),
                    (
                        'nationality_1',
                        'nationality_2',
                    ),
                    (
                        'market_value',
                        'salary_per_match',
                        'contract_until',
                    ),
                    (
                        'ws_injury_type',
                        'ws_injury_days_remaining',
                    ),
                    (
                        'ws_suspension_reason',
                        'ws_suspension_matches_remaining',
                    ),
                ),
            },
        ),
        (
            'Staerke',
            {
                'fields': (
                    'source_strength_summary',
                    'strength_breakdown_preview',
                    'strength_chart_preview',
                ),
            },
        ),
        (
            'Source',
            {
                'fields': (
                    'fm_inside_id',
                    'wsc_player_id',
                    'api_football_id',
                    'transfermarkt_id',
                    'transfermarkt_profile_url',
                    'transfermarkt_market_value_url',
                    'market_value_chart_preview',
                ),
            },
        ),
        (
            'Saison',
            {
                'fields': (
                    'season_career_admin_preview',
                    'weighted_rating_chart_preview',
                ),
            },
        ),
        (
            'Transferhistorie WS',
            {
                'fields': (
                    'transfer_history_admin_preview',
                ),
            },
        ),
        (
            'Geschichte',
            {
                'fields': (
                    'history_admin_preview',
                ),
            },
        ),
    )
    inlines = [
        PlayerExternalIdInline,
        PlayerSourceRatingInline,
    ]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'club',
            'club__league',
            'real_life_club',
            'real_life_club__league',
            'strength_profile',
        ).prefetch_related('source_ratings', 'form_snapshots')

    def changelist_view(self, request, extra_context=None):
        stats = Player.objects.aggregate(
            player_count=models.Count('id'),
            average_strength=models.Avg('strength_profile__final_strength'),
            average_market_value=models.Avg('market_value'),
            average_salary=models.Avg('salary_per_match'),
        )
        extra_context = {
            **(extra_context or {}),
            'player_admin_stats': {
                'player_count': stats['player_count'] or 0,
                'average_strength': self._format_decimal(
                    stats['average_strength'],
                    decimals=2,
                ),
                'average_market_value': self._format_currency(
                    stats['average_market_value'],
                ),
                'average_salary': self._format_currency(
                    stats['average_salary'],
                ),
            },
        }
        return super().changelist_view(request, extra_context=extra_context)

    def _format_decimal(self, value, decimals=2):
        if value is None:
            return '-'

        return f'{value:.{decimals}f}'.replace('.', ',')

    def _format_currency(self, value):
        if value is None:
            return '-'

        return f'{value:,.0f} EUR'.replace(',', '.')

    @admin.display(description='Bild')
    def portrait_thumbnail(self, obj):
        return self._portrait_image(obj, size=38)

    @admin.display(description='Spielerbild Vorschau')
    def portrait_preview(self, obj):
        if not obj or not obj.pk:
            return format_html(
                '<span class="ws-admin-muted">Nach dem Speichern wird hier das Spielerbild angezeigt.</span>'
            )

        return format_html(
            '<div class="ws-admin-portrait-preview">{}<div><strong>{}</strong><br>'
            '<span>Datei: {}</span><br><span>{}</span></div></div>',
            self._portrait_image(obj, size=96),
            obj.full_name,
            obj.portrait_static_path.rsplit('/', 1)[-1],
            obj.portrait_static_path,
        )

    def _portrait_image(self, obj, size):
        return format_html(
            '<img src="{}" alt="{}" style="width:{}px;height:{}px;'
            'object-fit:contain;object-position:center bottom;'
            'background:#f5f7fa;border:1px solid #b7c3ca;" />',
            static(obj.portrait_static_path),
            obj.full_name,
            size,
            size,
        )

    @admin.display(description='Staerke', ordering='strength_profile__final_strength')
    def final_strength(self, obj):
        if hasattr(obj, 'strength_profile'):
            return f'{obj.strength_profile.final_strength:.2f}'

        return '-'

    @admin.display(description='Quellen-Staerke')
    def source_strength_badge(self, obj):
        base_strength = obj.calculated_base_strength

        if obj.uses_default_base_strength:
            return format_html(
                '<span style="color:#ff7676;" title="{}">Default 40.00 <span style="cursor:help;">&#9432;</span></span>',
                obj.source_strength_explanation,
            )

        if obj.source_base_quality == 'partial':
            return format_html(
                '<span style="color:#ffd86b;" title="{}">Staerke {} <span style="cursor:help;">&#9432;</span></span>',
                obj.source_strength_explanation,
                f'{base_strength:.2f}',
            )

        return format_html(
            '<span title="{}">Staerke {} <span style="cursor:help;">&#9432;</span></span>',
            obj.source_strength_explanation,
            f'{base_strength:.2f}',
        )

    @admin.display(description='Datenstatus')
    def source_data_quality_badge(self, obj):
        colors = {
            'complete': '#72f2a5',
            'partial': '#ffd86b',
            'default': '#ff7676',
        }
        return format_html(
            '<span style="color:{};font-weight:700;">{}</span>',
            colors[obj.source_base_quality],
            obj.source_base_quality_label,
        )

    @admin.display(description='Berechnete Quellen-Staerke')
    def source_strength_summary(self, obj):
        base_strength = obj.calculated_base_strength
        potential_strength = obj.calculated_potential_strength

        if base_strength is None:
            label = 'Staerke unvollstaendig'
        else:
            label = f'Staerke {base_strength:.2f}'

        if potential_strength is not None:
            label = f'{label} / Potential {potential_strength:.2f}'

        return format_html(
            '<span title="{}">{} <span style="cursor:help;">&#9432;</span></span>',
            obj.source_strength_explanation,
            label,
        )

    def _active_strength_settings(self):
        settings = StrengthFormulaSettings.active()
        if settings:
            return settings

        return StrengthFormulaSettings(
            name='Standard (Fallback)',
            rating_modifier_factor=Decimal('5.00'),
            default_league_median_rating=Decimal('6.80'),
            default_freshness=Decimal('100.00'),
        )

    def _modifier_rules(self, settings, category):
        if settings and settings.pk:
            rules = list(
                settings.modifier_rules.filter(
                    category=category,
                    is_active=True,
                ).order_by('-min_value')
            )
            if rules:
                return rules

        fallback_rules = (
            DEFAULT_MINUTE_MODIFIER_RULES
            if category == StrengthModifierRule.CATEGORY_MINUTES
            else DEFAULT_FRESHNESS_MODIFIER_RULES
        )
        return [
            {
                'min_value': min_value,
                'max_value': max_value,
                'modifier': modifier,
                'label': label,
                'risk_label': risk_label,
            }
            for min_value, max_value, modifier, label, risk_label in fallback_rules
        ]

    def _matching_modifier_rule(self, settings, category, value):
        value = strength_decimal(value)

        for rule in self._modifier_rules(settings, category):
            min_value = rule.min_value if hasattr(rule, 'min_value') else rule['min_value']
            max_value = rule.max_value if hasattr(rule, 'max_value') else rule['max_value']
            if min_value <= value <= max_value:
                return {
                    'label': rule.label if hasattr(rule, 'label') else rule['label'],
                    'modifier': (
                        rule.modifier if hasattr(rule, 'modifier') else rule['modifier']
                    ),
                    'risk_label': (
                        rule.risk_label
                        if hasattr(rule, 'risk_label')
                        else rule['risk_label']
                    ),
                }

        return {
            'label': 'keine Regel',
            'modifier': Decimal('0.00'),
            'risk_label': '',
        }

    def _preferred_form_snapshots(self, obj):
        cutoff = timezone.localdate() - timedelta(days=90)
        snapshots = [
            snapshot
            for snapshot in obj.form_snapshots.all()
            if snapshot.fixture_date >= cutoff
        ]

        sportdb_snapshots = [
            snapshot
            for snapshot in snapshots
            if snapshot.source == PlayerFormSnapshot.SOURCE_SPORTDB_FLASHSCORE
        ]
        if sportdb_snapshots:
            return sorted(sportdb_snapshots, key=lambda snapshot: snapshot.fixture_date)

        api_snapshots = [
            snapshot
            for snapshot in snapshots
            if snapshot.source == PlayerFormSnapshot.SOURCE_API_FOOTBALL
        ]
        if api_snapshots:
            return sorted(api_snapshots, key=lambda snapshot: snapshot.fixture_date)

        return sorted(snapshots, key=lambda snapshot: snapshot.fixture_date)

    def _league_coefficient(self, obj):
        club = obj.real_life_club or obj.club
        if club and club.league_id:
            return club.league.strength_coefficient

        return Decimal('1.00')

    def _freshness_value(self, obj, settings):
        if hasattr(obj, 'strength_profile'):
            return obj.strength_profile.freshness

        return settings.default_freshness

    def _modifier_class(self, value):
        if value > 0:
            return 'ws-strength-positive'
        if value < 0:
            return 'ws-strength-negative'

        return 'ws-strength-neutral'

    def _fmt_decimal(self, value):
        if value is None:
            return '-'

        return f'{value:.2f}'

    def _source_for_median(self, snapshots):
        if snapshots:
            return snapshots[0].source

        return PlayerFormSnapshot.SOURCE_SPORTDB_FLASHSCORE

    def _dynamic_league_median_rating(self, obj, snapshots, settings):
        source = self._source_for_median(snapshots)
        cutoff = timezone.localdate() - timedelta(days=90)
        snapshot_queryset = PlayerFormSnapshot.objects.filter(
            source=source,
            fixture_date__gte=cutoff,
            rating__isnull=False,
            minutes_played__gt=0,
        )
        club = obj.real_life_club or obj.club
        if club and club.league_id:
            snapshot_queryset = snapshot_queryset.filter(
                player__real_life_club__league=club.league
            ) | snapshot_queryset.filter(
                player__real_life_club__isnull=True,
                player__club__league=club.league,
            )

        player_ratings = []
        grouped_snapshots = {}
        for snapshot in snapshot_queryset.select_related('player'):
            grouped_snapshots.setdefault(snapshot.player_id, []).append(snapshot)

        for player_snapshots in grouped_snapshots.values():
            rating_minutes = sum(snapshot.minutes_played for snapshot in player_snapshots)
            if not rating_minutes:
                continue

            player_ratings.append(
                strength_decimal(
                    sum(
                        snapshot.rating * snapshot.minutes_played
                        for snapshot in player_snapshots
                    ) / Decimal(rating_minutes)
                )
            )

        if not player_ratings:
            return settings.default_league_median_rating, 'Fallback'

        player_ratings = sorted(player_ratings)
        middle = len(player_ratings) // 2
        if len(player_ratings) % 2:
            return player_ratings[middle], f'{len(player_ratings)} Spieler'

        return strength_decimal(
            (player_ratings[middle - 1] + player_ratings[middle]) / Decimal('2')
        ), f'{len(player_ratings)} Spieler'

    @admin.display(description='Spielstaerke-Berechnung')
    def strength_breakdown_preview(self, obj):
        if not obj or not getattr(obj, 'pk', None):
            return '-'

        settings = self._active_strength_settings()
        base_strength = obj.calculated_base_strength
        potential_strength = obj.calculated_potential_strength
        snapshots = self._preferred_form_snapshots(obj)
        possible_minutes = sum(snapshot.possible_minutes for snapshot in snapshots)
        played_minutes = sum(snapshot.minutes_played for snapshot in snapshots)

        if possible_minutes:
            minutes_quote = strength_decimal(
                Decimal(played_minutes) /
                Decimal(possible_minutes) *
                Decimal('100')
            )
        else:
            minutes_quote = Decimal('0.00')

        minute_rule = self._matching_modifier_rule(
            settings,
            StrengthModifierRule.CATEGORY_MINUTES,
            minutes_quote,
        )
        minute_modifier = minute_rule['modifier']
        weighted_rating = None
        rating_minutes = sum(
            snapshot.minutes_played
            for snapshot in snapshots
            if snapshot.rating is not None and snapshot.minutes_played
        )
        if rating_minutes:
            weighted_rating = strength_decimal(
                sum(
                    snapshot.rating * snapshot.minutes_played
                    for snapshot in snapshots
                    if snapshot.rating is not None and snapshot.minutes_played
                ) / Decimal(rating_minutes)
            )

        median_rating, median_source = self._dynamic_league_median_rating(
            obj,
            snapshots,
            settings,
        )
        if weighted_rating is not None:
            rating_modifier = strength_decimal(
                (
                    weighted_rating -
                    median_rating
                ) * settings.rating_modifier_factor
            )
        else:
            rating_modifier = Decimal('0.00')

        league_coefficient = self._league_coefficient(obj)
        rl_form_modifier = strength_decimal(
            (minute_modifier + rating_modifier) * league_coefficient
        )
        freshness = self._freshness_value(obj, settings)
        freshness_rule = self._matching_modifier_rule(
            settings,
            StrengthModifierRule.CATEGORY_FRESHNESS,
            freshness,
        )
        freshness_modifier = freshness_rule['modifier']
        gap = (
            potential_strength - base_strength
            if base_strength is not None and potential_strength is not None
            else None
        )
        base_form_strength = (
            strength_decimal(base_strength + rl_form_modifier + freshness_modifier)
            if base_strength is not None
            else None
        )
        max_preview = (
            strength_decimal(potential_strength + rl_form_modifier + freshness_modifier)
            if potential_strength is not None
            else None
        )

        rows = [
            (
                'Potential-Luecke',
                self._fmt_decimal(gap),
                'Potential-Ceiling minus Source-Base.',
                '',
            ),
            (
                'Minutenquote',
                f'{played_minutes}/{possible_minutes} Min. = {minutes_quote:.2f} %',
                f'Regel {minute_rule["label"]}: {minute_modifier:+.2f} Staerkepunkte.',
                self._modifier_class(minute_modifier),
            ),
            (
                'Gewichtetes Rating',
                self._fmt_decimal(weighted_rating),
                (
                    f'Minutengewichtetes Spielerrating. Median {median_rating:.2f} '
                    f'({median_source}), Faktor {settings.rating_modifier_factor:.2f}.'
                ),
                '',
            ),
            (
                'Ratingmodifier',
                f'{rating_modifier:+.2f}',
                'Gewichtetes Rating minus dynamischer Liga-Median, danach Faktor.',
                self._modifier_class(rating_modifier),
            ),
            (
                'Liga-Koeffizient',
                self._fmt_decimal(league_coefficient),
                'Wirkt nur auf RL-Form, nicht auf Source-Base.',
                '',
            ),
            (
                'RL-Formmodifier',
                f'{rl_form_modifier:+.2f}',
                '(Minutenmodifier + Ratingmodifier) * Liga-Koeffizient.',
                self._modifier_class(rl_form_modifier),
            ),
            (
                'Frische',
                f'{freshness:.2f}',
                f'{freshness_rule["risk_label"] or freshness_rule["label"]}; Abzug {freshness_modifier:+.2f}.',
                self._modifier_class(freshness_modifier),
            ),
        ]
        rows_html = format_html_join(
            '',
            (
                '<div class="ws-strength-line">'
                '<span class="ws-strength-label">{} '
                '<span class="ws-info" title="{}">&#9432;</span></span>'
                '<strong class="{}">{}</strong>'
                '</div>'
            ),
            (
                (
                    label,
                    note,
                    css_class,
                    value,
                )
                for label, value, note, css_class in rows
            ),
        )

        if gap is not None and gap > 0:
            peak_rows = []
            for label, percentage in [
                ('normaler Beispiel-Peak', Decimal('0.20')),
                ('guter Beispiel-Peak', Decimal('0.50')),
                ('sehr starker Beispiel-Peak', Decimal('0.85')),
                ('Ausnahmeabend', Decimal('1.00')),
            ]:
                peak_strength = strength_decimal(
                    base_strength +
                    (gap * percentage) +
                    rl_form_modifier +
                    freshness_modifier
                )
                peak_rows.append(
                    (
                        label,
                        f'{percentage * 100:.0f} %',
                        f'{peak_strength:.2f}',
                    )
                )
            peak_rows_html = format_html_join(
                '',
                '<tr><td>{}</td><td>{}</td><td><strong>{}</strong></td></tr>',
                peak_rows,
            )
        else:
            peak_rows_html = format_html(
                '<tr><td colspan="3" class="ws-admin-muted">{}</td></tr>',
                'Kein Potential-Peak berechenbar.',
            )

        source_label = snapshots[0].get_source_display() if snapshots else 'keine Form-Snapshots'
        return format_html(
            (
                '<div class="ws-strength-panel">'
                '<div class="ws-strength-summary">'
                '<div class="ws-strength-card ws-strength-card-main">'
                '<span>Endstaerke ohne Peak</span><strong>{}</strong>'
                '<span class="ws-info" title="Source-Base + RL-Formmodifier + Frischeabzug.">&#9432;</span>'
                '</div>'
                '<div class="ws-strength-card ws-strength-card-max">'
                '<span>Endstaerke Max</span><strong>{}</strong>'
                '<span class="ws-info" title="Potential-Ceiling + RL-Formmodifier + Frischeabzug. Ausnahme-Obergrenze, kein Normalwert.">&#9432;</span>'
                '</div>'
                '</div>'
                '<p class="help">Quelle Formdaten: <strong>{}</strong>, letzte 90 Tage. '
                'Match-Peak ist eine Vorschau.</p>'
                '<div class="ws-strength-lines">{}</div>'
                '<h3>Beispiel-Peaks <span class="ws-info" title="Fliessende Beispielwerte aus der Potential-Luecke, kein gespeicherter Zufallswert.">&#9432;</span></h3>'
                '<table class="ws-admin-preview-table ws-strength-table">'
                '<thead><tr><th>Szenario</th><th>Anteil der Luecke</th><th>Endstaerke</th></tr></thead>'
                '<tbody>{}</tbody></table>'
                '</div>'
            ),
            self._fmt_decimal(base_form_strength),
            self._fmt_decimal(max_preview),
            source_label,
            rows_html,
            peak_rows_html,
        )

    @admin.display(description='Aktuelles Staerkeprofil')
    def strength_profile_summary(self, obj):
        if not obj or not getattr(obj, 'pk', None):
            return '-'

        if not hasattr(obj, 'strength_profile'):
            return mark_safe(
                '<span class="ws-admin-muted">Noch kein PlayerStrengthProfile hinterlegt.</span>'
            )

        profile = obj.strength_profile
        return format_html(
            (
                '<table class="ws-admin-preview-table">'
                '<thead><tr><th>Base</th><th>Form</th><th>Frische</th><th>Final</th></tr></thead>'
                '<tbody><tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr></tbody>'
                '</table>'
            ),
            f'{profile.base_strength:.2f}',
            f'{profile.form_modifier:.2f}',
            f'{profile.freshness:.2f}',
            f'{profile.final_strength:.2f}',
        )

    @admin.display(description='Gewichteter Rating-Verlauf')
    def weighted_rating_chart_preview(self, obj):
        if not obj or not getattr(obj, 'pk', None):
            return '-'

        points = list(
            obj.weighted_rating_snapshots.order_by(
                '-recorded_at',
                '-id',
            )[:10]
        )[::-1]

        if not points:
            return mark_safe(
                '<span class="ws-admin-muted">Noch keine gewichteten Spielratings vorhanden.</span>'
            )

        values = [Decimal(point.weighted_rating) for point in points]
        min_value = min(values)
        max_value = max(values)
        span = max_value - min_value
        width = Decimal('320')
        height = Decimal('118')
        left_padding = Decimal('38')
        right_padding = Decimal('12')
        top_padding = Decimal('18')
        bottom_padding = Decimal('30')
        usable_width = width - left_padding - right_padding
        usable_height = height - top_padding - bottom_padding
        denominator = max(len(values) - 1, 1)
        coordinates = []

        for index, value in enumerate(values):
            x = left_padding + (
                usable_width * Decimal(index) / Decimal(denominator)
            )
            if span:
                y = top_padding + (
                    (max_value - value) / span * usable_height
                )
            else:
                y = top_padding + (usable_height / Decimal('2'))
            coordinates.append((x, y))

        polyline = ' '.join(
            f'{x:.2f},{y:.2f}'
            for x, y in coordinates
        )
        point_markup = ''.join(
            [
                (
                    f'<circle cx="{x:.2f}" cy="{y:.2f}" r="2.8" '
                    'fill="#28d7e8"></circle>'
                    f'<text x="{x:.2f}" y="{max(float(y) - 7, 10):.2f}" '
                    'text-anchor="middle" fill="#e9fbff" font-size="8" '
                    'font-weight="700">'
                    f'{values[index]:.1f}</text>'
                )
                for index, (x, y) in enumerate(coordinates)
            ]
        )
        x_ticks = ''.join(
            (
                f'<text x="{x:.2f}" y="103" text-anchor="middle" '
                'fill="#86aab6" font-size="8">'
                f'{index + 1}</text>'
            )
            for index, (x, _y) in enumerate(coordinates)
        )
        y_ticks = ''.join(
            [
                (
                    f'<text x="32" y="{top_padding + 3:.2f}" text-anchor="end" '
                    'fill="#86aab6" font-size="8">'
                    f'{max_value:.1f}</text>'
                ),
                (
                    f'<text x="32" y="{height - bottom_padding + 3:.2f}" text-anchor="end" '
                    'fill="#86aab6" font-size="8">'
                    f'{min_value:.1f}</text>'
                ),
            ]
        )
        latest = values[-1]

        return format_html(
            (
                '<div class="ws-rating-chart">'
                '<svg viewBox="0 0 320 118" role="img" aria-label="Gewichteter Rating-Verlauf">'
                '<rect width="320" height="118" rx="8" fill="#071b24"></rect>'
                '<g opacity="0.22">{}</g>'
                '<line x1="38" y1="18" x2="38" y2="88" stroke="#86aab6" stroke-width="1"></line>'
                '<line x1="38" y1="88" x2="308" y2="88" stroke="#86aab6" stroke-width="1"></line>'
                '<text x="8" y="55" transform="rotate(-90 8 55)" fill="#c8e3eb" font-size="9" font-weight="800">Rating</text>'
                '<text x="173" y="115" text-anchor="middle" fill="#c8e3eb" font-size="9" font-weight="800">Spiele</text>'
                '{}'
                '{}'
                '<polyline points="{}" fill="none" stroke="#28d7e8" stroke-width="2.4" '
                'stroke-linecap="round" stroke-linejoin="round"></polyline>'
                '{}'
                '</svg>'
                '<strong>{}</strong>'
                '<span>letzte {} gewichtete Ratings</span>'
                '</div>'
            ),
            mark_safe(
                ''.join(
                    f'<line x1="{x}" y1="18" x2="{x}" y2="88" stroke="#ffffff"></line>'
                    for x in range(62, 308, 27)
                )
                + ''.join(
                    f'<line x1="38" y1="{y}" x2="308" y2="{y}" stroke="#ffffff"></line>'
                    for y in range(28, 88, 20)
                )
            ),
            mark_safe(y_ticks),
            mark_safe(x_ticks),
            polyline,
            mark_safe(point_markup),
            f'{latest:.2f}',
            len(values),
        )

    def _line_chart_coordinates(self, series, width, height, left_padding, top_padding, usable_width, usable_height, min_value, max_value):
        span = max_value - min_value
        denominator = max(len(series) - 1, 1)
        coordinates = []

        for index, value in enumerate(series):
            x = left_padding + (
                usable_width * Decimal(index) / Decimal(denominator)
            )
            if span:
                y = top_padding + (
                    (max_value - value) / span * usable_height
                )
            else:
                y = height / Decimal('2')
            coordinates.append((x, y))

        return coordinates

    def _format_eur_short(self, value):
        value = Decimal(value)
        million = Decimal('1000000')
        if abs(value) >= million:
            return f'{value / million:.1f} Mio'

        return f'{value:.0f}'

    @admin.display(description='Marktwert-Verlauf')
    def market_value_chart_preview(self, obj):
        if not obj or not getattr(obj, 'pk', None):
            return '-'

        points = list(
            obj.market_value_snapshots.order_by(
                '-recorded_at',
                '-id',
            )[:10]
        )[::-1]

        if not points:
            return mark_safe(
                '<span class="ws-admin-muted">Noch keine Marktwert-Snapshots vorhanden.</span>'
            )

        values = [Decimal(point.value_eur) for point in points]
        min_value = min(values)
        max_value = max(values)
        width = Decimal('340')
        height = Decimal('124')
        left_padding = Decimal('48')
        right_padding = Decimal('14')
        top_padding = Decimal('18')
        bottom_padding = Decimal('32')
        usable_width = width - left_padding - right_padding
        usable_height = height - top_padding - bottom_padding
        coordinates = self._line_chart_coordinates(
            values,
            width,
            height,
            left_padding,
            top_padding,
            usable_width,
            usable_height,
            min_value,
            max_value,
        )
        polyline = ' '.join(
            f'{x:.2f},{y:.2f}'
            for x, y in coordinates
        )
        point_markup = ''.join(
            [
                (
                    f'<circle cx="{x:.2f}" cy="{y:.2f}" r="2.8" '
                    'fill="#28d7e8"></circle>'
                    f'<text x="{x:.2f}" y="{max(float(y) - 7, 10):.2f}" '
                    'text-anchor="middle" fill="#e9fbff" font-size="8" '
                    'font-weight="700">'
                    f'{self._format_eur_short(values[index])}</text>'
                )
                for index, (x, y) in enumerate(coordinates)
            ]
        )
        x_ticks = ''.join(
            (
                f'<text x="{x:.2f}" y="108" text-anchor="middle" '
                'fill="#86aab6" font-size="8">'
                f'{index + 1}</text>'
            )
            for index, (x, _y) in enumerate(coordinates)
        )
        y_ticks = ''.join(
            [
                (
                    f'<text x="42" y="{top_padding + 3:.2f}" text-anchor="end" '
                    'fill="#86aab6" font-size="8">'
                    f'{self._format_eur_short(max_value)}</text>'
                ),
                (
                    f'<text x="42" y="{height - bottom_padding + 3:.2f}" '
                    'text-anchor="end" fill="#86aab6" font-size="8">'
                    f'{self._format_eur_short(min_value)}</text>'
                ),
            ]
        )
        latest = values[-1]

        return format_html(
            (
                '<div class="ws-market-chart">'
                '<svg viewBox="0 0 340 124" role="img" aria-label="Marktwert-Verlauf">'
                '<rect width="340" height="124" rx="8" fill="#071b24"></rect>'
                '<g opacity="0.20">{}</g>'
                '<line x1="48" y1="18" x2="48" y2="92" stroke="#86aab6" stroke-width="1"></line>'
                '<line x1="48" y1="92" x2="326" y2="92" stroke="#86aab6" stroke-width="1"></line>'
                '<text x="9" y="60" transform="rotate(-90 9 60)" fill="#c8e3eb" font-size="9" font-weight="800">Marktwert</text>'
                '<text x="187" y="121" text-anchor="middle" fill="#c8e3eb" font-size="9" font-weight="800">Updates</text>'
                '{}'
                '{}'
                '<polyline points="{}" fill="none" stroke="#28d7e8" stroke-width="2.4" '
                'stroke-linecap="round" stroke-linejoin="round"></polyline>'
                '{}'
                '</svg>'
                '<strong>{} EUR</strong>'
                '<span>letzte {} Marktwert-Updates</span>'
                '</div>'
            ),
            mark_safe(
                ''.join(
                    f'<line x1="{x}" y1="18" x2="{x}" y2="92" stroke="#ffffff"></line>'
                    for x in range(76, 326, 31)
                )
                + ''.join(
                    f'<line x1="48" y1="{y}" x2="326" y2="{y}" stroke="#ffffff"></line>'
                    for y in range(30, 92, 20)
                )
            ),
            mark_safe(y_ticks),
            mark_safe(x_ticks),
            polyline,
            mark_safe(point_markup),
            self._format_eur_short(latest),
            len(values),
        )

    @admin.display(description='Staerke-Verlauf')
    def strength_chart_preview(self, obj):
        if not obj or not getattr(obj, 'pk', None):
            return '-'

        points = list(
            obj.strength_snapshots.order_by(
                '-recorded_at',
                '-id',
            )[:10]
        )[::-1]

        if not points:
            return mark_safe(
                '<span class="ws-admin-muted">Noch keine Staerke-Snapshots vorhanden.</span>'
            )

        base_values = [Decimal(point.base_strength) for point in points]
        final_values = [Decimal(point.final_strength) for point in points]
        max_values = [Decimal(point.max_strength) for point in points]
        all_values = base_values + final_values + max_values
        min_value = min(all_values)
        max_value = max(all_values)
        width = Decimal('360')
        height = Decimal('132')
        left_padding = Decimal('40')
        right_padding = Decimal('14')
        top_padding = Decimal('18')
        bottom_padding = Decimal('32')
        usable_width = width - left_padding - right_padding
        usable_height = height - top_padding - bottom_padding
        series_config = [
            ('Base', base_values, '#7dd3fc'),
            ('Final', final_values, '#34d399'),
            ('Max', max_values, '#fbbf24'),
        ]
        lines = []
        labels = []

        for label, values, color in series_config:
            coordinates = self._line_chart_coordinates(
                values,
                width,
                height,
                left_padding,
                top_padding,
                usable_width,
                usable_height,
                min_value,
                max_value,
            )
            polyline = ' '.join(
                f'{x:.2f},{y:.2f}'
                for x, y in coordinates
            )
            circles = ''.join(
                (
                    f'<circle cx="{x:.2f}" cy="{y:.2f}" r="2.5" '
                    f'fill="{color}"></circle>'
                )
                for x, y in coordinates
            )
            lines.append(
                (
                    f'<polyline points="{polyline}" fill="none" '
                    f'stroke="{color}" stroke-width="2.4" '
                    'stroke-linecap="round" stroke-linejoin="round"></polyline>'
                    f'{circles}'
                )
            )
            labels.append(
                (
                    f'<span><i style="background:{color};"></i>{label}: '
                    f'{values[-1]:.2f}</span>'
                )
            )

        x_ticks = ''.join(
            (
                f'<text x="{x:.2f}" y="116" text-anchor="middle" '
                'fill="#86aab6" font-size="8">'
                f'{index + 1}</text>'
            )
            for index, (x, _y) in enumerate(
                self._line_chart_coordinates(
                    final_values,
                    width,
                    height,
                    left_padding,
                    top_padding,
                    usable_width,
                    usable_height,
                    min_value,
                    max_value,
                )
            )
        )
        y_ticks = ''.join(
            [
                (
                    f'<text x="34" y="{top_padding + 3:.2f}" text-anchor="end" '
                    'fill="#86aab6" font-size="8">'
                    f'{max_value:.0f}</text>'
                ),
                (
                    f'<text x="34" y="{height - bottom_padding + 3:.2f}" '
                    'text-anchor="end" fill="#86aab6" font-size="8">'
                    f'{min_value:.0f}</text>'
                ),
            ]
        )

        return format_html(
            (
                '<div class="ws-strength-chart">'
                '<svg viewBox="0 0 360 132" role="img" aria-label="Staerke-Verlauf">'
                '<rect width="360" height="132" rx="8" fill="#071b24"></rect>'
                '<g opacity="0.20">{}</g>'
                '<line x1="40" y1="18" x2="40" y2="100" stroke="#86aab6" stroke-width="1"></line>'
                '<line x1="40" y1="100" x2="346" y2="100" stroke="#86aab6" stroke-width="1"></line>'
                '<text x="8" y="64" transform="rotate(-90 8 64)" fill="#c8e3eb" font-size="9" font-weight="800">Staerke</text>'
                '<text x="193" y="129" text-anchor="middle" fill="#c8e3eb" font-size="9" font-weight="800">Snapshots</text>'
                '{}'
                '{}'
                '{}'
                '</svg>'
                '<div class="ws-strength-legend">{}</div>'
                '</div>'
            ),
            mark_safe(
                ''.join(
                    f'<line x1="{x}" y1="18" x2="{x}" y2="100" stroke="#ffffff"></line>'
                    for x in range(64, 346, 34)
                )
                + ''.join(
                    f'<line x1="40" y1="{y}" x2="346" y2="{y}" stroke="#ffffff"></line>'
                    for y in range(30, 100, 20)
                )
            ),
            mark_safe(y_ticks),
            mark_safe(x_ticks),
            mark_safe(''.join(lines)),
            mark_safe(''.join(labels)),
        )

    @admin.display(description='Saison und Karriere')
    def season_career_admin_preview(self, obj):
        return mark_safe(
            (
                '<div class="ws-season-career-grid">'
                '<section>'
                '<h3>Saison</h3>'
                '<table class="ws-admin-preview-table">'
                '<thead><tr><th>Saison</th><th>Wettbewerb</th><th>Sp</th>'
                '<th>T</th><th>V</th><th>Gelb</th><th>Rot</th><th>Min</th>'
                '<th>Score</th></tr></thead>'
                '<tbody><tr><td colspan="9" class="ws-admin-muted">'
                'Noch keine Websoccer-Saisonstatistik vorhanden.'
                '</td></tr></tbody></table>'
                '<p class="help">Echte Werte erscheinen nach den ersten simulierten Spielen.</p>'
                '</section>'
                '<section>'
                '<h3>Karriere</h3>'
                '<table class="ws-admin-preview-table">'
                '<thead><tr><th>Saisons</th><th>Sp</th><th>T</th><th>V</th>'
                '<th>Gelb</th><th>Rot</th><th>Min</th></tr></thead>'
                '<tbody><tr><td colspan="7" class="ws-admin-muted">'
                'Noch keine Websoccer-Karrierestatistik vorhanden.'
                '</td></tr></tbody></table>'
                '<p class="help">Karriere wird spaeter aus allen Websoccer-Saisons aggregiert.</p>'
                '</section>'
                '</div>'
            )
        )

    @admin.display(description='Transferhistorie WS')
    def transfer_history_admin_preview(self, obj):
        return mark_safe(
            (
                '<table class="ws-admin-preview-table">'
                '<thead><tr><th>Zeitpunkt</th><th>Spieler</th><th>von/zu</th>'
                '<th>Abloese</th></tr></thead>'
                '<tbody><tr><td colspan="4" class="ws-admin-muted">'
                'Noch keine Websoccer-Transfers vorhanden.'
                '</td></tr></tbody></table>'
                '<p class="help">Echte Werte erscheinen nach den ersten Websoccer-Transfers.</p>'
            )
        )

    @admin.display(description='Geschichte')
    def history_admin_preview(self, obj):
        if not obj or not getattr(obj, 'pk', None):
            return format_html(
                '<span class="ws-admin-muted">{}</span>',
                'Die Aenderungshistorie erscheint nach dem ersten Speichern.',
            )

        content_type = ContentType.objects.get_for_model(obj)
        log_entries = LogEntry.objects.select_related('user').filter(
            content_type=content_type,
            object_id=str(obj.pk),
        ).order_by('-action_time')[:20]

        if not log_entries:
            return format_html(
                '<span class="ws-admin-muted">{}</span>',
                'Noch keine Aenderungen fuer dieses Spielerprofil protokolliert.',
            )

        action_labels = {
            ADDITION: 'Angelegt',
            CHANGE: 'Geaendert',
            DELETION: 'Geloescht',
        }
        rows = format_html_join(
            '',
            (
                '<tr>'
                '<td>{}</td>'
                '<td>{}</td>'
                '<td>{}</td>'
                '<td>{}</td>'
                '</tr>'
            ),
            (
                (
                    entry.action_time.strftime('%d.%m.%Y %H:%M'),
                    entry.user.get_username() if entry.user else '-',
                    action_labels.get(entry.action_flag, entry.action_flag),
                    entry.get_change_message() or '-',
                )
                for entry in log_entries
            ),
        )

        return format_html(
            (
                '<table class="ws-admin-preview-table">'
                '<thead><tr><th>Zeitpunkt</th><th>Benutzer</th><th>Aktion</th>'
                '<th>Aenderung</th></tr></thead>'
                '<tbody>{}</tbody></table>'
            ),
            rows,
        )


class PlayerSourceRatingAdmin(admin.ModelAdmin):
    form = PlayerSourceRatingForm
    list_display = (
        'player',
        'source',
        'rating',
        'potential',
        'source_version',
        'checked_at',
        'updated_at',
    )
    search_fields = (
        'player__first_name',
        'player__last_name',
        'source_version',
    )
    list_filter = (
        'source',
        'checked_at',
    )


class DataSourceAdmin(admin.ModelAdmin):
    list_display = (
        'code',
        'name',
        'base_url',
    )
    search_fields = (
        'code',
        'name',
    )


class PlayerExternalIdAdmin(admin.ModelAdmin):
    list_display = (
        'player',
        'source',
        'external_id',
        'is_primary',
        'updated_at',
    )
    list_filter = (
        'source',
        'is_primary',
    )
    search_fields = (
        'player__first_name',
        'player__last_name',
        'external_id',
        'profile_url',
    )


class PlayerMarketValueSnapshotAdmin(admin.ModelAdmin):
    list_display = (
        'player',
        'source',
        'recorded_at',
        'value_eur',
        'update_current',
        'source_version',
    )
    list_filter = (
        'source',
        'recorded_at',
        'update_current',
    )
    search_fields = (
        'player__first_name',
        'player__last_name',
        'profile_url',
        'source_version',
    )


@admin.register(PlayerSeasonStat)
class PlayerSeasonStatAdmin(admin.ModelAdmin):
    list_display = (
        'player',
        'season_number',
        'season',
        'competition',
        'matches',
        'goals',
        'assists',
        'substitutions_in',
        'substitutions_out',
        'minutes_played',
        'player_of_match_awards',
        'average_grade',
    )
    list_filter = ('season_number', 'season', 'competition')
    search_fields = ('player__first_name', 'player__last_name', 'competition')


@admin.register(PlayerTransferHistory)
class PlayerTransferHistoryAdmin(admin.ModelAdmin):
    list_display = (
        'player',
        'transfer_date',
        'season',
        'from_club',
        'to_club',
        'fee_eur',
    )
    list_filter = ('season', 'from_club', 'to_club')
    search_fields = ('player__first_name', 'player__last_name')


@admin.register(PlayerInjuryRecord)
class PlayerInjuryRecordAdmin(admin.ModelAdmin):
    list_display = (
        'player',
        'start_date',
        'injury_type',
        'days_missed',
        'competition',
        'is_active',
    )
    list_filter = ('is_active', 'competition')
    search_fields = ('player__first_name', 'player__last_name', 'injury_type')


@admin.register(PlayerSuspensionRecord)
class PlayerSuspensionRecordAdmin(admin.ModelAdmin):
    list_display = (
        'player',
        'start_date',
        'reason',
        'matches_missed',
        'competition',
        'is_active',
    )
    list_filter = ('is_active', 'competition')
    search_fields = ('player__first_name', 'player__last_name', 'reason')


@admin.register(PlayerAwardTitle)
class PlayerAwardTitleAdmin(admin.ModelAdmin):
    list_display = (
        'player',
        'title',
        'season',
        'competition',
        'count',
        'trophy_asset_id',
    )
    list_filter = ('season', 'competition')
    search_fields = ('player__first_name', 'player__last_name', 'title')


class PlayerSourceRatingSnapshotAdmin(admin.ModelAdmin):
    list_display = (
        'player',
        'source',
        'recorded_at',
        'rating',
        'potential',
        'update_current',
        'source_version',
    )
    list_filter = (
        'source',
        'recorded_at',
        'update_current',
    )
    search_fields = (
        'player__first_name',
        'player__last_name',
        'source_url',
        'source_version',
    )


class PlayerWeightedRatingSnapshotAdmin(admin.ModelAdmin):
    list_display = (
        'player',
        'recorded_at',
        'source',
        'weighted_rating',
        'rating_minutes',
        'match_count',
        'fixture_reference',
    )
    list_filter = (
        'source',
        'recorded_at',
    )
    search_fields = (
        'player__first_name',
        'player__last_name',
        'fixture_reference',
    )


class PlayerStrengthSnapshotAdmin(admin.ModelAdmin):
    list_display = (
        'player',
        'recorded_at',
        'match_reference',
        'base_strength',
        'final_strength',
        'max_strength',
        'last_10_average_strength',
    )
    list_filter = (
        'recorded_at',
    )
    search_fields = (
        'player__first_name',
        'player__last_name',
        'match_reference',
    )


class PlayerFormSnapshotAdmin(admin.ModelAdmin):
    list_display = (
        'player',
        'fixture_date',
        'minutes_played',
        'minutes_quote',
        'started',
        'captain',
        'rating',
        'goals',
        'assists',
        'source',
    )
    list_filter = (
        'source',
        'fixture_date',
        'started',
        'captain',
    )
    search_fields = (
        'player__first_name',
        'player__last_name',
        'team_name',
        'opponent_name',
        'fixture_id',
    )


class PlayerEditRequestAdmin(admin.ModelAdmin):
    list_display = (
        'player',
        'field_name',
        'old_value_badge',
        'new_value_badge',
        'requester_name',
        'status',
        'created_at',
    )
    list_filter = (
        'status',
        'field_name',
        'created_at',
    )
    search_fields = (
        'player__first_name',
        'player__last_name',
        'old_value',
        'new_value',
        'requester_note',
    )
    readonly_fields = (
        'old_value_badge',
        'new_value_badge',
        'created_at',
        'updated_at',
        'decided_at',
    )
    fieldsets = (
        (
            'Antrag',
            {
                'fields': (
                    'player',
                    'field_name',
                    (
                        'old_value_badge',
                        'new_value_badge',
                    ),
                    (
                        'old_value',
                        'new_value',
                    ),
                    'requester_name',
                    'requester_note',
                ),
            },
        ),
        (
            'Entscheidung',
            {
                'fields': (
                    'status',
                    'decision_note',
                    'decided_by',
                    'decided_at',
                ),
            },
        ),
        (
            'System',
            {
                'fields': (
                    'created_at',
                    'updated_at',
                ),
            },
        ),
    )
    actions = [
        'accept_selected_requests',
        'reject_selected_requests',
    ]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'player',
            'player__club',
            'decided_by',
        )

    @admin.display(description='Alter Wert')
    def old_value_badge(self, obj):
        return format_html(
            '<span style="color:#ff7676;font-weight:700;">{}</span>',
            obj.old_value or '-',
        )

    @admin.display(description='Neuer Wert')
    def new_value_badge(self, obj):
        return format_html(
            '<span style="color:#72f2a5;font-weight:700;">{}</span>',
            obj.new_value or '-',
        )

    @admin.action(description='Ausgewaehlte Antraege annehmen')
    def accept_selected_requests(self, request, queryset):
        accepted_count = 0
        error_messages = []

        for edit_request in queryset.filter(status=PlayerEditRequest.STATUS_OPEN):
            try:
                edit_request.accept(user=request.user)
                accepted_count += 1
            except ValidationError as exc:
                error_messages.append(f'{edit_request}: {exc.messages[0]}')

        if accepted_count:
            self.message_user(
                request,
                f'{accepted_count} Antrag/Antraege angenommen.',
                messages.SUCCESS,
            )

        for error_message in error_messages:
            self.message_user(request, error_message, messages.ERROR)

    @admin.action(description='Ausgewaehlte Antraege ablehnen')
    def reject_selected_requests(self, request, queryset):
        rejected_count = 0

        for edit_request in queryset.filter(status=PlayerEditRequest.STATUS_OPEN):
            edit_request.reject(user=request.user)
            rejected_count += 1

        self.message_user(
            request,
            f'{rejected_count} Antrag/Antraege abgelehnt.',
            messages.SUCCESS,
        )


class PlayerDataReviewAdmin(admin.ModelAdmin):
    list_display = (
        'full_name',
        'club',
        'real_life_club',
        'source_strength_badge',
        'source_data_quality_badge',
        'open_requests_badge',
    )
    list_filter = (
        SourceBaseQualityFilter,
        'club',
        'real_life_club',
    )
    search_fields = (
        'first_name',
        'last_name',
        'fm_inside_id',
        'transfermarkt_id',
    )

    def get_queryset(self, request):
        queryset = super().get_queryset(request).select_related(
            'club',
            'real_life_club',
        ).prefetch_related('source_ratings')
        queryset = queryset.annotate(
            ea_source_count=models.Count(
                'source_ratings',
                filter=models.Q(source_ratings__source=PlayerSourceRating.SOURCE_EA),
                distinct=True,
            ),
            fm_source_count=models.Count(
                'source_ratings',
                filter=models.Q(source_ratings__source=PlayerSourceRating.SOURCE_FM),
                distinct=True,
            ),
            open_request_count=models.Count(
                'edit_requests',
                filter=models.Q(edit_requests__status=PlayerEditRequest.STATUS_OPEN),
                distinct=True,
            ),
        )
        return queryset.filter(
            models.Q(ea_source_count=0)
            | models.Q(fm_source_count=0)
            | models.Q(open_request_count__gt=0)
        )

    @admin.display(description='Quellen-Staerke')
    def source_strength_badge(self, obj):
        return PlayerAdmin.source_strength_badge(self, obj)

    @admin.display(description='Datenstatus')
    def source_data_quality_badge(self, obj):
        return PlayerAdmin.source_data_quality_badge(self, obj)

    @admin.display(description='Offene Antraege')
    def open_requests_badge(self, obj):
        count = getattr(obj, 'open_request_count', 0)
        color = '#72f2a5' if count == 0 else '#ffd86b'
        return format_html(
            '<span style="color:{};font-weight:700;">{}</span>',
            color,
            count,
        )


admin.site.register(Player, PlayerAdmin)
admin.site.register(PlayerDataReview, PlayerDataReviewAdmin)
admin.site.register(PlayerEditRequest, PlayerEditRequestAdmin)
admin.site.register(PlayerFormSnapshot, PlayerFormSnapshotAdmin)
admin.site.register(PlayerSourceRating, PlayerSourceRatingAdmin)
admin.site.register(PlayerStrengthProfile)
admin.site.register(StrengthFormulaSettings, StrengthFormulaSettingsAdmin)
