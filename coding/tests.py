import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from learning.seed_data import DEFAULT_CURRICULUM

from . import services
from .harness import ListNode, run_tests
from .models import CodingProblem, CodingSubmission
from .problems import PROBLEMS

User = get_user_model()
CODING_DIR = Path(__file__).resolve().parent


def make_user(name="u1"):
    return User.objects.create_user(name, f"{name}@example.com", "StrongPass#2026")


def problem(slug="two-sum"):
    return CodingProblem.objects.get(slug=slug)


def tests_of(p, n=None):
    return p["tests"][:n] if n else p["tests"]


class ProblemBankTests(TestCase):
    def test_bank_loaded_by_migrate_and_reload_is_harmless(self):
        self.assertEqual(CodingProblem.objects.count(), len(PROBLEMS))
        self.assertEqual(services.load_problems(), 0)
        self.assertEqual(CodingProblem.objects.count(), len(PROBLEMS))

    def test_all_three_difficulty_levels_and_beginner_start(self):
        levels = {p["difficulty"] for p in PROBLEMS}
        self.assertEqual(levels, {"easy", "medium", "hard"})
        self.assertGreater(sum(1 for p in PROBLEMS if p["difficulty"] == "easy"), sum(1 for p in PROBLEMS if p["difficulty"] == "hard"))
        self.assertEqual(CodingProblem.objects.first().difficulty, "easy")      # first problem is beginner level

    def test_categories_match_the_dsa_topics_of_the_curriculum(self):
        dsa = [d for d in DEFAULT_CURRICULUM if d[0] == "Data Structures and Algorithms"][0][2]
        self.assertEqual({p["category"] for p in PROBLEMS}, {name for name, _ in dsa})

    def test_slugs_are_unique_and_every_problem_has_enough_tests(self):
        slugs = [p["slug"] for p in PROBLEMS]
        self.assertEqual(len(slugs), len(set(slugs)))
        for p in PROBLEMS:
            self.assertGreaterEqual(len(p["tests"]), 5, p["slug"])
            self.assertIn(f"def {p['function_name']}(", p["starter_code"], p["slug"])
            self.assertTrue(p["description"].strip() and p["constraints"].strip(), p["slug"])

    def test_reference_solutions_pass_and_starter_code_fails(self):
        """Trusted project code only; user code is never run by the server."""
        for p in PROBLEMS:
            sol = run_tests(p["solution"], p["function_name"], p["tests"])
            self.assertIsNone(sol["error"], p["slug"])
            self.assertTrue(len(sol["results"]) == len(p["tests"]) and all(r["passed"] for r in sol["results"]), p["slug"])
            stub = run_tests(p["starter_code"], p["function_name"], p["tests"])
            self.assertLess(sum(r["passed"] for r in stub["results"]), len(p["tests"]), p["slug"])


class HarnessTests(TestCase):
    T = [{"args": [2, 3], "expected": 5}, {"args": [0, 0], "expected": 0}]

    def run_code(self, code, tests=None, fn="add"):
        return run_tests(code, fn, tests or self.T)

    def test_pass_and_fail_reporting(self):
        r = self.run_code("def add(a, b):\n    return a + b")
        self.assertEqual([x["passed"] for x in r["results"]], [True, True])
        r = self.run_code("def add(a, b):\n    return a * b")
        self.assertEqual([x["passed"] for x in r["results"]], [False, True])
        self.assertEqual(r["results"][0]["got"], "6")

    def test_syntax_error_missing_function_and_exception(self):
        self.assertIn("SyntaxError", self.run_code("def add(a, b)\n    return 1")["error"])
        self.assertIn("must define a function named add", self.run_code("x = 1")["error"])
        r = self.run_code("def add(a, b):\n    return 1 / 0")
        self.assertIn("ZeroDivisionError", r["results"][0]["error"])
        self.assertEqual(len(r["results"]), 2)      # one failing test does not stop the others

    def test_runtime_error_while_defining_is_reported(self):
        self.assertIn("NameError", self.run_code("undefined_name\ndef add(a, b): return 1")["error"])

    def test_infinite_recursion_is_reported_not_fatal(self):
        r = self.run_code("def add(a, b):\n    return add(a, b)")
        self.assertIn("RecursionError", r["results"][0]["error"])

    def test_printed_output_is_captured_and_limited(self):
        r = self.run_code("def add(a, b):\n    print('hi')\n    return a + b")
        self.assertIn("hi", r["stdout"])
        big = self.run_code("print('x' * 10000)\ndef add(a, b): return a + b")
        self.assertLessEqual(len(big["stdout"]), 2001)

    def test_exit_call_in_student_code_is_caught(self):
        r = self.run_code("def add(a, b):\n    raise SystemExit(1)")
        self.assertFalse(r["results"][0]["passed"])

    def test_tuples_become_lists_and_non_json_values_fail_cleanly(self):
        r = run_tests("def f():\n    return (1, 2)", "f", [{"args": [], "expected": [1, 2]}])
        self.assertTrue(r["results"][0]["passed"])
        r = run_tests("def f():\n    return {1, 2}", "f", [{"args": [], "expected": [1, 2]}])
        self.assertFalse(r["results"][0]["passed"])
        self.assertIn("TypeError", r["results"][0]["error"])

    def test_booleans_are_not_confused_with_integers(self):
        t = [{"args": [], "expected": True}]
        self.assertTrue(run_tests("def f():\n    return True", "f", t)["results"][0]["passed"])
        self.assertFalse(run_tests("def f():\n    return 1", "f", t)["results"][0]["passed"])

    def test_floats_use_a_small_tolerance(self):
        t = [{"args": [], "expected": 0.3}]
        self.assertTrue(run_tests("def f():\n    return 0.1 + 0.2", "f", t)["results"][0]["passed"])
        self.assertFalse(run_tests("def f():\n    return 0.31", "f", t)["results"][0]["passed"])

    def test_linked_list_arguments_and_results(self):
        code = "def f(head):\n    return head.next"
        t = [{"args": [{"$list": [1, 2, 3]}], "expected": [2, 3], "ll_result": True}]
        self.assertTrue(run_tests(code, "f", t)["results"][0]["passed"])
        empty = [{"args": [{"$list": []}], "expected": [], "ll_result": True}]
        self.assertTrue(run_tests("def f(head):\n    return None", "f", empty)["results"][0]["passed"])
        not_ll = [{"args": [[]], "expected": []}]
        self.assertFalse(run_tests("def f(x):\n    return None", "f", not_ll)["results"][0]["passed"])   # None is not []

    def test_tests_do_not_leak_state_between_runs_and_inputs_are_copied(self):
        code = "def f(nums):\n    nums.append(9)\n    return len(nums)"
        t = [{"args": [[1]], "expected": 2}]
        self.assertTrue(run_tests(code, "f", t)["results"][0]["passed"])
        self.assertEqual(t[0]["args"], [[1]])       # harness worked on a copy

    def test_name_main_block_does_not_run(self):
        r = self.run_code("def add(a, b):\n    return a + b\nif __name__ == '__main__':\n    print('should not run')")
        self.assertEqual(r["stdout"], "")


class ServerNeverRunsCodeTests(TestCase):
    """The safety promise: submitted code is stored as text and never executed by the server."""

    def setUp(self):
        self.user = make_user()
        self.client.force_login(self.user)
        self.marker = os.path.join(tempfile.gettempdir(), "ga_coding_marker.txt")
        if os.path.exists(self.marker):
            os.remove(self.marker)
        self.evil = f"open({self.marker!r}, 'w').write('x')\ndef two_sum(nums, target):\n    return [0, 1]\n"

    def test_every_submission_path_leaves_the_marker_file_uncreated(self):
        url = reverse("coding:submit", args=["two-sum"])
        self.client.post(url, {"action": "save", "code": self.evil})
        self.client.post(url, {"action": "self_solved", "confirm_self": "on", "code": self.evil})
        self.client.post(url, {"action": "browser_result", "code": self.evil,
                               "result": json.dumps({"passed": 5, "total": 5, "details": [], "error": "", "stdout": ""})})
        self.assertEqual(CodingSubmission.objects.count(), 3)
        self.assertFalse(os.path.exists(self.marker))
        self.client.get(reverse("coding:detail", args=["two-sum"]))
        self.client.get(reverse("coding:submission", args=[CodingSubmission.objects.first().pk]))
        self.assertFalse(os.path.exists(self.marker))

    def test_server_code_has_no_code_execution_machinery(self):
        for name in ("views.py", "services.py", "models.py", "urls.py"):
            source = (CODING_DIR / name).read_text()
            for forbidden in ("exec(", "eval(", "subprocess", "os.system", "os.popen", "__import__", "importlib", "compile("):
                self.assertNotIn(forbidden, source, f"{name} must not contain {forbidden}")
        self.assertNotIn("import harness", (CODING_DIR / "views.py").read_text())
        self.assertNotIn("from .harness", (CODING_DIR / "views.py").read_text())
        self.assertNotIn("run_tests(", (CODING_DIR / "views.py").read_text())

    def test_submitted_code_is_shown_as_escaped_text(self):
        evil = "</code></pre><script>alert(1)</script>"
        CodingSubmission.objects.create(user=self.user, problem=problem(), code=evil, mode="manual", status="saved")
        sub = CodingSubmission.objects.get()
        page = self.client.get(reverse("coding:submission", args=[sub.pk]))
        self.assertNotContains(page, "<script>alert(1)</script>")
        self.assertContains(page, "&lt;script&gt;")


class SubmissionRecordingTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.p = problem("two-sum")
        self.n = len(self.p.tests)

    def payload(self, passed, total=None, **kw):
        return {"passed": passed, "total": self.n if total is None else total, "details": [], "error": "", "stdout": "", **kw}

    def test_all_tests_passing_counts_as_solved(self):
        s = services.record_browser_result(self.user, self.p, "code", self.payload(self.n))
        self.assertEqual((s.status, s.mode, s.is_solved), ("passed", "browser", True))

    def test_partial_pass_or_error_is_a_failed_attempt(self):
        self.assertEqual(services.record_browser_result(self.user, self.p, "c", self.payload(self.n - 1)).status, "failed")
        self.assertEqual(services.record_browser_result(self.user, self.p, "c", self.payload(0, error="SyntaxError: bad")).status, "failed")
        self.assertEqual(services.record_browser_result(self.user, self.p, "c", self.payload(self.n, error="Time limit exceeded")).status, "failed")

    def test_a_report_that_skips_tests_cannot_mark_the_problem_solved(self):
        s = services.record_browser_result(self.user, self.p, "c", self.payload(1, total=1))
        self.assertEqual(s.status, "failed")

    def test_invalid_reports_are_rejected(self):
        for bad in ({"passed": 9, "total": 5}, {"passed": -1, "total": 5}, {"passed": "x", "total": 5}, {"passed": 1, "total": 500}, {}):
            with self.assertRaises(ValueError):
                services.record_browser_result(self.user, self.p, "c", bad)
        self.assertEqual(CodingSubmission.objects.count(), 0)

    def test_oversized_fields_are_truncated(self):
        big = self.payload(self.n, stdout="x" * 9000, details=[{"i": i, "p": True, "e": "e" * 999} for i in range(200)])
        s = services.record_browser_result(self.user, self.p, "y" * 50000, big)
        self.assertEqual((len(s.code), len(s.output), len(s.details)), (services.MAX_CODE, 2000, 50))
        self.assertTrue(all(len(d["e"]) <= 200 for d in s.details))

    def test_manual_save_and_self_solved(self):
        self.assertEqual(services.record_manual(self.user, self.p, "c", solved=False).status, "saved")
        self.assertEqual(services.record_manual(self.user, self.p, "c", solved=True).status, "self_solved")


class ProgressTests(TestCase):
    def setUp(self):
        self.user = make_user()

    def test_progress_counts_solved_once_per_problem_and_by_topic(self):
        a, b = problem("find-maximum"), problem("two-sum")
        n = len(a.tests)
        services.record_browser_result(self.user, a, "c", {"passed": n, "total": n})
        services.record_browser_result(self.user, a, "c", {"passed": n, "total": n})       # solved twice, counted once
        services.record_manual(self.user, b, "c", solved=True)
        prog = services.progress(self.user)
        self.assertEqual((prog["solved"], prog["total"]), (2, len(PROBLEMS)))
        arrays = [c for c in prog["categories"] if c["name"] == "Arrays"][0]
        self.assertEqual((arrays["solved"], arrays["total"], arrays["percent"]), (2, 3, 67))
        self.assertEqual(prog["difficulties"]["easy"]["solved"], 1)
        self.assertEqual(prog["difficulties"]["medium"]["solved"], 1)

    def test_failed_and_saved_attempts_do_not_count_as_solved(self):
        p = problem("find-maximum")
        services.record_browser_result(self.user, p, "c", {"passed": 1, "total": len(p.tests)})
        services.record_manual(self.user, p, "c", solved=False)
        self.assertEqual(services.progress(self.user)["solved"], 0)
        self.assertEqual(services.attempted_problem_ids(self.user), {p.pk})

    def test_progress_is_per_user(self):
        p = problem("find-maximum")
        services.record_manual(self.user, p, "c", solved=True)
        self.assertEqual(services.progress(make_user("other"))["solved"], 0)


class CodingViewTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_login(self.user)

    def post(self, slug, **data):
        return self.client.post(reverse("coding:submit", args=[slug]), data)

    def test_list_shows_progress_and_filters(self):
        r = self.client.get(reverse("coding:list"))
        for text in ("Topic-wise completion", "Two Sum", "Hard", "Linked Lists"):
            self.assertContains(r, text)
        r = self.client.get(reverse("coding:list") + "?difficulty=hard")
        self.assertContains(r, "All Permutations")
        self.assertNotContains(r, "Two Sum")
        r = self.client.get(reverse("coding:list") + "?category=Stacks")
        self.assertContains(r, "Valid Parentheses")
        self.assertNotContains(r, "Binary Search")

    def test_status_filter_and_markers(self):
        services.record_manual(self.user, problem("find-maximum"), "c", solved=True)
        solved = self.client.get(reverse("coding:list") + "?status=solved")
        self.assertContains(solved, "Find the Maximum")
        self.assertNotContains(solved, "Two Sum")
        todo = self.client.get(reverse("coding:list") + "?status=todo")
        self.assertNotContains(todo, "Find the Maximum")

    def test_detail_shows_statement_examples_hidden_count_and_editor(self):
        r = self.client.get(reverse("coding:detail", args=["two-sum"]))
        for text in ("Two Sum", "Constraints", "Example 1", "Example 2", "3 more hidden tests", 'id="editor"', "never runs your code",
                     "Run tests in browser", "Manual mode", 'id="problem-data"'):
            self.assertContains(r, text)
        self.assertContains(r, "def two_sum(nums, target):")                 # starter code
        cfg = r.context["config"]
        self.assertEqual((cfg["fn"], len(cfg["tests"])), ("two_sum", 5))
        self.assertTrue(cfg["pyodideBase"].endswith("js/vendor/pyodide/"))

    def test_solution_is_hidden_until_an_attempt_is_made(self):
        page = self.client.get(reverse("coding:detail", args=["two-sum"]))
        self.assertNotContains(page, "seen[target - n]")
        self.assertContains(page, "unlock the reference solution")
        self.post("two-sum", action="save", code="def two_sum(nums, target):\n    pass")
        self.assertContains(self.client.get(reverse("coding:detail", args=["two-sum"])), "seen[target - n]")

    def test_editor_shows_last_submission_and_load_parameter(self):
        self.post("two-sum", action="save", code="# first version")
        self.post("two-sum", action="save", code="# second version")
        page = self.client.get(reverse("coding:detail", args=["two-sum"]))
        self.assertContains(page, "# second version")
        first = CodingSubmission.objects.get(code="# first version")
        self.assertContains(self.client.get(reverse("coding:detail", args=["two-sum"]) + f"?load={first.pk}"), "# first version")

    def test_load_parameter_ignores_other_users_and_other_problems(self):
        other = make_user("other")
        theirs = CodingSubmission.objects.create(user=other, problem=problem("two-sum"), code="# PRIVATE", mode="manual", status="saved")
        page = self.client.get(reverse("coding:detail", args=["two-sum"]) + f"?load={theirs.pk}")
        self.assertNotContains(page, "# PRIVATE")
        mine = CodingSubmission.objects.create(user=self.user, problem=problem("find-maximum"), code="# WRONG PROBLEM", mode="manual", status="saved")
        self.assertNotContains(self.client.get(reverse("coding:detail", args=["two-sum"]) + f"?load={mine.pk}"), "# WRONG PROBLEM")

    def test_browser_result_endpoint_returns_json_and_records(self):
        n = len(problem("find-maximum").tests)
        r = self.post("find-maximum", action="browser_result", code="def find_max(nums): return 1",
                      result=json.dumps({"passed": n, "total": n, "details": [], "error": "", "stdout": ""}))
        self.assertEqual(r.status_code, 200)
        self.assertEqual((r.json()["ok"], r.json()["solved"]), (True, True))
        self.assertEqual(CodingSubmission.objects.get().status, "passed")
        self.assertContains(self.client.get(reverse("coding:detail", args=["find-maximum"])), "Solved")

    def test_browser_result_with_bad_data_gives_400(self):
        for result in ("not json", "[1,2]", json.dumps({"passed": 9, "total": 2})):
            r = self.post("find-maximum", action="browser_result", code="x = 1", result=result)
            self.assertEqual(r.status_code, 400, result)
        self.assertEqual(self.post("find-maximum", action="browser_result", code="  ", result="{}").status_code, 400)
        self.assertEqual(CodingSubmission.objects.count(), 0)

    def test_self_solved_requires_confirmation(self):
        self.post("find-maximum", action="self_solved", code="def find_max(nums): return 1")
        self.assertEqual(CodingSubmission.objects.count(), 0)
        self.post("find-maximum", action="self_solved", code="def find_max(nums): return 1", confirm_self="on")
        self.assertEqual(CodingSubmission.objects.get().status, "self_solved")

    def test_empty_code_and_unknown_action_are_refused(self):
        self.post("find-maximum", action="save", code="   ")
        self.post("find-maximum", action="explode", code="x = 1")
        self.assertEqual(CodingSubmission.objects.count(), 0)

    def test_submit_requires_post(self):
        self.assertEqual(self.client.get(reverse("coding:submit", args=["two-sum"])).status_code, 405)

    def test_unknown_problem_is_404(self):
        self.assertEqual(self.client.get(reverse("coding:detail", args=["nope"])).status_code, 404)

    def test_harness_endpoint_serves_runner_source(self):
        r = self.client.get(reverse("coding:harness"))
        self.assertEqual(r.status_code, 200)
        self.assertIn("def run_tests", r.content.decode())

    def test_sidebar_and_dashboard_show_dsa_progress(self):
        services.record_manual(self.user, problem("find-maximum"), "c", solved=True)
        page = self.client.get(reverse("dashboard:index"))
        self.assertEqual(page.context["dsa"]["solved"], 1)
        self.assertContains(page, "DSA problems solved")
        self.assertContains(page, reverse("coding:list"))


class CodingAccessTests(TestCase):
    def setUp(self):
        self.alice, self.bob = make_user("alice"), make_user("bob")
        self.sub = CodingSubmission.objects.create(user=self.alice, problem=problem(), code="# alice secret", mode="manual", status="saved")

    def test_anonymous_redirected(self):
        for name, args in (("coding:list", []), ("coding:detail", ["two-sum"]), ("coding:submission", [self.sub.pk]),
                           ("coding:harness", []), ("coding:local_script", ["two-sum"])):
            self.assertEqual(self.client.get(reverse(name, args=args)).status_code, 302, name)
        self.assertEqual(self.client.post(reverse("coding:submit", args=["two-sum"]), {"action": "save", "code": "x"}).status_code, 302)

    def test_other_user_cannot_view_a_submission(self):
        self.client.force_login(self.bob)
        self.assertEqual(self.client.get(reverse("coding:submission", args=[self.sub.pk])).status_code, 404)

    def test_other_users_submissions_are_not_listed_or_counted(self):
        services.record_manual(self.alice, problem("find-maximum"), "c", solved=True)
        self.client.force_login(self.bob)
        page = self.client.get(reverse("coding:detail", args=["two-sum"]))
        self.assertNotContains(page, "# alice secret")
        self.assertEqual(services.progress(self.bob)["solved"], 0)


class LocalScriptTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_login(self.user)

    def run_script(self, slug, solution):
        p = problem(slug)
        r = self.client.get(reverse("coding:local_script", args=[slug]))
        self.assertEqual(r.status_code, 200)
        self.assertIn("attachment", r["Content-Disposition"])
        script = r.content.decode()
        self.assertIn(f"def {p.function_name}(", script)
        self.assertIn("run_tests", script)
        script = script.replace(p.starter_code, solution, 1)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "local_test.py"
            path.write_text(script)
            done = subprocess.run([sys.executable, str(path)], capture_output=True, text=True, timeout=60)
        return done.stdout

    def test_downloaded_script_runs_on_its_own_and_reports_results(self):
        ref = {p["slug"]: p["solution"] for p in PROBLEMS}
        out = self.run_script("two-sum", ref["two-sum"])
        self.assertIn("5 of 5 tests passed", out)
        out = self.run_script("merge-two-linked-lists", ref["merge-two-linked-lists"])      # uses ListNode
        self.assertIn("5 of 5 tests passed", out)

    def test_script_reports_failures_for_the_starter_code(self):
        out = self.run_script("find-maximum", problem("find-maximum").starter_code)
        self.assertIn("FAIL", out)
        self.assertIn("0 of 5 tests passed", out)
