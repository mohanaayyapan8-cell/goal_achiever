import re

from django import forms
from django.core.exceptions import ValidationError

from accounts.forms import StyledFormMixin

from .models import Achievement, Certification, Education, Experience, Project, Resume
from .uploads import validate_upload

MAX_BULLETS, MAX_BULLET_LEN = 8, 300


def _http_only(value):
    """Links must be http(s): this rejects javascript:, data:, file: and similar."""
    if value and not value.lower().startswith(("http://", "https://")):
        raise ValidationError("Enter a web address starting with http:// or https://")
    return value


class _Styled(StyledFormMixin):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()

    def _clean_bullets(self, name="bullets"):
        text = self.cleaned_data.get(name, "")
        lines = [ln for ln in text.splitlines() if ln.strip()]
        if len(lines) > MAX_BULLETS:
            raise ValidationError(f"Use at most {MAX_BULLETS} bullets (one per line).")
        if any(len(ln) > MAX_BULLET_LEN for ln in lines):
            raise ValidationError(f"Each bullet should be under {MAX_BULLET_LEN} characters.")
        return text


class ResumeForm(_Styled, forms.ModelForm):
    class Meta:
        model = Resume
        fields = ("title", "layout", "full_name", "headline", "email", "phone", "location", "linkedin_url", "github_url",
                  "portfolio_url", "summary", "skills")
        widgets = {"summary": forms.Textarea(attrs={"rows": 4}), "skills": forms.Textarea(attrs={"rows": 5, "placeholder": "Languages: Python, SQL\nTools: Git, Django, Excel"})}

    def clean_phone(self):
        phone = self.cleaned_data["phone"].strip()
        if phone and not re.fullmatch(r"[0-9+()\-.\s]{7,30}", phone):
            raise ValidationError("Use digits, spaces, + ( ) - only, for example +91 98765 43210.")
        return phone

    def clean_linkedin_url(self):
        return _http_only(self.cleaned_data["linkedin_url"])

    def clean_github_url(self):
        return _http_only(self.cleaned_data["github_url"])

    def clean_portfolio_url(self):
        return _http_only(self.cleaned_data["portfolio_url"])

    def clean_full_name(self):
        name = " ".join(self.cleaned_data["full_name"].split())
        if not name:
            raise ValidationError("Please enter your name.")
        return name


class EducationForm(_Styled, forms.ModelForm):
    class Meta:
        model = Education
        fields = ("institution", "degree", "start", "end", "grade", "bullets")
        widgets = {"bullets": forms.Textarea(attrs={"rows": 3})}

    def clean_bullets(self):
        return self._clean_bullets()


class ExperienceForm(_Styled, forms.ModelForm):
    class Meta:
        model = Experience
        fields = ("role", "organization", "location", "start", "end", "bullets")
        widgets = {"bullets": forms.Textarea(attrs={"rows": 5, "placeholder": "Built …\nImproved … by 30%"})}

    def clean_bullets(self):
        return self._clean_bullets()


class ProjectForm(_Styled, forms.ModelForm):
    class Meta:
        model = Project
        fields = ("name", "tech_stack", "link", "bullets")
        widgets = {"bullets": forms.Textarea(attrs={"rows": 5, "placeholder": "Built …\nAutomated … saving 5 hours a week"})}

    def clean_link(self):
        return _http_only(self.cleaned_data["link"])

    def clean_bullets(self):
        return self._clean_bullets()


class CertificationForm(_Styled, forms.ModelForm):
    class Meta:
        model = Certification
        fields = ("name", "issuer", "year")


class AchievementForm(_Styled, forms.ModelForm):
    class Meta:
        model = Achievement
        fields = ("text",)


class UploadForm(_Styled, forms.Form):
    file = forms.FileField(label="Resume file (PDF, DOCX or TXT, up to 2 MB)")

    def clean_file(self):
        f = self.cleaned_data["file"]
        self.kind, self.data = validate_upload(f)       # extension + content checks, size limit
        return f


class ReviewForm(_Styled, forms.Form):
    job_description = forms.CharField(
        label="Job description (optional)", required=False, max_length=10000, widget=forms.Textarea(attrs={"rows": 9}),
        help_text="Paste the job posting to check keyword coverage. Leave empty for a general review.")
