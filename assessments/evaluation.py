"""Transparent, rule-based scoring for WRITTEN answers.

Nothing here runs the student's code: Python code is only parsed with ast.parse
(a syntax check) and searched with patterns. This is an indicative checklist
score, not a judgement from an expert; the model answer is always shown so
the student can self-review."""
import ast
import io
import re
import tokenize

CRITERIA = ("technical_correctness", "concept_understanding", "code_logic", "explanation_quality")
CRITERION_LABELS = {
    "technical_correctness": "Technical correctness", "concept_understanding": "Concept understanding",
    "code_logic": "Code logic", "explanation_quality": "Explanation quality",
}
_PROGRAM = {"technical_correctness": .30, "code_logic": .35, "concept_understanding": .15, "explanation_quality": .20}
WEIGHTS = {
    "explain": {"concept_understanding": .45, "technical_correctness": .35, "explanation_quality": .20},
    "explain_logic": {"concept_understanding": .45, "technical_correctness": .35, "explanation_quality": .20},
    "predict_output": {"technical_correctness": 1.0},
    "program": _PROGRAM, "practical": _PROGRAM,
    "debug": {"technical_correctness": .35, "code_logic": .35, "concept_understanding": .15, "explanation_quality": .15},
}
EXAMPLE_RE = re.compile(r"\b(example|for instance|such as|e\.g\.|suppose|consider|imagine)\b|\w+\s*=\s*\S+|\w+\(.*\)", re.I)


def count_words(text):
    return len(re.findall(r"[A-Za-z0-9_']+", text or ""))


def count_sentences(text):
    parts = re.split(r"[.!?\n]+", text or "")
    return sum(1 for p in parts if count_words(p) >= 3)


def check_syntax(code):
    """(ok, message). Parses only; the code is never executed."""
    try:
        ast.parse(code)
        return True, ""
    except SyntaxError as exc:
        return False, f"line {exc.lineno}: {exc.msg}"
    except (ValueError, RecursionError, MemoryError):
        return False, "the code could not be read"


def strip_comments(code):
    lines = code.split("\n")
    try:
        for tok in tokenize.generate_tokens(io.StringIO(code).readline):
            if tok.type == tokenize.COMMENT:
                row, col = tok.start
                lines[row - 1] = lines[row - 1][:col]
    except (tokenize.TokenError, IndentationError, SyntaxError):
        pass
    return "\n".join(lines)


def _norm_lines(text):
    return [ln.rstrip() for ln in (text or "").replace("\r\n", "\n").strip().split("\n")]


def _matches(patterns, text, flags=re.I | re.S):
    return any(re.search(p, text, flags) for p in patterns)


def _pct(fraction):
    return round(max(0.0, min(1.0, fraction)) * 100, 1)


def _score_points(q, text, crit, details, feedback):
    points = q.get("points") or []
    if not points:
        return
    hits = [(p, _matches(p["any"], text)) for p in points]
    for p, ok in hits:
        details.append({"group": "Key points", "label": p["label"], "passed": ok, "must": p["must"]})
    crit["concept_understanding"] = _pct(sum(ok for _, ok in hits) / len(hits))
    must = [ok for p, ok in hits if p["must"]]
    crit["technical_correctness"] = _pct(sum(must) / len(must)) if must else crit["concept_understanding"]
    if q.get("basic_only"):
        crit["technical_correctness"] = None
    missing = [p["label"] for p, ok in hits if not ok]
    feedback.append("You covered every key point." if not missing
                    else f"Missing key points: {'; '.join(missing)}.")


def _score_quality(q, text, crit, details, feedback):
    min_words = q.get("min_words", 0)
    if not min_words:
        return
    words, sentences = count_words(text), count_sentences(text)
    word_part = min(1.0, words / min_words)
    sent_part = 1.0 if sentences >= 2 else 0.4 if sentences == 1 else 0.0
    has_example = bool(EXAMPLE_RE.search(text))
    details.append({"group": "Explanation quality", "label": f"At least {min_words} words (you wrote {words})", "passed": words >= min_words})
    details.append({"group": "Explanation quality", "label": "Uses complete sentences (two or more)", "passed": sentences >= 2})
    if q.get("needs_example"):
        details.append({"group": "Explanation quality", "label": "Includes an example", "passed": has_example})
        value = .5 * word_part + .25 * sent_part + (.25 if has_example else 0)
    else:
        value = .65 * word_part + .35 * sent_part
    crit["explanation_quality"] = _pct(value)
    if words < min_words:
        feedback.append(f"Write a fuller explanation: aim for at least {min_words} words (you wrote {words}).")
    if q.get("needs_example") and not has_example:
        feedback.append("Add a short example to make the idea concrete.")


def _score_code(q, code, crit, details, feedback):
    ok, message = check_syntax(code) if code.strip() else (False, "no code was written")
    details.append({"group": "Code checks", "label": "The code is valid Python (syntax check only, it is not run)", "passed": ok})
    cleaned = strip_comments(code) if code.strip() else ""
    results = []
    for c in q.get("checks", []):
        found = bool(re.search(c["pattern"], cleaned, re.M))
        # An empty answer fails every check, including "must not contain" ones.
        passed = bool(code.strip()) and ((not found) if c.get("must_not") else found)
        results.append(passed)
        details.append({"group": "Code checks", "label": c["label"], "passed": passed})
    fraction = sum(results) / len(results) if results else (1.0 if ok else 0.0)
    unchanged = q["type"] == "debug" and q.get("code") and cleaned.split() == strip_comments(q["code"]).split()
    if unchanged:
        details.append({"group": "Code checks", "label": "You changed the buggy code", "passed": False})
        crit["technical_correctness"], crit["code_logic"] = 0.0, 0.0
        feedback.append("The code is the same as the buggy version: find the bug and change it.")
        return
    crit["technical_correctness"] = _pct(.4 * (1 if ok else 0) + .6 * fraction)
    crit["code_logic"] = _pct(fraction)
    if not ok:
        feedback.append(f"Syntax problem: {message}.")
    failed = [d["label"] for d in details if d["group"] == "Code checks" and not d["passed"] and "valid Python" not in d["label"]]
    if failed:
        feedback.append(f"Code checks not met: {'; '.join(failed)}.")
    elif ok and results:
        feedback.append("Your code passed every check.")


def _score_output(q, text, crit, details, feedback):
    expected, got = _norm_lines(q["expected_output"]), _norm_lines(text) if (text or "").strip() else []
    matched = sum(1 for a, b in zip(expected, got) if a == b)
    crit["technical_correctness"] = _pct(matched / max(len(expected), len(got), 1))
    exact = expected == got
    details.append({"group": "Output", "label": "Your output matches the expected output exactly", "passed": exact})
    feedback.append("Correct! Your predicted output is exact." if exact else
                    "Not quite. Trace the program one line at a time and compare with the expected output shown below.")


def evaluate_answer(q, answer_text, answer_code):
    """Return {"score", "criteria", "details", "feedback"} for one question."""
    text, code = (answer_text or "").strip(), (answer_code or "").strip()
    crit = {name: None for name in CRITERIA}
    details, feedback = [], []
    qtype = q["type"]
    if qtype == "predict_output":
        _score_output(q, text, crit, details, feedback)
    else:
        _score_points(q, text, crit, details, feedback)
        if qtype in ("program", "practical", "debug"):
            _score_code(q, code, crit, details, feedback)
        _score_quality(q, text, crit, details, feedback)
    weights = WEIGHTS[qtype]
    used = {k: w for k, w in weights.items() if crit[k] is not None}
    total = sum(used.values())
    score = round(sum(crit[k] * w for k, w in used.items()) / total, 1) if total else 0.0
    if not text and not code:
        feedback = ["No answer was written for this question."]
    return {"score": score, "criteria": crit, "details": details, "feedback": feedback}
