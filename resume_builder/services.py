from django.db.models import Count

from accounts.utils import get_profile
from coding.models import SOLVED_STATUSES, CodingSubmission
from learning.models import LearningProgress

from . import ats
from .models import MAX_REVIEWS, ResumeReview


def learned_skills(user):
    """Skills the user has actually practised in Goal Achiever: [(skill, reason)]."""
    out = []
    rows = (LearningProgress.objects.filter(user=user, status=LearningProgress.COMPLETED)
            .values("topic__technology__name").annotate(n=Count("id")).filter(n__gte=3))
    for row in rows:
        name = row["topic__technology__name"]
        for skill in ats.LEARNED_SKILLS.get(name.lower(), []):
            out.append((skill, f"You completed {row['n']} {name} topics on Goal Achiever"))
    solved = CodingSubmission.objects.filter(user=user, status__in=SOLVED_STATUSES).values("problem").distinct().count()
    if solved >= 5:
        out += [("data structures", f"You solved {solved} coding problems on Goal Achiever"), ("algorithms", f"You solved {solved} coding problems on Goal Achiever")]
    return out


def run_review(user, text, job_description, source_name, source_kind, meta=None, resume=None, upload=None, target_role=None):
    """Analyse text, save the result, and keep only the newest reviews."""
    role = target_role if target_role is not None else get_profile(user).target_role
    result = ats.analyze(text, job_description, meta=meta, target_role=role, learned=learned_skills(user))
    review = ResumeReview.objects.create(user=user, resume=resume, upload=upload, source_name=source_name[:120], source_kind=source_kind,
                                         job_description=(job_description or "")[:10000], score=result["score"], result=result)
    old = list(ResumeReview.objects.filter(user=user).values_list("pk", flat=True)[MAX_REVIEWS:])
    if old:
        ResumeReview.objects.filter(pk__in=old).delete()
    return review


def quick_wins(result, limit=3):
    """The checks that would add the most points, with advice."""
    checks = [c for g in result["groups"] for c in g["checks"] if c["max"] and c["earned"] < c["max"] and c["advice"]]
    return sorted(checks, key=lambda c: c["earned"] - c["max"])[:limit]
