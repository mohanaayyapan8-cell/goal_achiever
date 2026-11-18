import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.templatetags.static import static
from django.urls import reverse
from django.views.decorators.http import require_POST

from . import services
from .models import DIFFICULTY_CHOICES, CodingProblem, CodingSubmission

# SAFETY RULE: no view in this module executes, evaluates or imports submitted code.
# Code is only stored as text. Test execution happens in the student's own browser (Pyodide)
# or on their own computer.


@login_required
def problem_list(request):
    user = request.user
    problems = CodingProblem.objects.filter(is_active=True)
    category, difficulty, status = (request.GET.get(k, "") for k in ("category", "difficulty", "status"))
    if category:
        problems = problems.filter(category=category)
    if difficulty in dict(DIFFICULTY_CHOICES):
        problems = problems.filter(difficulty=difficulty)
    solved, attempted = services.solved_problem_ids(user), services.attempted_problem_ids(user)
    rows = []
    for p in problems:
        state = "solved" if p.pk in solved else "attempted" if p.pk in attempted else "todo"
        if status in ("solved", "attempted", "todo") and state != status:
            continue
        rows.append({"p": p, "state": state})
    prog = services.progress(user)
    return render(request, "coding/list.html", {
        "rows": rows, "progress": prog, "categories": [c["name"] for c in prog["categories"]],
        "difficulty_choices": DIFFICULTY_CHOICES, "f_category": category, "f_difficulty": difficulty, "f_status": status})


@login_required
def problem_detail(request, slug):
    problem = get_object_or_404(CodingProblem, slug=slug, is_active=True)
    submissions = list(problem.submissions.filter(user=request.user)[:10])
    code = problem.starter_code
    load = request.GET.get("load", "")
    if load.isdigit():
        chosen = CodingSubmission.objects.filter(pk=int(load), user=request.user, problem=problem).first()
        if chosen:
            code = chosen.code
    elif submissions:
        code = submissions[0].code
    solved = problem.submissions.filter(user=request.user, status__in=("passed", "self_solved")).exists()
    config = {
        "fn": problem.function_name, "timeoutMs": 10000,
        "tests": [{"args": t["args"], "expected": t["expected"], **({"ll_result": True} if t.get("ll_result") else {})} for t in problem.tests],
        "examples": problem.examples, "starter": problem.starter_code,
        "workerUrl": static("js/coding_worker.js"), "pyodideBase": static("js/vendor/pyodide/"),
        "harnessUrl": reverse("coding:harness"), "submitUrl": reverse("coding:submit", args=[problem.slug]),
    }
    return render(request, "coding/detail.html", {
        "problem": problem, "code": code, "submissions": submissions, "solved": solved,
        "can_reveal": bool(submissions) or solved, "config": config, "hidden_count": max(len(problem.tests) - 2, 0)})


@login_required
@require_POST
def problem_submit(request, slug):
    problem = get_object_or_404(CodingProblem, slug=slug, is_active=True)
    action, code = request.POST.get("action", ""), request.POST.get("code", "")
    if not code.strip():
        if action == "browser_result":
            return JsonResponse({"ok": False, "message": "There is no code to save."}, status=400)
        messages.error(request, "Write some code first.")
        return redirect("coding:detail", slug=slug)
    if action == "browser_result":
        try:
            payload = json.loads(request.POST.get("result", "{}"))
            if not isinstance(payload, dict):
                raise ValueError
            sub = services.record_browser_result(request.user, problem, code, payload)
        except ValueError:
            return JsonResponse({"ok": False, "message": "The test result could not be read."}, status=400)
        msg = "All tests passed! Problem solved." if sub.is_solved else f"{sub.passed_count} of {sub.total_count} tests passed. Saved to your history."
        return JsonResponse({"ok": True, "solved": sub.is_solved, "message": msg})
    if action == "self_solved":
        if not request.POST.get("confirm_self"):
            messages.error(request, "Tick the box to confirm you checked the code yourself.")
            return redirect("coding:detail", slug=slug)
        services.record_manual(request.user, problem, code, solved=True)
        messages.success(request, "Marked as solved (self-checked).")
    elif action == "save":
        services.record_manual(request.user, problem, code, solved=False)
        messages.success(request, "Code saved to your history.")
    else:
        messages.error(request, "Unknown action.")
    return redirect("coding:detail", slug=slug)


@login_required
def submission_detail(request, pk):
    sub = get_object_or_404(CodingSubmission.objects.select_related("problem"), pk=pk, user=request.user)
    return render(request, "coding/submission.html", {"sub": sub})


@login_required
def local_script(request, slug):
    problem = get_object_or_404(CodingProblem, slug=slug, is_active=True)
    response = HttpResponse(services.local_test_script(problem), content_type="text/x-python; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{problem.slug.replace("-", "_")}_local_test.py"'
    return response


@login_required
def harness(request):
    """The test-runner source, fetched by the browser worker. It contains no user data."""
    return HttpResponse(services.harness_source(), content_type="text/plain; charset=utf-8")
