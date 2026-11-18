def notifications(request):
    """Adds the unread count (navbar bell) and the browser-notification flag to every page."""
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {}
    from accounts.utils import get_profile
    from .services import unread_count
    return {"unread_notifications": unread_count(user), "browser_notify": get_profile(user).browser_reminders}
