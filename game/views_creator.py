import os
from decimal import Decimal, InvalidOperation

from django.apps import apps
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import Club, COUNTRY_FLAG_ASSETS, League, Player

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
    leagues = (
        League.objects
        .prefetch_related('club_set')
        .order_by('country', 'name')
    )
    countries = {}
    for league in leagues:
        country = league.country or 'Unbekannt'
        clubs = (
            league.club_set.all()
            .order_by('name')
        )
        if country not in countries:
            countries[country] = []
        countries[country].append({'league': league, 'clubs': clubs})

    return render(request, 'creator/index.html', {
        'countries': countries,
        'total_clubs': Club.objects.count(),
        'total_players': Player.objects.count(),
    })


def creator_club_edit(request, club_id):
    club = get_object_or_404(Club, id=club_id)
    ClubPublicProfile = apps.get_model('game', 'ClubPublicProfile')
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

    return render(request, 'creator/club_edit.html', {
        'club': club,
        'profile': profile,
        'players': players,
        'kits': kits,
        'stadium_path': stadium_path,
        'city_path': city_path,
        'crest_path': crest_path,
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
