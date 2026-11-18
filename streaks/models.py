from django.conf import settings
from django.db import models


class StreakRecord(models.Model):
    """One row per calendar day of the challenge. Past days are never edited or deleted:
    this is the permanent history behind the streak."""

    COMPLETED, MISSED = "completed", "missed"
    STATUS_CHOICES = [(COMPLETED, "Completed"), (MISSED, "Missed")]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="streak_records")
    date = models.DateField()                                   # the user's local calendar date
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    streak_after = models.PositiveIntegerField(default=0)       # current streak once this day was settled
    missed_run_after = models.PositiveSmallIntegerField(default=0)  # consecutive missed days up to and including this one
    day_number = models.PositiveSmallIntegerField(null=True, blank=True)
    goals_total = models.PositiveSmallIntegerField(default=0)
    goals_done = models.PositiveSmallIntegerField(default=0)
    written_count = models.PositiveSmallIntegerField(default=0)
    speaking_count = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["date"]
        constraints = [
            # One row per user per date: the same date can never add to the streak twice.
            models.UniqueConstraint(fields=["user", "date"], name="uniq_streak_record_per_date"),
        ]
        indexes = [models.Index(fields=["user", "status"])]

    def __str__(self):
        return f"{self.date}: {self.status} (streak {self.streak_after})"


class Achievement(models.Model):
    """A badge the user has earned. Badges are never taken away."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="achievements")
    key = models.CharField(max_length=40)
    title = models.CharField(max_length=80)
    description = models.CharField(max_length=200)
    icon = models.CharField(max_length=8, default="🏅")
    awarded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-awarded_at", "-id"]
        constraints = [models.UniqueConstraint(fields=["user", "key"], name="uniq_achievement_per_user")]

    def __str__(self):
        return f"{self.title} ({self.user_id})"
