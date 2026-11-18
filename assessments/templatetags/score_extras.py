from django import template

from assessments.evaluation import CRITERION_LABELS
from assessments.speaking_eval import LABELS as SPEAKING_LABELS

register = template.Library()


@register.filter
def score_class(value):
    """CSS class for a 0-100 score."""
    if value is None:
        return "score-none"
    return "score-good" if value >= 75 else "score-ok" if value >= 50 else "score-low"


@register.filter
def criterion_label(key):
    return CRITERION_LABELS.get(key) or SPEAKING_LABELS.get(key) or str(key).replace("_", " ").capitalize()


@register.filter
def group_details(details):
    """[{'group','label','passed'}] -> [(group, [items])] keeping order."""
    groups = {}
    for d in details or []:
        groups.setdefault(d["group"], []).append(d)
    return list(groups.items())


@register.filter
def get_item(mapping, key):
    return (mapping or {}).get(key, [])
