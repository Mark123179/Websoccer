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
    ClubFinancialTransaction,
    ClubNewsItem,
    ClubPublicProfile,
    ClubSponsor,
    ClubTrophy,
    DataSource,
    GameSeasonState,
    CoinTransaction,
    HoenessCoin,
    League,
    LeagueNews,
    LeagueStandings,
    Club,
    ManagerAtRisk,
    ManagerCareerStation,
    ManagerProfile,
    MatchdayRevenue,
    MatchResult,
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
    PresidentSatisfaction,
    SeasonGoal,
    PlayerTransferHistory,
    PlayerWeightedRatingSnapshot,
    SeasonFixture,
    Stadium,
    StrengthFormulaSettings,
    StrengthModifierRule,
    TacticSetup,
    TacticTemplate,
    strength_decimal,
)
from .season_goals import evaluate_goal_for_club


def _write_to_static(file_obj, static_path):
    """
    Schreibt file_obj direkt nach game/static/<static_path> und überschreibt
    eine vorhandene Datei. static_path ist der Pfad wie er in {% static %}
    verwendet wird (z.B. 'game/images/crests/915.png').
    """
    import os
    from pathlib import Path
    from django.conf import settings
    dest = Path(settings.BASE_DIR) / 'game' / 'static' / static_path
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, 'wb') as f:
        for chunk in file_obj.chunks():
            f.write(chunk)


def _ext(file_obj):
    """Gibt die Dateiendung des hochgeladenen Files zurück (z.B. 'png')."""
    name = file_obj.name or ''
    return name.rsplit('.', 1)[-1].lower() if '.' in name else 'jpg'


NATIONALITY_CHOICES = [
    ('', '---------'),
    *[
        (country, country)
        for country in sorted(COUNTRY_FLAG_ASSETS)
    ],
]


class PlayerNationalityForm(forms.ModelForm):
    portrait_file = forms.FileField(
        required=False,
        label='Spielerbild hochladen',
        help_text='JPG/PNG — überschreibt das bestehende Spielerbild (benötigt fm_inside_id).',
        widget=forms.ClearableFileInput(attrs={'accept': 'image/*'}),
    )
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
    nt_nationality = forms.ChoiceField(
        choices=NATIONALITY_CHOICES,
        required=False,
        label='NT-Nation (registriert)',
        help_text=(
            'Die Nation, für die der Spieler international registriert ist. '
            'Leer lassen, um automatisch die erste Nationalität zu verwenden.'
        ),
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

        if self.instance and self.instance.nt_nationality:
            self.fields['nt_nationality'].initial = self.instance.nt_nationality

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
        instance.nt_nationality = self.cleaned_data.get('nt_nationality') or ''
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


class StadiumInline(admin.StackedInline):
    model = Stadium
    extra = 0
    max_num = 1
    can_delete = False
    verbose_name = 'Stadion'
    verbose_name_plural = 'Stadion'
    fields = (
        ('name', 'city', 'lawn_quality'),
        ('nord_standing', 'nord_seating', 'nord_vip'),
        ('ost_standing',  'ost_seating',  'ost_vip'),
        ('sued_standing', 'sued_seating', 'sued_vip'),
        ('west_standing', 'west_seating', 'west_vip'),
        ('price_standing', 'price_seating', 'price_vip'),
    )


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


class ClubLeagueInline(admin.TabularInline):
    model = Club
    fk_name = 'league'
    fields = ('club_link', 'short_name', 'managed_by', 'budget', 'readiness_badge')
    readonly_fields = ('club_link', 'short_name', 'managed_by', 'budget', 'readiness_badge')
    extra = 0
    can_delete = False
    show_change_link = False
    verbose_name = 'Verein'
    verbose_name_plural = 'Vereine in dieser Liga'
    ordering = ('name',)

    @admin.display(description='Name')
    def club_link(self, obj):
        from django.urls import reverse
        url = reverse('admin:game_club_change', args=[obj.pk])
        return format_html('<a href="{}">{}</a>', url, obj.name)

    @admin.display(description='Spielbereit')
    def readiness_badge(self, obj):
        from game.match_readiness import has_valid_lineup
        setup = next(
            (s for s in obj.tactic_setups.all() if s.squad_scope == 'pro'),
            None,
        )
        ok = has_valid_lineup(setup, club=obj)
        color = '#4caf50' if ok else '#f44336'
        symbol = '✓' if ok else '✗'
        return format_html('<span style="color:{};font-weight:bold;">{}</span>', color, symbol)

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('tactic_setups').select_related('managed_by')

    def has_add_permission(self, request, obj=None):
        return False


class LeagueAdmin(admin.ModelAdmin):
    change_form_template = 'admin/game/league/change_form.html'

    list_display = (
        'name',
        'country',
        'api_football_id',
        'strength_coefficient',
        'coefficient_source',
        'club_count',
        'readiness_summary',
        'spielplan_link',
    )
    search_fields = (
        'name',
        'country',
    )
    fields = (
        'name',
        'country',
        'api_football_id',
        'strength_coefficient',
        'coefficient_source',
        'logo_static_path',
        'logo_preview',
        'cl_spots',
        'el_spots',
        'conference_spots',
        'relegation_spots',
    )
    readonly_fields = ('logo_preview',)
    inlines = [ClubLeagueInline]

    @admin.display(description='Logo-Vorschau')
    def logo_preview(self, obj):
        from django.contrib.staticfiles import finders
        from django.templatetags.static import static
        if not obj.logo_static_path:
            return format_html('<span style="color:#888;font-size:11px;">— kein Pfad gesetzt —</span>')
        if finders.find(obj.logo_static_path):
            return format_html(
                '<img src="{}" alt="{}" style="max-height:72px;max-width:140px;'
                'object-fit:contain;background:#1a1a1a;padding:6px;border-radius:4px;'
                'border:1px solid #333;">',
                static(obj.logo_static_path), obj.name,
            )
        return format_html(
            '<span style="color:#f44336;font-size:11px;">&#9888; Datei nicht gefunden: {}</span>',
            obj.logo_static_path,
        )

    @admin.display(description='Vereine')
    def club_count(self, obj):
        return obj.club_set.count()

    @admin.display(description='Spielbereitschaft')
    def readiness_summary(self, obj):
        from game.match_readiness import has_valid_lineup
        clubs = obj.club_set.prefetch_related('tactic_setups').all()
        total = clubs.count()
        if total == 0:
            return '—'
        ok = 0
        for club in clubs:
            setup = next(
                (s for s in club.tactic_setups.all() if s.squad_scope == 'pro'),
                None,
            )
            if has_valid_lineup(setup, club=club):
                ok += 1
        color = '#4caf50' if ok == total else ('#ff9800' if ok > 0 else '#f44336')
        return format_html(
            '<span style="color:{};font-weight:bold;">{}/{}</span>',
            color, ok, total,
        )

    @admin.display(description='Spielplan')
    def spielplan_link(self, obj):
        from django.urls import reverse
        url = reverse('admin:game_league_spielplan', args=[obj.pk])
        return format_html(
            '<a class="button" style="padding:2px 8px;font-size:11px;" href="{}">&#128197; Generieren</a>',
            url,
        )

    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        from collections import defaultdict
        from django.urls import reverse
        from game.models import SeasonFixture

        extra_context = extra_context or {}
        if object_id:
            try:
                league = League.objects.get(pk=object_id)
            except League.DoesNotExist:
                league = None
            if league:
                seasons = list(
                    SeasonFixture.objects.filter(league=league)
                    .values_list('season', flat=True)
                    .distinct()
                    .order_by('-season')
                )
                selected_season = request.GET.get('season') or (seasons[0] if seasons else None)

                spielplan_matchdays = []
                if selected_season:
                    fixtures = (
                        SeasonFixture.objects
                        .filter(league=league, season=selected_season)
                        .select_related('home_club', 'away_club')
                        .order_by('matchday', 'id')
                    )
                    by_md = defaultdict(list)
                    for f in fixtures:
                        by_md[f.matchday].append(f)
                    for md in sorted(by_md.keys()):
                        md_fixtures = by_md[md]
                        played = sum(1 for f in md_fixtures if f.is_played)
                        total = len(md_fixtures)
                        spielplan_matchdays.append({
                            'matchday': md,
                            'fixtures': md_fixtures,
                            'played': played,
                            'total': total,
                        })

                total_played = sum(b['played'] for b in spielplan_matchdays)
                total_fixtures = sum(b['total'] for b in spielplan_matchdays)
                total_matchdays = len(spielplan_matchdays)
                current_matchday = 0
                for b in spielplan_matchdays:
                    if b['played'] > 0:
                        current_matchday = b['matchday']

                extra_context.update({
                    'spielplan_seasons': seasons,
                    'spielplan_selected': selected_season,
                    'spielplan_matchdays': spielplan_matchdays,
                    'spielplan_gen_url': reverse('admin:game_league_spielplan', args=[object_id]),
                    'fixture_edit_url': reverse('admin:game_league_fixture_edit', args=[object_id]),
                    'change_object_id': object_id,
                    'spielplan_total_played': total_played,
                    'spielplan_total_fixtures': total_fixtures,
                    'spielplan_total_matchdays': total_matchdays,
                    'spielplan_current_matchday': current_matchday,
                    'spielplan_fixture_list_url': reverse('admin:game_seasonfixture_changelist'),
                })
        return super().changeform_view(request, object_id, form_url, extra_context)

    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        custom = [
            path(
                '<int:league_id>/spielplan/',
                self.admin_site.admin_view(self.schedule_view),
                name='game_league_spielplan',
            ),
            path(
                '<int:league_id>/fixture-edit/',
                self.admin_site.admin_view(self.fixture_edit_view),
                name='game_league_fixture_edit',
            ),
        ]
        return custom + urls

    def fixture_edit_view(self, request, league_id):
        import json
        from django.db import transaction
        from django.http import JsonResponse
        from django.shortcuts import get_object_or_404
        from game.models import SeasonFixture

        if request.method != 'POST':
            return JsonResponse({'error': 'POST required'}, status=405)

        if not request.user.has_perm('game.change_seasonfixture'):
            return JsonResponse({'error': 'Keine Berechtigung'}, status=403)

        league = get_object_or_404(League, pk=league_id)

        if not self.has_change_permission(request):
            return JsonResponse({'error': 'Keine Berechtigung'}, status=403)

        try:
            payload = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        fixtures_data = payload.get('fixtures', [])
        if not isinstance(fixtures_data, list):
            return JsonResponse({'error': 'fixtures must be a list'}, status=400)

        from datetime import datetime as dt_parse

        prepared = []
        errors = []
        for item in fixtures_data:
            fixture_id = item.get('id')
            try:
                fixture = SeasonFixture.objects.get(pk=fixture_id, league=league)
            except SeasonFixture.DoesNotExist:
                errors.append(f'Fixture {fixture_id} nicht gefunden')
                continue

            raw_date = item.get('scheduled_date', '')
            if raw_date:
                try:
                    fixture.scheduled_date = dt_parse.strptime(raw_date, '%Y-%m-%d').date()
                except ValueError:
                    errors.append(f'Fixture {fixture_id}: ungültiges Datum „{raw_date}"')
                    continue
            else:
                fixture.scheduled_date = None

            raw_time = item.get('scheduled_time', '')
            if raw_time:
                try:
                    fixture.scheduled_time = dt_parse.strptime(raw_time, '%H:%M').time()
                except ValueError:
                    errors.append(f'Fixture {fixture_id}: ungültige Uhrzeit „{raw_time}"')
                    continue
            else:
                fixture.scheduled_time = None

            fixture.is_played = bool(item.get('is_played', False))

            raw_home = item.get('home_goals')
            raw_away = item.get('away_goals')

            if raw_home is not None and raw_home != '':
                try:
                    val = int(raw_home)
                    if val < 0:
                        raise ValueError('negative')
                    fixture.home_goals = val
                except (ValueError, TypeError):
                    errors.append(f'Fixture {fixture_id}: ungültige Heimtore')
                    continue
            else:
                fixture.home_goals = None

            if raw_away is not None and raw_away != '':
                try:
                    val = int(raw_away)
                    if val < 0:
                        raise ValueError('negative')
                    fixture.away_goals = val
                except (ValueError, TypeError):
                    errors.append(f'Fixture {fixture_id}: ungültige Auswärtstore')
                    continue
            else:
                fixture.away_goals = None

            prepared.append(fixture)

        if errors:
            return JsonResponse({'ok': False, 'errors': errors}, status=400)

        save_fields = ['scheduled_date', 'scheduled_time', 'is_played', 'home_goals', 'away_goals']
        with transaction.atomic():
            for fixture in prepared:
                fixture.save(update_fields=save_fields)

        return JsonResponse({'ok': True, 'updated': len(prepared)})

    def schedule_view(self, request, league_id):
        from datetime import date, timedelta
        from django.shortcuts import render, redirect, get_object_or_404
        from django.urls import reverse
        from game.models import SeasonFixture
        from game.schedule_generator import create_round_robin_schedule, matchday_date

        league = get_object_or_404(League, pk=league_id)
        clubs = list(league.club_set.order_by('name'))

        class SpielplanForm(forms.Form):
            season = forms.CharField(
                label='Saison',
                max_length=20,
                widget=forms.TextInput(attrs={'placeholder': '2025/26'}),
            )
            rounds = forms.IntegerField(
                label='Anzahl Runden',
                initial=2,
                min_value=1,
                max_value=4,
                help_text='1 = Nur Hinrunde, 2 = Hin- & Rückrunde',
            )
            start_date = forms.DateField(
                label='Erster Spieltag (Datum)',
                initial=date.today,
                widget=forms.DateInput(attrs={'type': 'date'}),
            )
            start_time = forms.TimeField(
                label='Anstoßzeit',
                initial='15:30',
                widget=forms.TimeInput(attrs={'type': 'time'}),
            )
            day_interval = forms.IntegerField(
                label='Tage zwischen Spieltagen',
                initial=7,
                min_value=1,
                max_value=30,
            )
            round_break = forms.IntegerField(
                label='Extra-Pause zwischen Runden (Tage)',
                initial=0,
                min_value=0,
                max_value=90,
                help_text='Zusätzliche Pause zwischen Hin- und Rückrunde.',
            )

        errors = []
        if len(clubs) < 2:
            errors.append(
                f'Diese Liga hat nur {len(clubs)} Verein(e) — '
                f'mindestens 2 Vereine sind für einen Spielplan erforderlich.'
            )

        if request.method == 'POST' and not errors:
            form = SpielplanForm(request.POST)
            if form.is_valid():
                season = form.cleaned_data['season']
                rounds = form.cleaned_data['rounds']
                start_date_val = form.cleaned_data['start_date']
                start_time_val = form.cleaned_data['start_time']
                day_interval = form.cleaned_data['day_interval']
                round_break = form.cleaned_data['round_break']

                existing = SeasonFixture.objects.filter(league=league, season=season)
                proceed = True
                if existing.exists():
                    played_count = existing.filter(is_played=True).count()
                    unplayed_count = existing.filter(is_played=False).count()
                    if played_count > 0:
                        form.add_error(
                            'season',
                            f'Für die Saison „{season}" wurden bereits {played_count} '
                            f'Spiel(e) ausgetragen. Der Spielplan kann nicht '
                            f'zurückgesetzt werden, solange gespielte Partien existieren — '
                            f'eine Neugenerierung würde den bestehenden Spielplan '
                            f'inkonsistent machen.',
                        )
                        proceed = False
                    elif request.POST.get('confirm_reset') == '1':
                        existing.delete()
                        self.message_user(
                            request,
                            f'{unplayed_count} ungespieltes Spiel(e) aus Saison „{season}" gelöscht. '
                            f'Neuer Spielplan wird generiert…',
                            messages.WARNING,
                        )
                    else:
                        context = {
                            **self.admin_site.each_context(request),
                            'title': f'Spielplan generieren — {league}',
                            'league': league,
                            'clubs': clubs,
                            'form': form,
                            'errors': errors,
                            'opts': self.model._meta,
                            'existing_warning': True,
                            'unplayed_count': unplayed_count,
                            'played_count': 0,
                            'season': season,
                        }
                        return render(request, 'admin/game/league/schedule_generator.html', context)

                if proceed:
                    team_ids = [c.pk for c in clubs]
                    try:
                        schedule = create_round_robin_schedule(team_ids, rounds=rounds)
                    except ValueError as exc:
                        form.add_error(None, f'Spielplan-Generator: {exc}')
                        schedule = None

                    if schedule is not None:
                        n = len(clubs)
                        matchdays_per_round = n if n % 2 == 1 else n - 1

                        fixtures_to_create = []
                        for spieltag, pairs in sorted(schedule.items()):
                            match_date = matchday_date(
                                spieltag, start_date_val, day_interval,
                                matchdays_per_round, round_break,
                            )
                            for home_id, away_id in pairs:
                                fixtures_to_create.append(SeasonFixture(
                                    league=league,
                                    season=season,
                                    matchday=spieltag,
                                    home_club_id=home_id,
                                    away_club_id=away_id,
                                    scheduled_date=match_date,
                                    scheduled_time=start_time_val,
                                ))

                        SeasonFixture.objects.bulk_create(fixtures_to_create)

                        total_matchdays = len(schedule)
                        total_games = len(fixtures_to_create)
                        self.message_user(
                            request,
                            f'Spielplan für „{league}" Saison {season} generiert: '
                            f'{total_matchdays} Spieltage, {total_games} Spiele.',
                            messages.SUCCESS,
                        )
                        return redirect(
                            reverse('admin:game_seasonfixture_changelist')
                            + f'?league__id__exact={league_id}&season={season}'
                        )
        else:
            form = SpielplanForm()

        context = {
            **self.admin_site.each_context(request),
            'title': f'Spielplan generieren — {league}',
            'league': league,
            'clubs': clubs,
            'form': form,
            'errors': errors,
            'opts': self.model._meta,
        }
        return render(request, 'admin/game/league/schedule_generator.html', context)


def _assign_manager_action(modeladmin, request, queryset):
    """Admin action: Trainer zuweisen — öffnet eine einfache Zwischenseite."""
    from django.shortcuts import redirect
    from django.urls import reverse
    ids = ','.join(str(c.pk) for c in queryset)
    return redirect(
        reverse('admin:game_club_assign_manager') + f'?ids={ids}'
    )
_assign_manager_action.short_description = 'Trainer zuweisen…'


def _dismiss_manager_action(modeladmin, request, queryset):
    """Admin action: Trainer entlassen — setzt ended_at auf heute für alle
    ausgewählten Vereine, die gerade einen Manager haben."""
    from datetime import date
    from game.services import record_club_departure
    dismissed = 0
    for club in queryset:
        if club.managed_by_id:
            record_club_departure(club.managed_by, departure_date=date.today())
            dismissed += 1
    modeladmin.message_user(
        request,
        f'{dismissed} Trainer entlassen und Karriere-Station(en) geschlossen.',
    )
_dismiss_manager_action.short_description = 'Trainer entlassen (Abgang heute)'


class ClubImagesForm(forms.ModelForm):
    crest_file = forms.FileField(
        required=False,
        label='Wappen hochladen',
        help_text='PNG/JPG — überschreibt das vorhandene Wappen (benötigt fm_inside_id).',
        widget=forms.ClearableFileInput(attrs={'accept': 'image/*'}),
    )
    kit_home_file = forms.FileField(
        required=False,
        label='Heimtrikot hochladen',
        help_text='PNG/JPG — überschreibt das vorhandene Heimtrikot.',
        widget=forms.ClearableFileInput(attrs={'accept': 'image/*'}),
    )
    kit_away_file = forms.FileField(
        required=False,
        label='Auswärtstrikot hochladen',
        help_text='PNG/JPG — überschreibt das vorhandene Auswärtstrikot.',
        widget=forms.ClearableFileInput(attrs={'accept': 'image/*'}),
    )
    kit_third_file = forms.FileField(
        required=False,
        label='Ausweichtrikot hochladen',
        help_text='PNG/JPG — überschreibt das vorhandene Ausweichtrikot.',
        widget=forms.ClearableFileInput(attrs={'accept': 'image/*'}),
    )

    class Meta:
        model = Club
        fields = '__all__'


class ClubAdmin(admin.ModelAdmin):
    form = ClubImagesForm
    list_display = (
        'name',
        'short_name',
        'league',
        'managed_by',
        'readiness_status_display',
        'team_strength_display',
        'api_football_id',
        'fm_inside_id',
        'budget',
    )
    list_select_related = ('managed_by',)
    search_fields = (
        'name',
        'short_name',
        'fm_inside_id',
    )
    autocomplete_fields = ('managed_by',)
    readonly_fields = ('managed_by_hint', 'crest_preview', 'kits_preview')
    actions = [_assign_manager_action, _dismiss_manager_action]

    inlines = [
        StadiumInline,
        PlayerInline,
    ]

    @admin.display(description='Bereit')
    def readiness_status_display(self, obj):
        from game.match_readiness import club_readiness_status
        info = club_readiness_status(obj)
        icons = {
            'ok':    ('✓', '#4caf50'),
            'warn':  ('⚠', '#ff9800'),
            'error': ('✗', '#f44336'),
        }
        icon, color = icons.get(info['status'], ('?', '#999'))
        label = f'{icon} {info["player_count"]}P'
        return format_html(
            '<span title="{}" style="color:{};font-weight:bold;">{}</span>',
            f'Taktik:{info["has_tactic"]} | Aufstellung:{info["valid_lineup"]} | TW:{info["has_goalkeeper"]}',
            color, label,
        )

    @admin.display(description='Stärke')
    def team_strength_display(self, obj):
        from game.match_readiness import calculate_team_strength
        strength = calculate_team_strength(obj)
        val = float(strength.get('overall', 50))
        if val >= 70:
            color = '#4caf50'
        elif val >= 55:
            color = '#ff9800'
        else:
            color = '#aaa'
        return format_html(
            '<span style="color:{};">{}</span>',
            color, f'{val:.1f}',
        )

    def get_fieldsets(self, request, obj=None):
        return [
            (None, {
                'fields': (
                    'name', 'short_name', 'founded_year', 'budget', 'fan_popularity', 'league',
                    'fm_inside_id', 'api_football_id',
                ),
            }),
            ('Trainer-Zuweisung', {
                'fields': ('managed_by_hint',),
                'description': (
                    'Nutze die Admin-Aktionen "Trainer zuweisen" oder '
                    '"Trainer entlassen" auf der Vereins-Übersicht, '
                    'damit die Karrierekarte automatisch aktualisiert wird. '
                    'Das Feld "managed_by" nicht direkt über das Formular ändern.'
                ),
            }),
            ('Bilder: Wappen & Trikots', {
                'fields': (
                    'crest_preview', 'crest_file',
                    'kits_preview',
                    'kit_home_file', 'kit_away_file', 'kit_third_file',
                ),
                'description': (
                    'Datei hochladen → wird sofort in den Static-Ordner geschrieben und '
                    'ersetzt das bestehende Bild. fm_inside_id muss gesetzt sein.'
                ),
            }),
        ]

    @admin.display(description='Aktueller Trainer')
    def managed_by_hint(self, obj):
        if obj and obj.managed_by_id:
            return f'{obj.managed_by} (ID {obj.managed_by_id})'
        return '— kein Trainer zugewiesen —'

    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        custom = [
            path(
                'assign-manager/',
                self.admin_site.admin_view(self.assign_manager_view),
                name='game_club_assign_manager',
            ),
            path(
                'regression-status/',
                self.admin_site.admin_view(self.regression_status_view),
                name='game_regression_status',
            ),
        ]
        return custom + urls

    def regression_status_view(self, request):
        from pathlib import Path
        import json as _json
        from django.shortcuts import render

        HISTORY_DIR = Path('.local/regression_history')
        ALARM_THRESHOLD = 0.05
        KEY_METRICS = [
            'goals_per_game', 'home_pct', 'draw_pct', 'away_pct',
            'yellow_per_game', 'inj_per_game', 'spearman', 'pearson_xgd',
        ]

        def _median(values):
            if not values:
                return 0.0
            s = sorted(values)
            n = len(s)
            mid = n // 2
            return (s[mid - 1] + s[mid]) / 2 if n % 2 == 0 else s[mid]

        def _metric_median(data, key):
            series = data.get('metrics', {}).get(key)
            if series and isinstance(series, list):
                return _median([float(v) for v in series])
            return None

        def _pct_change(old, new):
            if old == 0.0:
                return 0.0 if new == 0.0 else float('inf')
            return abs(new - old) / abs(old)

        def _load_json(path):
            try:
                with open(path) as f:
                    return _json.load(f)
            except Exception:
                return None

        runs = []
        if HISTORY_DIR.is_dir():
            for d in sorted(HISTORY_DIR.iterdir(), key=lambda x: x.name, reverse=True):
                if d.is_dir() and (d / 'seeds_stability.json').exists():
                    runs.append(d)

        diff_result = None
        run_triggered = request.method == 'POST' and request.POST.get('action') == 'run_diff'

        if run_triggered or (request.method == 'GET' and len(runs) >= 2):
            if len(runs) >= 2:
                new_path = runs[0] / 'seeds_stability.json'
                old_path = runs[1] / 'seeds_stability.json'
                old_data = _load_json(old_path)
                new_data = _load_json(new_path)
                rows = []
                alarms = []
                compared = 0
                if old_data and new_data:
                    for key in KEY_METRICS:
                        old_val = _metric_median(old_data, key)
                        new_val = _metric_median(new_data, key)
                        if old_val is None and new_val is None:
                            continue
                        if old_val is None or new_val is None:
                            rows.append({
                                'key': key, 'old': None, 'new': None,
                                'pct': None, 'alarm': True, 'missing': True,
                            })
                            alarms.append(f'{key}: Metrik fehlt in einem Lauf')
                            continue
                        compared += 1
                        pct = _pct_change(old_val, new_val)
                        is_alarm = pct > ALARM_THRESHOLD
                        rows.append({
                            'key': key,
                            'old': f'{old_val:.5f}',
                            'new': f'{new_val:.5f}',
                            'pct': f'{100 * pct:.2f}',
                            'alarm': is_alarm,
                            'missing': False,
                        })
                        if is_alarm:
                            alarms.append(
                                f'{key}: {old_val:.5f} → {new_val:.5f} '
                                f'(Δ {100 * pct:.2f}% > {100 * ALARM_THRESHOLD:.0f}%)'
                            )
                    new_stability = new_data.get('stability', {})
                    unstable = [k for k, v in new_stability.items()
                                if isinstance(v, dict) and not v.get('ok', True)]
                    diff_result = {
                        'old_label': runs[1].name,
                        'new_label': runs[0].name,
                        'rows': rows,
                        'alarms': alarms,
                        'compared': compared,
                        'unstable_new': unstable,
                        'status': 'alarm' if alarms else 'stabil',
                    }

        latest_run = runs[0] if runs else None
        latest_label = latest_run.name if latest_run else None
        if latest_label:
            try:
                from datetime import datetime
                dt = datetime.strptime(latest_label, '%Y%m%d_%H%M%S')
                latest_label_fmt = dt.strftime('%-d.%-m.%Y %H:%M:%S UTC')
            except ValueError:
                latest_label_fmt = latest_label
        else:
            latest_label_fmt = None

        if not runs:
            overall_status = 'keine_daten'
        elif len(runs) == 1:
            overall_status = 'ein_lauf'
        elif diff_result:
            overall_status = diff_result['status']
        else:
            overall_status = 'ausstehend'

        context = {
            **self.admin_site.each_context(request),
            'title': 'Regressions-Status',
            'opts': self.model._meta,
            'run_count': len(runs),
            'latest_label': latest_label_fmt,
            'overall_status': overall_status,
            'diff_result': diff_result,
            'run_triggered': run_triggered,
        }
        return render(request, 'admin/game/club/regression_status.html', context)

    def assign_manager_view(self, request):
        from datetime import date
        from django import forms
        from django.contrib import messages
        from django.shortcuts import render, redirect
        from django.urls import reverse
        from game.models import ManagerProfile
        from game.services import record_club_assignment

        ids_str = request.GET.get('ids', '') or request.POST.get('ids', '')
        club_ids = [int(i) for i in ids_str.split(',') if i.strip().isdigit()]
        clubs = Club.objects.filter(pk__in=club_ids)

        class AssignForm(forms.Form):
            manager = forms.ModelChoiceField(
                queryset=ManagerProfile.objects.select_related('user').order_by('name'),
                label='Manager',
                help_text='Welcher Manager übernimmt die ausgewählten Vereine?',
            )
            assignment_date = forms.DateField(
                initial=date.today,
                widget=forms.DateInput(attrs={'type': 'date'}),
                label='Übernahmedatum',
                help_text='Tag, an dem der Manager den Verein übernimmt.',
            )

        # OneToOneField: one manager → one club. Reject multi-club selection to
        # prevent confusing timeline data (manager would end up at last club only
        # with all intermediate stations created and immediately closed).
        if clubs.count() > 1:
            messages.error(
                request,
                'Bitte nur EINEN Verein auswählen. Ein Manager kann immer nur '
                'einen Verein gleichzeitig leiten.',
            )
            return redirect(reverse('admin:game_club_changelist'))

        if request.method == 'POST':
            form = AssignForm(request.POST)
            if form.is_valid():
                manager = form.cleaned_data['manager']
                adate = form.cleaned_data['assignment_date']
                club = clubs.first()
                record_club_assignment(manager, club, assignment_date=adate)
                messages.success(
                    request,
                    f'{manager} wurde als Trainer für {club} eingetragen '
                    f'(ab {adate.strftime("%-d.%-m.%Y")}).',
                )
                return redirect(reverse('admin:game_club_changelist'))
        else:
            form = AssignForm()

        context = {
            **self.admin_site.each_context(request),
            'title': 'Trainer zuweisen',
            'form': form,
            'clubs': clubs,
            'ids': ids_str,
            'opts': self.model._meta,
        }
        return render(request, 'admin/game/club/assign_manager.html', context)

    @admin.display(description='Aktuelles Wappen')
    def crest_preview(self, obj):
        if not obj or not obj.pk:
            return format_html('<span style="color:#999;">Erst nach dem Speichern sichtbar.</span>')
        path = obj.crest_static_path
        if not path:
            return format_html('<span style="color:#999;">Kein Wappen gefunden (fm_inside_id prüfen).</span>')
        return format_html(
            '<img src="{}" alt="{}" style="width:80px;height:80px;object-fit:contain;'
            'border:1px solid #ddd;padding:4px;border-radius:4px;" />',
            path, obj.name,
        )

    @admin.display(description='Aktuelle Trikots (Heim / Auswärts / Ausweich)')
    def kits_preview(self, obj):
        if not obj or not obj.pk:
            return format_html('<span style="color:#999;">Erst nach dem Speichern sichtbar.</span>')
        kits = obj.kit_static_paths
        if not kits:
            return format_html('<span style="color:#999;">Keine Trikots gefunden (fm_inside_id prüfen).</span>')
        imgs = ''.join(
            f'<div style="text-align:center;margin:0 8px;">'
            f'<img src="{static(k["path"])}" alt="{k["label"]}" '
            f'style="width:80px;height:80px;object-fit:contain;border:1px solid #ddd;'
            f'padding:4px;border-radius:4px;" />'
            f'<div style="font-size:11px;margin-top:4px;">{k["label"]}</div></div>'
            for k in kits
        )
        return format_html(
            '<div style="display:flex;flex-wrap:wrap;gap:4px;">{}</div>',
            mark_safe(imgs),
        )

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        fm_id = obj.fm_inside_id
        if not fm_id:
            if any(form.cleaned_data.get(k) for k in ('crest_file', 'kit_home_file', 'kit_away_file', 'kit_third_file')):
                messages.warning(request, 'Bild-Upload übersprungen: fm_inside_id ist nicht gesetzt.')
            return

        kit_map = {
            'kit_home_file': f'game/images/kits/{fm_id}_home',
            'kit_away_file': f'game/images/kits/{fm_id}_away',
            'kit_third_file': f'game/images/kits/{fm_id}_third',
        }
        uploaded = []

        crest_file = form.cleaned_data.get('crest_file')
        if crest_file:
            dest = f'game/images/crests/{fm_id}.{_ext(crest_file)}'
            _write_to_static(crest_file, dest)
            uploaded.append('Wappen')

        for field_name, base_path in kit_map.items():
            f = form.cleaned_data.get(field_name)
            if f:
                dest = f'{base_path}.{_ext(f)}'
                _write_to_static(f, dest)
                uploaded.append(field_name.replace('_file', '').replace('kit_', '').capitalize() + '-Trikot')

        if uploaded:
            messages.success(request, f'Bilder hochgeladen: {", ".join(uploaded)}.')


admin.site.register(League, LeagueAdmin)
admin.site.register(Club, ClubAdmin)


class ClubPublicProfileForm(forms.ModelForm):
    stadium_image_file = forms.FileField(
        required=False,
        label='Stadionbild hochladen',
        help_text='JPG/PNG — überschreibt das bestehende Bild.',
        widget=forms.ClearableFileInput(attrs={'accept': 'image/*'}),
    )
    city_image_file = forms.FileField(
        required=False,
        label='Stadtbild hochladen',
        help_text='JPG/PNG — überschreibt das bestehende Bild.',
        widget=forms.ClearableFileInput(attrs={'accept': 'image/*'}),
    )

    class Meta:
        model = ClubPublicProfile
        fields = '__all__'


@admin.register(ClubPublicProfile)
class ClubPublicProfileAdmin(admin.ModelAdmin):
    form = ClubPublicProfileForm
    list_display = (
        'club',
        'stadium_name',
        'city_name',
        'partner_club',
    )
    search_fields = (
        'club__name',
        'stadium_name',
        'city_name',
    )
    readonly_fields = ('stadium_image_preview', 'city_image_preview')

    fieldsets = (
        (None, {
            'fields': (
                'club', 'stadium_name', 'city_name', 'partner_club',
                'average_attendance',
            ),
        }),
        ('Stadionbild', {
            'fields': ('stadium_image_preview', 'stadium_image_static_path', 'stadium_image_file'),
            'description': 'Datei hochladen überschreibt das bestehende Bild im Static-Ordner.',
        }),
        ('Stadtbild', {
            'fields': ('city_image_preview', 'city_image_static_path', 'city_image_file'),
            'description': 'Datei hochladen überschreibt das bestehende Bild im Static-Ordner.',
        }),
    )

    @admin.display(description='Aktuelles Stadionbild')
    def stadium_image_preview(self, obj):
        if not obj or not obj.pk or not obj.stadium_image_static_path:
            return format_html('<span style="color:#999;">Noch kein Bild gesetzt.</span>')
        return format_html(
            '<img src="{}" alt="Stadion" style="max-width:320px;max-height:140px;'
            'object-fit:cover;border-radius:4px;border:1px solid #ccc;" />',
            static(obj.stadium_image_static_path),
        )

    @admin.display(description='Aktuelles Stadtbild')
    def city_image_preview(self, obj):
        if not obj or not obj.pk or not obj.city_image_static_path:
            return format_html('<span style="color:#999;">Noch kein Bild gesetzt.</span>')
        return format_html(
            '<img src="{}" alt="Stadt" style="max-width:320px;max-height:140px;'
            'object-fit:cover;border-radius:4px;border:1px solid #ccc;" />',
            static(obj.city_image_static_path),
        )

    def save_model(self, request, obj, form, change):
        stadium_file = form.cleaned_data.get('stadium_image_file')
        if stadium_file:
            ext = _ext(stadium_file)
            if obj.stadium_image_static_path:
                dest_path = obj.stadium_image_static_path
            elif obj.club and obj.club.fm_inside_id:
                dest_path = f'game/images/stadiums/germany/{obj.club.fm_inside_id}.{ext}'
            else:
                dest_path = f'game/images/stadiums/germany/{obj.pk or "new"}.{ext}'
            _write_to_static(stadium_file, dest_path)
            obj.stadium_image_static_path = dest_path

        city_file = form.cleaned_data.get('city_image_file')
        if city_file:
            ext = _ext(city_file)
            if obj.city_image_static_path:
                dest_path = obj.city_image_static_path
            elif obj.club and obj.club.fm_inside_id:
                dest_path = f'game/images/city/{obj.club.fm_inside_id}.{ext}'
            else:
                dest_path = f'game/images/city/{obj.pk or "new"}.{ext}'
            _write_to_static(city_file, dest_path)
            obj.city_image_static_path = dest_path

        super().save_model(request, obj, form, change)

        if stadium_file or city_file:
            messages.success(request, 'Bild(er) erfolgreich hochgeladen und gespeichert.')


@admin.register(ClubTrophy)
class ClubTrophyAdmin(admin.ModelAdmin):
    list_display = (
        'club',
        'competition_name',
        'count',
        'sort_order',
    )
    list_editable = ('count',)
    list_filter = ('club',)
    search_fields = (
        'club__name',
        'competition_name',
    )


def _record_heimspiel_einnahmen(modeladmin, request, queryset):
    """
    Admin-Aktion: Verbucht Spieltags-Einnahmen für ausgewählte Heimspiele.
    Nur Einträge, bei denen home_club ein Stadion hat und noch keine Einnahmen
    verbucht wurden, werden verarbeitet.
    """
    from .stadium_revenue import record_matchday_revenue

    ok = 0
    skip_no_stadium = 0
    skip_already = 0
    skip_no_home_club = 0

    for match in queryset.select_related('home_club__stadium'):
        if not match.home_club:
            skip_no_home_club += 1
            continue
        try:
            _ = match.home_club.stadium
        except Exception:
            skip_no_stadium += 1
            continue
        try:
            _ = match.matchday_revenue
            skip_already += 1
            continue
        except Exception:
            pass
        try:
            record_matchday_revenue(match.home_club, match_result=match)
            ok += 1
        except Exception as exc:
            modeladmin.message_user(
                request,
                f'Fehler bei {match}: {exc}',
                level=messages.ERROR,
            )

    parts = []
    if ok:
        parts.append(f'{ok} Heimspiel(e) erfolgreich verbucht')
    if skip_already:
        parts.append(f'{skip_already} bereits verbucht (übersprungen)')
    if skip_no_stadium:
        parts.append(f'{skip_no_stadium} kein Stadion (übersprungen)')
    if skip_no_home_club:
        parts.append(f'{skip_no_home_club} kein Heimverein (übersprungen)')

    if parts:
        modeladmin.message_user(request, ' | '.join(parts))


_record_heimspiel_einnahmen.short_description = 'Spieltags-Einnahmen verbuchen (Heimspiele)'


@admin.register(MatchResult)
class MatchResultAdmin(admin.ModelAdmin):
    list_display = (
        'club',
        'season',
        'competition_name',
        'matchday_label',
        'date_label',
        'home_club',
        'away_club',
        'home_goals',
        'away_goals',
        'result_label',
        'sort_order',
        '_hat_einnahmen',
    )
    list_filter = ('club', 'season', 'competition_name', 'result_label')
    search_fields = (
        'club__name',
        'competition_name',
        'matchday_label',
        'home_club__name',
        'away_club__name',
    )
    fieldsets = (
        (None, {
            'fields': ('club', 'season', 'sort_order'),
        }),
        ('Wettbewerb', {
            'fields': ('competition_name', 'matchday_label', 'date_label'),
        }),
        ('Spieldetails', {
            'fields': (
                'home_club',
                'away_club',
                'home_goals',
                'away_goals',
                'result_label',
            ),
        }),
    )
    ordering = ('club', 'sort_order', 'id')
    actions = [_record_heimspiel_einnahmen]

    @admin.display(description='Einnahmen', boolean=True)
    def _hat_einnahmen(self, obj):
        return hasattr(obj, 'matchday_revenue')


@admin.register(MatchdayRevenue)
class MatchdayRevenueAdmin(admin.ModelAdmin):
    list_display = (
        'stadium',
        'competition_name',
        'match_label',
        'attendance',
        'auslastung_pct',
        'revenue_total',
        'created_at',
    )
    list_filter = ('stadium__club', 'competition_name')
    search_fields = ('stadium__name', 'stadium__club__name', 'match_label', 'competition_name')
    readonly_fields = (
        'stadium',
        'match_result',
        'match_label',
        'competition_name',
        'auslastung_pct',
        'attendance',
        'revenue_standing',
        'revenue_seating',
        'revenue_vip',
        'revenue_total',
        'created_at',
    )
    ordering = ('-created_at',)


@admin.register(ClubNewsItem)
class ClubNewsItemAdmin(admin.ModelAdmin):
    list_display = (
        'club',
        'title',
        'published_at',
        'sort_order',
    )
    list_filter = ('club', 'published_at')
    search_fields = (
        'club__name',
        'title',
    )


@admin.register(TacticSetup)
class TacticSetupAdmin(admin.ModelAdmin):
    list_display = (
        'club',
        'squad_scope',
        'formation_code',
        'is_confirmed',
        'confirmed_at',
        'updated_at',
    )
    list_filter = ('squad_scope', 'is_confirmed')
    search_fields = ('club__name',)
    readonly_fields = ('updated_at',)


@admin.register(TacticTemplate)
class TacticTemplateAdmin(admin.ModelAdmin):
    list_display = (
        'club',
        'squad_scope',
        'name',
        'formation_code',
        'updated_at',
    )
    list_filter = ('squad_scope',)
    search_fields = ('club__name', 'name')
    readonly_fields = ('created_at', 'updated_at')


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
            ('complete', 'CMTracker + FM'),
            ('partial', 'nur eine Quelle'),
            ('default', 'Default 40.00'),
        )

    def queryset(self, request, queryset):
        queryset = queryset.annotate(
            ea_source_count=models.Count(
                'source_ratings',
                filter=models.Q(source_ratings__source=PlayerSourceRating.SOURCE_CMTRACKER),
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
            ('complete_sources', 'Vollstaendig CMTracker + FM'),
            ('fmi_only', 'Nur FMI / ohne CMTracker'),
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
                filter=models.Q(source_ratings__source=PlayerSourceRating.SOURCE_CMTRACKER),
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
                if not player.fm_inside_id
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
        'pool_status',
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
        'pool_status',
        'scouting_category',
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
                    'portrait_file',
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
                    'nt_nationality',
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
            'Scouting-Pool',
            {
                'fields': (
                    (
                        'pool_status',
                        'scouting_category',
                    ),
                    (
                        'wsc_conflict',
                        'is_callable',
                        'admin_reviewed',
                    ),
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

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        portrait_file = form.cleaned_data.get('portrait_file')
        if portrait_file:
            fm_id = obj.fm_inside_id
            if not fm_id:
                messages.warning(request, 'Spielerbild-Upload übersprungen: fm_inside_id ist nicht gesetzt.')
                return
            dest = f'game/images/players/{fm_id}.{_ext(portrait_file)}'
            _write_to_static(portrait_file, dest)
            messages.success(request, f'Spielerbild hochgeladen: {dest}')

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
            obj.portrait_static_path,
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
        'club',
        'season',
        'competition',
        'matches',
        'starts',
        'goals',
        'assists',
        'minutes_played',
        'yellow_cards',
        'dismissals',
        'average_grade',
        'rating_best',
        'rating_worst',
        'rating_count',
        'player_of_match_awards',
    )
    list_filter = ('season', 'club', 'player__main_position_1')
    search_fields = (
        'player__first_name',
        'player__last_name',
        'club__name',
        'competition',
    )
    readonly_fields = ('rating_sum', 'rating_count', 'created_at', 'updated_at')
    ordering = ('-season', 'competition', 'average_grade')


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
        'display_full_name',
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

    @admin.display(description='Name', ordering='last_name')
    def display_full_name(self, obj):
        return obj.full_name

    def get_queryset(self, request):
        queryset = super().get_queryset(request).select_related(
            'club',
            'real_life_club',
        ).prefetch_related('source_ratings')
        queryset = queryset.annotate(
            ea_source_count=models.Count(
                'source_ratings',
                filter=models.Q(source_ratings__source=PlayerSourceRating.SOURCE_CMTRACKER),
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


class ManagerCareerStationInline(admin.TabularInline):
    model = ManagerCareerStation
    extra = 0
    fields = (
        'order',
        'club',
        'city_name',
        'city_country',
        'map_x',
        'map_y',
        'started_at',
        'ended_at',
        'games_played',
    )
    ordering = ('order',)


@admin.register(ManagerProfile)
class ManagerProfileAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'user',
        'trainer_type',
        'level',
        'xp',
        'member_since',
        'updated_at',
    )
    search_fields = ('name', 'user__username')
    list_filter = ('trainer_type',)
    readonly_fields = ('updated_at',)
    inlines = [ManagerCareerStationInline]


@admin.register(ManagerCareerStation)
class ManagerCareerStationAdmin(admin.ModelAdmin):
    list_display = (
        'manager',
        'order',
        'club',
        'city_name',
        'city_country',
        'started_at',
        'ended_at',
        'games_played',
    )
    list_filter = ('manager',)
    search_fields = ('manager__name', 'city_name', 'club__name')
    ordering = ('manager', 'order')


@admin.register(SeasonGoal)
class SeasonGoalAdmin(admin.ModelAdmin):
    list_display = (
        'club',
        'season_number',
        'goal_tier',
        'rank_in_league',
        'league_size',
        'required_max_rank',
        'final_rank',
        'achieved',
        'declared_at',
    )
    list_filter = ('season_number', 'goal_tier', 'achieved')
    search_fields = ('club__name',)
    readonly_fields = ('declared_at', 'evaluated_at')


@admin.register(HoenessCoin)
class HoenessCoinAdmin(admin.ModelAdmin):
    list_display = ('manager', 'amount', 'updated_at')
    search_fields = ('manager__name',)
    readonly_fields = ('updated_at',)


@admin.register(CoinTransaction)
class CoinTransactionAdmin(admin.ModelAdmin):
    list_display = ('manager', 'amount', 'reason', 'description', 'created_at')
    list_filter = ('reason',)
    search_fields = ('manager__name', 'description')
    readonly_fields = ('created_at',)


@admin.register(GameSeasonState)
class GameSeasonStateAdmin(admin.ModelAdmin):
    list_display = ('current_season', 'is_started', 'started_at', 'updated_at')
    readonly_fields = ('updated_at',)
    actions = ['evaluate_season_goals_action']

    @admin.action(description='Saison abschließen & Ziele auswerten (alle Manager-Vereine)')
    def evaluate_season_goals_action(self, request, queryset):
        """Wertet offene Saisonziele für alle Vereine mit Manager aus.

        Verwendet die aktuelle Saisonnummer aus dem (einzigen) GameSeasonState-
        Singleton. Die Coin-Vergabe ist idempotent — ein bereits gutgeschriebener
        Coin wird nicht ein zweites Mal vergeben, egal wie oft die Aktion läuft.
        """
        managed_clubs = Club.objects.filter(managed_by__isnull=False).select_related(
            'managed_by', 'league'
        )
        state = queryset.first()
        season_number = state.current_season if state else None
        achieved = 0
        not_achieved = 0
        skipped = 0

        for club in managed_clubs:
            goal = evaluate_goal_for_club(club, season_number=season_number)
            if goal is None:
                skipped += 1
            elif goal.achieved:
                achieved += 1
            else:
                not_achieved += 1

        self.message_user(
            request,
            (
                f'Auswertung abgeschlossen: {achieved} Ziel(e) erfüllt '
                f'(Coin vergeben), {not_achieved} nicht erfüllt, '
                f'{skipped} ohne gespeichertes Ziel übersprungen.'
            ),
            messages.SUCCESS,
        )


@admin.register(PresidentSatisfaction)
class PresidentSatisfactionAdmin(admin.ModelAdmin):
    list_display = ('manager', 'club', 'satisfaction_display', 'updated_at')
    list_filter = ('value',)
    search_fields = ('manager__name', 'club__name')
    ordering = ('value', '-updated_at')
    readonly_fields = ('updated_at',)

    @admin.display(description='Zufriedenheit')
    def satisfaction_display(self, obj):
        if obj.value == 0:
            color = '#c0392b'
        elif obj.value < 50:
            color = '#e67e22'
        elif obj.value < 100:
            color = '#27ae60'
        else:
            color = '#2980b9'
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 10px;'
            'border-radius:4px;font-weight:bold;font-size:12px;">{}&nbsp;%</span>',
            color,
            obj.value,
        )


@admin.register(ManagerAtRisk)
class ManagerAtRiskAdmin(admin.ModelAdmin):
    """Admin-Übersicht: Entlassungskandidaten — Manager mit Zufriedenheit 0 %."""

    list_display = ('manager', 'club', 'updated_at')
    search_fields = ('manager__name', 'club__name')
    ordering = ('-updated_at',)
    readonly_fields = ('manager', 'club', 'value', 'updated_at')

    def get_queryset(self, request):
        return super().get_queryset(request).filter(value=0)

    def has_add_permission(self, request):
        return False


# ── Sportgericht ───────────────────────────────────────────────────────────────

from .models import InactivityRecord, InactivityPenalty, SupportTicket  # noqa: E402


@admin.register(InactivityRecord)
class InactivityRecordAdmin(admin.ModelAdmin):
    list_display  = ('manager', 'club', 'squad_scope', 'season', 'matchday_label', 'recorded_at')
    list_filter   = ('squad_scope', 'season')
    search_fields = ('manager__name', 'club__name', 'matchday_label')
    ordering      = ('-recorded_at',)
    readonly_fields = ('recorded_at',)


@admin.register(InactivityPenalty)
class InactivityPenaltyAdmin(admin.ModelAdmin):
    list_display  = ('manager', 'given_at', 'reason')
    search_fields = ('manager__name',)
    ordering      = ('-given_at',)
    readonly_fields = ('given_at',)


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display   = ('id', 'title', 'manager', 'status', 'created_at', 'has_screenshot')
    list_filter    = ('status',)
    search_fields  = ('title', 'manager__name', 'description')
    ordering       = ('-created_at',)
    readonly_fields = ('manager', 'title', 'description', 'screenshot', 'created_at')
    fields         = ('manager', 'title', 'description', 'screenshot', 'status', 'admin_response', 'created_at', 'closed_at')

    @admin.display(description='Screenshot', boolean=True)
    def has_screenshot(self, obj):
        return bool(obj.screenshot)


@admin.register(ClubFinancialTransaction)
class ClubFinancialTransactionAdmin(admin.ModelAdmin):
    list_display  = ('date', 'club', 'category', 'description', 'amount', 'season')
    list_filter   = ('club', 'category', 'season')
    search_fields = ('description', 'club__name')
    ordering      = ('-date', '-created_at')
    date_hierarchy = 'date'
    fields        = ('club', 'date', 'season', 'category', 'description', 'amount')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('club')


@admin.register(ClubSponsor)
class ClubSponsorAdmin(admin.ModelAdmin):
    list_display  = ('club', 'sponsor_type', 'name', 'amount_per_season', 'season', 'is_active')
    list_filter   = ('club', 'sponsor_type', 'season', 'is_active')
    search_fields = ('name', 'club__name')
    ordering      = ('club', 'sponsor_type')
    fields        = ('club', 'name', 'sponsor_type', 'amount_per_season', 'season', 'is_active')


@admin.register(LeagueNews)
class LeagueNewsAdmin(admin.ModelAdmin):
    list_display   = ('league', 'title', 'published_at', 'sort_order')
    list_filter    = ('league',)
    search_fields  = ('title', 'body')
    ordering       = ('league', 'sort_order', '-published_at')
    fields         = ('league', 'title', 'published_at', 'thumbnail_static_path', 'body', 'sort_order')
    date_hierarchy = 'published_at'


@admin.register(LeagueStandings)
class LeagueStandingsAdmin(admin.ModelAdmin):
    list_display   = (
        'league', 'season', 'position', 'club', 'played',
        'won', 'drawn', 'lost', 'goals_display', 'points', 'point_deduction', 'form',
    )
    list_filter    = ('league', 'season')
    search_fields  = ('club__name',)
    ordering       = ('league', 'season', 'position')
    fields         = (
        'league', 'club', 'season',
        'position', 'position_change',
        'played', 'won', 'drawn', 'lost',
        'goals_for', 'goals_against',
        'points', 'point_deduction',
        'form',
    )

    @admin.display(description='Tore')
    def goals_display(self, obj):
        return f'{obj.goals_for}:{obj.goals_against}'


from .models import CupSeason, CupRound, CupFixture  # noqa: E402


@admin.register(CupSeason)
class CupSeasonAdmin(admin.ModelAdmin):
    list_display  = ('competition', 'season', 'status', 'winner_club', 'participant_count')
    list_filter   = ('status', 'competition')
    search_fields = ('competition__name', 'season', 'winner_club__name')
    ordering      = ('-season', 'competition')
    filter_horizontal = ('participants',)

    @admin.display(description='Teilnehmer')
    def participant_count(self, obj):
        return obj.participants.count()


@admin.register(CupRound)
class CupRoundAdmin(admin.ModelAdmin):
    list_display  = ('cup_season', 'round_number', 'round_code', 'status', 'scheduled_date', 'fixture_count')
    list_filter   = ('status', 'cup_season__competition')
    search_fields = ('cup_season__competition__name', 'round_code')
    ordering      = ('cup_season', 'round_number')

    @admin.display(description='Spiele')
    def fixture_count(self, obj):
        return obj.fixtures.count()


@admin.register(CupFixture)
class CupFixtureAdmin(admin.ModelAdmin):
    list_display  = ('cup_round', 'bracket_position', 'home_club', 'away_club', 'score_display', 'winner_club', 'status')
    list_filter   = ('status', 'decided_by', 'is_bye')
    search_fields = ('home_club__name', 'away_club__name', 'winner_club__name')
    ordering      = ('cup_round', 'bracket_position')
    readonly_fields = ('score_display',)

    @admin.display(description='Ergebnis')
    def score_display(self, obj):
        return obj.score_display


@admin.register(SeasonFixture)
class SeasonFixtureAdmin(admin.ModelAdmin):
    list_display   = (
        'league', 'season', 'matchday',
        'home_club', 'result_or_dash', 'away_club',
        'scheduled_date', 'scheduled_time', 'is_played',
    )
    list_filter    = ('league', 'season', 'matchday', 'is_played')
    search_fields  = ('home_club__name', 'away_club__name')
    ordering       = ('league', 'season', 'matchday', 'scheduled_date', 'scheduled_time')
    fields         = (
        'league', 'season', 'matchday',
        'home_club', 'away_club',
        'scheduled_date', 'scheduled_time',
        'home_goals', 'away_goals', 'is_played',
        'home_lineup_set', 'away_lineup_set',
        'home_lineup_malus', 'away_lineup_malus',
    )

    @admin.display(description='Ergebnis')
    def result_or_dash(self, obj):
        if obj.is_played and obj.home_goals is not None and obj.away_goals is not None:
            return f'{obj.home_goals}:{obj.away_goals}'
        return '—'


# ── Scouting-System (Task #594) ───────────────────────────────────────────────
from .models import (
    ScoutingDepartment,
    ScoutingAssignment,
    ScoutingFind,
    ScoutingBid,
    WatchlistEntry,
    CountryNetwork,
    CommunitySubmission,
)


@admin.register(ScoutingDepartment)
class ScoutingDepartmentAdmin(admin.ModelAdmin):
    list_display = ('club', 'level')
    search_fields = ('club__name',)


@admin.register(ScoutingAssignment)
class ScoutingAssignmentAdmin(admin.ModelAdmin):
    list_display = (
        'club', 'scope_type', 'scope_key', 'profile', 'position',
        'status', 'finds_generated', 'started_on', 'completes_on', 'season_id',
    )
    list_filter = ('status', 'scope_type', 'finds_generated')
    search_fields = ('club__name', 'scope_key')


@admin.register(ScoutingFind)
class ScoutingFindAdmin(admin.ModelAdmin):
    list_display = ('assignment', 'order', 'player', 'min_bid', 'observer_count', 'status')
    list_filter = ('status',)
    search_fields = ('player__first_name', 'player__last_name')


@admin.register(ScoutingBid)
class ScoutingBidAdmin(admin.ModelAdmin):
    list_display = ('club', 'player', 'amount', 'min_bid', 'window_date', 'status', 'season_id')
    list_filter = ('status',)
    search_fields = ('club__name', 'player__first_name', 'player__last_name')


@admin.register(WatchlistEntry)
class WatchlistEntryAdmin(admin.ModelAdmin):
    list_display = ('manager', 'player', 'status', 'updated_at')
    list_filter = ('status',)
    search_fields = ('player__first_name', 'player__last_name')


class CountryNetworkAdminForm(forms.ModelForm):
    class Meta:
        model = CountryNetwork
        fields = '__all__'

    def clean_iso2(self):
        value = (self.cleaned_data.get('iso2') or '').strip().upper()
        if not (len(value) == 2 and value.isalpha() and value.isascii()):
            raise ValidationError('Der ISO2-Code muss aus genau 2 Buchstaben (A–Z) bestehen.')
        qs = CountryNetwork.objects.filter(iso2=value)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError(f'Ein Land mit dem ISO2-Code „{value}" existiert bereits.')
        return value


@admin.register(CountryNetwork)
class CountryNetworkAdmin(admin.ModelAdmin):
    form = CountryNetworkAdminForm
    list_display = (
        'iso2', 'name', 'continent', 'region',
        'community_points', 'activity_points', 'is_paused',
    )
    list_filter = ('is_paused', 'continent', 'region')
    list_editable = ('community_points', 'activity_points', 'is_paused')
    search_fields = ('iso2', 'name', 'continent', 'region')
    ordering = ('name',)
    list_per_page = 50


@admin.register(CommunitySubmission)
class CommunitySubmissionAdmin(admin.ModelAdmin):
    list_display = ('manager', 'iso2', 'player_name', 'status', 'week_key', 'created_at')
    list_filter = ('status', 'iso2')
    search_fields = ('player_name', 'manager__name')
