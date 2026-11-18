"""Planner logic. 'today' is always passed in (the USER's local date) so it is easy to test."""
from datetime import timedelta

from django.db import transaction
from django.db.models import Count, Q, Sum
from django.utils import timezone

from .models import CHALLENGE_DAYS, DailyGoal, DailyPlan

DONE_Q = Q(goals__status=DailyGoal.COMPLETED)


def percent(done, total):
    return round(done * 100 / total) if total else 0


def has_challenge(user):
    return DailyPlan.objects.filter(user=user).exists()


@transaction.atomic
def start_challenge(user, start_date):
    if has_challenge(user):
        raise ValueError("The challenge has already been started.")
    DailyPlan.objects.bulk_create([
        DailyPlan(user=user, day_number=n, date=start_date + timedelta(days=n - 1))
        for n in range(1, CHALLENGE_DAYS + 1)])


@transaction.atomic
def shift_start_date(user, new_start):
    """Move Day 1 to a new date. Every goal stays on its day number."""
    plans = list(DailyPlan.objects.filter(user=user))
    for plan in plans:
        plan.date = new_start + timedelta(days=plan.day_number - 1)
    DailyPlan.objects.bulk_update(plans, ["date"])


def annotated_plans(user):
    return DailyPlan.objects.filter(user=user).annotate(
        total=Count("goals", distinct=True), done=Count("goals", filter=DONE_Q, distinct=True))


def plan_for_date(user, date):
    return DailyPlan.objects.filter(user=user, date=date).first()


def day_state(plan, today, total, done):
    """'done', 'today', 'upcoming', 'incomplete' (past day with unfinished goals) or 'empty'."""
    if total and done == total:
        return "done"
    if plan.date == today:
        return "today"
    if plan.date > today:
        return "upcoming"
    return "incomplete" if total > done else "empty"


def _decorate(plan, today):
    plan.percent = percent(plan.done, plan.total)
    plan.state = day_state(plan, today, plan.total, plan.done)
    plan.is_today = plan.date == today
    return plan


def calendar_weeks(user, today):
    """Weeks (Monday to Sunday) covering the challenge; None marks blank cells."""
    plans = [_decorate(p, today) for p in annotated_plans(user)]
    if not plans:
        return []
    cells = [None] * plans[0].date.weekday() + plans
    cells += [None] * (-len(cells) % 7)
    return [cells[i:i + 7] for i in range(0, len(cells), 7)]


def challenge_summary(user, today):
    plans = [_decorate(p, today) for p in annotated_plans(user)]
    if not plans:
        return None
    start, end = plans[0].date, plans[-1].date
    goals_total = sum(p.total for p in plans)
    goals_done = sum(p.done for p in plans)
    minutes = (DailyGoal.objects.filter(user=user, status=DailyGoal.COMPLETED)
               .aggregate(m=Sum("estimated_minutes"))["m"] or 0)
    if today < start:
        current, phase = 0, "not_started"
    elif today > end:
        current, phase = CHALLENGE_DAYS, "finished"
    else:
        current, phase = (today - start).days + 1, "running"
    return {
        "start": start, "end": end, "phase": phase, "current_day": current, "days": CHALLENGE_DAYS,
        "days_left": max((end - today).days, 0) if phase != "finished" else 0,
        "days_fully_done": sum(1 for p in plans if p.state == "done"),
        "goals_total": goals_total, "goals_done": goals_done, "goals_pending": goals_total - goals_done,
        "goal_percent": percent(goals_done, goals_total),
        "minutes_done": minutes, "hours_done": round(minutes / 60, 1),
        "calendar_percent": round(current * 100 / CHALLENGE_DAYS),
    }


def overdue_goals(user, today):
    """Pending goals on days that are already over. Shown to the user, never deleted."""
    return (DailyGoal.objects.filter(user=user, status=DailyGoal.PENDING, plan__date__lt=today)
            .select_related("plan", "topic").order_by("plan__date", "id"))


def set_goal_completed(goal, completed):
    if completed:
        if not goal.is_completed:
            goal.status, goal.completed_at = DailyGoal.COMPLETED, timezone.now()
    else:
        goal.status, goal.completed_at = DailyGoal.PENDING, None
    goal.save(update_fields=["status", "completed_at"])
    return goal


def reschedule_goal(goal, new_plan):
    """Move an unfinished goal to another day, remembering where it started."""
    if new_plan.user_id != goal.user_id:
        raise ValueError("That day does not belong to you.")
    if goal.is_completed:
        raise ValueError("Completed goals cannot be rescheduled.")
    if new_plan.pk == goal.plan_id:
        raise ValueError("The goal is already on that day.")
    if goal.rescheduled_from_id is None:
        goal.rescheduled_from_id = goal.plan_id   # remember the ORIGINAL day
    goal.plan = new_plan
    goal.reschedule_count += 1
    goal.save(update_fields=["plan", "rescheduled_from", "reschedule_count"])
    return goal


@transaction.atomic
def auto_schedule(user, technology, per_day, first_day, minutes):
    """Spread a technology's unfinished topics over the days, `per_day` goals each.
    Skips topics already completed or already waiting in a pending goal.
    Returns (goals_created, topics_left_over)."""
    from learning.models import LearningProgress

    scheduled = set(DailyGoal.objects.filter(user=user, status=DailyGoal.PENDING, topic__isnull=False)
                    .values_list("topic_id", flat=True))
    topics = [t for t in technology.topics.select_related("progress")
              if t.status != LearningProgress.COMPLETED and t.pk not in scheduled]
    plans = {p.day_number: p for p in DailyPlan.objects.filter(user=user, day_number__gte=first_day)}
    goals, day, slot = [], first_day, 0
    for topic in topics:
        if day > CHALLENGE_DAYS:
            break
        goals.append(DailyGoal(user=user, plan=plans[day], topic=topic, title=f"Learn: {topic.name}",
                               estimated_minutes=minutes))
        slot += 1
        if slot == per_day:
            day, slot = day + 1, 0
    DailyGoal.objects.bulk_create(goals)
    return len(goals), len(topics) - len(goals)
