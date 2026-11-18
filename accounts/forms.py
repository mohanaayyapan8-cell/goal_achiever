from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm

from .models import UserProfile
from .timezones import TIMEZONE_CHOICES

User = get_user_model()


class StyledFormMixin:
    """Adds the 'form-control' CSS class to every field."""

    def _style_fields(self):
        for field in self.fields.values():
            widget = field.widget
            css = "form-check" if isinstance(widget, forms.CheckboxInput) else "form-control"
            widget.attrs["class"] = f"{widget.attrs.get('class', '')} {css}".strip()


def _check_unique_email(email, exclude_pk=None):
    email = email.strip().lower()
    qs = User.objects.filter(email__iexact=email)
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    if qs.exists():
        raise forms.ValidationError("An account with this email already exists.")
    return email


class RegisterForm(StyledFormMixin, UserCreationForm):
    first_name = forms.CharField(max_length=150, label="First name")
    email = forms.EmailField(label="Email address")

    class Meta:
        model = User
        fields = ("username", "first_name", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()

    def clean_email(self):
        return _check_unique_email(self.cleaned_data["email"])

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.first_name = self.cleaned_data["first_name"]
        if commit:
            user.save()
        return user


class UserUpdateForm(StyledFormMixin, forms.ModelForm):
    email = forms.EmailField(label="Email address")

    class Meta:
        model = User
        fields = ("first_name", "last_name", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()

    def clean_email(self):
        return _check_unique_email(self.cleaned_data["email"], exclude_pk=self.instance.pk)


class ProfileForm(StyledFormMixin, forms.ModelForm):
    timezone = forms.ChoiceField(choices=TIMEZONE_CHOICES)

    class Meta:
        model = UserProfile
        fields = ("timezone", "college", "target_role", "bio", "daily_reminder_time", "email_reminders")
        widgets = {
            "bio": forms.Textarea(attrs={"rows": 3}),
            "daily_reminder_time": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()
