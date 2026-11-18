from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from .models import Notification


def notify(user, kind, title, message="", link="", key=""):
    """Create an in-app notification. With a key, the same event never creates a second one.
    Returns (notification, created)."""
    if key:
        return Notification.objects.get_or_create(
            user=user, dedupe_key=key, defaults={"kind": kind, "title": title, "message": message, "link": link})
    return Notification.objects.create(user=user, kind=kind, title=title, message=message, link=link), True


def unread_count(user):
    return Notification.objects.filter(user=user, read_at__isnull=True).count()


def mark_read(user, pk=None):
    qs = Notification.objects.filter(user=user, read_at__isnull=True)
    if pk is not None:
        qs = qs.filter(pk=pk)
    return qs.update(read_at=timezone.now())


def send_reminder_email(notification):
    """E-mail one reminder. Only called from the send_reminders command. Returns True if sent."""
    user = notification.user
    if not user.email or notification.emailed_at:
        return False
    name = user.first_name or user.get_username()
    link = f"{settings.SITE_URL}{notification.link}" if notification.link else settings.SITE_URL
    body = (f"Hi {name},\n\n{notification.message}\n\nOpen Goal Achiever: {link}\n\n"
            "You can turn these e-mails off in Notifications > Reminder settings.\n")
    send_mail(f"Goal Achiever: {notification.title}", body, settings.DEFAULT_FROM_EMAIL, [user.email])
    notification.emailed_at = timezone.now()
    notification.save(update_fields=["emailed_at"])
    return True
