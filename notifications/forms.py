from django import forms

from accounts.forms import StyledFormMixin
from accounts.models import UserProfile


class ReminderSettingsForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ("daily_reminder_time", "email_reminders", "browser_reminders")
        labels = {"daily_reminder_time": "Daily reminder time (your local time)",
                  "email_reminders": "Also send me an e-mail reminder",
                  "browser_reminders": "Show browser notifications while the site is open"}
        widgets = {"daily_reminder_time": forms.TimeInput(attrs={"type": "time"}, format="%H:%M")}
        help_texts = {"daily_reminder_time": "A reminder appears in the app after this time on days you have not finished yet."}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()

    def clean(self):
        cleaned = super().clean()
        if (cleaned.get("email_reminders") or cleaned.get("browser_reminders")) and not cleaned.get("daily_reminder_time"):
            self.add_error("daily_reminder_time", "Choose a reminder time to use e-mail or browser reminders.")
        return cleaned
