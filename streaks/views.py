import re
from datetime import date

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from accounts.utils import get_user_today

from . import services
from .badges import BADGES
from .models import Achievement, StreakRecord


def _month_from(request, today):
    m = re.fullmatch(r"(\d{4})-(\d{2})", request.GET.get("month", ""))
    year, month = (int(m[1]), int(m[2])) if m and 1 <= int(m[2]) <= 12 else (today.year, today.month)
    index = year * 12 + month - 1                      # keep within two years of today
    low, high = today.year * 12 + today.month - 1 - 24, today.year * 12 + today.month - 1 + 24
    index = min(max(index, low), high)
    return index // 12, index % 12 + 1


def _shift(year, month, delta):
    index = year * 12 + month - 1 + delta
    return index // 12, index % 12 + 1


@login_required
def overview(request):
    user = request.user
    services.refresh(user)
    today = get_user_today(user)
    year, month = _month_from(request, today)
    py, pm = _shift(year, month, -1)
    ny, nm = _shift(year, month, 1)
    earned = {a.key: a for a in Achievement.objects.filter(user=user)}
    return render(request, "streaks/overview.html", {
        "status": services.status(user, today), "stats": services.overview_stats(user, today),
        "weeks": services.heatmap(user, year, month, today), "month_label": date(year, month, 1).strftime("%B %Y"),
        "prev_month": f"{py}-{pm:02d}", "next_month": f"{ny}-{nm:02d}", "is_current_month": (year, month) == (today.year, today.month),
        "badges": [{"badge": b, "ach": earned.get(b.key)} for b in BADGES], "earned_count": len(earned),
        "history": StreakRecord.objects.filter(user=user).order_by("-date")[:30]})
