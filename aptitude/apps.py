from django.apps import AppConfig
from django.db.models.signals import post_migrate


def _load_bank(sender, **kwargs):
    from .services import load_bank
    load_bank()


class AptitudeConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "aptitude"

    def ready(self):
        # Fill (or refresh) the shared question bank every time `migrate` runs.
        post_migrate.connect(_load_bank, sender=self)
