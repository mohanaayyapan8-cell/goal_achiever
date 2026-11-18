"""Re-check streaks and badges whenever progress changes. Kept here so no other app needs to know about streaks."""
from django.contrib.auth import get_user_model
from django.db.models.signals import post_delete, post_save


def _touch(user):
    from .services import on_activity
    on_activity(user)


def _goal_saved(sender, instance, raw=False, **kwargs):
    if not raw:
        _touch(instance.user)


def _goal_deleted(sender, instance, origin=None, **kwargs):
    if isinstance(origin, get_user_model()):      # the whole account is being deleted: do nothing
        return
    _touch(instance.user)


def _submitted(sender, instance, raw=False, **kwargs):
    if not raw and getattr(instance, "status", "") == "submitted":
        _touch(instance.user)


def _created_or_changed(sender, instance, raw=False, **kwargs):
    if not raw:
        _touch(instance.user)


def connect():
    from aptitude.models import AptitudeAttempt
    from assessments.models import SpeakingAssessment, WrittenAssessment
    from coding.models import CodingSubmission
    from learning.models import LearningProgress
    from planner.models import DailyGoal
    from resume_builder.models import Resume, ResumeReview

    post_save.connect(_goal_saved, sender=DailyGoal, dispatch_uid="streaks_goal_saved")
    post_delete.connect(_goal_deleted, sender=DailyGoal, dispatch_uid="streaks_goal_deleted")
    for model in (WrittenAssessment, SpeakingAssessment, AptitudeAttempt):
        post_save.connect(_submitted, sender=model, dispatch_uid=f"streaks_submitted_{model.__name__}")
    for model in (CodingSubmission, LearningProgress, Resume, ResumeReview):
        post_save.connect(_created_or_changed, sender=model, dispatch_uid=f"streaks_changed_{model.__name__}")
