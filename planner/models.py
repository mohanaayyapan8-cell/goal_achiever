from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from learning.models import Topic

CHALLENGE_DAYS = 40


class DailyPlan(models.Model):
    """One day of the 40-day challenge for one user."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="daily_plans")
    day_number = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(CHALLENGE_DAYS)])
    date = models.DateField()  # the user's local calendar date for this day
    title = models.CharField("Day focus", max_length=100, blank=True)
    # Streaks only count days from when the challenge was created (never penalise the past).
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["day_number"]
        constraints = [models.UniqueConstraint(fields=["user", "day_number"], name="uniq_plan_day_per_user")]
        indexes = [models.Index(fields=["user", "date"])]

    def __str__(self):
        return f"Day {self.day_number} ({self.date})"


class DailyGoal(models.Model):
    """One thing to do on a day. Goals are never deleted automatically; unfinished
    goals stay visible and can be rescheduled to another day."""

    PENDING, COMPLETED = "pending", "completed"
    STATUS_CHOICES = [(PENDING, "Pending"), (COMPLETED, "Completed")]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="daily_goals")
    plan = models.ForeignKey(DailyPlan, on_delete=models.CASCADE, related_name="goals")
    topic = models.ForeignKey(Topic, on_delete=models.SET_NULL, null=True, blank=True, related_name="goals")
    title = models.CharField(max_length=200)
    estimated_minutes = models.PositiveSmallIntegerField(
        default=30, validators=[MinValueValidator(1), MaxValueValidator(600)])
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=PENDING)
    completed_at = models.DateTimeField(null=True, blank=True)
    # Reschedule history
    rescheduled_from = models.ForeignKey(DailyPlan, on_delete=models.SET_NULL, null=True, blank=True,
                                         related_name="moved_goals")
    reschedule_count = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]
        indexes = [models.Index(fields=["plan", "status"]), models.Index(fields=["user", "status"])]

    def __str__(self):
        return self.title

    @property
    def is_completed(self):
        return self.status == self.COMPLETED
