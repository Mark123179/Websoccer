"""Benachrichtigungs-Liste (Glocke im Header, Spec Show-Auktion §12)."""
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .models import ManagerProfile, Notification


@login_required(login_url='/auth/login/')
def notifications_page(request):
    manager, _ = ManagerProfile.objects.get_or_create(
        user=request.user,
        defaults={'name': request.user.username},
    )
    items = list(
        Notification.objects.filter(recipient=manager)[:100]
    )
    # Öffnen der Liste markiert alles als gelesen (die geladenen Objekte
    # behalten ihren alten is_read-Stand für die Hervorhebung im Template).
    Notification.objects.filter(recipient=manager, is_read=False).update(is_read=True)
    return render(request, 'game/notifications.html', {
        'notifications': items,
    })
