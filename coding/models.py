import json

from django.conf import settings
from django.db import models

EASY, MEDIUM, HARD = "easy", "medium", "hard"
DIFFICULTY_CHOICES = [(EASY, "Easy"), (MEDIUM, "Medium"), (HARD, "Hard")]
PASSED, FAILED, SAVED, SELF_SOLVED = "passed", "failed", "saved", "self_solved"
SOLVED_STATUSES = (PASSED, SELF_SOLVED)


class CodingProblem(models.Model):
    """Shared problem bank (not owned by a user). Loaded from coding/problems.py on migrate."""

    slug = models.SlugField(max_length=60, unique=True)
    title = models.CharField(max_length=100)
    category = models.CharField(max_length=40)           # matches the DSA topics: Arrays, Strings, ...
    difficulty = models.CharField(max_length=6, choices=DIFFICULTY_CHOICES)
    description = models.TextField()
    constraints = models.TextField(blank=True)
    function_name = models.CharField(max_length=60)
    starter_code = models.TextField()
    solution = models.TextField()
    hint = models.TextField(blank=True)
    tests = models.JSONField(default=list)               # [{"args": [...], "expected": ..., "ll_result": bool}]
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["order", "id"]
        indexes = [models.Index(fields=["category", "difficulty"])]

    def __str__(self):
        return self.title

    @property
    def examples(self):
        """The first two tests, formatted for display."""
        return [{"args": ", ".join(json.dumps(a) if not (isinstance(a, dict) and "$list" in a) else f"list {a['$list']}" for a in t["args"]),
                 "expected": json.dumps(t["expected"])} for t in self.tests[:2]]


class CodingSubmission(models.Model):
    """One saved attempt. The server NEVER ran this code: 'browser' results come from the student's own
    browser sandbox (Pyodide); 'manual' ones are self-reported."""

    MODE_CHOICES = [("browser", "Run in browser sandbox"), ("manual", "Manual / self-checked")]
    STATUS_CHOICES = [(PASSED, "All tests passed"), (FAILED, "Some tests failed"), (SAVED, "Saved"), (SELF_SOLVED, "Marked solved (self-checked)")]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="coding_submissions")
    problem = models.ForeignKey(CodingProblem, on_delete=models.CASCADE, related_name="submissions")
    code = models.TextField()
    mode = models.CharField(max_length=8, choices=MODE_CHOICES)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES)
    passed_count = models.PositiveSmallIntegerField(default=0)
    total_count = models.PositiveSmallIntegerField(default=0)
    details = models.JSONField(default=list, blank=True)     # [{"i": test number, "p": passed, "e": error}]
    output = models.TextField(blank=True)
    error = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["user", "problem", "created_at"]), models.Index(fields=["user", "status"])]

    def __str__(self):
        return f"{self.problem.title}: {self.get_status_display()}"

    @property
    def is_solved(self):
        return self.status in SOLVED_STATUSES
