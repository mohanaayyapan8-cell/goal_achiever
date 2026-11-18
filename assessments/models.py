from django.conf import settings
from django.db import models
from django.db.models import Q

from learning.models import Topic

IN_PROGRESS, SUBMITTED = "in_progress", "submitted"
STATUS_CHOICES = [(IN_PROGRESS, "In progress"), (SUBMITTED, "Submitted")]


class WrittenAssessment(models.Model):
    """Stage 1: one written attempt on one topic. History is kept even if the topic is deleted."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="written_assessments")
    topic = models.ForeignKey(Topic, on_delete=models.SET_NULL, null=True, blank=True, related_name="written_assessments")
    topic_name = models.CharField(max_length=150)          # snapshot, survives topic deletion
    technology_name = models.CharField(max_length=100, blank=True)
    attempt_number = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=IN_PROGRESS)
    score = models.FloatField(null=True, blank=True)       # average of the answers, 0-100
    created_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            # Only ONE unfinished attempt per topic: no duplicate assessments.
            models.UniqueConstraint(fields=["user", "topic"], condition=Q(status="in_progress"),
                                    name="uniq_open_written_per_topic"),
        ]
        indexes = [models.Index(fields=["user", "status"]), models.Index(fields=["user", "submitted_at"])]

    def __str__(self):
        return f"Written: {self.topic_name} (attempt {self.attempt_number})"

    @property
    def is_submitted(self):
        return self.status == SUBMITTED


class WrittenAnswer(models.Model):
    """One question (stored as a snapshot) and the user's answer."""

    TYPE_LABELS = {
        "explain": "Explain a concept", "program": "Write a program", "predict_output": "Predict the output",
        "debug": "Debug a program", "explain_logic": "Explain the logic", "practical": "Solve a practical problem",
    }

    assessment = models.ForeignKey(WrittenAssessment, on_delete=models.CASCADE, related_name="answers")
    position = models.PositiveSmallIntegerField()
    question_type = models.CharField(max_length=20)
    prompt = models.TextField()
    code_snippet = models.TextField(blank=True)             # code shown with the question
    question_data = models.JSONField(default=dict)          # rubric: points, checks, expected output, model answer
    answer_text = models.TextField(blank=True)
    answer_code = models.TextField(blank=True)
    score = models.FloatField(null=True, blank=True)
    criteria = models.JSONField(default=dict, blank=True)   # {criterion: percent or null}
    details = models.JSONField(default=list, blank=True)    # each rubric check and whether it passed
    feedback = models.JSONField(default=list, blank=True)
    evaluated_at = models.DateTimeField(null=True, blank=True)
    ai_feedback = models.TextField(blank=True)               # optional, never part of the score

    class Meta:
        ordering = ["position"]
        constraints = [models.UniqueConstraint(fields=["assessment", "position"], name="uniq_answer_position")]

    def __str__(self):
        return f"Q{self.position}: {self.prompt[:40]}"

    @property
    def type_label(self):
        return self.TYPE_LABELS.get(self.question_type, self.question_type)

    @property
    def uses_code(self):
        return self.question_type in ("program", "practical", "debug")


class SpeakingAssessment(models.Model):
    """Stage 2: one spoken question on a topic."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="speaking_assessments")
    topic = models.ForeignKey(Topic, on_delete=models.SET_NULL, null=True, blank=True, related_name="speaking_assessments")
    topic_name = models.CharField(max_length=150)
    technology_name = models.CharField(max_length=100, blank=True)
    attempt_number = models.PositiveIntegerField(default=1)
    question_text = models.TextField()
    question_data = models.JSONField(default=dict)          # key points, target length
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=IN_PROGRESS)
    created_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["user", "topic"], condition=Q(status="in_progress"),
                                    name="uniq_open_speaking_per_topic"),
        ]
        indexes = [models.Index(fields=["user", "status"]), models.Index(fields=["user", "submitted_at"])]

    def __str__(self):
        return f"Speaking: {self.topic_name} (attempt {self.attempt_number})"

    @property
    def is_submitted(self):
        return self.status == SUBMITTED


class SpeakingAnswer(models.Model):
    METHOD_CHOICES = [("speech", "Speech recognition"), ("typed", "Typed")]

    assessment = models.OneToOneField(SpeakingAssessment, on_delete=models.CASCADE, related_name="answer")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="speaking_answers")
    raw_transcript = models.TextField(blank=True)           # exactly what speech recognition produced
    final_text = models.TextField()                         # what the user submitted after editing
    input_method = models.CharField(max_length=8, choices=METHOD_CHOICES, default="typed")
    speaking_seconds = models.PositiveIntegerField(default=0)
    overall = models.FloatField(default=0)
    criteria = models.JSONField(default=dict)               # seven criteria, 0-100 each
    details = models.JSONField(default=dict)                # notes, grammar issues, statistics
    submitted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Speaking answer for {self.assessment.topic_name}"
