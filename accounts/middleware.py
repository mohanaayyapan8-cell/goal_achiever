from django.utils import timezone

from .utils import get_profile


class UserTimezoneMiddleware:
    """Activates the logged-in user's timezone for the whole request."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            timezone.activate(get_profile(request.user).tzinfo)
        else:
            timezone.deactivate()
        try:
            return self.get_response(request)
        finally:
            timezone.deactivate()
