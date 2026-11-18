import re

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.http import FileResponse, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.utils import get_profile

from . import services
from .content import completeness, resume_content, resume_to_text
from .forms import (AchievementForm, CertificationForm, EducationForm, ExperienceForm, ProjectForm, ResumeForm,
                    ReviewForm, UploadForm)
from .models import (MAX_RESUMES, MAX_UPLOADS, Achievement, Certification, Education, Experience, Project, Resume,
                     ResumeReview, ResumeUpload)
from .pdf import build_pdf, unsupported_characters
from .uploads import ExtractionError, extract_text

# SECURITY RULES: every resume, section, upload and review is fetched with the owner (404 for anyone else).
# Uploaded files are private: they are only ever sent through upload_download, to their owner.

# kind -> (model, form, label, related name, maximum items)
SECTIONS = {
    "education": (Education, EducationForm, "education", "educations", 5),
    "experience": (Experience, ExperienceForm, "experience / internship", "experiences", 8),
    "project": (Project, ProjectForm, "project", "projects", 8),
    "certification": (Certification, CertificationForm, "certification", "certifications", 10),
    "achievement": (Achievement, AchievementForm, "achievement", "achievements", 10),
}


def _resume(request, pk):
    return get_object_or_404(Resume, pk=pk, user=request.user)


def _form_page(request, form, title):
    return render(request, "learning/form.html", {"form": form, "title": title, "cancel_url": ""})


def _confirm(request, kind, name, detail, cancel_href):
    return render(request, "resume_builder/confirm_delete.html", {"kind": kind, "name": name, "detail": detail, "cancel_href": cancel_href})


# ---------------------------------------------------------------- overview
@login_required
def resume_list(request):
    resumes = list(Resume.objects.filter(user=request.user))
    for r in resumes:
        r.percent, _ = completeness(r)
    return render(request, "resume_builder/list.html", {
        "resumes": resumes, "uploads": ResumeUpload.objects.filter(user=request.user),
        "reviews": ResumeReview.objects.filter(user=request.user)[:5],
        "max_resumes": MAX_RESUMES, "max_uploads": MAX_UPLOADS})


@login_required
def ats_guide(request):
    return render(request, "resume_builder/ats_guide.html")


# ---------------------------------------------------------- builder: resume
@login_required
def resume_create(request):
    if Resume.objects.filter(user=request.user).count() >= MAX_RESUMES:
        messages.error(request, f"You can keep up to {MAX_RESUMES} resumes. Delete one first.")
        return redirect("resume_builder:list")
    profile = get_profile(request.user)
    initial = {"title": "My resume", "full_name": request.user.get_full_name() or request.user.get_username(),
               "email": request.user.email, "headline": profile.target_role}
    form = ResumeForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        resume = form.save(commit=False)
        resume.user = request.user
        resume.save()
        messages.success(request, "Resume created. Now add your education, projects and more.")
        return redirect("resume_builder:editor", pk=resume.pk)
    return _form_page(request, form, "New resume")


@login_required
def resume_editor(request, pk):
    resume = _resume(request, pk)
    percent, missing = completeness(resume)
    sections = []
    for kind, (model, _, label, related, maximum) in SECTIONS.items():
        items = list(getattr(resume, related).all())
        sections.append({"kind": kind, "title": label.capitalize(), "items": items, "can_add": len(items) < maximum, "maximum": maximum})
    return render(request, "resume_builder/editor.html", {"resume": resume, "percent": percent, "missing": missing, "sections": sections})


@login_required
def resume_update(request, pk):
    resume = _resume(request, pk)
    form = ResumeForm(request.POST or None, instance=resume)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Resume details saved.")
        return redirect("resume_builder:editor", pk=pk)
    return _form_page(request, form, "Edit resume details")


@login_required
def resume_delete(request, pk):
    resume = _resume(request, pk)
    if request.method == "POST":
        resume.delete()
        messages.success(request, "Resume deleted.")
        return redirect("resume_builder:list")
    return _confirm(request, "resume", resume.title, "Its sections are deleted too. Saved reviews are kept.", f"/resume/{pk}/")


# ------------------------------------------------------- builder: sections
def _section_kind(kind):
    if kind not in SECTIONS:
        from django.http import Http404
        raise Http404("Unknown section")
    return SECTIONS[kind]


@login_required
def section_create(request, pk, kind):
    resume = _resume(request, pk)
    model, form_class, label, related, maximum = _section_kind(kind)
    existing = getattr(resume, related)
    if existing.count() >= maximum:
        messages.error(request, f"You can add up to {maximum} {label} entries.")
        return redirect("resume_builder:editor", pk=pk)
    form = form_class(request.POST or None)
    if request.method == "POST" and form.is_valid():
        item = form.save(commit=False)
        item.resume = resume
        last = existing.order_by("-order").first()
        item.order = (last.order if last else 0) + 1
        item.save()
        messages.success(request, f"Added to {label}.")
        return redirect("resume_builder:editor", pk=pk)
    return _form_page(request, form, f"Add {label}")


def _own_section(request, kind, pk):
    model, form_class, label, related, _ = _section_kind(kind)
    return get_object_or_404(model.objects.select_related("resume"), pk=pk, resume__user=request.user), form_class, label


@login_required
def section_update(request, kind, pk):
    item, form_class, label = _own_section(request, kind, pk)
    form = form_class(request.POST or None, instance=item)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Saved.")
        return redirect("resume_builder:editor", pk=item.resume_id)
    return _form_page(request, form, f"Edit {label}")


@login_required
def section_delete(request, kind, pk):
    item, _, label = _own_section(request, kind, pk)
    resume_id = item.resume_id
    if request.method == "POST":
        item.delete()
        messages.success(request, "Removed.")
        return redirect("resume_builder:editor", pk=resume_id)
    return _confirm(request, label, str(item.__dict__.get("name") or item.__dict__.get("role") or item.__dict__.get("institution") or item.__dict__.get("text") or label),
                    "", f"/resume/{resume_id}/")


# ---------------------------------------------------- preview, PDF, review
@login_required
def resume_preview(request, pk):
    resume = _resume(request, pk)
    return render(request, "resume_builder/preview.html", {"resume": resume, "content": resume_content(resume), "bad_chars": unsupported_characters(resume)})


@login_required
def resume_pdf(request, pk):
    resume = _resume(request, pk)
    filename = (re.sub(r"[^A-Za-z0-9]+", "_", resume.full_name).strip("_") or "resume") + "_Resume.pdf"
    response = HttpResponse(build_pdf(resume), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


@login_required
def resume_review(request, pk):
    resume = _resume(request, pk)
    form = ReviewForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        review = services.run_review(request.user, resume_to_text(resume), form.cleaned_data["job_description"], resume.title, "builder",
                                     meta={"source": "builder"}, resume=resume, target_role=resume.headline or None)
        return redirect("resume_builder:review", pk=review.pk)
    return render(request, "resume_builder/review_form.html", {"form": form, "source": resume.title, "action": "builder"})


# ----------------------------------------------------------------- uploads
@login_required
def upload_create(request):
    if ResumeUpload.objects.filter(user=request.user).count() >= MAX_UPLOADS:
        messages.error(request, f"You can keep up to {MAX_UPLOADS} uploaded resumes. Delete one first.")
        return redirect("resume_builder:list")
    form = UploadForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        original = form.cleaned_data["file"].name.replace("\\", "/").rsplit("/", 1)[-1][:120]
        upload = ResumeUpload(user=request.user, original_name=original or f"resume.{form.kind}", kind=form.kind, size=len(form.data))
        upload.file.save(f"resume.{form.kind}", ContentFile(form.data), save=False)    # real name is random (see upload_path)
        upload.save()
        messages.success(request, "Uploaded. Only you can see this file. Now run a review.")
        return redirect("resume_builder:list")
    return render(request, "resume_builder/upload_form.html", {"form": form})


CONTENT_TYPES = {"pdf": "application/pdf", "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                 "txt": "text/plain; charset=utf-8"}


@login_required
def upload_download(request, pk):
    upload = get_object_or_404(ResumeUpload, pk=pk, user=request.user)
    response = FileResponse(upload.file.open("rb"), as_attachment=True, filename=upload.safe_download_name, content_type=CONTENT_TYPES[upload.kind])
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


@login_required
def upload_delete(request, pk):
    upload = get_object_or_404(ResumeUpload, pk=pk, user=request.user)
    if request.method == "POST":
        upload.delete()                      # also removes the file from disk
        messages.success(request, "Uploaded resume deleted from the server.")
        return redirect("resume_builder:list")
    return _confirm(request, "uploaded resume", upload.original_name, "The file is permanently deleted from the server.", "/resume/")


@login_required
def upload_review(request, pk):
    upload = get_object_or_404(ResumeUpload, pk=pk, user=request.user)
    form = ReviewForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            with upload.file.open("rb") as fh:
                extracted = extract_text(upload.kind, fh.read())
        except (ExtractionError, FileNotFoundError, OSError) as exc:
            messages.error(request, str(exc) if isinstance(exc, ExtractionError) else "The stored file could not be opened.")
            return redirect("resume_builder:list")
        review = services.run_review(request.user, extracted["text"], form.cleaned_data["job_description"], upload.original_name, "upload",
                                     meta={"pages": extracted["pages"], "has_tables": extracted["has_tables"], "source": "upload"}, upload=upload)
        return redirect("resume_builder:review", pk=review.pk)
    return render(request, "resume_builder/review_form.html", {"form": form, "source": upload.original_name, "action": "upload"})


# ----------------------------------------------------------------- reviews
@login_required
def review_list(request):
    return render(request, "resume_builder/review_list.html", {"reviews": ResumeReview.objects.filter(user=request.user)})


@login_required
def review_detail(request, pk):
    review = get_object_or_404(ResumeReview, pk=pk, user=request.user)
    return render(request, "resume_builder/review_detail.html", {"review": review, "r": review.result, "wins": services.quick_wins(review.result)})


@login_required
@require_POST
def review_delete(request, pk):
    get_object_or_404(ResumeReview, pk=pk, user=request.user).delete()
    messages.success(request, "Review deleted.")
    return redirect("resume_builder:reviews")
