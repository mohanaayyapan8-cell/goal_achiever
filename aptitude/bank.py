"""Builds the full aptitude question list (computed + hand-written) with stable keys."""
import random
import zlib

from .bank_text import LOGICAL, VERBAL
from .generators import generated_questions
from .topics import SECTIONS


def _finish(key, section, q):
    if "options" in q:   # generated questions and fixed-order questions already have final options
        options, correct = list(q["options"]), q["correct"]
    else:
        rng = random.Random(zlib.crc32(key.encode()))
        options = [q["correct_text"]] + list(q["wrongs"])
        rng.shuffle(options)
        correct = options.index(q["correct_text"])
    return {"key": key, "section": section, "topic": q["topic"], "passage": q.get("passage", ""), "stem": q["stem"],
            "options": options, "correct_index": correct, "explanation": q["explanation"]}


def all_questions():
    rows = [_finish(key, section, q) for key, section, q in generated_questions()]
    for section, items in (("logical", LOGICAL), ("verbal", VERBAL)):
        counters = {}
        for q in items:
            counters[q["topic"]] = counters.get(q["topic"], 0) + 1
            slug = q["topic"].lower().replace(" ", "-")
            rows.append(_finish(f"{section}-{slug}-{counters[q['topic']]:02d}", section, q))
    return rows


def validate(rows):
    """Return a list of problems (empty if the bank is sound)."""
    problems, keys = [], set()
    topics = {(s, t) for s, (_, ts) in SECTIONS.items() for t in ts}
    for r in rows:
        if r["key"] in keys:
            problems.append(f"duplicate key {r['key']}")
        keys.add(r["key"])
        if (r["section"], r["topic"]) not in topics:
            problems.append(f"{r['key']}: unknown topic {r['topic']}")
        if len(r["options"]) != 4 or len(set(r["options"])) != 4:
            problems.append(f"{r['key']}: needs 4 different options")
        if not 0 <= r["correct_index"] < 4:
            problems.append(f"{r['key']}: bad answer index")
        if not r["stem"].strip() or not r["explanation"].strip():
            problems.append(f"{r['key']}: empty stem/explanation")
    seen = {}
    for r in rows:
        k = (r["section"], r["topic"], r["stem"])
        if k in seen:
            problems.append(f"{r['key']}: same question as {seen[k]}")
        seen[k] = r["key"]
    for s, t in topics:
        n = sum(1 for r in rows if r["section"] == s and r["topic"] == t)
        if n < 5:
            problems.append(f"topic {t} has only {n} questions")
    return problems
