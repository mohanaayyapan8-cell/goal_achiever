from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from accounts.utils import get_profile
from streaks import services as streak_services

from . import services
from .forms import ReminderSettingsForm
from .models import Notification


@login_required
def notification_list(request):
    show = request.GET.get("show", "all")
    qs = Notification.objects.filter(user=request.user)
    if show == "unread":
        qs = qs.filter(read_at__isnull=True)
    streak_services.refresh(request.user)
    return render(request, "notifications/list.html", {
        "items": qs[:100], "show": show, "unread": services.unread_count(request.user)})


@login_required
@require_POST
def mark_read(request, pk):
    note = get_object_or_404(Notification, pk=pk, user=request.user)
    services.mark_read(request.user, note.pk)
    return redirect("notifications:list")


@login_required
@require_POST
def mark_all_read(request):
    n = services.mark_read(request.user)
    if n:
        messages.success(request, f"Marked {n} notification{'s' if n != 1 else ''} as read.")
    return redirect("notifications:list")


@login_required
@require_POST
def delete(request, pk):
    get_object_or_404(Notification, pk=pk, user=request.user).delete()
    return redirect("notifications:list")


@login_required
def reminder_settings(request):
    profile = get_profile(request.user)
    form = ReminderSettingsForm(request.POST or None, instance=profile)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Reminder settings saved.")
        return redirect("notifications:settings")
    return render(request, "notifications/settings.html", {"form": form})


@login_required
@require_GET
def poll(request):
    """Called by the page every minute while it is open: refreshes streak/reminder state and
    returns the newest unread notifications (the browser may show them as pop-ups)."""
    streak_services.refresh(request.user)
    unread = Notification.objects.filter(user=request.user, read_at__isnull=True)
    return JsonResponse({"unread": unread.count(), "items": [
        {"id": n.pk, "kind": n.kind, "title": n.title, "message": n.message, "link": n.link} for n in unread[:10]]})
