from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from accounts.utils import get_profile, get_user_now
from learning import services
from learning.models import LearningProgress
from aptitude import services as aptitude_services
from assessments import services as assessment_services
from coding import services as coding_services
from planner import services as planner
from resume_builder.models import Resume, ResumeReview, ResumeUpload
from streaks import services as streak_services
from streaks.models import Achievement

PHASES = [
    ("Phase 1", "Project architecture and setup", "done"),
    ("Phase 2", "Authentication and user profiles", "done"),
    ("Phase 3", "Dashboard and domain management", "done"),
    ("Phase 4", "Learning content and daily planner", "done"),
    ("Phase 5", "Written and speaking assessments", "done"),
    ("Phase 6", "Aptitude and DSA", "done"),
    ("Phase 7", "Streaks and notifications", "done"),
    ("Phase 8", "Resume and professional profile", "done"),
    ("Phase 9", "Analytics and reports", "next"),
    ("Phase 10", "Testing, GitHub and deployment", "todo"),
]


def home(request):
    """Public landing page. Logged-in users go straight to their dashboard."""
    if request.user.is_authenticated:
        return redirect("dashboard:index")
    return render(request, "dashboard/home.html", {"phases": PHASES, "debug": settings.DEBUG})


MOTIVATION = [
    "Small steps every day beat big bursts once a month.",
    "You do not have to be perfect. You just have to show up today.",
    "Every topic you finish is one less thing between you and the offer letter.",
    "Consistency is your superpower. Keep the chain going!",
    "Hard today, easier tomorrow. Keep learning.",
    "Your future self will thank you for the work you do right now.",
    "Progress, not perfection.",
]


@login_required
def index(request):
    """Personal dashboard. Streak, planner and hours widgets arrive in later phases."""
    user = request.user
    profile = get_profile(user)
    streak_services.refresh(user)        # settle finished days, today's record, badges and due reminders
    now = get_user_now(user)
    hour = now.hour
    greeting = "Good morning" if hour < 12 else "Good afternoon" if hour < 17 else "Good evening"

    stats = services.overall_stats(user)
    domains = services.domains_with_progress(user)
    recent = (LearningProgress.objects.filter(user=user, status=LearningProgress.COMPLETED)
              .select_related("topic__technology__domain").order_by("-completed_at")[:5])
    in_progress = (LearningProgress.objects.filter(user=user, status=LearningProgress.IN_PROGRESS)
                   .select_related("topic__technology__domain").order_by("-updated_at")[:5])

    today = now.date()
    summary = planner.challenge_summary(user, today)
    today_plan = planner.plan_for_date(user, today) if summary else None
    today_goals = list(today_plan.goals.select_related("topic")) if today_plan else []
    today_done = sum(1 for g in today_goals if g.is_completed)
    overdue_count = planner.overdue_goals(user, today).count() if summary else 0

    chart_data = {
        "overall": {"labels": ["Completed", "In progress", "Not started"],
                    "values": [stats["completed"], stats["in_progress"], stats["not_started"]]},
        "domains": {"labels": [d.name for d in domains], "values": [d.percent for d in domains]},
    }
    return render(request, "dashboard/index.html", {
        "profile": profile, "now": now, "greeting": greeting, "stats": stats, "domains": domains,
        "recent": recent, "in_progress": in_progress, "chart_data": chart_data,
        "challenge": summary, "today_plan": today_plan, "today_goals": today_goals,
        "today_done": today_done, "today_percent": planner.percent(today_done, len(today_goals)),
        "overdue_count": overdue_count, "assess": assessment_services.overview_stats(user),
        "resume_info": {"resumes": Resume.objects.filter(user=user).count(), "uploads": ResumeUpload.objects.filter(user=user).count(),
                        "last_review": ResumeReview.objects.filter(user=user).first()},
        "streak": streak_services.status(user), "recent_badges": Achievement.objects.filter(user=user)[:4],
        "apt": aptitude_services.overall_stats(user), "dsa": coding_services.progress(user),
        "motivation": MOTIVATION[now.date().toordinal() % len(MOTIVATION)],
    })
