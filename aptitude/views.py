from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from . import services
from .models import SUBMITTED, AptitudeAttempt
from .topics import SECTIONS

# SECURITY RULE: attempts are fetched with user=request.user (other users get a 404).


def _own(request, pk):
    return get_object_or_404(AptitudeAttempt, pk=pk, user=request.user)


@login_required
def overview(request):
    user = request.user
    open_attempt = AptitudeAttempt.objects.filter(user=user, status="in_progress").first()
    if open_attempt:
        open_attempt = services.finalize_if_expired(open_attempt)
        if open_attempt.is_submitted:
            messages.info(request, "Your previous test ran out of time and was graded automatically.")
            open_attempt = None
    stats = services.section_stats(user)
    sections = [{"key": k, "title": title, "topics": topics, "stats": stats[k]} for k, (title, topics) in SECTIONS.items()]
    accuracy = [a for a in services.topic_accuracy(user) if a[3] >= 3][:5]
    return render(request, "aptitude/overview.html", {
        "sections": sections, "open_attempt": open_attempt, "overall": services.overall_stats(user),
        "recent": AptitudeAttempt.objects.filter(user=user, status=SUBMITTED)[:8], "weakest": accuracy,
        "count_choices": services.COUNT_CHOICES, "minute_choices": services.MINUTE_CHOICES})


@login_required
@require_POST
def start(request):
    try:
        count = int(request.POST.get("count", 10))
        minutes = int(request.POST["minutes"]) if request.POST.get("minutes") else None
        attempt, created = services.start_attempt(request.user, request.POST.get("section", ""), request.POST.get("topic", ""),
                                                  count, minutes)
    except (ValueError, TypeError) as exc:
        messages.error(request, str(exc) or "Please check your choices.")
        return redirect("aptitude:overview")
    if not created:
        messages.info(request, "You already have a test in progress. Finish it first.")
    return redirect("aptitude:attempt", pk=attempt.pk)


@login_required
def attempt_detail(request, pk):
    attempt = services.finalize_if_expired(_own(request, pk))
    if attempt.is_submitted:
        return render(request, "aptitude/result.html", _result_context(attempt))
    items, last_passage = [], None
    for i, q in enumerate(attempt.questions):
        items.append({"i": i, "q": q, "chosen": attempt.answers.get(str(i)),
                      "show_passage": bool(q["passage"]) and q["passage"] != last_passage})
        last_passage = q["passage"] or last_passage
    return render(request, "aptitude/take.html", {
        "attempt": attempt, "items": items, "remaining": attempt.remaining_seconds(),
        "answered": len(attempt.answers)})


def _result_context(attempt):
    rows, topics = [], {}
    for i, q in enumerate(attempt.questions):
        chosen = attempt.answers.get(str(i))
        state = "unanswered" if chosen is None else "correct" if chosen == q["correct"] else "wrong"
        rows.append({"n": i + 1, "q": q, "chosen": chosen, "state": state})
        cell = topics.setdefault(q["topic"], [0, 0])
        cell[1] += 1
        cell[0] += state == "correct"
    return {"attempt": attempt, "rows": rows, "unanswered": sum(1 for r in rows if r["state"] == "unanswered"),
            "topic_rows": [{"topic": t, "correct": c, "total": n, "percent": round(100 * c / n)} for t, (c, n) in topics.items()],
            "minutes_used": round(attempt.seconds_used / 60, 1)}


@login_required
@require_POST
def answer(request, pk):
    attempt = _own(request, pk)
    try:
        index = int(request.POST.get("index", ""))
        raw = request.POST.get("option", "")
        option = int(raw) if raw != "" else None
    except ValueError:
        return JsonResponse({"saved": False, "error": "bad request"}, status=400)
    saved = services.autosave_answer(attempt, index, option)
    return JsonResponse({"saved": saved, "expired": attempt.is_expired() or attempt.is_submitted}, status=200 if saved else 409)


@login_required
@require_POST
def submit(request, pk):
    attempt = _own(request, pk)
    posted = {k[1:]: v for k, v in request.POST.items() if k.startswith("q") and k[1:].isdigit()}
    attempt, graded = services.finalize(attempt, posted)
    if graded:
        messages.success(request, f"Test submitted: {attempt.correct_count} of {attempt.total_count} correct.")
    return redirect("aptitude:attempt", pk=attempt.pk)


@login_required
def history(request):
    attempts = AptitudeAttempt.objects.filter(user=request.user, status=SUBMITTED)
    section = request.GET.get("section", "")
    if section in SECTIONS:
        attempts = attempts.filter(section=section)
    return render(request, "aptitude/history.html", {
        "attempts": attempts[:200], "section": section, "sections": [(k, v[0]) for k, v in SECTIONS.items()]})
