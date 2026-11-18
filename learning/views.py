from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from . import services
from .forms import ContentForm, DomainForm, NoteForm, TechnologyForm, TopicForm
from .models import Domain, LearningProgress, Technology, Topic, UserNote
from .references import links_for

# SECURITY RULE: every object is fetched with user=request.user, so another
# user's id simply gives a 404 page.


def _form_page(request, form, title, cancel_url):
    return render(request, "learning/form.html", {"form": form, "title": title, "cancel_url": cancel_url})


def _safe_next(request, fallback):
    nxt = request.POST.get("next", "")
    if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}):
        return nxt
    return fallback


# ------------------------------------------------------------------ Domains
@login_required
def domain_list(request):
    return render(request, "learning/domain_list.html", {"domains": services.domains_with_progress(request.user)})


@login_required
def domain_create(request):
    form = DomainForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        domain = form.save(commit=False)
        domain.user = request.user
        domain.order = services.next_order(Domain.objects.filter(user=request.user))
        domain.save()
        messages.success(request, f"Domain “{domain.name}” added.")
        return redirect("learning:domain_detail", pk=domain.pk)
    return _form_page(request, form, "Add a domain", "learning:domain_list")


@login_required
def domain_detail(request, pk):
    domain = get_object_or_404(Domain, pk=pk, user=request.user)
    return render(request, "learning/domain_detail.html", {
        "domain": domain, "technologies": services.technologies_with_progress(domain)})


@login_required
def domain_update(request, pk):
    domain = get_object_or_404(Domain, pk=pk, user=request.user)
    form = DomainForm(request.POST or None, instance=domain, user=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Domain updated.")
        return redirect("learning:domain_detail", pk=domain.pk)
    return _form_page(request, form, f"Edit domain: {domain.name}", "learning:domain_list")


@login_required
def domain_delete(request, pk):
    domain = get_object_or_404(Domain, pk=pk, user=request.user)
    if request.method == "POST":
        name = domain.name
        domain.delete()
        messages.success(request, f"Domain “{name}” and everything inside it was deleted.")
        return redirect("learning:domain_list")
    return render(request, "learning/confirm_delete.html", {
        "kind": "domain", "name": domain.name,
        "detail": f"This also deletes its {domain.technologies.count()} technologies, "
                  f"{Topic.objects.filter(technology__domain=domain).count()} topics and their progress.",
        "cancel_url": "learning:domain_detail", "cancel_arg": domain.pk})


# ------------------------------------------------------------- Technologies
@login_required
def technology_create(request, domain_pk):
    domain = get_object_or_404(Domain, pk=domain_pk, user=request.user)
    form = TechnologyForm(request.POST or None, domain=domain)
    if request.method == "POST" and form.is_valid():
        tech = form.save(commit=False)
        tech.user, tech.domain = request.user, domain
        tech.order = services.next_order(domain.technologies.all())
        tech.save()
        messages.success(request, f"Technology “{tech.name}” added.")
        return redirect("learning:technology_detail", pk=tech.pk)
    return _form_page(request, form, f"Add a technology to {domain.name}", "learning:domain_list")


@login_required
def technology_detail(request, pk):
    tech = get_object_or_404(Technology.objects.select_related("domain"), pk=pk, user=request.user)
    topics = list(tech.topics.select_related("progress"))
    done = sum(1 for t in topics if t.status == LearningProgress.COMPLETED)
    return render(request, "learning/technology_detail.html", {
        "tech": tech, "topics": topics, "done": done, "total": len(topics),
        "percent": services.percent(done, len(topics))})


@login_required
def technology_update(request, pk):
    tech = get_object_or_404(Technology, pk=pk, user=request.user)
    form = TechnologyForm(request.POST or None, instance=tech, domain=tech.domain)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Technology updated.")
        return redirect("learning:technology_detail", pk=tech.pk)
    return _form_page(request, form, f"Edit technology: {tech.name}", "learning:domain_list")


@login_required
def technology_delete(request, pk):
    tech = get_object_or_404(Technology, pk=pk, user=request.user)
    if request.method == "POST":
        domain_pk, name = tech.domain_id, tech.name
        tech.delete()
        messages.success(request, f"Technology “{name}” was deleted.")
        return redirect("learning:domain_detail", pk=domain_pk)
    return render(request, "learning/confirm_delete.html", {
        "kind": "technology", "name": tech.name,
        "detail": f"This also deletes its {tech.topics.count()} topics and their progress.",
        "cancel_url": "learning:technology_detail", "cancel_arg": tech.pk})


# ------------------------------------------------------------------- Topics
@login_required
def topic_create(request, technology_pk):
    tech = get_object_or_404(Technology, pk=technology_pk, user=request.user)
    form = TopicForm(request.POST or None, technology=tech)
    if request.method == "POST" and form.is_valid():
        topic = form.save(commit=False)
        topic.user, topic.technology = request.user, tech
        topic.order = services.next_order(tech.topics.all())
        topic.save()
        messages.success(request, f"Topic “{topic.name}” added.")
        return redirect("learning:technology_detail", pk=tech.pk)
    return _form_page(request, form, f"Add a topic to {tech.name}", "learning:domain_list")


@login_required
def topic_update(request, pk):
    topic = get_object_or_404(Topic.objects.select_related("technology"), pk=pk, user=request.user)
    form = TopicForm(request.POST or None, instance=topic, technology=topic.technology)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Topic updated.")
        return redirect("learning:technology_detail", pk=topic.technology_id)
    return _form_page(request, form, f"Edit topic: {topic.name}", "learning:domain_list")


@login_required
def topic_delete(request, pk):
    topic = get_object_or_404(Topic.objects.select_related("technology"), pk=pk, user=request.user)
    if request.method == "POST":
        tech_pk, name = topic.technology_id, topic.name
        topic.delete()
        messages.success(request, f"Topic “{name}” was deleted.")
        return redirect("learning:technology_detail", pk=tech_pk)
    return render(request, "learning/confirm_delete.html", {
        "kind": "topic", "name": topic.name, "detail": "Its progress is deleted too.",
        "cancel_url": "learning:technology_detail", "cancel_arg": topic.technology_id})


@login_required
@require_POST
def topic_set_status(request, pk):
    topic = get_object_or_404(Topic, pk=pk, user=request.user)
    status = request.POST.get("status", "")
    if status not in dict(LearningProgress.STATUS_CHOICES):
        return HttpResponseBadRequest("Invalid status")
    services.set_topic_status(request.user, topic, status)
    if status == LearningProgress.COMPLETED:
        messages.success(request, f"Great job! “{topic.name}” is marked completed.")
    fallback = redirect("learning:technology_detail", pk=topic.technology_id).url
    return redirect(_safe_next(request, fallback))


# ----------------------------------------------------------------- Defaults
@login_required
@require_POST
def load_defaults(request):
    created = services.seed_default_curriculum(request.user)
    if any(created.values()):
        messages.success(request, f"Added {created['domains']} domains, {created['technologies']} technologies, "
                                  f"{created['topics']} topics and {created['content']} lessons.")
    else:
        messages.info(request, "You already have the whole default curriculum.")
    return redirect("learning:domain_list")


# ------------------------------------------------------------ Topic lesson page
def _own_topic(request, pk):
    return get_object_or_404(Topic.objects.select_related("technology__domain", "progress"), pk=pk, user=request.user)


@login_required
def topic_detail(request, pk):
    topic = _own_topic(request, pk)
    content = getattr(topic, "content", None)
    siblings = list(topic.technology.topics.values_list("pk", "name"))
    idx = [i for i, (pk_, _) in enumerate(siblings) if pk_ == topic.pk][0]
    return render(request, "learning/topic_detail.html", {
        "topic": topic, "content": content, "sections": content.sections() if content else [],
        "notes": topic.notes.all(), "note_form": NoteForm(),
        "references": links_for(topic.technology.name),
        "prev": siblings[idx - 1] if idx > 0 else None,
        "next": siblings[idx + 1] if idx < len(siblings) - 1 else None,
        "number": idx + 1, "count": len(siblings)})


@login_required
def content_edit(request, pk):
    topic = _own_topic(request, pk)
    from .models import LearningContent
    content = getattr(topic, "content", None) or LearningContent(user=request.user, topic=topic)
    form = ContentForm(request.POST or None, instance=content)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Lesson saved.")
        return redirect("learning:topic_detail", pk=topic.pk)
    return render(request, "learning/content_form.html", {"form": form, "topic": topic})


@login_required
@require_POST
def note_create(request, pk):
    topic = _own_topic(request, pk)
    form = NoteForm(request.POST)
    if form.is_valid():
        note = form.save(commit=False)
        note.user, note.topic = request.user, topic
        note.save()
        messages.success(request, "Note saved.")
    else:
        messages.error(request, "A note cannot be empty.")
    return redirect(f"{redirect('learning:topic_detail', pk=topic.pk).url}#notes")


@login_required
def note_update(request, pk):
    note = get_object_or_404(UserNote.objects.select_related("topic"), pk=pk, user=request.user)
    form = NoteForm(request.POST or None, instance=note)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Note updated.")
        return redirect(f"{redirect('learning:topic_detail', pk=note.topic_id).url}#notes")
    return _form_page(request, form, f"Edit note ({note.topic.name})", "learning:domain_list")


@login_required
def note_delete(request, pk):
    note = get_object_or_404(UserNote.objects.select_related("topic"), pk=pk, user=request.user)
    if request.method == "POST":
        topic_pk = note.topic_id
        note.delete()
        messages.success(request, "Note deleted.")
        return redirect(f"{redirect('learning:topic_detail', pk=topic_pk).url}#notes")
    return render(request, "learning/confirm_delete.html", {
        "kind": "note", "name": note.body[:60], "detail": "",
        "cancel_url": "learning:topic_detail", "cancel_arg": note.topic_id})
