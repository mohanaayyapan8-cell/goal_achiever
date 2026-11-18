from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Exists, OuterRef
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from learning.models import LearningProgress, Topic

from . import ai, services
from .models import SUBMITTED, SpeakingAssessment, WrittenAnswer, WrittenAssessment

# SECURITY RULE: every assessment, answer and topic is fetched with user=request.user.


def _topic(request, pk):
    return get_object_or_404(Topic.objects.select_related("technology__domain", "progress"), pk=pk, user=request.user)


@login_required
def overview(request):
    user = request.user
    done_w = WrittenAssessment.objects.filter(user=user, topic=OuterRef("pk"), status=SUBMITTED)
    done_s = SpeakingAssessment.objects.filter(user=user, topic=OuterRef("pk"), status=SUBMITTED)
    ready = (Topic.objects.filter(user=user, progress__status=LearningProgress.COMPLETED)
             .annotate(has_w=Exists(done_w), has_s=Exists(done_s)).select_related("technology")
             .exclude(has_w=True, has_s=True))
    return render(request, "assessments/overview.html", {
        "stats": services.overview_stats(user), "ready": ready[:15],
        "written": WrittenAssessment.objects.filter(user=user, status=SUBMITTED)[:10],
        "speaking": SpeakingAssessment.objects.filter(user=user, status=SUBMITTED).select_related("answer")[:10]})


@login_required
def topic_hub(request, topic_pk):
    topic = _topic(request, topic_pk)
    return render(request, "assessments/hub.html", {
        "topic": topic, "summary": services.topic_summary(request.user, topic),
        "written_history": WrittenAssessment.objects.filter(user=request.user, topic=topic, status=SUBMITTED),
        "speaking_history": SpeakingAssessment.objects.filter(user=request.user, topic=topic, status=SUBMITTED)
        .select_related("answer")})


# ------------------------------------------------------------------ written
@login_required
@require_POST
def written_start(request, topic_pk):
    topic = _topic(request, topic_pk)
    assessment, created = services.start_written(request.user, topic)
    if not created:
        messages.info(request, "You have an unfinished written assessment for this topic. Continue it below.")
    return redirect("assessments:written_detail", pk=assessment.pk)


def _own_written(request, pk):
    return get_object_or_404(WrittenAssessment.objects.select_related("topic__technology"), pk=pk, user=request.user)


@login_required
def written_detail(request, pk):
    assessment = _own_written(request, pk)
    if assessment.is_submitted:
        return redirect("assessments:written_result", pk=pk)
    if request.method == "POST":
        action = request.POST.get("action", "save")
        try:
            if action == "submit":
                services.submit_written(assessment, request.POST)
                messages.success(request, "Submitted! Here are your scores and feedback.")
                return redirect("assessments:written_result", pk=pk)
            services.apply_written_post(assessment, request.POST)
            messages.success(request, "Draft saved. You can continue later.")
            return redirect("assessments:written_detail", pk=pk)
        except ValueError as exc:
            messages.error(request, str(exc))
    items = []
    for a in assessment.answers.all():
        data = a.question_data
        items.append({"a": a, "needs_explanation": data.get("min_words", 0) > 0,
                      "code_value": a.answer_code or (a.code_snippet if a.question_type == "debug" else "")})
    return render(request, "assessments/written_take.html", {"assessment": assessment, "items": items})


@login_required
def written_result(request, pk):
    assessment = _own_written(request, pk)
    if not assessment.is_submitted:
        return redirect("assessments:written_detail", pk=pk)
    return render(request, "assessments/written_result.html", {
        "assessment": assessment, "answers": assessment.answers.all(), "ai_enabled": ai.ai_enabled()})


@login_required
@require_POST
def written_ai(request, answer_pk):
    answer = get_object_or_404(WrittenAnswer.objects.select_related("assessment"), pk=answer_pk,
                               assessment__user=request.user)
    if not answer.assessment.is_submitted:
        return redirect("assessments:written_detail", pk=answer.assessment_id)
    if not ai.ai_enabled():
        messages.warning(request, "AI feedback is not set up. Add ANTHROPIC_API_KEY to your .env file to enable it.")
    else:
        try:
            answer.ai_feedback = ai.get_ai_feedback(answer.prompt, answer.answer_text, answer.answer_code)
            answer.save(update_fields=["ai_feedback"])
        except ai.AIError as exc:
            messages.error(request, str(exc))
    return redirect(f"{redirect('assessments:written_result', pk=answer.assessment_id).url}#q{answer.position}")


# ----------------------------------------------------------------- speaking
@login_required
@require_POST
def speaking_start(request, topic_pk):
    topic = _topic(request, topic_pk)
    assessment, created = services.start_speaking(request.user, topic)
    if not created:
        messages.info(request, "You have an unfinished speaking assessment for this topic. Continue it below.")
    return redirect("assessments:speaking_detail", pk=assessment.pk)


def _own_speaking(request, pk):
    return get_object_or_404(SpeakingAssessment.objects.select_related("topic__technology"), pk=pk, user=request.user)


@login_required
def speaking_detail(request, pk):
    assessment = _own_speaking(request, pk)
    if assessment.is_submitted:
        return redirect("assessments:speaking_result", pk=pk)
    initial = ""
    if request.method == "POST":
        initial = request.POST.get("final_text", "")
        try:
            services.submit_speaking(assessment, initial, request.POST.get("raw_transcript", ""),
                                     request.POST.get("input_method", "typed"), request.POST.get("speaking_seconds", 0))
            messages.success(request, "Submitted! Here are your scores and tips.")
            return redirect("assessments:speaking_result", pk=pk)
        except ValueError as exc:
            messages.error(request, str(exc))
    return render(request, "assessments/speaking_take.html", {
        "assessment": assessment, "initial": initial, "target": assessment.question_data.get("target_words", 50)})


@login_required
def speaking_result(request, pk):
    assessment = _own_speaking(request, pk)
    if not assessment.is_submitted:
        return redirect("assessments:speaking_detail", pk=pk)
    return render(request, "assessments/speaking_result.html", {"assessment": assessment, "answer": assessment.answer})
