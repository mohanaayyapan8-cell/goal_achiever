from django.utils import timezone

from .models import UserProfile


def get_profile(user):
    """Return the user's profile, creating it if an old user does not have one yet."""
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return profile


def get_user_now(user, now=None):
    """Current date-time in the user's own timezone."""
    now = now or timezone.now()
    return now.astimezone(get_profile(user).tzinfo)


def get_user_today(user, now=None):
    """Today's calendar date for this user. Phase 7 (streaks) relies on this."""
    return get_user_now(user, now).date()


def safe_next(request, fallback):
    """Return the POSTed 'next' address only if it stays on this site (prevents open redirects)."""
    from django.utils.http import url_has_allowed_host_and_scheme

    nxt = request.POST.get("next", "")
    if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}):
        return nxt
    return fallback
