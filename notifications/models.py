from django.conf import settings
from django.db import models
from django.db.models import Q


class Notification(models.Model):
    INFO, SUCCESS, WARNING, BADGE, REMINDER = "info", "success", "warning", "badge", "reminder"
    KIND_CHOICES = [(INFO, "Info"), (SUCCESS, "Success"), (WARNING, "Warning"), (BADGE, "Badge"), (REMINDER, "Reminder")]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    kind = models.CharField(max_length=10, choices=KIND_CHOICES, default=INFO)
    title = models.CharField(max_length=120)
    message = models.TextField(blank=True)
    link = models.CharField(max_length=200, blank=True)        # an address inside this site
    # Stops the same event from creating the same notification twice (e.g. "missed:2026-03-05").
    dedupe_key = models.CharField(max_length=80, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)
    emailed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["user", "dedupe_key"], condition=~Q(dedupe_key=""), name="uniq_notification_key_per_user"),
        ]
        indexes = [models.Index(fields=["user", "read_at"])]

    def __str__(self):
        return f"{self.get_kind_display()}: {self.title}"

    @property
    def is_read(self):
        return self.read_at is not None
