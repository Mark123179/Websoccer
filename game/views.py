from django.shortcuts import render, get_object_or_404
from .models import Club


def club_list(request):
    clubs = Club.objects.all()

    return render(
        request,
        'game/club_list.html',
        {
            'clubs': clubs
        }
    )


def club_detail(request, club_id):
    club = get_object_or_404(Club, id=club_id)
    players = club.player_set.all()

    return render(
        request,
        'game/club_detail.html',
        {
            'club': club,
            'players': players,
        }
    )