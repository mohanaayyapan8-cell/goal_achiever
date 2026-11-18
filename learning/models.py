from django.conf import settings
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone


class Domain(models.Model):
    """Top-level group, e.g. 'Technical Skills'. Owned by one user."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="domains")
    name = models.CharField(max_length=100)
    description = models.CharField(max_length=300, blank=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "id"]
        constraints = [
            # Case-insensitive: "python" and "Python" count as the same name.
            models.UniqueConstraint(Lower("name"), "user", name="uniq_domain_name_per_user"),
        ]

    def __str__(self):
        return self.name


class Technology(models.Model):
    """A subject inside a domain, e.g. 'Python' inside 'Technical Skills'."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="technologies")
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE, related_name="technologies")
    name = models.CharField(max_length=100)
    description = models.CharField(max_length=300, blank=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "id"]
        verbose_name_plural = "technologies"
        constraints = [
            models.UniqueConstraint(Lower("name"), "domain", name="uniq_technology_name_per_domain"),
        ]

    def __str__(self):
        return f"{self.name} ({self.domain.name})"


class Topic(models.Model):
    """A single thing to learn, e.g. 'Loops' inside 'Python'."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="topics")
    technology = models.ForeignKey(Technology, on_delete=models.CASCADE, related_name="topics")
    name = models.CharField(max_length=150)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "id"]
        constraints = [
            models.UniqueConstraint(Lower("name"), "technology", name="uniq_topic_name_per_technology"),
        ]

    def __str__(self):
        return self.name

    @property
    def status(self):
        """'not_started', 'in_progress' or 'completed'. Use select_related('progress') in lists."""
        try:
            return self.progress.status
        except LearningProgress.DoesNotExist:
            return LearningProgress.NOT_STARTED

    @property
    def completed_at(self):
        try:
            return self.progress.completed_at
        except LearningProgress.DoesNotExist:
            return None


class LearningProgress(models.Model):
    """Progress of one user on one topic. At most one row per topic."""

    NOT_STARTED, IN_PROGRESS, COMPLETED = "not_started", "in_progress", "completed"
    STATUS_CHOICES = [
        (NOT_STARTED, "Not started"),
        (IN_PROGRESS, "In progress"),
        (COMPLETED, "Completed"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="learning_progress")
    topic = models.OneToOneField(Topic, on_delete=models.CASCADE, related_name="progress")
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=NOT_STARTED)
    completed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["user", "status"])]
        verbose_name_plural = "learning progress"

    def __str__(self):
        return f"{self.topic.name}: {self.get_status_display()}"

    def set_status(self, status):
        """Change status; keeps the ORIGINAL completion time if completed twice."""
        if status not in dict(self.STATUS_CHOICES):
            raise ValueError(f"Unknown status: {status}")
        if status == self.COMPLETED:
            if self.status != self.COMPLETED or self.completed_at is None:
                self.completed_at = timezone.now()
        else:
            self.completed_at = None
        self.status = status
        self.save()


class LearningContent(models.Model):
    """The 10-part lesson for one topic. Belongs to the user, so it can be edited freely."""

    # (field, label, is_code)
    SECTIONS = [
        ("introduction", "1. Topic introduction", False),
        ("definition", "2. Simple definition", False),
        ("explanation", "3. Detailed explanation", False),
        ("syntax", "4. Syntax", True),
        ("examples", "5. Practical code examples", True),
        ("applications", "6. Real-time applications", False),
        ("common_mistakes", "7. Common mistakes", False),
        ("interview_questions", "8. Interview questions", False),
        ("practice_exercises", "9. Practice exercises", False),
        ("revision_notes", "10. Quick revision notes", False),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="learning_content")
    topic = models.OneToOneField(Topic, on_delete=models.CASCADE, related_name="content")
    introduction = models.TextField(blank=True)
    definition = models.TextField(blank=True)
    explanation = models.TextField(blank=True)
    syntax = models.TextField(blank=True)
    examples = models.TextField(blank=True)
    applications = models.TextField(blank=True)
    common_mistakes = models.TextField(blank=True)
    interview_questions = models.TextField(blank=True)
    practice_exercises = models.TextField(blank=True)
    revision_notes = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Content: {self.topic.name}"

    def sections(self):
        """[(label, text, is_code)] for the sections that are not empty."""
        return [(label, getattr(self, field), is_code)
                for field, label, is_code in self.SECTIONS if getattr(self, field).strip()]


class UserNote(models.Model):
    """A personal note the user writes while studying a topic."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notes")
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name="notes")
    body = models.TextField(max_length=5000)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-id"]
        indexes = [models.Index(fields=["user", "topic"])]

    def __str__(self):
        return f"Note on {self.topic.name}"
