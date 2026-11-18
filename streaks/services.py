"""Streak engine.

RULES (all dates are the user's LOCAL calendar dates, see accounts.utils.get_user_today):
 1. A day counts as COMPLETED when its plan has at least one goal, every goal on it is done,
    AND at least one written and one speaking assessment were submitted on that local date.
 2. Each completed day adds 1 to the current streak. A date can only be recorded once.
 3. One missed day INTERRUPTS the streak (warning shown) but does not lose it:
    the next completed day continues it.
 4. Two missed calendar days in a row RESET the current streak to 0.
 5. A new streak starts with the next completed day.
 6. Past days are never edited and nothing is deleted when a streak resets:
    longest streak, completed days, goals and badges all stay.
Only days of the 40-day challenge from the moment it was created are judged.
"""
import calendar
from datetime import datetime, time, timedelta

from django.db import IntegrityError, transaction
from django.db.models import Count, Max
from django.urls import reverse

from accounts.utils import get_profile, get_user_now, get_user_today
from aptitude.models import AptitudeAttempt
from assessments.models import SUBMITTED, SpeakingAnswer, SpeakingAssessment, WrittenAssessment
from coding.models import SOLVED_STATUSES, CodingSubmission
from learning.models import LearningProgress
from notifications.services import notify
from planner.models import DailyGoal, DailyPlan
from resume_builder.models import Resume, ResumeReview

from .badges import BADGES
from .models import Achievement, StreakRecord

COMPLETE_MESSAGE = "Excellent work! You completed today's learning goals. Keep moving forward!"
MISSED_MESSAGE = "You missed that day's target. Don't give up. Your next successful day is a fresh opportunity!"
MILESTONES = (3, 7, 14, 21, 30, 40)


# ------------------------------------------------------------------ dates
def tz_of(user):
    return get_profile(user).tzinfo


def local_date(moment, tz):
    return moment.astimezone(tz).date()


def day_bounds(date, tz):
    """[start, end) of a local calendar day as aware datetimes (daylight-saving safe)."""
    return (datetime.combine(date, time.min, tzinfo=tz), datetime.combine(date + timedelta(days=1), time.min, tzinfo=tz))


# --------------------------------------------------------- one day's progress
def day_progress(user, date, tz=None):
    """What the user has done on `date`, and whether that makes it a completed day. None if no plan day."""
    tz = tz or tz_of(user)
    plan = DailyPlan.objects.filter(user=user, date=date).first()
    if plan is None:
        return None
    total = plan.goals.count()
    pending = plan.goals.filter(status=DailyGoal.PENDING).count()
    start, end = day_bounds(date, tz)
    written = WrittenAssessment.objects.filter(user=user, status=SUBMITTED, submitted_at__gte=start, submitted_at__lt=end).count()
    speaking = SpeakingAssessment.objects.filter(user=user, status=SUBMITTED, submitted_at__gte=start, submitted_at__lt=end).count()
    goals_ok, written_ok, speaking_ok = total > 0 and pending == 0, written >= 1, speaking >= 1
    return {"plan": plan, "day_number": plan.day_number, "total": total, "done": total - pending, "pending": pending,
            "written": written, "speaking": speaking, "goals_ok": goals_ok, "written_ok": written_ok,
            "speaking_ok": speaking_ok, "complete": goals_ok and written_ok and speaking_ok}


# ------------------------------------------------------- recording days (immutable)
def _previous(user, date):
    return StreakRecord.objects.filter(user=user, date__lt=date).order_by("-date").first()


def record_completed(user, date, progress=None):
    """Settle `date` as completed. Returns (record, created). A date already recorded is left untouched."""
    try:
        with transaction.atomic():
            existing = StreakRecord.objects.filter(user=user, date=date).first()
            if existing:
                return existing, False
            prev = _previous(user, date)
            p = progress or {}
            return StreakRecord.objects.create(
                user=user, date=date, status=StreakRecord.COMPLETED, streak_after=(prev.streak_after if prev else 0) + 1,
                missed_run_after=0, day_number=p.get("day_number"), goals_total=p.get("total", 0), goals_done=p.get("done", 0),
                written_count=p.get("written", 0), speaking_count=p.get("speaking", 0)), True
    except IntegrityError:
        return StreakRecord.objects.get(user=user, date=date), False


def record_missed(user, date, day_number=None):
    """Settle `date` as missed: the 1st miss interrupts the streak, the 2nd in a row resets it to 0."""
    try:
        with transaction.atomic():
            existing = StreakRecord.objects.filter(user=user, date=date).first()
            if existing:
                return existing, False
            prev = _previous(user, date)
            run = (prev.missed_run_after if prev and prev.status == StreakRecord.MISSED else 0) + 1
            streak = 0 if run >= 2 else (prev.streak_after if prev else 0)
            return StreakRecord.objects.create(user=user, date=date, status=StreakRecord.MISSED, streak_after=streak,
                                               missed_run_after=run, day_number=day_number), True
    except IntegrityError:
        return StreakRecord.objects.get(user=user, date=date), False


def has_challenge(user):
    return DailyPlan.objects.filter(user=user).exists()


def sync(user, today=None):
    """Settle every finished day (before `today`) that has no record yet as MISSED.
    Today is never judged until it is over. Returns the newly created records."""
    today = today or get_user_today(user)
    plans = list(DailyPlan.objects.filter(user=user).order_by("date"))
    if not plans:
        return []
    tz = tz_of(user)
    tracking_start = max(plans[0].date, local_date(plans[0].created_at, tz))
    have = set(StreakRecord.objects.filter(user=user).values_list("date", flat=True))
    created = []
    for plan in plans:
        if plan.date < tracking_start or plan.date >= today or plan.date in have:
            continue
        rec, was_new = record_missed(user, plan.date, plan.day_number)
        if was_new:
            created.append(rec)
    if created:
        _notify_missed(user, created)
    return created


def _notify_missed(user, new_records):
    last = new_records[-1]
    if any(r.missed_run_after == 2 for r in new_records) or last.missed_run_after >= 2:
        notify(user, "warning", "Your streak was reset",
               f"You missed two days in a row, so your current streak went back to 0. Your history, badges and longest streak are safe. "
               f"{MISSED_MESSAGE}", reverse("planner:today"), key=f"reset:{last.date}")
    else:
        notify(user, "warning", "You missed a day",
               f"{MISSED_MESSAGE} Your streak is interrupted, not lost: complete today to keep it going. "
               "Missing today as well will reset it.", reverse("planner:today"), key=f"missed:{last.date}")


def evaluate_today(user, today=None):
    """Re-check today. Today's record is provisional: it appears when the day becomes complete and
    is withdrawn if the day stops being complete before midnight. Returns (progress, record)."""
    today = today or get_user_today(user)
    sync(user, today)
    progress = day_progress(user, today)
    if progress is None:
        return None, None
    rec = StreakRecord.objects.filter(user=user, date=today).first()
    if progress["complete"]:
        if rec is None:
            rec, created = record_completed(user, today, progress)
            if created:
                notify(user, "success", "Day complete!", f"{COMPLETE_MESSAGE} Current streak: {rec.streak_after} day{'s' if rec.streak_after != 1 else ''}.",
                       reverse("streaks:overview"), key=f"day-complete:{today}")
    elif rec is not None and rec.status == StreakRecord.COMPLETED:
        rec.delete()     # only ever today's own record, withdrawn the same day
        rec = None
    return progress, rec


# ------------------------------------------------------------------- status
def status(user, today=None):
    """Read-only snapshot used by the dashboard and the streak page."""
    today = today or get_user_today(user)
    plans = list(DailyPlan.objects.filter(user=user).order_by("date").values_list("date", flat=True))
    out = {"state": "no_challenge", "streak": 0, "longest": 0, "missed_run": 0, "progress": None, "today": today}
    if not plans:
        out["message"] = "Start your 40-day challenge to begin building a streak."
        return out
    # records dated after "today" can only appear after a timezone change: ignore them until that date arrives
    latest = StreakRecord.objects.filter(user=user, date__lte=today).order_by("-date").first()
    out["streak"] = latest.streak_after if latest else 0
    out["longest"] = StreakRecord.objects.filter(user=user, date__lte=today).aggregate(m=Max("streak_after"))["m"] or 0
    out["missed_run"] = latest.missed_run_after if latest and latest.status == StreakRecord.MISSED else 0
    out["progress"] = day_progress(user, today)
    done_today = bool(latest and latest.date == today and latest.status == StreakRecord.COMPLETED)
    if plans[-1] < today:
        state, msg = "challenge_over", "Your 40-day challenge has finished. Well done for showing up!"
    elif plans[0] > today:
        state, msg = "not_started", f"Your challenge starts on {plans[0]:%d %b %Y}. Get ready!"
    elif out["progress"] is None:
        state, msg = "no_plan", "There is no plan for today. Check your start date in the planner."
    elif done_today:
        state, msg = "completed_today", COMPLETE_MESSAGE
    elif out["missed_run"] >= 2:
        state, msg = "reset", "Your streak was reset. Don't give up. Your next successful day starts a fresh streak!"
    elif out["missed_run"] == 1:
        state, msg = "interrupted", "You missed yesterday. Your streak is interrupted but not lost: complete today to keep it going. Missing today too will reset it."
    elif out["progress"]["total"] == 0:
        state, msg = "no_goals", "Add at least one goal for today, then finish it and both assessments to extend your streak."
    else:
        state, msg = "in_progress", "Finish today's goals and both assessments to keep your streak alive."
    out.update(state=state, message=msg, done_today=done_today)
    return out


def activity_dates(user):
    """Every local date on which the user did something (goal, assessment, aptitude test, coding attempt)."""
    tz = tz_of(user)
    moments = []
    moments += DailyGoal.objects.filter(user=user, completed_at__isnull=False).values_list("completed_at", flat=True)
    moments += WrittenAssessment.objects.filter(user=user, status=SUBMITTED).values_list("submitted_at", flat=True)
    moments += SpeakingAssessment.objects.filter(user=user, status=SUBMITTED).values_list("submitted_at", flat=True)
    moments += AptitudeAttempt.objects.filter(user=user, status="submitted").values_list("submitted_at", flat=True)
    moments += CodingSubmission.objects.filter(user=user).values_list("created_at", flat=True)
    return {local_date(m, tz) for m in moments if m}


def weekly_consistency(user, today):
    """Completed days among the challenge days of the last 7 days (today counts only once completed)."""
    start = today - timedelta(days=6)
    plan_dates = set(DailyPlan.objects.filter(user=user, date__range=(start, today)).values_list("date", flat=True))
    done = set(StreakRecord.objects.filter(user=user, status=StreakRecord.COMPLETED, date__range=(start, today)).values_list("date", flat=True))
    if today not in done:
        plan_dates.discard(today)
    plan_dates |= done
    days = len(plan_dates)
    return {"completed": len(done), "days": days, "percent": round(100 * len(done) / days) if days else None}


def overview_stats(user, today=None):
    today = today or get_user_today(user)
    st = status(user, today)
    return {
        "streak": st["streak"], "longest": st["longest"],
        "completed_days": StreakRecord.objects.filter(user=user, status=StreakRecord.COMPLETED).count(),
        "active_days": len(activity_dates(user)),
        "goals_done": DailyGoal.objects.filter(user=user, status=DailyGoal.COMPLETED).count(),
        "weekly": weekly_consistency(user, today),
    }


def heatmap(user, year, month, today):
    """Weeks (Monday first) for one month. Cell: {date, state, number}; None for blanks.
    state: completed, missed, partial (some activity), today, upcoming (inside the challenge), none."""
    records = {r.date: r for r in StreakRecord.objects.filter(user=user, date__year=year, date__month=month)}
    plan_dates = set(DailyPlan.objects.filter(user=user, date__year=year, date__month=month).values_list("date", flat=True))
    active = activity_dates(user)
    first_weekday, days = calendar.monthrange(year, month)
    cells = [None] * first_weekday
    for day in range(1, days + 1):
        d = datetime(year, month, day).date()
        rec = records.get(d)
        if rec and rec.status == StreakRecord.COMPLETED:
            state = "completed"
        elif rec and rec.status == StreakRecord.MISSED:
            state = "missed"
        elif d == today:
            state = "today"
        elif d in active and d < today:
            state = "partial"
        elif d in plan_dates and d > today:
            state = "upcoming"
        else:
            state = "none"
        cells.append({"date": d, "number": day, "state": state, "is_today": d == today, "in_challenge": d in plan_dates})
    cells += [None] * (-len(cells) % 7)
    return [cells[i:i + 7] for i in range(0, len(cells), 7)]


# ------------------------------------------------------------------- badges
def badge_stats(user):
    done = StreakRecord.objects.filter(user=user, status=StreakRecord.COMPLETED)
    records = list(StreakRecord.objects.filter(user=user).order_by("date").values_list("status", flat=True))
    comeback = any(a == StreakRecord.MISSED and b == StreakRecord.COMPLETED for a, b in zip(records, records[1:]))
    written = WrittenAssessment.objects.filter(user=user, status=SUBMITTED)
    apt = AptitudeAttempt.objects.filter(user=user, status="submitted")
    solved = CodingSubmission.objects.filter(user=user, status__in=SOLVED_STATUSES)
    return {
        "completed_days": done.count(), "longest": StreakRecord.objects.filter(user=user).aggregate(m=Max("streak_after"))["m"] or 0,
        "comeback": comeback, "goals_done": DailyGoal.objects.filter(user=user, status=DailyGoal.COMPLETED).count(),
        "topics_completed": LearningProgress.objects.filter(user=user, status=LearningProgress.COMPLETED).count(),
        "written_count": written.count(), "written_best": written.aggregate(m=Max("score"))["m"],
        "speaking_count": SpeakingAssessment.objects.filter(user=user, status=SUBMITTED).count(),
        "speaking_best": SpeakingAnswer.objects.filter(user=user).aggregate(m=Max("overall"))["m"],
        "resume_count": Resume.objects.filter(user=user).count(), "review_count": ResumeReview.objects.filter(user=user).count(),
        "aptitude_count": apt.count(), "aptitude_best": apt.aggregate(m=Max("percent"))["m"],
        "coding_solved": solved.values("problem").distinct().count(),
        "coding_hard_solved": solved.filter(problem__difficulty="hard").values("problem").distinct().count(),
    }


def award_badges(user):
    """Give every badge the user has now earned. Idempotent. Returns the newly awarded badges."""
    have = set(Achievement.objects.filter(user=user).values_list("key", flat=True))
    stats = badge_stats(user)
    new = []
    for badge in BADGES:
        if badge.key in have or not badge.check(stats):
            continue
        ach, created = Achievement.objects.get_or_create(
            user=user, key=badge.key, defaults={"title": badge.title, "description": badge.description, "icon": badge.icon})
        if created:
            new.append(ach)
            notify(user, "badge", f"New badge: {badge.title}", f"{badge.icon} {badge.description}", reverse("streaks:overview"), key=f"badge:{badge.key}")
    return new


# ---------------------------------------------------------------- reminders
def ensure_reminder(user, now=None):
    """Create today's in-app reminder once, if the reminder time has passed and today is not complete yet."""
    profile = get_profile(user)
    if not profile.daily_reminder_time:
        return None
    local_now = get_user_now(user, now)
    if local_now.time() < profile.daily_reminder_time:
        return None
    progress = day_progress(user, local_now.date())
    if progress is None or progress["complete"]:
        return None
    todo = []
    if progress["total"] == 0:
        todo.append("add today's goals")
    elif progress["pending"]:
        todo.append(f"{progress['pending']} goal{'s' if progress['pending'] != 1 else ''}")
    if not progress["written_ok"]:
        todo.append("the written assessment")
    if not progress["speaking_ok"]:
        todo.append("the speaking assessment")
    listed = todo[0] if len(todo) == 1 else ", ".join(todo[:-1]) + " and " + todo[-1]
    note, _ = notify(user, "reminder", "Today's goals are waiting",
                     f"Day {progress['day_number']}: still to do: {listed}. A small step now keeps your streak alive.",
                     reverse("planner:today"), key=f"reminder:{local_now.date()}")
    return note


# ---------------------------------------------------------------- entry points
def on_activity(user):
    """Called after anything that can change progress (see signals.py)."""
    today = get_user_today(user)
    if has_challenge(user):
        evaluate_today(user, today)
    award_badges(user)


def refresh(user, now=None):
    """Bring everything up to date when the user opens a page (or the reminder command runs)."""
    on_activity(user)
    return ensure_reminder(user, now)
