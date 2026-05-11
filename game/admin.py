from django import forms
from django.contrib import admin
from django.contrib.admin.models import CHANGE, ADDITION, DELETION, LogEntry
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils.html import format_html, format_html_join
from django.utils.safestring import mark_safe
from .models import (
    COUNTRY_FLAG_ASSETS,
    League,
    Club,
    Player,
    PlayerSourceRating,
    PlayerStrengthProfile
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


class PlayerInline(admin.TabularInline):
    model = Player
    form = PlayerNationalityForm
    fk_name = 'club'
    extra = 0

    fields = (
        'fm_inside_id',
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


class PlayerAdmin(admin.ModelAdmin):
    form = PlayerNationalityForm
    change_form_template = 'admin/game/player/change_form.html'
    list_display = (
        'first_name',
        'last_name',
        'club',
        'real_life_club',
        'main_position_1',
        'source_strength_badge',
        'final_strength',
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
        'real_life_club',
        'main_position_1',
    )
    readonly_fields = (
        'source_strength_summary',
        'strength_profile_summary',
        'season_admin_preview',
        'career_admin_preview',
        'transfer_history_admin_preview',
        'history_admin_preview',
    )
    fieldsets = (
        (
            'Spielerprofil',
            {
                'fields': (
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
                    'strength_profile_summary',
                ),
            },
        ),
        (
            'Source',
            {
                'fields': (
                    'fm_inside_id',
                    'transfermarkt_id',
                    'transfermarkt_profile_url',
                    'transfermarkt_market_value_url',
                ),
            },
        ),
        (
            'Saison',
            {
                'fields': (
                    'season_admin_preview',
                ),
            },
        ),
        (
            'Karriere',
            {
                'fields': (
                    'career_admin_preview',
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
        PlayerSourceRatingInline,
    ]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'club',
            'real_life_club',
            'strength_profile',
        ).prefetch_related('source_ratings')

    @admin.display(description='Stärke', ordering='strength_profile__final_strength')
    def final_strength(self, obj):
        if hasattr(obj, 'strength_profile'):
            return obj.strength_profile.final_strength

        return '-'

    @admin.display(description='Quellen-Staerke')
    def source_strength_badge(self, obj):
        base_strength = obj.calculated_base_strength

        if base_strength is None:
            return format_html(
                '<span title="{}">unvollstaendig <span style="cursor:help;">&#9432;</span></span>',
                obj.source_strength_explanation,
            )

        return format_html(
            '<span title="{}">Staerke {} <span style="cursor:help;">&#9432;</span></span>',
            obj.source_strength_explanation,
            base_strength,
        )

    @admin.display(description='Berechnete Quellen-Staerke')
    def source_strength_summary(self, obj):
        base_strength = obj.calculated_base_strength
        potential_strength = obj.calculated_potential_strength

        if base_strength is None:
            label = 'Staerke unvollstaendig'
        else:
            label = f'Staerke {base_strength}'

        if potential_strength is not None:
            label = f'{label} / Potential {potential_strength}'

        return format_html(
            '<span title="{}">{} <span style="cursor:help;">&#9432;</span></span>',
            obj.source_strength_explanation,
            label,
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
                '<thead><tr><th>Base</th><th>Form</th><th>Final</th></tr></thead>'
                '<tbody><tr><td>{}</td><td>{}</td><td>{}</td></tr></tbody>'
                '</table>'
            ),
            profile.base_strength,
            profile.form_modifier,
            profile.final_strength,
        )

    @admin.display(description='Saison')
    def season_admin_preview(self, obj):
        return mark_safe(
            (
                '<table class="ws-admin-preview-table">'
                '<thead><tr><th>Wettbewerb</th><th>Sp</th><th>T</th><th>V</th>'
                '<th>Gelb</th><th>Rot</th><th>Min</th><th>Score</th></tr></thead>'
                '<tbody>'
                '<tr><td>Bundesliga</td><td>15</td><td>18</td><td>5</td>'
                '<td>2</td><td>0</td><td>1327</td><td><strong>2.5</strong></td></tr>'
                '<tr><td><strong>Insgesamt</strong></td><td><strong>15</strong></td>'
                '<td><strong>18</strong></td><td><strong>5</strong></td>'
                '<td><strong>2</strong></td><td><strong>0</strong></td>'
                '<td><strong>1327</strong></td><td><strong>2.5</strong></td></tr>'
                '</tbody></table>'
                '<p class="help">Dummywerte fuer die spaetere Saisonstatistik.</p>'
            )
        )

    @admin.display(description='Karriere')
    def career_admin_preview(self, obj):
        return mark_safe(
            (
                '<table class="ws-admin-preview-table">'
                '<thead><tr><th>Wettbewerb</th><th>Sp</th><th>T</th><th>V</th>'
                '<th>Gelb</th><th>Rot</th><th>Min</th></tr></thead>'
                '<tbody>'
                '<tr><td>Premier League</td><td>320</td><td>213</td><td>51</td>'
                '<td>34</td><td>0</td><td>26794</td></tr>'
                '<tr><td>Bundesliga</td><td>95</td><td>88</td><td>24</td>'
                '<td>8</td><td>0</td><td>8461</td></tr>'
                '<tr><td><strong>Insgesamt</strong></td><td><strong>415</strong></td>'
                '<td><strong>301</strong></td><td><strong>75</strong></td>'
                '<td><strong>42</strong></td><td><strong>0</strong></td>'
                '<td><strong>35255</strong></td></tr>'
                '</tbody></table>'
                '<p class="help">Dummywerte fuer die spaetere Karriereansicht.</p>'
            )
        )

    @admin.display(description='Transferhistorie WS')
    def transfer_history_admin_preview(self, obj):
        player_name = obj.full_name if obj and getattr(obj, 'pk', None) else 'Spieler'
        return format_html(
            (
                '<table class="ws-admin-preview-table">'
                '<thead><tr><th>Zeitpunkt</th><th>Spieler</th><th>von/zu</th>'
                '<th>Abloese</th></tr></thead>'
                '<tbody><tr><td>12.07.25<br>21:01</td><td>{}</td>'
                '<td>FC Bayern Muenchen -&gt; Borussia Dortmund</td>'
                '<td>95.000.000 EUR</td></tr></tbody></table>'
                '<p class="help">Dummywert fuer die spaetere WS-Transferhistorie.</p>'
            ),
            player_name,
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


admin.site.register(Player, PlayerAdmin)
admin.site.register(PlayerSourceRating, PlayerSourceRatingAdmin)
admin.site.register(PlayerStrengthProfile)
