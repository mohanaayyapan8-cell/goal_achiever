from datetime import timedelta

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from .topics import SECTION_CHOICES

IN_PROGRESS, SUBMITTED = "in_progress", "submitted"


class AptitudeQuestion(models.Model):
    """Shared question bank (not owned by a user). Loaded from aptitude/bank.py on migrate."""

    key = models.CharField(max_length=80, unique=True)
    section = models.CharField(max_length=10, choices=SECTION_CHOICES)
    topic = models.CharField(max_length=60)
    passage = models.TextField(blank=True)
    stem = models.TextField()
    options = models.JSONField()                 # exactly four strings
    correct_index = models.PositiveSmallIntegerField()
    explanation = models.TextField()
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["section", "topic", "key"]
        indexes = [models.Index(fields=["section", "topic", "is_active"])]

    def __str__(self):
        return f"{self.key}: {self.stem[:50]}"


class AptitudeAttempt(models.Model):
    """One timed practice test. The questions are copied into the attempt, so old results never change."""

    STATUS_CHOICES = [(IN_PROGRESS, "In progress"), (SUBMITTED, "Submitted")]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="aptitude_attempts")
    section = models.CharField(max_length=10, choices=SECTION_CHOICES)
    topic = models.CharField(max_length=60, blank=True)            # blank = all topics of the section
    questions = models.JSONField(default=list)                      # snapshots: topic, stem, passage, options, correct, explanation
    answers = models.JSONField(default=dict, blank=True)            # {"0": chosen option index}
    time_limit_seconds = models.PositiveIntegerField()
    started_at = models.DateTimeField(default=timezone.now)
    submitted_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=IN_PROGRESS)
    correct_count = models.PositiveSmallIntegerField(default=0)
    total_count = models.PositiveSmallIntegerField(default=0)
    percent = models.FloatField(null=True, blank=True)
    timed_out = models.BooleanField(default=False)
    seconds_used = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-started_at", "-id"]
        constraints = [
            # One unfinished test at a time per user: no duplicate attempts.
            models.UniqueConstraint(fields=["user"], condition=Q(status="in_progress"), name="uniq_open_aptitude_per_user"),
        ]
        indexes = [models.Index(fields=["user", "status"]), models.Index(fields=["user", "submitted_at"])]

    def __str__(self):
        return f"{self.get_section_display()} test ({self.topic or 'all topics'})"

    @property
    def deadline(self):
        return self.started_at + timedelta(seconds=self.time_limit_seconds)

    def remaining_seconds(self, now=None):
        return max(0, int((self.deadline - (now or timezone.now())).total_seconds()))

    def is_expired(self, now=None):
        return (now or timezone.now()) >= self.deadline

    @property
    def is_submitted(self):
        return self.status == SUBMITTED

    @property
    def label(self):
        return f"{self.get_section_display()}: {self.topic or 'all topics'}"
