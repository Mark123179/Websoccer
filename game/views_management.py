from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .views import current_manager_club


@login_required(login_url='/auth/login/')
def management_hub(request):
    club = current_manager_club(user=request.user)
    stadium = None
    if club:
        try:
            stadium = club.stadium
        except Exception:
            stadium = None

    return render(request, 'game/management/hub.html', {
        'club': club,
        'stadium': stadium,
    })
