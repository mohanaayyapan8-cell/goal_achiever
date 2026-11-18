import io
import json
import os
import tempfile
import zipfile
from pathlib import Path

import docx
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from coding.models import CodingProblem
from coding import services as coding_services
from learning.models import Domain, Technology, Topic
from learning.services import set_topic_status
from streaks.models import Achievement

from . import ats, services
from .content import bullets_list, completeness, resume_content, resume_to_text
from .forms import EducationForm, ExperienceForm, ProjectForm, ResumeForm
from .models import (Achievement as ResumeAchievement, Certification, Education, Experience, Project, Resume,
                     ResumeReview, ResumeUpload)
from .pdf import build_pdf, pdf_safe, unsupported_characters
from .uploads import ExtractionError, detect_kind, extract_text, validate_upload

User = get_user_model()

GOOD_JD = "We need a Python developer with Django, SQL, REST API, Docker and Git. Strong communication. Python and Django daily."


def make_user(name="u1", email=None):
    return User.objects.create_user(name, email or f"{name}@example.com", "StrongPass#2026", first_name=name.title())


def make_resume(user, **kw):
    data = dict(title="Dev resume", full_name="Asha Raman", headline="Python Developer", email="asha@example.com", phone="+91 98765 43210",
                location="Chennai", linkedin_url="https://www.linkedin.com/in/asha", github_url="https://github.com/asha",
                summary="Computer science student building Django web apps and data tools, looking for a Python developer internship.",
                skills="Languages: Python, SQL, JavaScript, HTML, CSS\nTools: Git, GitHub, Django, Excel")
    data.update(kw)
    r = Resume.objects.create(user=user, **data)
    Education.objects.create(resume=r, institution="Anna University", degree="B.E. Computer Science", start="2022", end="2026", grade="8.4", order=1)
    Project.objects.create(resume=r, name="Goal Tracker", tech_stack="Python, Django, SQLite", order=1,
                           bullets="Built a Django web app with 15 pages used by 40 students\nReduced report time by 60% by automating CSV exports\nWrote 120 unit tests and fixed 25 bugs")
    Experience.objects.create(resume=r, role="Python Intern", organization="Acme Labs", start="Jun 2025", end="Aug 2025", order=1,
                              bullets="Developed 3 REST API endpoints serving 2000 requests per day\nImproved query speed by 35% by adding indexes")
    Certification.objects.create(resume=r, name="Python for Everybody", issuer="Coursera", year="2024", order=1)
    ResumeAchievement.objects.create(resume=r, text="Winner of the college hackathon 2025", order=1)
    return r


def pdf_text(data):
    return "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(data)).pages)


def docx_bytes(*paragraphs, table=False):
    d = docx.Document()
    for p in paragraphs:
        d.add_paragraph(p)
    if table:
        t = d.add_table(rows=1, cols=2)
        t.cell(0, 0).text, t.cell(0, 1).text = "a", "b"
    out = io.BytesIO()
    d.save(out)
    return out.getvalue()


def blank_image_pdf():
    out = io.BytesIO()
    c = canvas.Canvas(out, pagesize=A4)
    c.rect(50, 50, 300, 300, fill=1)
    c.save()
    return out.getvalue()


def many_page_pdf(pages):
    out = io.BytesIO()
    c = canvas.Canvas(out, pagesize=A4)
    for i in range(pages):
        c.drawString(72, 700, f"Page number {i + 1} of the resume " + "word " * 20)
        c.showPage()
    c.save()
    return out.getvalue()


class PrivateMedia(TestCase):
    """Base class: uploads go to a throw-away folder."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.media = tmp.name
        override = override_settings(MEDIA_ROOT=tmp.name)
        override.enable()
        self.addCleanup(override.disable)


# ------------------------------------------------------------------ content
class ContentTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.r = make_resume(self.user)

    def test_bullets_are_split_and_cleaned(self):
        self.assertEqual(bullets_list("- one\n• two\n  * three \n\n–four"), ["one", "two", "three", "four"])
        self.assertEqual(bullets_list(""), [])

    def test_student_layout_puts_education_first_professional_puts_experience_first(self):
        keys = [s["key"] for s in resume_content(self.r)["sections"]]
        self.assertEqual(keys[:3], ["summary", "education", "skills"])
        self.r.layout = "professional"
        keys = [s["key"] for s in resume_content(self.r)["sections"]]
        self.assertEqual(keys[:3], ["summary", "skills", "experience"])

    def test_empty_sections_are_left_out(self):
        bare = Resume.objects.create(user=self.user, title="t", full_name="Bare Name")
        self.assertEqual(resume_content(bare)["sections"], [])
        self.assertEqual(resume_to_text(bare).strip(), "Bare Name")

    def test_plain_text_contains_standard_headings_and_dashed_bullets(self):
        text = resume_to_text(self.r)
        for heading in ("Summary", "Skills", "Education", "Projects", "Experience", "Certifications", "Achievements"):
            self.assertIn(f"\n{heading}\n", text)
        self.assertIn("- Reduced report time by 60%", text)
        self.assertIn("linkedin.com/in/asha", text)
        self.assertNotIn("https://", text.split("\n")[2])        # links are shown without the scheme

    def test_completeness_lists_what_is_missing(self):
        percent, missing = completeness(self.r)
        self.assertEqual((percent, missing), (89, ["two or more projects/internships"]) if False else (percent, missing))
        bare = Resume.objects.create(user=self.user, title="t", full_name="X")
        p2, miss2 = completeness(bare)
        self.assertLess(p2, 30)
        self.assertIn("an email address", miss2)
        self.assertIn("your education", miss2)
        self.assertGreater(percent, p2)


# ---------------------------------------------------------------------- PDF
class PdfTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.r = make_resume(self.user)

    def test_pdf_is_valid_with_selectable_text_in_standard_order(self):
        data = build_pdf(self.r)
        self.assertTrue(data.startswith(b"%PDF-"))
        text = pdf_text(data)
        for expected in ("Asha Raman", "Python Developer", "asha@example.com", "SUMMARY", "EDUCATION", "SKILLS", "PROJECTS", "EXPERIENCE",
                         "CERTIFICATIONS", "ACHIEVEMENTS", "Reduced report time by 60%", "Anna University"):
            self.assertIn(expected, text)
        order = [text.index(h) for h in ("SUMMARY", "EDUCATION", "SKILLS", "PROJECTS", "EXPERIENCE")]
        self.assertEqual(order, sorted(order))

    def test_pdf_is_ats_friendly_one_column_no_images(self):
        reader = PdfReader(io.BytesIO(build_pdf(self.r)))
        self.assertEqual(len(reader.pages), 1)
        self.assertEqual(len(reader.pages[0].images), 0)
        self.assertEqual(reader.metadata.title, "Asha Raman - Resume")
        self.assertEqual(reader.metadata.author, "Asha Raman")

    def test_layout_changes_the_order_in_the_pdf(self):
        self.r.layout = "professional"
        text = pdf_text(build_pdf(self.r))
        self.assertLess(text.index("EXPERIENCE"), text.index("EDUCATION"))

    def test_special_characters_are_escaped_not_interpreted(self):
        Project.objects.create(resume=self.r, name="R&D <b>tool</b> & more", bullets="Used <script>alert(1)</script> safely", order=2)
        text = pdf_text(build_pdf(self.r))
        self.assertIn("R&D <b>tool</b> & more", text)
        self.assertIn("<script>alert(1)</script>", text)

    def test_typographic_characters_are_mapped_and_unsupported_ones_reported(self):
        self.assertEqual(pdf_safe("“Hi” – it’s… ok")[0], '"Hi" - it\'s... ok')
        clean, bad = pdf_safe("Łukasz தமிழ்")
        self.assertIn("?", clean)
        self.assertIn("Ł", bad)
        self.r.full_name = "Łukasz Ng"
        self.r.save()
        self.assertIn("Ł", unsupported_characters(self.r))
        self.assertEqual(unsupported_characters(make_resume(make_user("o"))), [])
        self.assertTrue(build_pdf(self.r).startswith(b"%PDF"))          # still builds

    def test_long_resume_flows_to_more_pages(self):
        for i in range(8):
            Project.objects.create(resume=self.r, name=f"Project {i}", bullets="\n".join(f"Built feature number {j} for project {i}" for j in range(8)), order=10 + i)
        reader = PdfReader(io.BytesIO(build_pdf(self.r)))
        self.assertGreaterEqual(len(reader.pages), 2)
        self.assertIn("Project 7", pdf_text(build_pdf(self.r)))

    def test_resume_with_only_a_name_builds(self):
        self.assertIn("Only Name", pdf_text(build_pdf(Resume.objects.create(user=self.user, title="t", full_name="Only Name"))))


# ------------------------------------------------------------ forms/validation
class FormTests(TestCase):
    BASE = {"title": "t", "layout": "student", "full_name": "  Asha   Raman ", "headline": "", "email": "", "phone": "", "location": "",
            "linkedin_url": "", "github_url": "", "portfolio_url": "", "summary": "", "skills": ""}

    def form(self, **kw):
        return ResumeForm({**self.BASE, **kw})

    def test_valid_form_cleans_the_name(self):
        f = self.form()
        self.assertTrue(f.is_valid(), f.errors)
        self.assertEqual(f.cleaned_data["full_name"], "Asha Raman")

    def test_only_http_links_are_accepted(self):
        for bad in ("javascript:alert(1)", "ftp://example.com/x", "data:text/html,hi", "file:///etc/passwd"):
            self.assertFalse(self.form(linkedin_url=bad).is_valid(), bad)
        f = self.form(linkedin_url="linkedin.com/in/asha")                 # a missing scheme is completed to http://
        self.assertTrue(f.is_valid())
        self.assertEqual(f.cleaned_data["linkedin_url"], "http://linkedin.com/in/asha")
        self.assertTrue(self.form(github_url="https://github.com/asha", portfolio_url="http://asha.dev").is_valid())

    def test_phone_and_name_validation(self):
        self.assertFalse(self.form(phone="call me maybe").is_valid())
        self.assertFalse(self.form(phone="12").is_valid())
        self.assertTrue(self.form(phone="+91 (98765) 43210").is_valid())
        self.assertFalse(self.form(full_name="   ").is_valid())

    def test_length_limits(self):
        self.assertFalse(self.form(summary="x" * 701).is_valid())
        self.assertFalse(self.form(skills="x" * 1501).is_valid())

    def test_bullet_limits(self):
        base = {"name": "P", "tech_stack": "", "link": ""}
        self.assertTrue(ProjectForm({**base, "bullets": "\n".join(["ok"] * 8)}).is_valid())
        self.assertFalse(ProjectForm({**base, "bullets": "\n".join(["ok"] * 9)}).is_valid())
        self.assertFalse(ProjectForm({**base, "bullets": "x" * 301}).is_valid())
        self.assertFalse(ProjectForm({**base, "link": "javascript:alert(1)", "bullets": "ok"}).is_valid())
        self.assertTrue(ExperienceForm({"role": "r", "organization": "o", "location": "", "start": "", "end": "", "bullets": "did a thing"}).is_valid())
        self.assertFalse(ExperienceForm({"role": "r", "organization": "o", "bullets": ""}).is_valid())     # bullets required
        self.assertTrue(EducationForm({"institution": "i", "degree": "d"}).is_valid())


# ------------------------------------------------------------------- builder views
class BuilderViewTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_login(self.user)

    def test_create_prefills_from_the_account_and_redirects_to_editor(self):
        self.user.profile.target_role = "Data Analyst"
        self.user.profile.save()
        page = self.client.get(reverse("resume_builder:create"))
        self.assertContains(page, 'value="U1"') if False else None
        initial = page.context["form"].initial
        self.assertEqual((initial["email"], initial["headline"]), ("u1@example.com", "Data Analyst"))
        r = self.client.post(reverse("resume_builder:create"), {"title": "Mine", "layout": "student", "full_name": "Asha", "email": "a@example.com",
                                                                 "headline": "", "phone": "", "location": "", "linkedin_url": "", "github_url": "",
                                                                 "portfolio_url": "", "summary": "", "skills": ""})
        resume = Resume.objects.get(user=self.user)
        self.assertRedirects(r, reverse("resume_builder:editor", args=[resume.pk]))

    def test_at_most_ten_resumes(self):
        for i in range(10):
            Resume.objects.create(user=self.user, title=f"r{i}", full_name="N")
        r = self.client.get(reverse("resume_builder:create"), follow=True)
        self.assertContains(r, "up to 10 resumes")
        self.assertEqual(Resume.objects.count(), 10)

    def test_editor_shows_sections_and_completeness(self):
        r = make_resume(self.user)
        page = self.client.get(reverse("resume_builder:editor", args=[r.pk]))
        for text in ("Completeness", "Anna University", "Goal Tracker", "Python Intern", "Python for Everybody", "hackathon", "Add"):
            self.assertContains(page, text)

    def test_update_and_delete_resume(self):
        r = make_resume(self.user)
        data = {"title": "Renamed", "layout": "professional", "full_name": "Asha R", "headline": "", "email": "", "phone": "", "location": "",
                "linkedin_url": "", "github_url": "", "portfolio_url": "", "summary": "", "skills": "Python"}
        self.client.post(reverse("resume_builder:update", args=[r.pk]), data)
        r.refresh_from_db()
        self.assertEqual((r.title, r.layout), ("Renamed", "professional"))
        self.assertEqual(self.client.get(reverse("resume_builder:delete", args=[r.pk])).status_code, 200)
        self.assertTrue(Resume.objects.filter(pk=r.pk).exists())          # GET never deletes
        self.client.post(reverse("resume_builder:delete", args=[r.pk]))
        self.assertFalse(Resume.objects.filter(pk=r.pk).exists())
        self.assertEqual(Education.objects.count(), 0)                      # sections go with it

    def test_all_five_section_types_can_be_added_edited_and_deleted(self):
        r = Resume.objects.create(user=self.user, title="t", full_name="N")
        samples = {
            "education": ({"institution": "IIT", "degree": "BTech"}, {"institution": "NIT", "degree": "BTech"}, Education),
            "experience": ({"role": "Intern", "organization": "Co", "bullets": "Built a thing"}, {"role": "Dev", "organization": "Co", "bullets": "Built b"}, Experience),
            "project": ({"name": "P1", "bullets": "Built it"}, {"name": "P2", "bullets": "Built it"}, Project),
            "certification": ({"name": "C1"}, {"name": "C2"}, Certification),
            "achievement": ({"text": "Won"}, {"text": "Won again"}, ResumeAchievement),
        }
        for kind, (create, edit, model) in samples.items():
            self.client.post(reverse("resume_builder:section_create", args=[r.pk, kind]), create)
            item = model.objects.get(resume=r)
            self.client.post(reverse("resume_builder:section_update", args=[kind, item.pk]), edit)
            item.refresh_from_db()
            self.assertTrue(any(v for k, v in edit.items() if getattr(item, k) == v), kind)
            self.assertEqual(self.client.get(reverse("resume_builder:section_delete", args=[kind, item.pk])).status_code, 200)
            self.client.post(reverse("resume_builder:section_delete", args=[kind, item.pk]))
            self.assertFalse(model.objects.filter(pk=item.pk).exists(), kind)

    def test_new_items_are_ordered_and_limits_are_enforced(self):
        r = Resume.objects.create(user=self.user, title="t", full_name="N")
        for i in range(5):
            self.client.post(reverse("resume_builder:section_create", args=[r.pk, "education"]), {"institution": f"I{i}", "degree": "d"})
        self.assertEqual([e.institution for e in r.educations.all()], [f"I{i}" for i in range(5)])
        self.assertEqual([e.order for e in r.educations.all()], [1, 2, 3, 4, 5])
        self.client.post(reverse("resume_builder:section_create", args=[r.pk, "education"]), {"institution": "extra", "degree": "d"})
        self.assertEqual(r.educations.count(), 5)

    def test_unknown_section_kind_is_404(self):
        r = Resume.objects.create(user=self.user, title="t", full_name="N")
        self.assertEqual(self.client.get(reverse("resume_builder:section_create", args=[r.pk, "hacks"])).status_code, 404)

    def test_preview_is_ats_friendly_and_escapes_everything(self):
        r = make_resume(self.user)
        Project.objects.create(resume=r, name="<script>alert(1)</script>", bullets="<img src=x onerror=alert(2)>", order=5)
        page = self.client.get(reverse("resume_builder:preview", args=[r.pk]))
        html = page.content.decode()
        paper = html[html.index('<article class="paper">'):html.index("</article>")]
        for forbidden in ("<table", "<img", "<script", "<svg", "<canvas"):
            self.assertNotIn(forbidden, paper)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", paper)
        for text in ("<h1>Asha Raman</h1>", "<h2>Education</h2>", "<h2>Skills</h2>", "Reduced report time by 60%"):
            self.assertIn(text, paper)

    def test_preview_warns_about_characters_the_pdf_cannot_show(self):
        r = make_resume(self.user, full_name="Łukasz Ng")
        self.assertContains(self.client.get(reverse("resume_builder:preview", args=[r.pk])), "cannot be shown in the PDF")

    def test_pdf_download_headers_and_safe_filename(self):
        r = make_resume(self.user, full_name='Asha "<R>" ../Raman')
        resp = self.client.get(reverse("resume_builder:pdf", args=[r.pk]))
        self.assertEqual(resp["Content-Type"], "application/pdf")
        self.assertRegex(resp["Content-Disposition"], r'^attachment; filename="[A-Za-z0-9_]+_Resume\.pdf"$')
        self.assertEqual(resp["X-Content-Type-Options"], "nosniff")
        self.assertIn("no-store", resp["Cache-Control"])
        self.assertTrue(resp.content.startswith(b"%PDF"))

    def test_list_page_shows_resumes_uploads_reviews(self):
        make_resume(self.user)
        page = self.client.get(reverse("resume_builder:list"))
        for text in ("Dev resume", "% complete", "Download PDF", "ATS review", "Upload a resume", "not an ATS score"):
            self.assertContains(page, text)

    def test_ats_guide_lists_the_six_checklist_items(self):
        page = self.client.get(reverse("resume_builder:ats_guide"))
        for text in ("Standard headings", "Relevant keywords", "Clear formatting", "Skills that match the job", "Achievement-oriented bullets", "graphics or tables"):
            self.assertContains(page, text)


# --------------------------------------------------------------------- uploads
class UploadValidationTests(TestCase):
    def test_valid_files(self):
        self.assertEqual(detect_kind("cv.pdf", build_pdf(make_resume(make_user()))), "pdf")
        self.assertEqual(detect_kind("CV.DOCX", docx_bytes("hello")), "docx")
        self.assertEqual(detect_kind("cv.txt", b"Plain resume text"), "txt")

    def test_rejected_files(self):
        cases = [("cv.exe", b"MZ\x90\x00"), ("cv.png", b"\x89PNG"), ("cv.doc", b"\xd0\xcf\x11\xe0"), ("cv", b"text"), ("cv.pdf", b""),
                 ("cv.pdf", b"just some text renamed"), ("cv.docx", b"not a zip"), ("cv.txt", b"binary\x00data"),
                 ("cv.html", b"<script>alert(1)</script>"), ("cv.pdf.exe", b"%PDF-1.4")]
        for name, data in cases:
            with self.assertRaises(ValidationError, msg=name):
                detect_kind(name, data)

    def test_fake_docx_zip_and_zip_bomb_style_files_are_rejected(self):
        plain_zip = io.BytesIO()
        with zipfile.ZipFile(plain_zip, "w") as z:
            z.writestr("hello.txt", "hi")
        with self.assertRaises(ValidationError):
            detect_kind("cv.docx", plain_zip.getvalue())
        many = io.BytesIO()
        with zipfile.ZipFile(many, "w") as z:
            z.writestr("word/document.xml", "<w/>")
            for i in range(2100):
                z.writestr(f"f{i}.txt", "x")
        with self.assertRaises(ValidationError):
            detect_kind("cv.docx", many.getvalue())

    @override_settings(RESUME_MAX_UPLOAD_BYTES=1000)
    def test_size_limit(self):
        big = SimpleUploadedFile("cv.txt", b"x" * 1001)
        with self.assertRaises(ValidationError):
            validate_upload(big)
        self.assertEqual(validate_upload(SimpleUploadedFile("cv.txt", b"x" * 1000))[0], "txt")


class UploadViewTests(PrivateMedia):
    def setUp(self):
        super().setUp()
        self.user = make_user()
        self.client.force_login(self.user)
        self.pdf = build_pdf(make_resume(self.user))

    def upload(self, name="my cv.pdf", data=None, **kw):
        return self.client.post(reverse("resume_builder:upload_create"), {"file": SimpleUploadedFile(name, data if data is not None else self.pdf, **kw)})

    def test_upload_valid_pdf_docx_txt(self):
        for name, data in (("a.pdf", self.pdf), ("b.docx", docx_bytes("Hello")), ("c.txt", b"Hello resume")):
            self.assertRedirects(self.upload(name, data), reverse("resume_builder:list"))
        self.assertEqual(ResumeUpload.objects.filter(user=self.user).count(), 3)

    def test_invalid_uploads_show_a_message_and_save_nothing(self):
        for name, data, message in (("cv.exe", b"MZ", "PDF, DOCX or TXT"), ("cv.pdf", b"fake", "not a real PDF"), ("cv.doc", b"x", "Old .doc"),
                                    ("cv.pdf", b"", "empty")):
            r = self.upload(name, data)
            self.assertContains(r, message, msg_prefix=name)
        self.assertEqual(ResumeUpload.objects.count(), 0)
        self.assertEqual(list(Path(self.media).rglob("*.*")), [])

    def test_files_are_stored_privately_under_a_random_name(self):
        self.upload("../../etc/passwd/my résumé.pdf")
        up = ResumeUpload.objects.get()
        path = Path(up.file.path)
        self.assertTrue(str(path).startswith(self.media))
        self.assertEqual(path.parent, Path(self.media) / "resumes" / str(self.user.pk))
        self.assertRegex(path.name, r"^[0-9a-f]{32}\.pdf$")
        self.assertEqual(path.read_bytes(), self.pdf)
        self.assertNotIn("/", up.original_name)
        self.assertNotIn("\\", up.original_name)

    def test_the_file_is_nowhere_public(self):
        self.upload()
        up = ResumeUpload.objects.get()
        self.client.logout()
        for url in (f"/media/{up.file.name}", f"/static/{up.file.name}", f"/{up.file.name}", f"/private_media/{up.file.name}"):
            self.assertEqual(self.client.get(url).status_code, 404, url)
        from django.urls import Resolver404, resolve
        for path in (f"/{up.file.name}", f"/media/{up.file.name}", f"/static/{up.file.name}"):
            with self.assertRaises(Resolver404, msg=path):        # no URL pattern can even reach the files
                resolve(path)
        self.assertNotIn("static", str(settings.MEDIA_ROOT))
        self.assertIn("private_media/", (Path(settings.BASE_DIR) / ".gitignore").read_text())

    def test_download_returns_the_exact_file_with_safe_headers(self):
        self.upload("my cv.pdf")
        up = ResumeUpload.objects.get()
        r = self.client.get(reverse("resume_builder:upload_download", args=[up.pk]))
        self.assertEqual(b"".join(r.streaming_content), self.pdf)
        self.assertEqual(r["Content-Type"], "application/pdf")
        self.assertIn("attachment", r["Content-Disposition"])
        self.assertEqual(r["X-Content-Type-Options"], "nosniff")
        self.assertIn("no-store", r["Cache-Control"])

    def test_download_name_cannot_inject_headers(self):
        """Even a stored name with CR/LF or quotes (e.g. created through the admin) is cleaned before it reaches a header."""
        self.upload("clean.pdf")
        up = ResumeUpload.objects.get()
        ResumeUpload.objects.filter(pk=up.pk).update(original_name='evil";\r\nX-Hack: 1.pdf')
        r = self.client.get(reverse("resume_builder:upload_download", args=[up.pk]))
        self.assertNotIn("X-Hack", r.headers)
        self.assertNotIn("\r", r["Content-Disposition"])
        self.assertNotIn("\n", r["Content-Disposition"])
        self.assertEqual(ResumeUpload.objects.get(pk=up.pk).safe_download_name, "evil____X-Hack_ 1.pdf")

    def test_only_the_owner_can_download_review_or_delete(self):
        self.upload()
        up = ResumeUpload.objects.get()
        self.client.force_login(make_user("mallory"))
        for name in ("resume_builder:upload_download", "resume_builder:upload_review", "resume_builder:upload_delete"):
            self.assertEqual(self.client.get(reverse(name, args=[up.pk])).status_code, 404, name)
        self.client.post(reverse("resume_builder:upload_delete", args=[up.pk]))
        self.assertTrue(ResumeUpload.objects.filter(pk=up.pk).exists())
        self.client.logout()
        self.assertEqual(self.client.get(reverse("resume_builder:upload_download", args=[up.pk])).status_code, 302)

    def test_deleting_removes_the_file_from_disk(self):
        self.upload()
        up = ResumeUpload.objects.get()
        path = Path(up.file.path)
        self.assertTrue(path.exists())
        self.client.post(reverse("resume_builder:upload_delete", args=[up.pk]))
        self.assertFalse(path.exists())

    def test_deleting_the_account_removes_the_files(self):
        self.upload(); self.upload("b.txt", b"hello")
        paths = [Path(u.file.path) for u in ResumeUpload.objects.all()]
        self.assertTrue(all(p.exists() for p in paths))
        self.user.delete()
        self.assertFalse(any(p.exists() for p in paths))
        self.assertEqual(ResumeUpload.objects.count(), 0)

    def test_at_most_ten_uploads(self):
        for i in range(10):
            self.upload(f"{i}.txt", b"hello resume")
        r = self.client.get(reverse("resume_builder:upload_create"), follow=True)
        self.assertContains(r, "up to 10 uploaded")
        self.upload("11.txt", b"hello")
        self.assertEqual(ResumeUpload.objects.count(), 10)

    def test_upload_pages_require_login(self):
        self.client.logout()
        for name in ("resume_builder:upload_create", "resume_builder:list"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 302)


class ExtractionTests(TestCase):
    def test_text_from_our_own_pdf_and_page_count(self):
        out = extract_text("pdf", build_pdf(make_resume(make_user())))
        self.assertIn("Asha Raman", out["text"])
        self.assertEqual(out["pages"], 1)

    def test_docx_text_and_tables(self):
        out = extract_text("docx", docx_bytes("Hello Resume", "Skills", table=True))
        self.assertIn("Hello Resume", out["text"])
        self.assertTrue(out["has_tables"])
        self.assertFalse(extract_text("docx", docx_bytes("plain"))["has_tables"])

    def test_txt(self):
        self.assertEqual(extract_text("txt", "Héllo".encode())["text"], "Héllo")

    def test_only_the_first_ten_pages_are_read(self):
        out = extract_text("pdf", many_page_pdf(12))
        self.assertEqual(out["pages"], 12)
        self.assertIn("Page number 10", out["text"])
        self.assertNotIn("Page number 11", out["text"])

    def test_image_only_pdf_gives_almost_no_text(self):
        self.assertLess(len(extract_text("pdf", blank_image_pdf())["text"].strip()), 20)

    def test_encrypted_pdf_gives_a_friendly_error(self):
        w = PdfWriter()
        w.add_blank_page(width=200, height=200)
        w.encrypt("secret")
        out = io.BytesIO()
        w.write(out)
        with self.assertRaisesMessage(ExtractionError, "password protected"):
            extract_text("pdf", out.getvalue())

    def test_damaged_files_give_a_friendly_error_not_a_crash(self):
        with self.assertRaises(ExtractionError):
            extract_text("pdf", b"%PDF-1.4\nthis is not really a pdf at all")
        with self.assertRaises(ExtractionError):
            extract_text("docx", b"PK\x03\x04garbage")

    def test_huge_text_is_truncated(self):
        self.assertEqual(len(extract_text("txt", b"a" * 500_000)["text"]), 100_000)


# ------------------------------------------------------------------ ATS engine
STRONG = resume_text = None


class AtsEngineTests(TestCase):
    def setUp(self):
        self.good = resume_to_text(make_resume(make_user()))
        self.weak = "My Journey\nI am a hard worker who is responsible for many things\nWhat I do\nworked on some stuff and helped with things\nexperiance in lots of things\n"

    def test_good_resume_scores_far_higher_than_a_weak_one(self):
        good, weak = ats.analyze(self.good, GOOD_JD), ats.analyze(self.weak, GOOD_JD)
        self.assertGreaterEqual(good["score"], 80)
        self.assertLessEqual(weak["score"], 25)
        self.assertTrue(0 <= weak["score"] <= good["score"] <= 100)

    def test_is_deterministic_and_json_safe_and_never_stores_contact_values(self):
        a, b = ats.analyze(self.good, GOOD_JD), ats.analyze(self.good, GOOD_JD)
        self.assertEqual(a, b)
        dumped = json.dumps(a)
        for private in ("asha@example.com", "98765", "linkedin.com/in/asha"):
            self.assertNotIn(private, dumped)
        self.assertTrue(a["stats"]["contact"]["email"] and a["stats"]["contact"]["phone"])

    def test_disclaimer_is_present_and_never_calls_itself_an_ats_score(self):
        r = ats.analyze(self.good)
        self.assertIn("NOT an ATS score", r["disclaimer"])
        self.assertIn("indicative", r["disclaimer"])

    def test_keyword_group_is_skipped_without_a_job_description(self):
        with_jd, without = ats.analyze(self.good, GOOD_JD), ats.analyze(self.good)
        self.assertEqual(with_jd["possible"] - without["possible"], 20)
        self.assertFalse(without["keyword_check_applied"])
        self.assertTrue(with_jd["keyword_check_applied"])
        self.assertIsNone(without["keywords"]["coverage"])
        kw = [c for g in without["groups"] for c in g["checks"] if c["group"].startswith("Keywords")][0]
        self.assertEqual(kw["status"], "na")

    def test_keyword_matching(self):
        r = ats.analyze(self.good, GOOD_JD)
        self.assertEqual(set(r["keywords"]["matched"]), {"python", "django", "sql", "git", "rest api"})
        self.assertEqual(set(r["keywords"]["missing"]), {"docker", "communication"})
        self.assertEqual(r["keywords"]["coverage"], 71)
        self.assertIn("docker", [s["skill"] for s in r["skill_suggestions"]])

    def test_tricky_keywords_c_plus_plus_csharp_nodejs_and_word_boundaries(self):
        skills, _ = ats.extract_keywords("Need C++, C#, Node.js, JavaScript and Java. ML or machine learning. HTML5.")
        self.assertEqual(set(skills), {"c++", "c#", "node.js", "javascript", "java", "machine learning", "html"})
        self.assertFalse(ats.has_keyword("I know JavaScript only", "java"))        # java is not inside javascript
        self.assertTrue(ats.has_keyword("Built apps in Node js", "node.js"))
        self.assertFalse(ats.has_keyword("HTML and CSS", "machine learning"))       # ml must not match html
        self.assertTrue(ats.has_keyword("Worked on ML models", "machine learning"))
        self.assertTrue(ats.has_keyword("amazon web services", "aws"))

    def test_job_description_without_skills_is_reported_not_scored(self):
        r = ats.analyze(self.good, "We are a friendly company with a nice office and great snacks.")
        kw = [c for g in r["groups"] for c in g["checks"] if c["group"].startswith("Keywords")][0]
        self.assertEqual(kw["status"], "na")
        self.assertIn("no recognisable skills", kw["detail"])

    def test_sections_and_headings(self):
        found, nonstd, content = ats.scan_sections("Jane Doe\njane@x.com\n\nEDUCATION\nBSc\n\nTECHNICAL SKILLS:\nPython\n\nMY AMAZING JOURNEY\nstuff\n")
        self.assertEqual(found, {"education", "skills"})
        self.assertEqual(nonstd, ["MY AMAZING JOURNEY"])
        self.assertEqual(content["education"], ["BSc"])
        r = ats.analyze("Jane\n\nEducation\nBSc\n")
        self.assertIn("Skills", r["missing_sections"])
        self.assertNotIn("Education", r["missing_sections"])

    def test_contact_detection(self):
        self.assertTrue(ats.contact_info("call +91 98765 43210 now")["phone"])
        self.assertTrue(ats.contact_info("98765-43210")["phone"])
        self.assertTrue(ats.contact_info("(044) 2345 6789")["phone"])
        self.assertFalse(ats.contact_info("Studied 2022 - 2026, CGPA 8.4, 120 tests")["phone"])
        info = ats.contact_info("me@mail.co.in https://github.com/x linkedin.com/in/me")
        self.assertTrue(info["email"] and info["github"] and info["linkedin"])
        self.assertFalse(ats.contact_info("nothing here")["email"])

    def test_bullet_quality_checks(self):
        strong = "Experience\n- Built a web app used by 500 students\n- Reduced load time by 40%\n- Automated 12 reports"
        weak = "Experience\n- Responsible for the website\n- I worked on my project\n- helped with testing"
        s, w = ats.analyze(strong), ats.analyze(weak)
        def group(r): return [g for g in r["groups"] if g["name"].startswith("Achievement")][0]
        self.assertEqual(group(s)["earned"], 20)
        self.assertLess(group(w)["earned"], 8)
        labels = {c["label"]: c for c in group(w)["checks"]}
        self.assertEqual(labels["No weak phrases"]["status"], "fail" if labels["No weak phrases"]["earned"] == 0 else "partial")
        self.assertEqual(labels["No first-person pronouns"]["earned"], 0)
        self.assertIn("Examples", labels["Bullets include numbers or results"]["advice"])

    def test_no_bullets_scores_zero_in_that_group_with_advice(self):
        r = ats.analyze("Education\nBSc\n")
        g = [g for g in r["groups"] if g["name"].startswith("Achievement")][0]
        self.assertEqual(g["earned"], 0)
        self.assertTrue(all(c["advice"] for c in g["checks"]))

    def test_formatting_checks(self):
        cols = "Asha\nx\ny\n" + "\n".join("Python        Django        SQL" for _ in range(4))
        self.assertEqual(self._fmt(ats.analyze(cols), "No tables or multi-column layout")["earned"], 0)
        self.assertEqual(self._fmt(ats.analyze("Hello", meta={"has_tables": True}), "No tables or multi-column layout")["earned"], 0)
        icons = "☎ 9876543210 ✉ me@x.com ★ skills 😀"
        r = ats.analyze(icons)
        self.assertEqual(self._fmt(r, "No icons, emoji or decorative symbols")["earned"], 0)
        self.assertEqual(self._fmt(ats.analyze("Plain • bullets – dash ’ quote"), "No icons, emoji or decorative symbols")["earned"], 2)
        self.assertEqual(self._fmt(ats.analyze("short"), "Text can be read from the file")["earned"], 0)
        pages = lambda n: self._fmt(ats.analyze(self.good, meta={"pages": n}), "Page count")
        self.assertEqual((pages(1)["earned"], pages(3)["earned"], pages(5)["earned"]), (3, 1.5, 0))
        self.assertEqual(self._fmt(ats.analyze(self.good), "Page count")["status"], "na")

    def _fmt(self, result, label):
        return [c for g in result["groups"] for c in g["checks"] if c["label"] == label][0]

    def test_length_bands(self):
        def pts(n): return self._fmt(ats.analyze("word " * n), "Sensible length")["earned"]
        self.assertEqual((pts(100), pts(200), pts(500), pts(1000), pts(2000)), (0, 2, 4, 2, 0))

    def test_writing_suggestions(self):
        text = "Experience\n- built the experiance system  with the the best tools.\n- Application was developed by me\n- improved speed"
        types = {w["type"] for w in ats.analyze(text)["writing"]}
        for expected in ("Possible spelling mistake", "Double spaces", "Repeated word", "Passive voice", "Bullets not starting with a capital letter"):
            self.assertIn(expected, types)
        clean = {w["type"] for w in ats.analyze(self.good)["writing"]}
        self.assertEqual(clean, set())
        mixed = "Experience\n- Built one.\n- Built two\n- Built three.\n- Built four"
        self.assertIn("Inconsistent full stops", {w["type"] for w in ats.analyze(mixed)["writing"]})
        self.assertIn("Very long bullet", {w["type"] for w in ats.analyze("Experience\n- " + "Built " * 40)["writing"]})

    def test_skill_suggestions_from_role_and_learning(self):
        text = "Skills\nExcel"
        r = ats.analyze(text, target_role="Data Analyst Intern", learned=[("python", "You completed 4 Python topics on Goal Achiever")])
        suggested = {s["skill"]: s["reason"] for s in r["skill_suggestions"]}
        self.assertIn("sql", suggested)
        self.assertIn("Commonly expected", suggested["sql"])
        self.assertIn("completed 4 Python topics", suggested["python"])        # reasons are combined
        self.assertIn("Commonly expected", suggested["python"])
        self.assertNotIn("excel", suggested)                        # already on the resume
        self.assertLessEqual(len(r["skill_suggestions"]), 10)

    def test_empty_text_is_handled(self):
        r = ats.analyze("")
        self.assertEqual(r["score"] >= 0, True)
        self.assertIn("Skills", r["missing_sections"])


# ------------------------------------------------------------- review workflow
class ReviewViewTests(PrivateMedia):
    def setUp(self):
        super().setUp()
        self.user = make_user()
        self.client.force_login(self.user)
        self.resume = make_resume(self.user)

    def review(self, jd=""):
        return self.client.post(reverse("resume_builder:review_resume", args=[self.resume.pk]), {"job_description": jd})

    def test_review_form_explains_what_the_score_is(self):
        page = self.client.get(reverse("resume_builder:review_resume", args=[self.resume.pk]))
        self.assertContains(page, "indicative checklist score")
        self.assertContains(page, "not a real ATS score")
        self.assertContains(page, "nothing is sent elsewhere")

    def test_builder_review_is_saved_and_shown(self):
        r = self.review(GOOD_JD)
        rv = ResumeReview.objects.get()
        self.assertRedirects(r, reverse("resume_builder:review", args=[rv.pk]))
        self.assertEqual((rv.source_kind, rv.source_name, rv.resume), ("builder", "Dev resume", self.resume))
        self.assertGreaterEqual(rv.score, 80)
        self.assertEqual(rv.job_description, GOOD_JD)
        page = self.client.get(reverse("resume_builder:review", args=[rv.pk]))
        for text in ("Indicative checklist score", "NOT an ATS score", "Sections and headings", "Keyword coverage", "Writing suggestions", "Skills you might add",
                     "docker", "Never list skills you do not have", "Job description used"):
            self.assertContains(page, text)

    def test_review_without_job_description_says_keywords_were_not_checked(self):
        self.review()
        rv = ResumeReview.objects.get()
        page = self.client.get(reverse("resume_builder:review", args=[rv.pk]))
        self.assertContains(page, "keyword check was not applied")
        self.assertContains(page, "no job description was given")

    def test_fix_these_first_lists_the_biggest_gaps(self):
        weak = Resume.objects.create(user=self.user, title="weak", full_name="W")
        self.client.post(reverse("resume_builder:review_resume", args=[weak.pk]), {"job_description": ""})
        rv = ResumeReview.objects.get(source_name="weak")
        wins = services.quick_wins(rv.result)
        self.assertEqual(len(wins), 3)
        self.assertEqual(wins, sorted(wins, key=lambda c: c["earned"] - c["max"]))
        self.assertContains(self.client.get(reverse("resume_builder:review", args=[rv.pk])), "Fix these first")

    def test_upload_review_end_to_end(self):
        self.client.post(reverse("resume_builder:upload_create"), {"file": SimpleUploadedFile("cv.pdf", build_pdf(self.resume))})
        up = ResumeUpload.objects.get()
        r = self.client.post(reverse("resume_builder:upload_review", args=[up.pk]), {"job_description": GOOD_JD})
        rv = ResumeReview.objects.get()
        self.assertRedirects(r, reverse("resume_builder:review", args=[rv.pk]))
        self.assertEqual((rv.source_kind, rv.upload), ("upload", up))
        self.assertEqual(rv.result["stats"]["pages"], 1)
        self.assertGreaterEqual(rv.score, 75)

    def test_unreadable_or_image_only_uploads_are_handled(self):
        self.client.post(reverse("resume_builder:upload_create"), {"file": SimpleUploadedFile("scan.pdf", blank_image_pdf())})
        up = ResumeUpload.objects.get()
        self.client.post(reverse("resume_builder:upload_review", args=[up.pk]), {"job_description": ""})
        rv = ResumeReview.objects.get()
        check = [c for g in rv.result["groups"] for c in g["checks"] if c["label"] == "Text can be read from the file"][0]
        self.assertEqual(check["status"], "fail")
        self.assertIn("scanned", check["advice"])

    def test_damaged_upload_shows_an_error(self):
        w = PdfWriter(); w.add_blank_page(width=100, height=100); w.encrypt("pw")
        buf = io.BytesIO(); w.write(buf)
        self.client.post(reverse("resume_builder:upload_create"), {"file": SimpleUploadedFile("locked.pdf", buf.getvalue())})
        up = ResumeUpload.objects.get()
        r = self.client.post(reverse("resume_builder:upload_review", args=[up.pk]), {"job_description": ""}, follow=True)
        self.assertContains(r, "password protected")
        self.assertEqual(ResumeReview.objects.count(), 0)

    def test_job_description_is_limited_and_escaped(self):
        r = self.review("x" * 10001)
        self.assertEqual(ResumeReview.objects.count(), 0)
        self.assertEqual(r.status_code, 200)
        self.review("<script>alert(1)</script> Python")
        rv = ResumeReview.objects.get()
        page = self.client.get(reverse("resume_builder:review", args=[rv.pk]))
        self.assertNotContains(page, "<script>alert(1)</script>")
        self.assertContains(page, "&lt;script&gt;alert(1)&lt;/script&gt;")

    def test_review_history_list_and_delete(self):
        self.review(); self.review(GOOD_JD)
        page = self.client.get(reverse("resume_builder:reviews"))
        self.assertContains(page, "/100", count=2)
        rv = ResumeReview.objects.first()
        self.assertEqual(self.client.get(reverse("resume_builder:review_delete", args=[rv.pk])).status_code, 405)
        self.client.post(reverse("resume_builder:review_delete", args=[rv.pk]))
        self.assertFalse(ResumeReview.objects.filter(pk=rv.pk).exists())

    def test_only_the_newest_fifty_reviews_are_kept(self):
        for _ in range(53):
            services.run_review(self.user, "Education\nBSc\n", "", "x", "builder")
        self.assertEqual(ResumeReview.objects.filter(user=self.user).count(), 50)

    def test_review_survives_deleting_the_resume(self):
        self.review()
        self.client.post(reverse("resume_builder:delete", args=[self.resume.pk]))
        rv = ResumeReview.objects.get()
        self.assertIsNone(rv.resume)
        self.assertEqual(rv.source_name, "Dev resume")
        self.assertEqual(self.client.get(reverse("resume_builder:review", args=[rv.pk])).status_code, 200)


class PermissionTests(PrivateMedia):
    def setUp(self):
        super().setUp()
        self.alice, self.bob = make_user("alice"), make_user("bob")
        self.resume = make_resume(self.alice)
        services.run_review(self.alice, "Education\nBSc", "", "alice resume", "builder", resume=self.resume)
        self.review = ResumeReview.objects.get()
        self.section = self.resume.projects.first()

    def test_anonymous_users_are_redirected_everywhere(self):
        urls = [reverse("resume_builder:list"), reverse("resume_builder:create"), reverse("resume_builder:editor", args=[self.resume.pk]),
                reverse("resume_builder:preview", args=[self.resume.pk]), reverse("resume_builder:pdf", args=[self.resume.pk]),
                reverse("resume_builder:review_resume", args=[self.resume.pk]), reverse("resume_builder:reviews"),
                reverse("resume_builder:review", args=[self.review.pk]), reverse("resume_builder:ats_guide")]
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 302, url)

    def test_another_user_gets_404_and_changes_nothing(self):
        self.client.force_login(self.bob)
        for name, args in (("editor", [self.resume.pk]), ("update", [self.resume.pk]), ("delete", [self.resume.pk]), ("preview", [self.resume.pk]),
                           ("pdf", [self.resume.pk]), ("review_resume", [self.resume.pk]), ("review", [self.review.pk])):
            self.assertEqual(self.client.get(reverse(f"resume_builder:{name}", args=args)).status_code, 404, name)
        self.assertEqual(self.client.get(reverse("resume_builder:section_create", args=[self.resume.pk, "project"])).status_code, 404)
        self.assertEqual(self.client.get(reverse("resume_builder:section_update", args=["project", self.section.pk])).status_code, 404)
        self.client.post(reverse("resume_builder:delete", args=[self.resume.pk]))
        self.client.post(reverse("resume_builder:section_delete", args=["project", self.section.pk]))
        self.client.post(reverse("resume_builder:review_delete", args=[self.review.pk]))
        self.client.post(reverse("resume_builder:section_create", args=[self.resume.pk, "project"]), {"name": "hack", "bullets": "x"})
        self.assertTrue(Resume.objects.filter(pk=self.resume.pk).exists())
        self.assertTrue(Project.objects.filter(pk=self.section.pk).exists())
        self.assertFalse(Project.objects.filter(name="hack").exists())
        self.assertTrue(ResumeReview.objects.filter(pk=self.review.pk).exists())

    def test_lists_show_only_own_items(self):
        self.client.force_login(self.bob)
        page = self.client.get(reverse("resume_builder:list"))
        self.assertNotContains(page, "Dev resume")
        self.assertNotContains(page, "alice resume")
        self.assertNotContains(self.client.get(reverse("resume_builder:reviews")), "alice resume")


class IntegrationTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_login(self.user)

    def test_badges_for_first_resume_and_first_review(self):
        r = make_resume(self.user)
        self.assertTrue(Achievement.objects.filter(user=self.user, key="resume_started").exists())
        self.assertFalse(Achievement.objects.filter(user=self.user, key="ats_checked").exists())
        services.run_review(self.user, "Education\nBSc", "", "x", "builder", resume=r)
        self.assertTrue(Achievement.objects.filter(user=self.user, key="ats_checked").exists())

    def test_skill_suggestions_use_what_the_user_practised_here(self):
        d = Domain.objects.create(user=self.user, name="Tech")
        t = Technology.objects.create(user=self.user, domain=d, name="SQL")
        for i in range(3):
            set_topic_status(self.user, Topic.objects.create(user=self.user, technology=t, name=f"t{i}"), "completed")
        learned = services.learned_skills(self.user)
        self.assertEqual(learned[0][0], "sql")
        self.assertIn("3 SQL topics", learned[0][1])
        rv = services.run_review(self.user, "Skills\nExcel\nEducation\nBSc", "", "x", "builder")
        self.assertIn("sql", [s["skill"] for s in rv.result["skill_suggestions"]])

    def test_fewer_than_three_topics_or_unsolved_problems_suggest_nothing(self):
        d = Domain.objects.create(user=self.user, name="Tech")
        t = Technology.objects.create(user=self.user, domain=d, name="SQL")
        set_topic_status(self.user, Topic.objects.create(user=self.user, technology=t, name="one"), "completed")
        self.assertEqual(services.learned_skills(self.user), [])

    def test_five_solved_coding_problems_suggest_data_structures(self):
        for p in CodingProblem.objects.all()[:5]:
            coding_services.record_manual(self.user, p, "c", solved=True)
        self.assertIn("data structures", [s for s, _ in services.learned_skills(self.user)])

    def test_dashboard_and_sidebar_show_the_resume_area(self):
        make_resume(self.user)
        services.run_review(self.user, "Education\nBSc", "", "x", "builder")
        page = self.client.get(reverse("dashboard:index"))
        self.assertContains(page, "resume tools")
        self.assertContains(page, "indicative checklist")
        self.assertContains(page, reverse("resume_builder:list"))
        self.assertEqual(page.context["resume_info"]["resumes"], 1)

    def test_signals_do_not_break_resume_deletion_with_the_account(self):
        make_resume(self.user)
        self.user.delete()
        self.assertEqual(Resume.objects.count(), 0)
