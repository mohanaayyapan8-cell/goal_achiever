import re
import uuid

from django.conf import settings
from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver

MAX_RESUMES, MAX_UPLOADS, MAX_REVIEWS = 10, 10, 50


class Resume(models.Model):
    """A resume built in the app. Always owned by one user."""

    LAYOUT_CHOICES = [("student", "Student / fresher (Education first)"), ("professional", "Professional (Experience first)")]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="resumes")
    title = models.CharField("Resume name", max_length=80, help_text="Only for you, e.g. “Data Analyst resume”.")
    layout = models.CharField(max_length=12, choices=LAYOUT_CHOICES, default="student")
    full_name = models.CharField(max_length=100)
    headline = models.CharField("Target role / headline", max_length=100, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    location = models.CharField(max_length=80, blank=True)
    linkedin_url = models.URLField(blank=True)
    github_url = models.URLField(blank=True)
    portfolio_url = models.URLField(blank=True)
    summary = models.TextField("Professional summary", max_length=700, blank=True)
    skills = models.TextField(max_length=1500, blank=True,
                              help_text="One group per line, e.g. “Languages: Python, SQL”. Or just a comma-separated list.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-id"]

    def __str__(self):
        return self.title


class ResumeSection(models.Model):
    """Base for the repeatable sections. `bullets` holds one bullet per line."""

    resume = models.ForeignKey(Resume, on_delete=models.CASCADE, related_name="%(class)ss")
    order = models.PositiveIntegerField(default=0)

    class Meta:
        abstract = True
        ordering = ["order", "id"]


class Education(ResumeSection):
    institution = models.CharField("College / school", max_length=120)
    degree = models.CharField("Degree / course", max_length=120)
    start = models.CharField("From", max_length=20, blank=True, help_text="e.g. 2022")
    end = models.CharField("To", max_length=20, blank=True, help_text="e.g. 2026 or Expected 2026")
    grade = models.CharField("CGPA / percentage", max_length=30, blank=True)
    bullets = models.TextField("Highlights (optional)", max_length=800, blank=True)

    class Meta(ResumeSection.Meta):
        verbose_name_plural = "education"


class Experience(ResumeSection):
    role = models.CharField("Role", max_length=120, help_text="e.g. Python Developer Intern")
    organization = models.CharField("Company / organisation", max_length=120)
    location = models.CharField(max_length=80, blank=True)
    start = models.CharField("From", max_length=20, blank=True, help_text="e.g. Jun 2025")
    end = models.CharField("To", max_length=20, blank=True, help_text="e.g. Aug 2025 or Present")
    bullets = models.TextField("What you did (one bullet per line)", max_length=2400)


class Project(ResumeSection):
    name = models.CharField("Project name", max_length=120)
    tech_stack = models.CharField("Technologies used", max_length=200, blank=True, help_text="e.g. Python, Django, SQLite")
    link = models.URLField("Link (optional)", blank=True)
    bullets = models.TextField("What you built (one bullet per line)", max_length=2400)


class Certification(ResumeSection):
    name = models.CharField("Certification", max_length=150)
    issuer = models.CharField("Issued by", max_length=120, blank=True)
    year = models.CharField(max_length=20, blank=True)


class Achievement(ResumeSection):
    text = models.CharField("Achievement", max_length=300)


def upload_path(instance, filename):
    """Stored under a random name: the user's file name is never used on disk."""
    return f"resumes/{instance.user_id}/{uuid.uuid4().hex}.{instance.kind}"


class ResumeUpload(models.Model):
    """A resume file the user uploaded for review. PRIVATE: stored outside any public folder and only
    served through a login-protected view that checks the owner."""

    KIND_CHOICES = [("pdf", "PDF"), ("docx", "Word (.docx)"), ("txt", "Plain text")]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="resume_uploads")
    original_name = models.CharField(max_length=120)             # for display only
    kind = models.CharField(max_length=4, choices=KIND_CHOICES)
    file = models.FileField(upload_to=upload_path, max_length=200)
    size = models.PositiveIntegerField(default=0)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at", "-id"]

    def __str__(self):
        return self.original_name

    @property
    def safe_download_name(self):
        return re.sub(r"[^A-Za-z0-9._ -]", "_", self.original_name)[:100] or f"resume.{self.kind}"


@receiver(post_delete, sender=ResumeUpload)
def _remove_file_from_disk(sender, instance, **kwargs):
    """Deleting an upload (or the whole account) also deletes the file itself."""
    if instance.file:
        instance.file.delete(save=False)


class ResumeReview(models.Model):
    """A saved resume review. The job description (if any) is kept so the result can be understood later."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="resume_reviews")
    resume = models.ForeignKey(Resume, on_delete=models.SET_NULL, null=True, blank=True, related_name="reviews")
    upload = models.ForeignKey(ResumeUpload, on_delete=models.SET_NULL, null=True, blank=True, related_name="reviews")
    source_name = models.CharField(max_length=120)               # snapshot: survives deleting the resume
    source_kind = models.CharField(max_length=10)                # builder / upload
    job_description = models.TextField(max_length=10000, blank=True)
    score = models.PositiveSmallIntegerField()                   # indicative checklist score, 0-100
    result = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["user", "created_at"])]

    def __str__(self):
        return f"Review of {self.source_name}: {self.score}"
