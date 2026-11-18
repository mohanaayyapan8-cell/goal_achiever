from django.apps import AppConfig
from django.db.models.signals import post_migrate


def _load_problems(sender, **kwargs):
    from .services import load_problems
    load_problems()


class CodingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "coding"

    def ready(self):
        # Fill (or refresh) the shared problem bank every time `migrate` runs.
        post_migrate.connect(_load_problems, sender=self)
