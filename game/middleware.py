from django.conf import settings
from django.contrib.auth import get_user_model, login
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect

_LAST_SEEN_INTERVAL_S = 120


class ManagerTransferBanMiddleware:
    """Enforce the inactivity transfer ban across all transfer POST routes."""

    # These actions do not create, accept or improve a transfer commitment.
    _ALLOWED_DURING_BAN = {
        'transfer_market_pin',
        'transfer_rumor_react',
        'transfer_report_create',
        'transfer_deal_decline',
        'transfer_deal_withdraw',
        'transfer_deal_counter_decline',
        'transfer_deal_bid_remove',
        'transfer_loan_listing_withdraw',
        'scouting_watch',
        'scouting_withdraw',
        'scouting_reject',
        'scouting_watchlist_add',
        'scouting_watchlist_remove',
        'scouting_community_submit',
    }

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (
            request.method == 'POST'
            and request.path.startswith('/transfers/')
            and request.user.is_authenticated
            and request.resolver_match
            and request.resolver_match.url_name not in self._ALLOWED_DURING_BAN
        ):
            try:
                profile = request.user.manager_profile
            except Exception:
                profile = None
            if profile is not None and profile.transfer_ban_until:
                text = (
                    'Transfersperre: Bestätige beim nächsten Pflichtspiel '
                    'eigenhändig deine Aufstellung, um sie zu beenden.'
                )
                if (
                    request.headers.get('X-Requested-With') == 'XMLHttpRequest'
                    or 'application/json' in request.headers.get('Accept', '')
                ):
                    return JsonResponse({'ok': False, 'error': text}, status=403)
                messages.error(request, text)
                return redirect(request.META.get('HTTP_REFERER') or '/transfers/markt/')
        return self.get_response(request)


class LastSeenMiddleware:
    """Aktualisiert ManagerProfile.last_seen bei jedem authentifizierten Request
    (gedrosselt: max. einmal alle 2 Minuten, um DB-Last zu begrenzen)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # The isolated material pilot must not grant rewards or touch activity.
        # Authentication/authorization are still enforced by its normal views.
        if request.path.startswith('/live/rasen-test/'):
            return self.get_response(request)
        if request.user.is_authenticated:
            try:
                mp = request.user.manager_profile
                from .manager_profile import award_login_reward
                award_login_reward(mp)
            except Exception:
                pass
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
