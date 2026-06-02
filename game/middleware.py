from django.conf import settings
from django.contrib.auth import get_user_model, login


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
