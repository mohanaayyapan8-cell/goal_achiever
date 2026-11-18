import json
from pathlib import Path

from django.db.models import Count, Q

from .models import (EASY, FAILED, HARD, MEDIUM, PASSED, SAVED, SELF_SOLVED, SOLVED_STATUSES, CodingProblem,
                     CodingSubmission)
from .problems import PROBLEMS

HARNESS_PATH = Path(__file__).with_name("harness.py")
MAX_CODE = 20000


def harness_source():
    return HARNESS_PATH.read_text(encoding="utf-8")


def load_problems():
    """Insert or update the shared problem bank. Safe to run any number of times."""
    created = 0
    for order, p in enumerate(PROBLEMS, start=1):
        _, was_created = CodingProblem.objects.update_or_create(slug=p["slug"], defaults={
            "title": p["title"], "category": p["category"], "difficulty": p["difficulty"], "description": p["description"],
            "constraints": p["constraints"], "function_name": p["function_name"], "starter_code": p["starter_code"],
            "solution": p["solution"], "hint": p["hint"], "tests": p["tests"], "order": order})
        created += was_created
    return created


def solved_problem_ids(user):
    return set(CodingSubmission.objects.filter(user=user, status__in=SOLVED_STATUSES).values_list("problem_id", flat=True))


def attempted_problem_ids(user):
    return set(CodingSubmission.objects.filter(user=user).values_list("problem_id", flat=True))


def progress(user):
    """Solved count and topic-wise completion percentage."""
    solved = solved_problem_ids(user)
    problems = list(CodingProblem.objects.filter(is_active=True).values("id", "category", "difficulty"))
    cats, diffs = {}, {EASY: [0, 0], MEDIUM: [0, 0], HARD: [0, 0]}
    for p in problems:
        c = cats.setdefault(p["category"], [0, 0])
        c[1] += 1
        diffs[p["difficulty"]][1] += 1
        if p["id"] in solved:
            c[0] += 1
            diffs[p["difficulty"]][0] += 1
    total = len(problems)
    return {
        "solved": sum(1 for p in problems if p["id"] in solved), "total": total,
        "percent": round(100 * len([1 for p in problems if p["id"] in solved]) / total) if total else 0,
        "categories": [{"name": n, "solved": s, "total": t, "percent": round(100 * s / t) if t else 0} for n, (s, t) in cats.items()],
        "difficulties": {k: {"solved": s, "total": t} for k, (s, t) in diffs.items()},
    }


def _short(text, limit):
    return str(text or "")[:limit]


def record_browser_result(user, problem, code, payload):
    """Store the outcome that the student's browser sandbox reported. The server did not run the code."""
    code = _short(code, MAX_CODE)
    total_tests = len(problem.tests)
    try:
        passed, total = int(payload.get("passed", 0)), int(payload.get("total", 0))
    except (TypeError, ValueError):
        raise ValueError("Invalid result.")
    error = _short(payload.get("error"), 300)
    details = [{"i": int(d.get("i", 0)), "p": bool(d.get("p")), "e": _short(d.get("e"), 200)}
               for d in (payload.get("details") or [])[:50] if isinstance(d, dict)]
    if not 0 <= passed <= total or not 1 <= total <= 50:
        raise ValueError("Invalid result.")
    all_passed = (not error) and total == total_tests and passed == total
    return CodingSubmission.objects.create(
        user=user, problem=problem, code=code, mode="browser", status=PASSED if all_passed else FAILED,
        passed_count=passed, total_count=total, details=details, output=_short(payload.get("stdout"), 2000), error=error)


def record_manual(user, problem, code, solved):
    return CodingSubmission.objects.create(user=user, problem=problem, code=_short(code, MAX_CODE), mode="manual",
                                           status=SELF_SOLVED if solved else SAVED, total_count=len(problem.tests))


def local_test_script(problem):
    """A file the student can run on their own computer (VS Code): solution on top, runner below."""
    tests = json.dumps(problem.tests)
    return (f'# {problem.title}: local test script\n'
            f'# 1) Replace the starter code below with your solution (keep the function name {problem.function_name}).\n'
            f'# 2) Run this file with Python. It runs on YOUR computer; nothing is sent anywhere.\n\n'
            f'{problem.starter_code}\n'
            f'# ===== test runner: do not edit below this line =====\n'
            f'{harness_source()}\n'
            f'TESTS = json.loads({tests!r})\n\n'
            f'if __name__ == "__main__":\n'
            f'    source = open(__file__, encoding="utf-8").read().split("# ===== test runner")[0]\n'
            f'    report = run_tests(source, {problem.function_name!r}, TESTS)\n'
            f'    if report["error"]:\n'
            f'        print("Problem:", report["error"])\n'
            f'    for r in report["results"]:\n'
            f'        print("Test", r["index"] + 1, "PASS" if r["passed"] else "FAIL", "" if r["passed"] else (r["error"] or "got " + str(r["got"])))\n'
            f'    print(sum(r["passed"] for r in report["results"]), "of", len(TESTS), "tests passed")\n')
