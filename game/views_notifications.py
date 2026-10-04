"""Benachrichtigungs-Liste (Glocke im Header, Spec Show-Auktion §12)."""
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .models import ManagerProfile, Notification


def _safe_notification_url(request, url):
    """Validate display URLs without changing the stored notification."""
    return url if url_has_allowed_host_and_scheme(
        url, allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ) else ''


@login_required(login_url='/auth/login/')
@require_POST
def notifications_open(request):
    """Opening the popup reads only its ten displayed, manager-owned rows."""
    manager = ManagerProfile.objects.filter(user=request.user).first()
    if manager is None:
        return JsonResponse({'error': 'Kein Managerprofil vorhanden.'}, status=404)
    with transaction.atomic():
        items = list(
            Notification.objects.filter(recipient=manager)
            .select_for_update().order_by('-created_at', '-pk')[:10]
        )
        payload = []
        for item in items:
            payload.append({
                'id': item.pk, 'title': item.title, 'body': item.body,
                'url': _safe_notification_url(request, item.url), 'is_new': not item.is_read,
                'created_at': item.created_at.isoformat(),
                'date_label': timezone.localtime(item.created_at).strftime('%d.%m.%Y · %H:%M'),
            })
        Notification.objects.filter(
            recipient=manager, pk__in=[item.pk for item in items], is_read=False,
        ).update(is_read=True)
        unread = Notification.objects.filter(recipient=manager, is_read=False).count()
    response = JsonResponse({'items': payload, 'unread_count': unread})
    response['Cache-Control'] = 'private, no-store'
    return response


@login_required(login_url='/auth/login/')
def notifications_page(request):
    manager, _ = ManagerProfile.objects.get_or_create(
        user=request.user,
        defaults={'name': request.user.username},
    )
    items = list(
        Notification.objects.filter(recipient=manager)[:100]
    )
    for item in items:
        item.safe_url = _safe_notification_url(request, item.url)
    # Nur die geladenen Meldungen als gelesen markieren (die Objekte
    # behalten ihren alten is_read-Stand für die Hervorhebung im Template).
    Notification.objects.filter(
        recipient=manager, pk__in=[item.pk for item in items], is_read=False,
    ).update(is_read=True)
    return render(request, 'game/notifications.html', {
        'notifications': items,
    })
