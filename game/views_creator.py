import os
from decimal import Decimal, InvalidOperation

from django.apps import apps
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import (
    Club, COUNTRY_FLAG_ASSETS, League, Player,
    Stadium, ClubPublicProfile, ClubTrophy, ClubSponsor, SeasonGoal,
    ManagerProfile, ManagerCareerStation, HoenessCoin, CoinTransaction,
    PresidentSatisfaction,
)

STATIC_BASE = 'game/static'
POSITION_CHOICES = [
    ('', '----------'),
    ('TW', 'TW'), ('IV', 'IV'), ('LI', 'LI'), ('LV', 'LV'),
    ('RV', 'RV'), ('LOV', 'LOV'), ('ROV', 'ROV'), ('DM', 'DM'),
    ('ZM', 'ZM'), ('LM', 'LM'), ('RM', 'RM'), ('LOM', 'LOM'),
    ('ROM', 'ROM'), ('OM', 'OM'), ('LF', 'LF'), ('RF', 'RF'), ('ST', 'ST'),
]
NATIONALITY_CHOICES = [''] + sorted(COUNTRY_FLAG_ASSETS.keys())


def _static_file_path(rel_path):
    full = os.path.join(STATIC_BASE, rel_path)
    return rel_path if os.path.exists(full) else ''


def _save_as_jpg(file_obj, dest_path):
    from PIL import Image as PILImage
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    img = PILImage.open(file_obj).convert('RGB')
    img.save(dest_path, 'JPEG', quality=90)


def _save_as_png(file_obj, dest_path):
    from PIL import Image as PILImage
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    img = PILImage.open(file_obj).convert('RGBA')
    img.save(dest_path, 'PNG')


def creator_index(request):
    country_filter = request.GET.get('country', '').strip()
    league_filter = request.GET.get('league', '').strip()

    # ── Level 3: Vereine einer Liga ──────────────────────────────────────────
    if league_filter:
        league = get_object_or_404(League, id=league_filter)
        clubs = list(league.club_set.order_by('name'))
        flag_code = (
            COUNTRY_FLAG_ASSETS.get(league.country or '', {}).get('code', '').lower()
        )
        return render(request, 'creator/index.html', {
            'level': 3,
            'league': league,
            'clubs': clubs,
            'country': league.country,
            'flag_code': flag_code,
        })

    # ── Level 2: Ligen eines Landes ──────────────────────────────────────────
    if country_filter:
        leagues_qs = League.objects.filter(country=country_filter).order_by('name')
        flag_code = (
            COUNTRY_FLAG_ASSETS.get(country_filter, {}).get('code', '').lower()
        )
        leagues_data = []
        for lg in leagues_qs:
            leagues_data.append({
                'league': lg,
                'club_count': lg.club_set.count(),
            })
        return render(request, 'creator/index.html', {
            'level': 2,
            'country': country_filter,
            'flag_code': flag_code,
            'leagues_data': leagues_data,
        })

    # ── Level 1: Länder ───────────────────────────────────────────────────────
    from django.db.models import Count
    country_rows = (
        League.objects
        .values('country')
        .annotate(league_count=Count('id'))
        .order_by('country')
    )
    countries_data = []
    for row in country_rows:
        name = row['country'] or 'Unbekannt'
        code = COUNTRY_FLAG_ASSETS.get(name, {}).get('code', '').lower()
        countries_data.append({
            'name': name,
            'code': code,
            'league_count': row['league_count'],
        })
    return render(request, 'creator/index.html', {
        'level': 1,
        'countries_data': countries_data,
        'total_clubs': Club.objects.count(),
        'total_players': Player.objects.count(),
    })


def creator_club_edit(request, club_id):
    club = get_object_or_404(Club, id=club_id)
    profile, _ = ClubPublicProfile.objects.get_or_create(club=club)

    players = Player.objects.filter(club=club).order_by('last_name', 'first_name')

    kits = []
    for kit_type, label in [('home', 'Heim'), ('away', 'Auswärts'), ('third', 'Third')]:
        found_path = None
        for ext in ['png', 'svg']:
            rel = f'game/images/kits/{club.fm_inside_id}_{kit_type}.{ext}'
            if os.path.exists(os.path.join(STATIC_BASE, rel)):
                found_path = rel
                break
        kits.append({'type': kit_type, 'label': label, 'path': found_path})

    stadium_path = _static_file_path(profile.stadium_image_static_path) if profile.stadium_image_static_path else ''
    city_path = _static_file_path(profile.city_image_static_path) if profile.city_image_static_path else ''
    crest_path = club.crest_static_path

    try:
        stadium = club.stadium
    except Stadium.DoesNotExist:
        stadium = None

    trophies = ClubTrophy.objects.filter(club=club).order_by('sort_order', 'competition_name')
    sponsors = ClubSponsor.objects.filter(club=club).order_by('sponsor_type', 'name')
    goals = SeasonGoal.objects.filter(club=club).order_by('-season_number')
    all_clubs = Club.objects.exclude(id=club_id).order_by('name')

    active_tab = request.GET.get('tab', 'bilder')

    return render(request, 'creator/club_edit.html', {
        'club': club,
        'profile': profile,
        'players': players,
        'kits': kits,
        'stadium_path': stadium_path,
        'city_path': city_path,
        'crest_path': crest_path,
        'stadium': stadium,
        'trophies': trophies,
        'sponsors': sponsors,
        'goals': goals,
        'all_clubs': all_clubs,
        'active_tab': active_tab,
        'all_leagues': League.objects.order_by('name'),
        'sponsor_type_choices': ClubSponsor.TYPE_CHOICES,
        'goal_tier_choices': SeasonGoal.TIER_CHOICES,
    })


@require_POST
def creator_upload_stadium(request, club_id):
    club = get_object_or_404(Club, id=club_id)
    ClubPublicProfile = apps.get_model('game', 'ClubPublicProfile')
    profile, _ = ClubPublicProfile.objects.get_or_create(club=club)
    f = request.FILES.get('image')
    if not f:
        messages.error(request, 'Keine Datei ausgewählt.')
        return redirect('creator_club_edit', club_id=club_id)
    rel = f'game/images/stadiums/germany/{club.fm_inside_id}.jpg'
    _save_as_jpg(f, os.path.join(STATIC_BASE, rel))
    profile.stadium_image_static_path = rel
    profile.save(update_fields=['stadium_image_static_path'])
    messages.success(request, 'Stadionbild gespeichert.')
    return redirect('creator_club_edit', club_id=club_id)


@require_POST
def creator_upload_city(request, club_id):
    club = get_object_or_404(Club, id=club_id)
    ClubPublicProfile = apps.get_model('game', 'ClubPublicProfile')
    profile, _ = ClubPublicProfile.objects.get_or_create(club=club)
    f = request.FILES.get('image')
    if not f:
        messages.error(request, 'Keine Datei ausgewählt.')
        return redirect('creator_club_edit', club_id=club_id)
    rel = f'game/images/city/{club.fm_inside_id}.jpg'
    _save_as_jpg(f, os.path.join(STATIC_BASE, rel))
    profile.city_image_static_path = rel
    profile.save(update_fields=['city_image_static_path'])
    messages.success(request, 'Citypic gespeichert.')
    return redirect('creator_club_edit', club_id=club_id)


@require_POST
def creator_upload_kit(request, club_id, kit_type):
    club = get_object_or_404(Club, id=club_id)
    if kit_type not in ['home', 'away', 'third']:
        messages.error(request, 'Ungültiger Trikot-Typ.')
        return redirect('creator_club_edit', club_id=club_id)
    f = request.FILES.get('image')
    if not f:
        messages.error(request, 'Keine Datei ausgewählt.')
        return redirect('creator_club_edit', club_id=club_id)
    for ext in ['png', 'svg', 'jpg', 'webp']:
        old = os.path.join(STATIC_BASE, f'game/images/kits/{club.fm_inside_id}_{kit_type}.{ext}')
        if os.path.exists(old):
            os.remove(old)
    dest = os.path.join(STATIC_BASE, f'game/images/kits/{club.fm_inside_id}_{kit_type}.png')
    _save_as_png(f, dest)
    messages.success(request, f'Trikot ({kit_type}) gespeichert.')
    return redirect('creator_club_edit', club_id=club_id)


@require_POST
def creator_upload_crest(request, club_id):
    club = get_object_or_404(Club, id=club_id)
    f = request.FILES.get('image')
    if not f:
        messages.error(request, 'Keine Datei ausgewählt.')
        return redirect('creator_club_edit', club_id=club_id)
    for ext in ['png', 'svg', 'jpg', 'webp']:
        old = os.path.join(STATIC_BASE, f'game/images/crests/{club.fm_inside_id}.{ext}')
        if os.path.exists(old):
            os.remove(old)
    dest = os.path.join(STATIC_BASE, f'game/images/crests/{club.fm_inside_id}.png')
    _save_as_png(f, dest)
    messages.success(request, 'Vereinswappen gespeichert.')
    return redirect('creator_club_edit', club_id=club_id)


def creator_player_edit(request, player_id):
    player = get_object_or_404(Player, id=player_id)
    all_clubs = Club.objects.order_by('name')

    if request.method == 'POST':
        player.first_name = request.POST.get('first_name', player.first_name).strip()
        player.last_name = request.POST.get('last_name', player.last_name).strip()

        club_id = request.POST.get('club')
        if club_id:
            try:
                player.club = Club.objects.get(id=int(club_id))
            except Club.DoesNotExist:
                pass

        rl_club_id = request.POST.get('real_life_club')
        if rl_club_id:
            try:
                player.real_life_club = Club.objects.get(id=int(rl_club_id))
            except Club.DoesNotExist:
                pass
        elif rl_club_id == '':
            player.real_life_club = None

        for field in ['main_position_1', 'main_position_2', 'main_position_3',
                      'secondary_position_1', 'secondary_position_2', 'secondary_position_3',
                      'strong_foot']:
            val = request.POST.get(field, '')
            setattr(player, field, val)

        dob = request.POST.get('date_of_birth', '')
        if dob:
            from datetime import date as date_type
            try:
                from datetime import datetime
                player.date_of_birth = datetime.strptime(dob, '%Y-%m-%d').date()
                from datetime import date
                today = date.today()
                player.age = today.year - player.date_of_birth.year - (
                    (today.month, today.day) < (player.date_of_birth.month, player.date_of_birth.day)
                )
            except ValueError:
                pass

        height = request.POST.get('height_cm', '')
        if height:
            try:
                player.height_cm = int(height)
            except ValueError:
                pass

        nat1 = request.POST.get('nationality_1', '').strip()
        nat2 = request.POST.get('nationality_2', '').strip()
        nats = [n for n in [nat1, nat2] if n]
        player.nationalities = ','.join(nats)

        for dec_field in ['market_value', 'salary_per_match']:
            val = request.POST.get(dec_field, '').strip().replace(',', '.')
            if val:
                try:
                    setattr(player, dec_field, Decimal(val))
                except InvalidOperation:
                    pass

        contract = request.POST.get('contract_until', '')
        if contract:
            try:
                from datetime import datetime
                player.contract_until = datetime.strptime(contract, '%Y-%m-%d').date()
            except (ValueError, AttributeError):
                pass

        player.ws_injury_type = request.POST.get('ws_injury_type', '').strip()
        try:
            player.ws_injury_days_remaining = int(request.POST.get('ws_injury_days_remaining', 0))
        except ValueError:
            pass

        player.ws_suspension_reason = request.POST.get('ws_suspension_reason', '').strip()
        try:
            player.ws_suspension_matches_remaining = int(request.POST.get('ws_suspension_matches_remaining', 0))
        except ValueError:
            pass

        player.save()

        portrait_file = request.FILES.get('portrait')
        if portrait_file and player.fm_inside_id:
            dest = os.path.join(STATIC_BASE, f'game/images/players/{player.fm_inside_id}.png')
            _save_as_png(portrait_file, dest)

        action = request.POST.get('action', 'save')
        if action == 'save_new':
            messages.success(request, f'{player.first_name} {player.last_name} gespeichert.')
            return redirect('creator_new_player', club_id=player.club_id)
        elif action == 'save_continue':
            messages.success(request, 'Gespeichert.')
            return redirect('creator_player_edit', player_id=player.id)
        else:
            messages.success(request, f'{player.first_name} {player.last_name} gespeichert.')
            return redirect('creator_club_edit', club_id=player.club_id)

    nats = [n.strip() for n in (player.nationalities or '').split(',') if n.strip()]
    nat1 = nats[0] if len(nats) > 0 else ''
    nat2 = nats[1] if len(nats) > 1 else ''

    portrait_path = player.portrait_static_path if player.fm_inside_id else ''

    return render(request, 'creator/player_edit.html', {
        'player': player,
        'all_clubs': all_clubs,
        'position_choices': POSITION_CHOICES,
        'nationality_choices': NATIONALITY_CHOICES,
        'nat1': nat1,
        'nat2': nat2,
        'portrait_path': portrait_path,
    })


def creator_new_player(request, club_id):
    club = get_object_or_404(Club, id=club_id)
    all_clubs = Club.objects.order_by('name')

    if request.method == 'POST':
        from datetime import date
        player = Player(
            first_name=request.POST.get('first_name', '').strip(),
            last_name=request.POST.get('last_name', '').strip(),
            club=club,
            age=0,
        )
        club_id_post = request.POST.get('club')
        if club_id_post:
            try:
                player.club = Club.objects.get(id=int(club_id_post))
            except Club.DoesNotExist:
                pass

        for field in ['main_position_1', 'main_position_2', 'main_position_3',
                      'secondary_position_1', 'secondary_position_2', 'secondary_position_3',
                      'strong_foot']:
            setattr(player, field, request.POST.get(field, ''))

        dob = request.POST.get('date_of_birth', '')
        if dob:
            try:
                from datetime import datetime
                player.date_of_birth = datetime.strptime(dob, '%Y-%m-%d').date()
                today = date.today()
                player.age = today.year - player.date_of_birth.year - (
                    (today.month, today.day) < (player.date_of_birth.month, player.date_of_birth.day)
                )
            except ValueError:
                pass

        height = request.POST.get('height_cm', '')
        if height:
            try:
                player.height_cm = int(height)
            except ValueError:
                pass

        nat1 = request.POST.get('nationality_1', '').strip()
        nat2 = request.POST.get('nationality_2', '').strip()
        player.nationalities = ','.join(n for n in [nat1, nat2] if n)

        for dec_field in ['market_value', 'salary_per_match']:
            val = request.POST.get(dec_field, '').replace(',', '.')
            if val:
                try:
                    setattr(player, dec_field, Decimal(val))
                except InvalidOperation:
                    pass

        player.ws_injury_type = request.POST.get('ws_injury_type', '').strip()
        player.ws_suspension_reason = request.POST.get('ws_suspension_reason', '').strip()

        player.save()
        messages.success(request, f'{player.first_name} {player.last_name} hinzugefügt.')

        action = request.POST.get('action', 'save')
        if action == 'save_new':
            return redirect('creator_new_player', club_id=player.club_id)
        elif action == 'save_continue':
            return redirect('creator_player_edit', player_id=player.id)
        return redirect('creator_club_edit', club_id=player.club_id)

    return render(request, 'creator/player_edit.html', {
        'player': None,
        'club': club,
        'all_clubs': all_clubs,
        'position_choices': POSITION_CHOICES,
        'nationality_choices': NATIONALITY_CHOICES,
        'nat1': '',
        'nat2': '',
        'portrait_path': '',
    })


def _redirect_tab(club_id, tab):
    from django.urls import reverse
    return redirect(reverse('creator_club_edit', args=[club_id]) + f'?tab={tab}')


@require_POST
def creator_save_stammdaten(request, club_id):
    club = get_object_or_404(Club, id=club_id)
    profile, _ = ClubPublicProfile.objects.get_or_create(club=club)

    club.name = request.POST.get('name', club.name).strip()
    club.short_name = request.POST.get('short_name', club.short_name).strip()

    founded = request.POST.get('founded_year', '').strip()
    if founded:
        try:
            club.founded_year = int(founded)
        except ValueError:
            pass

    budget_raw = request.POST.get('budget', '').strip().replace(',', '.')
    if budget_raw:
        try:
            club.budget = Decimal(budget_raw)
        except InvalidOperation:
            pass

    fan = request.POST.get('fan_popularity', '').strip()
    if fan:
        try:
            club.fan_popularity = max(1, min(100, int(fan)))
        except ValueError:
            pass

    league_id = request.POST.get('league', '').strip()
    if league_id:
        try:
            club.league = League.objects.get(id=int(league_id))
        except (League.DoesNotExist, ValueError):
            pass

    club.save()

    profile.city_name = request.POST.get('city_name', '').strip()
    profile.city_country = request.POST.get('city_country', '').strip()
    lat = request.POST.get('map_lat', '').strip()
    lng = request.POST.get('map_lng', '').strip()
    try:
        profile.map_lat = float(lat) if lat else None
    except ValueError:
        profile.map_lat = None
    try:
        profile.map_lng = float(lng) if lng else None
    except ValueError:
        profile.map_lng = None

    partner_id = request.POST.get('partner_club', '').strip()
    if partner_id:
        try:
            profile.partner_club = Club.objects.get(id=int(partner_id))
        except (Club.DoesNotExist, ValueError):
            profile.partner_club = None
    else:
        profile.partner_club = None

    profile.save()
    messages.success(request, 'Stammdaten gespeichert.')
    return _redirect_tab(club_id, 'stammdaten')


# ─── Club: Infrastruktur ──────────────────────────────────────────────────────

@require_POST
def creator_save_infrastruktur(request, club_id):
    club = get_object_or_404(Club, id=club_id)
    try:
        stadium = club.stadium
    except Stadium.DoesNotExist:
        stadium = Stadium(club=club, name=club.name, city='')

    sname = request.POST.get('stadium_name', '').strip()
    if sname:
        stadium.name = sname
    scity = request.POST.get('stadium_city', '').strip()
    if scity:
        stadium.city = scity

    for field in ['nlz_level', 'medizin_level', 'training_level', 'office_level']:
        val = request.POST.get(field, '').strip()
        if val:
            try:
                setattr(stadium, field, max(0, min(3, int(val))))
            except ValueError:
                pass

    stadium.save()
    messages.success(request, 'Infrastruktur gespeichert.')
    return _redirect_tab(club_id, 'infrastruktur')


# ─── Club: Pokale ─────────────────────────────────────────────────────────────

@require_POST
def creator_add_trophy(request, club_id):
    club = get_object_or_404(Club, id=club_id)
    comp = request.POST.get('competition_name', '').strip()
    if not comp:
        messages.error(request, 'Wettbewerbsname erforderlich.')
        return _redirect_tab(club_id, 'pokale')

    count_raw = request.POST.get('count', '1').strip()
    try:
        count = max(1, int(count_raw))
    except ValueError:
        count = 1

    asset_id = request.POST.get('trophy_asset_id', '').strip()
    if not asset_id:
        asset_id = ClubTrophy.COMPETITION_DEFAULT_ASSETS.get(comp, '')

    sort_raw = request.POST.get('sort_order', '0').strip()
    try:
        sort_order = int(sort_raw)
    except ValueError:
        sort_order = 0

    ClubTrophy.objects.create(
        club=club,
        competition_name=comp,
        count=count,
        trophy_asset_id=asset_id,
        sort_order=sort_order,
    )
    messages.success(request, f'Pokal "{comp}" hinzugefügt.')
    return _redirect_tab(club_id, 'pokale')


@require_POST
def creator_delete_trophy(request, club_id, trophy_id):
    club = get_object_or_404(Club, id=club_id)
    trophy = get_object_or_404(ClubTrophy, id=trophy_id, club=club)
    name = trophy.competition_name
    trophy.delete()
    messages.success(request, f'"{name}" entfernt.')
    return _redirect_tab(club_id, 'pokale')


@require_POST
def creator_edit_trophy(request, club_id, trophy_id):
    club = get_object_or_404(Club, id=club_id)
    trophy = get_object_or_404(ClubTrophy, id=trophy_id, club=club)

    comp = request.POST.get('competition_name', '').strip()
    if comp:
        trophy.competition_name = comp

    count_raw = request.POST.get('count', '').strip()
    if count_raw:
        try:
            trophy.count = max(1, int(count_raw))
        except ValueError:
            pass

    asset_id = request.POST.get('trophy_asset_id', '').strip()
    trophy.trophy_asset_id = asset_id

    sort_raw = request.POST.get('sort_order', '').strip()
    if sort_raw:
        try:
            trophy.sort_order = int(sort_raw)
        except ValueError:
            pass

    trophy.save()
    messages.success(request, f'"{trophy.competition_name}" aktualisiert.')
    return _redirect_tab(club_id, 'pokale')


# ─── Club: Sponsoring ─────────────────────────────────────────────────────────

@require_POST
def creator_add_sponsor(request, club_id):
    club = get_object_or_404(Club, id=club_id)
    name = request.POST.get('name', '').strip()
    sponsor_type = request.POST.get('sponsor_type', 'sonstig').strip()
    amount_raw = request.POST.get('amount_per_season', '0').strip().replace(',', '.')
    season = request.POST.get('season', '').strip()

    if not name:
        messages.error(request, 'Sponsorname erforderlich.')
        return _redirect_tab(club_id, 'sponsoring')

    try:
        amount = Decimal(amount_raw)
    except InvalidOperation:
        amount = Decimal('0')

    ClubSponsor.objects.create(
        club=club,
        name=name,
        sponsor_type=sponsor_type,
        amount_per_season=amount,
        season=season,
        is_active=True,
    )
    messages.success(request, f'Sponsor "{name}" hinzugefügt.')
    return _redirect_tab(club_id, 'sponsoring')


@require_POST
def creator_delete_sponsor(request, club_id, sponsor_id):
    club = get_object_or_404(Club, id=club_id)
    sponsor = get_object_or_404(ClubSponsor, id=sponsor_id, club=club)
    name = sponsor.name
    sponsor.delete()
    messages.success(request, f'Sponsor "{name}" entfernt.')
    return _redirect_tab(club_id, 'sponsoring')


@require_POST
def creator_toggle_sponsor(request, club_id, sponsor_id):
    club = get_object_or_404(Club, id=club_id)
    sponsor = get_object_or_404(ClubSponsor, id=sponsor_id, club=club)
    sponsor.is_active = not sponsor.is_active
    sponsor.save(update_fields=['is_active'])
    status = 'aktiviert' if sponsor.is_active else 'deaktiviert'
    messages.success(request, f'Sponsor "{sponsor.name}" {status}.')
    return _redirect_tab(club_id, 'sponsoring')


# ─── Club: Saisonziele ────────────────────────────────────────────────────────

@require_POST
def creator_add_goal(request, club_id):
    club = get_object_or_404(Club, id=club_id)

    season_raw = request.POST.get('season_number', '1').strip()
    goal_tier = request.POST.get('goal_tier', '').strip()
    rank_raw = request.POST.get('rank_in_league', '1').strip()

    if not goal_tier:
        messages.error(request, 'Zielkategorie erforderlich.')
        return _redirect_tab(club_id, 'saisonziele')

    try:
        season_number = int(season_raw)
    except ValueError:
        season_number = 1

    try:
        rank_in_league = int(rank_raw)
    except ValueError:
        rank_in_league = 1

    if SeasonGoal.objects.filter(club=club, season_number=season_number).exists():
        messages.error(request, f'Für Saison {season_number} existiert bereits ein Ziel.')
        return _redirect_tab(club_id, 'saisonziele')

    required_max = request.POST.get('required_max_rank', '').strip()
    try:
        req_rank = int(required_max)
    except ValueError:
        req_rank = 0

    SeasonGoal.objects.create(
        club=club,
        season_number=season_number,
        goal_tier=goal_tier,
        rank_in_league=rank_in_league,
        required_max_rank=req_rank,
    )
    messages.success(request, f'Saisonziel für Saison {season_number} gesetzt.')
    return _redirect_tab(club_id, 'saisonziele')


@require_POST
def creator_delete_goal(request, club_id, goal_id):
    club = get_object_or_404(Club, id=club_id)
    goal = get_object_or_404(SeasonGoal, id=goal_id, club=club)
    sn = goal.season_number
    goal.delete()
    messages.success(request, f'Saisonziel Saison {sn} entfernt.')
    return _redirect_tab(club_id, 'saisonziele')


# ═══════════════════════════════════════════════════════════════════════════════
#  Creator Mode — Manager-Profile-Editor
# ═══════════════════════════════════════════════════════════════════════════════

def _redirect_manager_tab(manager_id, tab):
    from django.urls import reverse
    return redirect(f"{reverse('creator_manager_edit', args=[manager_id])}?tab={tab}")


def creator_manager_list(request):
    managers = list(
        ManagerProfile.objects
        .select_related('user', 'favourite_club')
        .order_by('name')
    )
    club_map = {c.managed_by_id: c for c in Club.objects.filter(managed_by__isnull=False).select_related('league')}
    # Build (manager, club_or_None) rows for the template
    manager_rows = [(m, club_map.get(m.id)) for m in managers]
    return render(request, 'creator/manager_list.html', {
        'manager_rows': manager_rows,
        'total_managers': len(managers),
        'total_with_club': sum(1 for m in managers if m.id in club_map),
    })


def creator_manager_edit(request, manager_id):
    manager = get_object_or_404(ManagerProfile, id=manager_id)
    active_tab = request.GET.get('tab', 'profil')

    # Managed club (Club.managed_by OneToOneField → ManagerProfile)
    managed_club = Club.objects.filter(managed_by=manager).select_related('league').first()
    career_stations = manager.career_stations.select_related('club').order_by('order')
    try:
        coin_balance = manager.hoeness_coins.amount
    except HoenessCoin.DoesNotExist:
        coin_balance = 0
    coin_transactions = CoinTransaction.objects.filter(manager=manager).order_by('-created_at')[:30]
    satisfactions = PresidentSatisfaction.objects.filter(manager=manager).select_related('club').order_by('value')
    all_clubs = Club.objects.select_related('league').order_by('name')
    free_clubs = Club.objects.filter(managed_by__isnull=True).select_related('league').order_by('name')

    # Compute avatar URL if profile_image is set
    avatar_url = None
    if manager.profile_image:
        avatar_url = manager.profile_image

    return render(request, 'creator/manager_edit.html', {
        'manager': manager,
        'active_tab': active_tab,
        'managed_club': managed_club,
        'career_stations': career_stations,
        'coin_balance': coin_balance,
        'coin_transactions': coin_transactions,
        'coin_reason_choices': CoinTransaction.REASON_CHOICES,
        'satisfactions': satisfactions,
        'all_clubs': all_clubs,
        'free_clubs': free_clubs,
        'trainer_type_choices': ManagerProfile.TRAINER_TYPE_CHOICES,
        'avatar_url': avatar_url,
    })


@require_POST
def creator_save_manager_profil(request, manager_id):
    manager = get_object_or_404(ManagerProfile, id=manager_id)
    name = request.POST.get('name', '').strip()
    if not name:
        messages.error(request, 'Name darf nicht leer sein.')
        return _redirect_manager_tab(manager_id, 'profil')
    if ManagerProfile.objects.filter(name=name).exclude(id=manager_id).exists():
        messages.error(request, f'Name „{name}" ist bereits vergeben.')
        return _redirect_manager_tab(manager_id, 'profil')

    trainer_type = request.POST.get('trainer_type', manager.trainer_type)
    nationality_flag = request.POST.get('nationality_flag', '').strip()
    nationality_name = request.POST.get('nationality_name', '').strip()
    member_since = request.POST.get('member_since', '') or None
    highscore = request.POST.get('highscore', '').strip()
    name_confirmed = request.POST.get('name_confirmed', '0') == '1'
    fav_club_id = request.POST.get('favourite_club', '') or None

    try:
        level = max(1, int(request.POST.get('level', manager.level)))
    except (ValueError, TypeError):
        level = manager.level
    try:
        xp = max(0, int(request.POST.get('xp', manager.xp)))
    except (ValueError, TypeError):
        xp = manager.xp
    try:
        xp_max = max(1, int(request.POST.get('xp_max', manager.xp_max)))
    except (ValueError, TypeError):
        xp_max = manager.xp_max

    manager.name = name
    manager.trainer_type = trainer_type
    manager.nationality_flag = nationality_flag
    manager.nationality_name = nationality_name
    manager.highscore = highscore
    manager.name_confirmed = name_confirmed
    manager.level = level
    manager.xp = xp
    manager.xp_max = xp_max
    if fav_club_id:
        manager.favourite_club_id = fav_club_id
    else:
        manager.favourite_club = None
    if member_since:
        from datetime import date
        try:
            manager.member_since = date.fromisoformat(member_since)
        except ValueError:
            pass
    else:
        manager.member_since = None

    manager.save()
    messages.success(request, 'Profil gespeichert.')
    return _redirect_manager_tab(manager_id, 'profil')


@require_POST
def creator_save_manager_club(request, manager_id):
    manager = get_object_or_404(ManagerProfile, id=manager_id)
    action = request.POST.get('action', '')

    if action == 'unassign':
        old_club = Club.objects.filter(managed_by=manager).first()
        if old_club:
            old_club.managed_by = None
            old_club.save(update_fields=['managed_by'])
            messages.success(request, f'Verein „{old_club.name}" wurde vom Manager getrennt.')
        else:
            messages.error(request, 'Kein Verein zugeordnet.')

    elif action == 'assign':
        club_id = request.POST.get('club_id', '')
        if not club_id:
            messages.error(request, 'Kein Verein ausgewählt.')
            return _redirect_manager_tab(manager_id, 'verein')
        new_club = get_object_or_404(Club, id=club_id)

        # Remove manager from current club first
        old_club = Club.objects.filter(managed_by=manager).exclude(id=new_club.id).first()
        if old_club:
            old_club.managed_by = None
            old_club.save(update_fields=['managed_by'])

        # Remove existing manager from new club if occupied
        if new_club.managed_by and new_club.managed_by_id != manager_id:
            displaced = new_club.managed_by
            messages.warning(request, f'Manager „{displaced.name}" wurde von „{new_club.name}" entfernt.')

        new_club.managed_by = manager
        new_club.save(update_fields=['managed_by'])
        messages.success(request, f'Manager erfolgreich „{new_club.name}" zugeordnet.')

    return _redirect_manager_tab(manager_id, 'verein')


@require_POST
def creator_add_career_station(request, manager_id):
    manager = get_object_or_404(ManagerProfile, id=manager_id)
    city_name = request.POST.get('city_name', '').strip()
    if not city_name:
        messages.error(request, 'Stadtname ist Pflichtfeld.')
        return _redirect_manager_tab(manager_id, 'karriere')

    club_id = request.POST.get('club_id', '') or None
    custom_club_name = request.POST.get('custom_club_name', '').strip()
    city_country = request.POST.get('city_country', '').strip()
    started_at = request.POST.get('started_at', '') or None
    ended_at = request.POST.get('ended_at', '') or None
    games_played = max(0, int(request.POST.get('games_played', 0) or 0))
    order = max(1, int(request.POST.get('order', 1) or 1))
    map_x = max(0, int(request.POST.get('map_x', 271) or 271))
    map_y = max(0, int(request.POST.get('map_y', 214) or 214))

    from datetime import date
    started = None
    if started_at:
        try:
            started = date.fromisoformat(started_at)
        except ValueError:
            pass
    ended = None
    if ended_at:
        try:
            ended = date.fromisoformat(ended_at)
        except ValueError:
            pass

    club = Club.objects.filter(id=club_id).first() if club_id else None

    ManagerCareerStation.objects.create(
        manager=manager,
        club=club,
        custom_club_name=custom_club_name,
        city_name=city_name,
        city_country=city_country,
        order=order,
        map_x=map_x,
        map_y=map_y,
        started_at=started,
        ended_at=ended,
        games_played=games_played,
    )
    messages.success(request, f'Karrierestation „{city_name}" hinzugefügt.')
    return _redirect_manager_tab(manager_id, 'karriere')


@require_POST
def creator_delete_career_station(request, manager_id, station_id):
    manager = get_object_or_404(ManagerProfile, id=manager_id)
    station = get_object_or_404(ManagerCareerStation, id=station_id, manager=manager)
    city = station.city_name
    station.delete()
    messages.success(request, f'Station „{city}" entfernt.')
    return _redirect_manager_tab(manager_id, 'karriere')


@require_POST
def creator_save_coins(request, manager_id):
    manager = get_object_or_404(ManagerProfile, id=manager_id)
    try:
        new_amount = max(0, int(request.POST.get('amount', 0) or 0))
    except (ValueError, TypeError):
        messages.error(request, 'Ungültiger Betrag.')
        return _redirect_manager_tab(manager_id, 'coins')

    reason = request.POST.get('reason', CoinTransaction.REASON_WIN)
    description = request.POST.get('description', '').strip() or 'Admin-Korrektur'

    coin, _ = HoenessCoin.objects.get_or_create(manager=manager, defaults={'amount': 0})
    old_amount = coin.amount
    diff = new_amount - old_amount
    coin.amount = new_amount
    coin.save()

    if diff != 0:
        CoinTransaction.objects.create(
            manager=manager,
            amount=diff,
            reason=reason,
            description=description,
        )
    messages.success(request, f'Guthaben auf {new_amount} gesetzt (Δ {diff:+d}).')
    return _redirect_manager_tab(manager_id, 'coins')


@require_POST
def creator_save_satisfaction(request, manager_id, sat_id):
    manager = get_object_or_404(ManagerProfile, id=manager_id)
    sat = get_object_or_404(PresidentSatisfaction, id=sat_id, manager=manager)
    try:
        value = max(0, min(100, int(request.POST.get('value', sat.value) or sat.value)))
    except (ValueError, TypeError):
        value = sat.value
    sat.value = value
    sat.save(update_fields=['value', 'updated_at'])
    messages.success(request, f'Zufriedenheit auf {value} % gesetzt.')
    return _redirect_manager_tab(manager_id, 'praesident')


@require_POST
def creator_add_satisfaction(request, manager_id):
    manager = get_object_or_404(ManagerProfile, id=manager_id)
    club_id = request.POST.get('club_id', '')
    if not club_id:
        messages.error(request, 'Verein fehlt.')
        return _redirect_manager_tab(manager_id, 'praesident')
    club = get_object_or_404(Club, id=club_id)
    try:
        value = max(0, min(100, int(request.POST.get('value', 100) or 100)))
    except (ValueError, TypeError):
        value = 100
    sat, created = PresidentSatisfaction.objects.get_or_create(
        manager=manager, club=club,
        defaults={'value': value},
    )
    if not created:
        sat.value = value
        sat.save(update_fields=['value', 'updated_at'])
    messages.success(request, f'Zufriedenheit für „{club.name}" auf {sat.value} % gesetzt.')
    return _redirect_manager_tab(manager_id, 'praesident')


# ═══════════════════════════════════════════════════════════════════════════════
# CREATOR MODE — LIGA-EDITOR
# ═══════════════════════════════════════════════════════════════════════════════

def creator_league_edit(request, league_id):
    from collections import defaultdict
    from django.contrib.staticfiles import finders
    from game.models import SeasonFixture

    league = get_object_or_404(League, id=league_id)
    active_tab = request.GET.get('tab', 'stammdaten')

    clubs = list(
        league.club_set.order_by('name').prefetch_related('tactic_setups')
    )

    logo_path = league.logo_static_path or ''

    spielplan_seasons = []
    spielplan_matchdays = []
    spielplan_selected = None
    spielplan_total_played = 0
    spielplan_total_fixtures = 0
    spielplan_total_matchdays = 0
    spielplan_current_matchday = None
    show_confirm_reset = False
    confirm_reset_season = None

    if active_tab == 'spielplan':
        spielplan_seasons = list(
            SeasonFixture.objects.filter(league=league)
            .values_list('season', flat=True)
            .distinct()
            .order_by('-season')
        )
        spielplan_selected = request.GET.get('season') or (
            spielplan_seasons[0] if spielplan_seasons else None
        )
        # Confirm-reset flow: if ?confirm_reset=1 and existing unplayed fixtures
        if request.GET.get('confirm_reset') == '1':
            season_param = request.GET.get('season', '')
            existing = SeasonFixture.objects.filter(league=league, season=season_param)
            if existing.exists() and not existing.filter(is_played=True).exists():
                show_confirm_reset = True
                confirm_reset_season = season_param

        if spielplan_selected:
            fixtures_qs = (
                SeasonFixture.objects
                .filter(league=league, season=spielplan_selected)
                .select_related('home_club', 'away_club')
                .order_by('matchday', 'id')
            )
            by_md = defaultdict(list)
            for f in fixtures_qs:
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
                if played > 0:
                    spielplan_current_matchday = md
            spielplan_total_fixtures = sum(b['total'] for b in spielplan_matchdays)
            spielplan_total_played = sum(b['played'] for b in spielplan_matchdays)
            spielplan_total_matchdays = len(spielplan_matchdays)

    return render(request, 'creator/league_edit.html', {
        'league': league,
        'clubs': clubs,
        'active_tab': active_tab,
        'logo_path': logo_path,
        'spielplan_seasons': spielplan_seasons,
        'spielplan_selected': spielplan_selected,
        'spielplan_matchdays': spielplan_matchdays,
        'spielplan_total_played': spielplan_total_played,
        'spielplan_total_fixtures': spielplan_total_fixtures,
        'spielplan_total_matchdays': spielplan_total_matchdays,
        'spielplan_current_matchday': spielplan_current_matchday,
        'show_confirm_reset': show_confirm_reset,
        'confirm_reset_season': confirm_reset_season,
    })


@require_POST
def creator_league_save_stammdaten(request, league_id):
    league = get_object_or_404(League, id=league_id)
    league.name = request.POST.get('name', league.name).strip() or league.name
    league.country = request.POST.get('country', league.country).strip()
    league.logo_static_path = request.POST.get('logo_static_path', '').strip()
    league.coefficient_source = request.POST.get('coefficient_source', '').strip()
    try:
        league.strength_coefficient = Decimal(request.POST.get('strength_coefficient', '1.00'))
    except InvalidOperation:
        pass
    for field in ('cl_spots', 'el_spots', 'conference_spots', 'relegation_spots'):
        try:
            setattr(league, field, int(request.POST.get(field, getattr(league, field))))
        except (ValueError, TypeError):
            pass
    league.save()
    messages.success(request, f'Liga „{league.name}" gespeichert.')
    return redirect(f'/creator/leagues/{league_id}/?tab=stammdaten')


@require_POST
def creator_league_spielplan_generate(request, league_id):
    from datetime import date, datetime, time as dt_time
    from game.models import SeasonFixture
    from game.schedule_generator import create_round_robin_schedule, matchday_date

    league = get_object_or_404(League, id=league_id)
    clubs = list(league.club_set.order_by('name'))

    season = request.POST.get('season', '').strip()
    confirm_reset = request.POST.get('confirm_reset') == '1'

    if not season or len(clubs) < 2:
        messages.error(request, 'Saison angeben und mindestens 2 Vereine in der Liga.')
        return redirect(f'/creator/leagues/{league_id}/?tab=spielplan')

    try:
        rounds = max(1, min(4, int(request.POST.get('rounds', 2))))
    except (ValueError, TypeError):
        rounds = 2
    try:
        start_date_val = datetime.strptime(request.POST.get('start_date', ''), '%Y-%m-%d').date()
    except (ValueError, TypeError):
        start_date_val = date.today()
    try:
        parts = request.POST.get('start_time', '15:30').split(':')
        start_time_val = dt_time(int(parts[0]), int(parts[1]))
    except (ValueError, IndexError):
        start_time_val = dt_time(15, 30)
    try:
        day_interval = max(1, int(request.POST.get('day_interval', 7)))
    except (ValueError, TypeError):
        day_interval = 7
    try:
        round_break = max(0, int(request.POST.get('round_break', 0)))
    except (ValueError, TypeError):
        round_break = 0

    existing = SeasonFixture.objects.filter(league=league, season=season)
    if existing.exists():
        played_count = existing.filter(is_played=True).count()
        if played_count > 0:
            messages.error(
                request,
                f'Saison „{season}" hat {played_count} gespielte Partie(n) — '
                f'Zurücksetzen nicht möglich.',
            )
            return redirect(f'/creator/leagues/{league_id}/?tab=spielplan&season={season}')
        if not confirm_reset:
            unplayed = existing.filter(is_played=False).count()
            messages.warning(
                request,
                f'__CONFIRM_RESET__{season}__{unplayed}',
            )
            return redirect(
                f'/creator/leagues/{league_id}/?tab=spielplan&season={season}&confirm_reset=1'
            )
        existing.delete()

    try:
        schedule = create_round_robin_schedule([c.pk for c in clubs], rounds=rounds)
    except ValueError as exc:
        messages.error(request, f'Spielplan-Generator Fehler: {exc}')
        return redirect(f'/creator/leagues/{league_id}/?tab=spielplan')

    n = len(clubs)
    matchdays_per_round = n if n % 2 == 1 else n - 1
    fixtures_to_create = []
    for spieltag, pairs in sorted(schedule.items()):
        match_date = matchday_date(spieltag, start_date_val, day_interval, matchdays_per_round, round_break)
        for home_id, away_id in pairs:
            fixtures_to_create.append(SeasonFixture(
                league=league, season=season, matchday=spieltag,
                home_club_id=home_id, away_club_id=away_id,
                scheduled_date=match_date, scheduled_time=start_time_val,
            ))
    SeasonFixture.objects.bulk_create(fixtures_to_create)
    messages.success(
        request,
        f'Spielplan Saison „{season}" generiert: {len(schedule)} Spieltage, '
        f'{len(fixtures_to_create)} Partien.',
    )
    return redirect(f'/creator/leagues/{league_id}/?tab=spielplan&season={season}')


def creator_league_fixture_save(request, league_id):
    import json
    from django.http import JsonResponse
    from django.db import transaction
    from game.models import SeasonFixture
    from datetime import datetime, time as dt_time

    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    league = get_object_or_404(League, id=league_id)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Ungültiges JSON'}, status=400)

    rows = data.get('fixtures', [])
    errors = []
    updates = []

    for row in rows:
        fid = row.get('id')
        try:
            fixture = SeasonFixture.objects.get(pk=fid, league=league)
        except SeasonFixture.DoesNotExist:
            errors.append(f'Fixture {fid} nicht gefunden.')
            continue

        sd = (row.get('scheduled_date') or '').strip()
        st = (row.get('scheduled_time') or '').strip()
        hg = row.get('home_goals')
        ag = row.get('away_goals')
        ip = bool(row.get('is_played', False))

        if sd:
            try:
                fixture.scheduled_date = datetime.strptime(sd, '%Y-%m-%d').date()
            except ValueError:
                errors.append(f'Ungültiges Datum bei Fixture {fid}: {sd}')
                continue
        else:
            fixture.scheduled_date = None

        if st:
            try:
                parts = st.split(':')
                fixture.scheduled_time = dt_time(int(parts[0]), int(parts[1]))
            except (ValueError, IndexError):
                errors.append(f'Ungültige Uhrzeit bei Fixture {fid}: {st}')
                continue
        else:
            fixture.scheduled_time = None

        fixture.home_goals = int(hg) if (hg is not None and str(hg) != '') else None
        fixture.away_goals = int(ag) if (ag is not None and str(ag) != '') else None
        fixture.is_played = ip
        updates.append(fixture)

    if errors:
        return JsonResponse({'error': '\n'.join(errors)}, status=400)

    with transaction.atomic():
        for f in updates:
            f.save(update_fields=[
                'scheduled_date', 'scheduled_time',
                'home_goals', 'away_goals', 'is_played',
            ])

    return JsonResponse({'ok': True, 'saved': len(updates)})
