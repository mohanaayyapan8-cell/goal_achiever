from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from .timezones import DEFAULT_TIMEZONE, is_valid_timezone


def validate_timezone(value):
    if not is_valid_timezone(value):
        raise ValidationError("Unknown timezone.")


class UserProfile(models.Model):
    """Extra information for each user. Created automatically with the user."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    timezone = models.CharField(
        max_length=64, default=DEFAULT_TIMEZONE, validators=[validate_timezone],
        help_text="Used to decide when your day starts and ends (streaks, daily goals).",
    )
    college = models.CharField("College / University", max_length=150, blank=True)
    target_role = models.CharField(max_length=100, blank=True, help_text="Example: Python Developer, Data Analyst")
    bio = models.TextField(max_length=500, blank=True)
    # Used by the reminder features in Phase 7.
    daily_reminder_time = models.TimeField(null=True, blank=True)
    email_reminders = models.BooleanField(default=False)
    # Show browser notifications while the site is open in a tab (needs the browser's permission).
    browser_reminders = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Profile of {self.user.get_username()}"

    @property
    def tzinfo(self):
        """ZoneInfo object for this user; falls back to the default if invalid."""
        try:
            return ZoneInfo(self.timezone)
        except Exception:
            return ZoneInfo(DEFAULT_TIMEZONE)

    @property
    def display_name(self):
        return self.user.get_full_name() or self.user.get_username()
