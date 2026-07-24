from django.conf import settings
from django.contrib.auth import get_user_model, login

_LAST_SEEN_INTERVAL_S = 120


class LastSeenMiddleware:
    """Aktualisiert ManagerProfile.last_seen bei jedem authentifizierten Request
    (gedrosselt: max. einmal alle 2 Minuten, um DB-Last zu begrenzen)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.user.is_authenticated:
            try:
                mp = request.user.manager_profile
                from django.utils import timezone
                now = timezone.now()
                if mp.last_seen is None or (now - mp.last_seen).total_seconds() > _LAST_SEEN_INTERVAL_S:
                    mp.last_seen = now
                    mp.save(update_fields=['last_seen'])
            except Exception:
                pass
        return response


class DevNoCacheMiddleware:
    """
    DEBUG-only: verbietet Browsern und Proxies das Zwischenspeichern von
    Antworten, damit in der Entwicklung nie veraltete Seiten angezeigt werden.
    In Produktion (DEBUG=False) komplett inaktiv.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if settings.DEBUG:
            response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            response['Pragma'] = 'no-cache'
            response['Expires'] = '0'
        return response


class DevAutoLoginMiddleware:
    """
    DEBUG-only: automatically logs in the first superuser if no user is
    authenticated. Lets developers test authenticated views without a login form.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if settings.DEBUG and not request.user.is_authenticated:
            User = get_user_model()
            superuser = User.objects.filter(is_superuser=True).first()
            if superuser:
                superuser.backend = 'django.contrib.auth.backends.ModelBackend'
                login(request, superuser)
        return self.get_response(request)
