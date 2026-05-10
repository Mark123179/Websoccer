from django.shortcuts import render, get_object_or_404
from django.db.models import Avg, Count, Sum
from .models import Club, League, Player


def home(request):
    clubs = Club.objects.select_related('league').annotate(
        player_count=Count('player'),
        average_strength=Avg('player__strength_profile__final_strength'),
    )

    totals = {
        'league_count': League.objects.count(),
        'club_count': Club.objects.count(),
        'player_count': Player.objects.count(),
        'total_budget': Club.objects.aggregate(total=Sum('budget'))['total'] or 0,
    }

    return render(
        request,
        'game/home.html',
        {
            'richest_clubs': clubs.order_by('-budget')[:5],
            'totals': totals,
        }
    )


def club_list(request):
    clubs = Club.objects.select_related('league').annotate(
        player_count=Count('player'),
        average_strength=Avg('player__strength_profile__final_strength'),
    )

    return render(
        request,
        'game/club_list.html',
        {
            'clubs': clubs
        }
    )


def club_detail(request, club_id):
    club = get_object_or_404(
        Club.objects.select_related('league'),
        id=club_id
    )
    players = club.player_set.select_related('strength_profile').order_by(
        'position',
        'last_name',
        'first_name',
    )
    average_strength = players.aggregate(
        average=Avg('strength_profile__final_strength')
    )['average']

    return render(
        request,
        'game/club_detail.html',
        {
            'club': club,
            'players': players,
            'player_count': players.count(),
            'average_strength': average_strength,
        }
    )


def player_detail(request, player_id):
    player = get_object_or_404(
        Player.objects.select_related('club', 'club__league', 'strength_profile'),
        id=player_id,
    )

    return render(
        request,
        'game/player_detail.html',
        {
            'player': player,
        }
    )
