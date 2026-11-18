from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.utils import get_user_today, safe_next
from learning.models import Topic

from . import services
from .forms import (AutoScheduleForm, DayTitleForm, GoalForm, RescheduleForm, StartChallengeForm)
from .models import CHALLENGE_DAYS, DailyGoal, DailyPlan

# SECURITY RULE: every plan and goal is fetched with user=request.user (other users get a 404).


def _needs_challenge(request):
    """Redirect to the planner start page if the 40-day challenge has not been created yet."""
    if not services.has_challenge(request.user):
        messages.info(request, "Start your 40-day challenge first.")
        return redirect("planner:overview")
    return None


@login_required
def overview(request):
    user = request.user
    today = get_user_today(user)
    if not services.has_challenge(user):
        form = StartChallengeForm(initial={"start_date": today})
        return render(request, "planner/start.html", {"form": form, "mode": "start"})
    return render(request, "planner/overview.html", {
        "summary": services.challenge_summary(user, today),
        "weeks": services.calendar_weeks(user, today),
        "overdue": services.overdue_goals(user, today),
        "today_plan": services.plan_for_date(user, today),
        "today": today})


@login_required
def start_challenge(request):
    if services.has_challenge(request.user):
        return redirect("planner:overview")
    form = StartChallengeForm(request.POST or None, initial={"start_date": get_user_today(request.user)})
    if request.method == "POST" and form.is_valid():
        services.start_challenge(request.user, form.cleaned_data["start_date"])
        messages.success(request, "Your 40-day challenge has started. Add goals to each day!")
        return redirect("planner:overview")
    return render(request, "planner/start.html", {"form": form, "mode": "start"})


@login_required
def change_start_date(request):
    if (r := _needs_challenge(request)):
        return r
    first = DailyPlan.objects.get(user=request.user, day_number=1)
    form = StartChallengeForm(request.POST or None, initial={"start_date": first.date})
    if request.method == "POST" and form.is_valid():
        services.shift_start_date(request.user, form.cleaned_data["start_date"])
        messages.success(request, "Start date changed. All goals kept their day numbers.")
        return redirect("planner:overview")
    return render(request, "planner/start.html", {"form": form, "mode": "change"})


@login_required
def today_redirect(request):
    if (r := _needs_challenge(request)):
        return r
    plan = services.plan_for_date(request.user, get_user_today(request.user))
    if plan is None:
        messages.info(request, "Today is outside your 40-day challenge dates.")
        return redirect("planner:overview")
    return redirect("planner:day_detail", day=plan.day_number)


@login_required
def day_detail(request, day):
    if (r := _needs_challenge(request)):
        return r
    plan = get_object_or_404(DailyPlan, user=request.user, day_number=day)
    today = get_user_today(request.user)
    goals = list(plan.goals.select_related("topic", "rescheduled_from"))
    done = sum(1 for g in goals if g.is_completed)
    return render(request, "planner/day_detail.html", {
        "plan": plan, "goals": goals, "done": done, "total": len(goals),
        "percent": services.percent(done, len(goals)),
        "planned_minutes": sum(g.estimated_minutes for g in goals),
        "done_minutes": sum(g.estimated_minutes for g in goals if g.is_completed),
        "state": services.day_state(plan, today, len(goals), done), "is_today": plan.date == today,
        "has_prev": day > 1, "has_next": day < CHALLENGE_DAYS,
        "title_form": DayTitleForm(instance=plan)})


@login_required
@require_POST
def day_title(request, day):
    plan = get_object_or_404(DailyPlan, user=request.user, day_number=day)
    form = DayTitleForm(request.POST, instance=plan)
    if form.is_valid():
        form.save()
        messages.success(request, "Day focus saved.")
    return redirect("planner:day_detail", day=day)


@login_required
def goal_create(request):
    if (r := _needs_challenge(request)):
        return r
    initial = {}
    if request.GET.get("day", "").isdigit():
        plan = DailyPlan.objects.filter(user=request.user, day_number=int(request.GET["day"])).first()
        if plan:
            initial["plan"] = plan
    if request.GET.get("topic", "").isdigit():
        topic = Topic.objects.filter(user=request.user, pk=int(request.GET["topic"])).first()
        if topic:
            initial.update(topic=topic, title=f"Learn: {topic.name}")
    form = GoalForm(request.POST or None, user=request.user, with_plan=True, initial=initial)
    if request.method == "POST" and form.is_valid():
        goal = form.save(commit=False)
        goal.user, goal.plan = request.user, form.cleaned_data["plan"]
        goal.save()
        messages.success(request, f"Goal added to Day {goal.plan.day_number}.")
        return redirect("planner:day_detail", day=goal.plan.day_number)
    return render(request, "planner/goal_form.html", {"form": form, "title": "Add a goal"})


@login_required
def goal_update(request, pk):
    goal = get_object_or_404(DailyGoal.objects.select_related("plan"), pk=pk, user=request.user)
    form = GoalForm(request.POST or None, instance=goal, user=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Goal updated.")
        return redirect("planner:day_detail", day=goal.plan.day_number)
    return render(request, "planner/goal_form.html", {"form": form, "title": f"Edit goal (Day {goal.plan.day_number})"})


@login_required
def goal_delete(request, pk):
    goal = get_object_or_404(DailyGoal.objects.select_related("plan"), pk=pk, user=request.user)
    if request.method == "POST":
        day = goal.plan.day_number
        goal.delete()
        messages.success(request, "Goal deleted.")
        return redirect("planner:day_detail", day=day)
    return render(request, "learning/confirm_delete.html", {
        "kind": "goal", "name": goal.title, "detail": "",
        "cancel_url": "planner:day_detail", "cancel_arg": goal.plan.day_number})


@login_required
@require_POST
def goal_toggle(request, pk):
    goal = get_object_or_404(DailyGoal.objects.select_related("plan"), pk=pk, user=request.user)
    completed = not goal.is_completed
    services.set_goal_completed(goal, completed)
    if completed:
        messages.success(request, f"Done: {goal.title}")
    return redirect(safe_next(request, redirect("planner:day_detail", day=goal.plan.day_number).url))


@login_required
def goal_reschedule(request, pk):
    goal = get_object_or_404(DailyGoal.objects.select_related("plan"), pk=pk, user=request.user)
    if goal.is_completed:
        messages.warning(request, "Completed goals cannot be rescheduled.")
        return redirect("planner:day_detail", day=goal.plan.day_number)
    form = RescheduleForm(request.POST or None, user=request.user, goal=goal,
                          initial=_suggest_plan(request.user, goal))
    if request.method == "POST" and form.is_valid():
        target = form.cleaned_data["plan"]
        services.reschedule_goal(goal, target)
        messages.success(request, f"“{goal.title}” moved to Day {target.day_number} ({target.date:%d %b}).")
        return redirect(safe_next(request, redirect("planner:day_detail", day=target.day_number).url))
    return render(request, "planner/reschedule.html", {"form": form, "goal": goal})


def _suggest_plan(user, goal):
    """Pre-select today (or the next day) as the new day."""
    today = get_user_today(user)
    plan = DailyPlan.objects.filter(user=user, date__gte=today).exclude(pk=goal.plan_id).order_by("date").first()
    return {"plan": plan} if plan else {}


@login_required
def auto_schedule(request):
    if (r := _needs_challenge(request)):
        return r
    today = get_user_today(request.user)
    current = services.plan_for_date(request.user, today)
    form = AutoScheduleForm(request.POST or None, user=request.user,
                            initial={"first_day": current.day_number if current else 1})
    if request.method == "POST" and form.is_valid():
        cd = form.cleaned_data
        created, left = services.auto_schedule(request.user, cd["technology"], cd["topics_per_day"],
                                               cd["first_day"], cd["minutes_per_topic"])
        msg = f"Created {created} goals from {cd['technology'].name}."
        if left:
            msg += f" {left} topics did not fit in the 40 days; they are not scheduled."
        if created == 0 and not left:
            msg = "Nothing to schedule: every topic is already completed or already planned."
        messages.success(request, msg)
        return redirect("planner:overview")
    return render(request, "planner/auto_schedule.html", {"form": form})
