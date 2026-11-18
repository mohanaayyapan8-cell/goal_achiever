from django import forms

from accounts.forms import StyledFormMixin

from .models import Domain, LearningContent, Technology, Topic, UserNote


class _UniqueNameMixin(StyledFormMixin):
    """Rejects a name already used by a sibling (case-insensitive)."""

    kind = "item"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()

    def siblings(self):
        raise NotImplementedError

    def clean_name(self):
        name = " ".join(self.cleaned_data["name"].split())
        if not name:
            raise forms.ValidationError("Please enter a name.")
        qs = self.siblings().filter(name__iexact=name)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError(f"You already have a {self.kind} named “{name}”.")
        return name


class DomainForm(_UniqueNameMixin, forms.ModelForm):
    kind = "domain"

    class Meta:
        model = Domain
        fields = ("name", "description")

    def __init__(self, *args, user, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def siblings(self):
        return Domain.objects.filter(user=self.user)


class TechnologyForm(_UniqueNameMixin, forms.ModelForm):
    kind = "technology"

    class Meta:
        model = Technology
        fields = ("name", "description")

    def __init__(self, *args, domain, **kwargs):
        self.domain = domain
        super().__init__(*args, **kwargs)

    def siblings(self):
        return Technology.objects.filter(domain=self.domain)


class TopicForm(_UniqueNameMixin, forms.ModelForm):
    kind = "topic"

    class Meta:
        model = Topic
        fields = ("name",)

    def __init__(self, *args, technology, **kwargs):
        self.technology = technology
        super().__init__(*args, **kwargs)

    def siblings(self):
        return Topic.objects.filter(technology=self.technology)


class ContentForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = LearningContent
        fields = [f for f, _, _ in LearningContent.SECTIONS]
        labels = {f: label for f, label, _ in LearningContent.SECTIONS}
        widgets = {f: forms.Textarea(attrs={"rows": 8 if code else 5, "class": "code-input" if code else ""})
                   for f, _, code in LearningContent.SECTIONS}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()


class NoteForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = UserNote
        fields = ("body",)
        labels = {"body": "Your note"}
        widgets = {"body": forms.Textarea(attrs={"rows": 4, "placeholder": "Write what you learned, a tricky point, a reminder…"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()

    def clean_body(self):
        body = self.cleaned_data["body"].strip()
        if not body:
            raise forms.ValidationError("A note cannot be empty.")
        return body
