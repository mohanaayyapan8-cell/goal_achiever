from datetime import date

from django import forms

from accounts.forms import StyledFormMixin
from learning.models import Technology, Topic

from .models import CHALLENGE_DAYS, DailyGoal, DailyPlan


def plan_label(plan):
    return f"Day {plan.day_number} · {plan.date:%a %d %b %Y}"


class PlanChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return plan_label(obj)


class StartChallengeForm(StyledFormMixin, forms.Form):
    start_date = forms.DateField(label="Day 1 date", widget=forms.DateInput(attrs={"type": "date"}),
                                 help_text="Usually today. Day 40 will be 39 days after this date.")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()


class GoalForm(StyledFormMixin, forms.ModelForm):
    """Create (with a day picker) or edit (without) a goal. Only the user's own days/topics are offered."""

    title = forms.CharField(max_length=200, required=False,
                            help_text="Leave blank to use “Study: <topic name>”.")

    class Meta:
        model = DailyGoal
        fields = ("title", "topic", "estimated_minutes")
        labels = {"estimated_minutes": "Estimated time (minutes)"}

    def __init__(self, *args, user, with_plan=False, **kwargs):
        super().__init__(*args, **kwargs)
        topics = Topic.objects.filter(user=user).select_related("technology")
        self.fields["topic"].queryset = topics
        self.fields["topic"].label_from_instance = lambda t: f"{t.technology.name} › {t.name}"
        self.fields["topic"].required = False
        if with_plan:
            self.fields["plan"] = PlanChoiceField(queryset=DailyPlan.objects.filter(user=user), label="Day")
            self.order_fields(["plan", "title", "topic", "estimated_minutes"])
        self._style_fields()

    def clean(self):
        cleaned = super().clean()
        title = (cleaned.get("title") or "").strip()
        topic = cleaned.get("topic")
        if not title and topic:
            title = f"Study: {topic.name}"
        if not title:
            self.add_error("title", "Enter a title or choose a topic.")
        cleaned["title"] = title
        return cleaned


class RescheduleForm(StyledFormMixin, forms.Form):
    plan = PlanChoiceField(queryset=DailyPlan.objects.none(), label="Move to")

    def __init__(self, *args, user, goal, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["plan"].queryset = DailyPlan.objects.filter(user=user).exclude(pk=goal.plan_id)
        self._style_fields()


class AutoScheduleForm(StyledFormMixin, forms.Form):
    technology = forms.ModelChoiceField(queryset=Technology.objects.none())
    topics_per_day = forms.IntegerField(min_value=1, max_value=5, initial=1)
    first_day = forms.IntegerField(min_value=1, max_value=CHALLENGE_DAYS, initial=1, label="Start on day")
    minutes_per_topic = forms.IntegerField(min_value=5, max_value=600, initial=45)

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        qs = Technology.objects.filter(user=user).select_related("domain")
        self.fields["technology"].queryset = qs
        self.fields["technology"].label_from_instance = lambda t: f"{t.name} ({t.domain.name})"
        self._style_fields()


class DayTitleForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = DailyPlan
        fields = ("title",)
        labels = {"title": "Focus of the day"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()
