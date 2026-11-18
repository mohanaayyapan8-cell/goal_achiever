from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from accounts.models import UserProfile
from notifications.services import send_reminder_email
from streaks import services


class Command(BaseCommand):
    help = ("Update streaks, create due reminders and e-mail them to users who turned e-mail reminders on. "
            "Schedule it every 15 minutes (cron, Windows Task Scheduler or your host's scheduler). "
            "Without it, reminders still appear inside the app when you open it.")

    def handle(self, *args, **options):
        User = get_user_model()
        checked = created = emailed = 0
        for user in User.objects.filter(is_active=True):
            checked += 1
            note = services.refresh(user)
            profile = UserProfile.objects.filter(user=user).first()
            if note and profile and profile.email_reminders and note.emailed_at is None:
                created += 1
                try:
                    emailed += bool(send_reminder_email(note))
                except Exception as exc:                       # keep going for the other users
                    self.stderr.write(f"Could not e-mail {user.get_username()}: {exc}")
        self.stdout.write(f"Checked {checked} users; {emailed} reminder e-mail(s) sent.")
