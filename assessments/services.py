import re

from django.db import IntegrityError, transaction
from django.db.models import Avg, Count
from django.utils import timezone

from . import question_bank
from .evaluation import evaluate_answer
from .models import (IN_PROGRESS, SUBMITTED, SpeakingAnswer, SpeakingAssessment, WrittenAnswer,
                     WrittenAssessment)
from .speaking_eval import evaluate_speaking

MAX_TEXT, MAX_CODE, MAX_SPOKEN, MAX_SECONDS = 5000, 10000, 4000, 1800
_STOP = {"and", "the", "of", "to", "in", "with", "for", "basic", "basics", "introduction", "using", "your"}


def _topic_patterns(topic):
    """Regexes (prefix matches) for the words of the topic and technology names."""
    words = re.findall(r"[A-Za-z]+", f"{topic.name} {topic.technology.name}")
    return [r"\b" + re.escape(w.lower()[:max(3, len(w) - 2)]) for w in words if len(w) > 2 and w.lower() not in _STOP]


def _generic_written(topic):
    name, tech = topic.name, topic.technology.name
    content = getattr(topic, "content", None)
    model = ""
    if content and (content.definition or content.explanation):
        model = f"{content.definition} {content.explanation}".strip()
    patterns = _topic_patterns(topic) or [r"\w+"]
    base = {"type": "explain", "points": [{"label": "Mentions the topic itself", "any": patterns, "must": True}],
            "checks": [], "model_answer": model or "Compare your answer with your lesson notes for this topic.",
            "model_code": "", "basic_only": True}
    q3_prompt = f"What are two common mistakes or doubts beginners have about {name}, and how can they be avoided?"
    if content and content.interview_questions.strip():
        first = next((ln[2:].strip() for ln in content.interview_questions.splitlines() if ln.startswith("- ")), "")
        if first:
            q3_prompt = f"Interview question: {first}"
    return [
        {**base, "prompt": f"Explain “{name}” in {tech} in your own words, as if you were teaching a friend.", "min_words": 40, "needs_example": True},
        {**base, "prompt": f"Describe a real-world situation where {name} is useful, and explain why.", "min_words": 30, "needs_example": False},
        {**base, "prompt": q3_prompt, "min_words": 30, "needs_example": False},
    ]


def written_questions_for(topic):
    bank = question_bank.written_questions(topic.technology.name, topic.name)
    return bank if bank else _generic_written(topic)


def spoken_question_for(topic):
    q = question_bank.spoken_question(topic.technology.name, topic.name)
    if q:
        return q
    return {"prompt": f"Explain {topic.name} in {topic.technology.name} in your own words. Give one real-time example.",
            "points": [], "terms": _topic_patterns(topic), "target_words": 50, "needs_example": True}


# ------------------------------------------------------------------ written
def start_written(user, topic):
    """Resume the unfinished attempt for this topic, or create a new one. Returns (assessment, created)."""
    existing = WrittenAssessment.objects.filter(user=user, topic=topic, status=IN_PROGRESS).first()
    if existing:
        return existing, False
    try:
        with transaction.atomic():
            attempt = WrittenAssessment.objects.filter(user=user, topic=topic).count() + 1
            a = WrittenAssessment.objects.create(user=user, topic=topic, topic_name=topic.name,
                                                 technology_name=topic.technology.name, attempt_number=attempt)
            WrittenAnswer.objects.bulk_create([
                WrittenAnswer(assessment=a, position=i, question_type=q["type"], prompt=q["prompt"],
                              code_snippet=q.get("code", ""), question_data=q)
                for i, q in enumerate(written_questions_for(topic), start=1)])
        return a, True
    except IntegrityError:   # a double click created it first
        return WrittenAssessment.objects.get(user=user, topic=topic, status=IN_PROGRESS), False


def apply_written_post(assessment, post):
    """Copy the form fields onto the answers. Raises ValueError if something is too long."""
    answers = list(assessment.answers.all())
    for a in answers:
        text, code = post.get(f"text_{a.pk}", ""), post.get(f"code_{a.pk}", "")
        if len(text) > MAX_TEXT or len(code) > MAX_CODE:
            raise ValueError(f"Answer {a.position} is too long (limit {MAX_TEXT} characters of text, {MAX_CODE} of code).")
        a.answer_text, a.answer_code = text.replace("\r\n", "\n"), code.replace("\r\n", "\n")
    WrittenAnswer.objects.bulk_update(answers, ["answer_text", "answer_code"])
    return answers


@transaction.atomic
def submit_written(assessment, post=None):
    """Save the last edits, score every answer, lock the assessment. Safe to call twice."""
    assessment = WrittenAssessment.objects.select_for_update().get(pk=assessment.pk)
    if assessment.is_submitted:
        return assessment, False
    answers = apply_written_post(assessment, post) if post is not None else list(assessment.answers.all())
    now = timezone.now()
    for a in answers:
        result = evaluate_answer(a.question_data, a.answer_text, a.answer_code)
        a.score, a.criteria, a.details, a.feedback, a.evaluated_at = (
            result["score"], result["criteria"], result["details"], result["feedback"], now)
    WrittenAnswer.objects.bulk_update(answers, ["score", "criteria", "details", "feedback", "evaluated_at"])
    assessment.score = round(sum(a.score for a in answers) / len(answers), 1) if answers else 0.0
    assessment.status, assessment.submitted_at = SUBMITTED, now
    assessment.save(update_fields=["score", "status", "submitted_at"])
    return assessment, True


# ----------------------------------------------------------------- speaking
def start_speaking(user, topic):
    existing = SpeakingAssessment.objects.filter(user=user, topic=topic, status=IN_PROGRESS).first()
    if existing:
        return existing, False
    q = spoken_question_for(topic)
    try:
        with transaction.atomic():
            attempt = SpeakingAssessment.objects.filter(user=user, topic=topic).count() + 1
            a = SpeakingAssessment.objects.create(user=user, topic=topic, topic_name=topic.name,
                                                  technology_name=topic.technology.name, attempt_number=attempt,
                                                  question_text=q["prompt"], question_data=q)
        return a, True
    except IntegrityError:
        return SpeakingAssessment.objects.get(user=user, topic=topic, status=IN_PROGRESS), False


@transaction.atomic
def submit_speaking(assessment, final_text, raw_transcript="", input_method="typed", seconds=0):
    assessment = SpeakingAssessment.objects.select_for_update().get(pk=assessment.pk)
    if assessment.is_submitted:
        return assessment, False
    final_text = (final_text or "").strip()
    if not final_text:
        raise ValueError("Please speak or type your answer before submitting.")
    if len(final_text) > MAX_SPOKEN or len(raw_transcript or "") > MAX_SPOKEN * 2:
        raise ValueError("The answer is too long.")
    method = input_method if input_method in ("speech", "typed") else "typed"
    seconds = max(0, min(int(seconds or 0), MAX_SECONDS))
    result = evaluate_speaking(assessment.question_data, final_text, method, seconds)
    SpeakingAnswer.objects.create(assessment=assessment, user=assessment.user, raw_transcript=raw_transcript or "",
                                  final_text=final_text, input_method=method, speaking_seconds=seconds,
                                  overall=result["overall"], criteria=result["criteria"], details=result["details"])
    assessment.status, assessment.submitted_at = SUBMITTED, timezone.now()
    assessment.save(update_fields=["status", "submitted_at"])
    return assessment, True


# ---------------------------------------------------------------- summaries
def stage_summary(qs, score_field):
    done = qs.filter(status=SUBMITTED)
    latest = done.order_by("-submitted_at").first()
    return {"attempts": done.count(), "latest": latest,
            "best": done.order_by(f"-{score_field}").first(),
            "open": qs.filter(status=IN_PROGRESS).first()}


def topic_summary(user, topic):
    return {"written": stage_summary(WrittenAssessment.objects.filter(user=user, topic=topic), "score"),
            "speaking": stage_summary(SpeakingAssessment.objects.filter(user=user, topic=topic), "answer__overall")}


def overview_stats(user):
    w = WrittenAssessment.objects.filter(user=user, status=SUBMITTED).aggregate(n=Count("id"), avg=Avg("score"))
    s = SpeakingAnswer.objects.filter(user=user).aggregate(n=Count("id"), avg=Avg("overall"))
    return {"written_count": w["n"], "written_avg": round(w["avg"]) if w["avg"] is not None else None,
            "speaking_count": s["n"], "speaking_avg": round(s["avg"]) if s["avg"] is not None else None}
