"""Test runner for coding problems.

SAFETY: this file is run INSIDE THE USER'S BROWSER (Pyodide, in a Web Worker) or on the
user's own computer (the downloadable local test script). The Django server never
imports this module to run user code. Only trusted reference solutions are run by the
project's own automated tests.
"""
import contextlib
import copy
import io
import json


class ListNode:
    """Singly linked list node, provided to linked-list problems."""

    def __init__(self, val=0, next=None):
        self.val = val
        self.next = next


def _build(value):
    """Test data {"$list": [1, 2, 3]} becomes a linked list; lists are converted recursively."""
    if isinstance(value, dict) and "$list" in value:
        head = None
        for item in reversed(value["$list"]):
            head = ListNode(item, head)
        return head
    if isinstance(value, list):
        return [_build(v) for v in value]
    return value


def _plain(value):
    if isinstance(value, ListNode):
        out, steps = [], 0
        while value is not None and steps < 10000:
            out.append(value.val)
            value = value.next
            steps += 1
        return out
    return value


def _equal(a, b):
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b
    if isinstance(a, float) or isinstance(b, float):
        try:
            return abs(a - b) < 1e-6
        except TypeError:
            return False
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_equal(x, y) for x, y in zip(a, b))
    return a == b


def _short(text, limit):
    text = str(text)
    return text if len(text) <= limit else text[:limit] + "…"


def run_tests(code, fn_name, tests, max_chars=2000):
    """Run `fn_name` from `code` against `tests`.
    tests: [{"args": [...], "expected": ..., "ll_result": bool}]
    Returns {"error": str or None, "stdout": str, "results": [{"index", "passed", "got", "error"}]}"""
    out = io.StringIO()
    namespace = {"__name__": "__solution__", "ListNode": ListNode}
    try:
        with contextlib.redirect_stdout(out):
            exec(compile(code, "<your code>", "exec"), namespace)
    except BaseException as exc:  # noqa: BLE001 - report any problem in the student's code
        line = f" (line {exc.lineno})" if isinstance(exc, SyntaxError) and exc.lineno else ""
        return {"error": f"{type(exc).__name__}: {exc}{line}", "stdout": _short(out.getvalue(), max_chars), "results": []}
    fn = namespace.get(fn_name)
    if not callable(fn):
        return {"error": f"Your code must define a function named {fn_name}.", "stdout": _short(out.getvalue(), max_chars), "results": []}
    results = []
    for index, test in enumerate(tests):
        args = _build(copy.deepcopy(test["args"]))
        try:
            with contextlib.redirect_stdout(out):
                got = _plain(fn(*args))
            if got is None and test.get("ll_result"):
                got = []
            got = json.loads(json.dumps(got))      # tuples become lists; non-JSON values raise
            results.append({"index": index, "passed": _equal(got, test["expected"]), "got": _short(repr(got), 200), "error": None})
        except BaseException as exc:  # noqa: BLE001
            results.append({"index": index, "passed": False, "got": None, "error": _short(f"{type(exc).__name__}: {exc}", 200)})
    return {"error": None, "stdout": _short(out.getvalue(), max_chars), "results": results}
