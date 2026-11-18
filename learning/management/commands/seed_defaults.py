from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from learning.services import seed_default_curriculum


class Command(BaseCommand):
    help = "Add the default curriculum (domains, technologies, topics) to existing users. Safe to re-run."

    def add_arguments(self, parser):
        parser.add_argument("--username", help="Only seed this user (default: all users)")

    def handle(self, *args, **options):
        User = get_user_model()
        users = User.objects.all()
        if options["username"]:
            users = users.filter(username=options["username"])
            if not users.exists():
                raise CommandError(f"No user named {options['username']}")
        for user in users:
            created = seed_default_curriculum(user)
            self.stdout.write(f"{user.username}: {created}")
