import random
from collections import defaultdict
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.db.models import Avg, Max
from django.utils import timezone

from .bank import all_questions
from .models import IN_PROGRESS, SUBMITTED, AptitudeAttempt, AptitudeQuestion
from .topics import SECTIONS

GRACE_SECONDS = 20                     # network delay allowed when the page auto-submits at 0:00
COUNT_CHOICES = [5, 10, 15, 20]
MINUTE_CHOICES = [5, 10, 15, 20, 30, 45, 60]


def load_bank():
    """Insert or update the shared question bank. Safe to run any number of times."""
    created = updated = 0
    for row in all_questions():
        obj, was_created = AptitudeQuestion.objects.update_or_create(key=row["key"], defaults={
            k: row[k] for k in ("section", "topic", "passage", "stem", "options", "correct_index", "explanation")})
        created += was_created
        updated += not was_created
    return created, updated


def default_minutes(count):
    return min([m for m in MINUTE_CHOICES if m >= count] or [60])


def start_attempt(user, section, topic="", count=10, minutes=None, now=None):
    """Start a test, or return the unfinished one. Returns (attempt, created)."""
    now = now or timezone.now()
    if section not in SECTIONS:
        raise ValueError("Unknown section.")
    if topic and topic not in SECTIONS[section][1]:
        raise ValueError("Unknown topic for this section.")
    if count not in COUNT_CHOICES:
        raise ValueError("Choose 5, 10, 15 or 20 questions.")
    minutes = minutes or default_minutes(count)
    if minutes not in MINUTE_CHOICES:
        raise ValueError("Unsupported time limit.")
    open_attempt = AptitudeAttempt.objects.filter(user=user, status=IN_PROGRESS).first()
    if open_attempt:
        if not open_attempt.is_expired(now):
            return open_attempt, False
        finalize(open_attempt, now=now)           # an old unfinished test: grade it first
    pool = AptitudeQuestion.objects.filter(section=section, is_active=True)
    if topic:
        pool = pool.filter(topic=topic)
    ids = list(pool.values_list("pk", flat=True))
    if not ids:
        raise ValueError("There are no questions for that choice yet.")
    chosen = random.sample(ids, min(count, len(ids)))
    by_id = {q.pk: q for q in AptitudeQuestion.objects.filter(pk__in=chosen)}
    snapshots = [{"topic": by_id[i].topic, "stem": by_id[i].stem, "passage": by_id[i].passage, "options": by_id[i].options,
                  "correct": by_id[i].correct_index, "explanation": by_id[i].explanation} for i in chosen]
    try:
        with transaction.atomic():
            attempt = AptitudeAttempt.objects.create(user=user, section=section, topic=topic, questions=snapshots,
                                                     time_limit_seconds=minutes * 60, started_at=now, total_count=len(snapshots))
        return attempt, True
    except IntegrityError:        # double click: someone else created it first
        return AptitudeAttempt.objects.get(user=user, status=IN_PROGRESS), False


def autosave_answer(attempt, index, option, now=None):
    """Remember one answer while the test is running. Refused after the deadline."""
    now = now or timezone.now()
    if attempt.is_submitted or attempt.is_expired(now):
        return False
    if not (0 <= index < len(attempt.questions)) or option not in (None, 0, 1, 2, 3):
        return False
    answers = dict(attempt.answers)
    if option is None:
        answers.pop(str(index), None)
    else:
        answers[str(index)] = option
    attempt.answers = answers
    attempt.save(update_fields=["answers"])
    return True


def _clean_posted(attempt, posted):
    clean = {}
    for key, value in (posted or {}).items():
        try:
            i, v = int(key), int(value)
        except (TypeError, ValueError):
            continue
        if 0 <= i < len(attempt.questions) and 0 <= v <= 3:
            clean[str(i)] = v
    return clean


@transaction.atomic
def finalize(attempt, posted=None, now=None):
    """Grade and lock the test. Answers posted after deadline + grace are ignored; saved answers still count.
    Safe to call twice. Returns (attempt, graded_now)."""
    now = now or timezone.now()
    attempt = AptitudeAttempt.objects.select_for_update().get(pk=attempt.pk)
    if attempt.is_submitted:
        return attempt, False
    answers = dict(attempt.answers)
    if posted and now <= attempt.deadline + timedelta(seconds=GRACE_SECONDS):
        answers.update(_clean_posted(attempt, posted))
    attempt.answers = answers
    attempt.correct_count = sum(1 for i, q in enumerate(attempt.questions) if answers.get(str(i)) == q["correct"])
    attempt.total_count = len(attempt.questions)
    attempt.percent = round(100 * attempt.correct_count / attempt.total_count, 1) if attempt.total_count else 0.0
    attempt.timed_out = now > attempt.deadline
    attempt.seconds_used = int(max(0, (min(now, attempt.deadline) - attempt.started_at).total_seconds()))
    attempt.status, attempt.submitted_at = SUBMITTED, now
    attempt.save()
    return attempt, True


def finalize_if_expired(attempt, now=None):
    now = now or timezone.now()
    if not attempt.is_submitted and attempt.is_expired(now):
        return finalize(attempt, now=now)[0]
    return attempt


# ----------------------------------------------------------------- statistics
def section_stats(user):
    rows = {}
    for key, (title, _) in SECTIONS.items():
        qs = AptitudeAttempt.objects.filter(user=user, section=key, status=SUBMITTED)
        agg = qs.aggregate(avg=Avg("percent"), best=Max("percent"))
        rows[key] = {"title": title, "attempts": qs.count(), "avg": round(agg["avg"]) if agg["avg"] is not None else None,
                     "best": round(agg["best"]) if agg["best"] is not None else None}
    return rows


def topic_accuracy(user, section=None, limit=100):
    """[(section, topic, correct, total, percent)] from the latest submitted attempts, weakest first."""
    qs = AptitudeAttempt.objects.filter(user=user, status=SUBMITTED)
    if section:
        qs = qs.filter(section=section)
    totals = defaultdict(lambda: [0, 0])
    for attempt in qs.order_by("-submitted_at")[:limit]:
        for i, q in enumerate(attempt.questions):
            cell = totals[(attempt.section, q["topic"])]
            cell[1] += 1
            cell[0] += attempt.answers.get(str(i)) == q["correct"]
    out = [(s, t, c, n, round(100 * c / n)) for (s, t), (c, n) in totals.items()]
    return sorted(out, key=lambda r: (r[4], -r[3]))


def overall_stats(user):
    qs = AptitudeAttempt.objects.filter(user=user, status=SUBMITTED)
    agg = qs.aggregate(avg=Avg("percent"))
    return {"attempts": qs.count(), "avg": round(agg["avg"]) if agg["avg"] is not None else None}
