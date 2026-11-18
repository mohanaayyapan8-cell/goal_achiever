"""Business logic for the learning app (kept out of views so it is easy to test)."""
from django.db import transaction
from django.db.models import Count, Max, Q

from .content_data import CONTENT
from .models import Domain, LearningContent, LearningProgress, Technology, Topic
from .seed_data import DEFAULT_CURRICULUM

DONE = Q(technologies__topics__progress__status=LearningProgress.COMPLETED)


def percent(done, total):
    return round(done * 100 / total) if total else 0


def next_order(queryset):
    return (queryset.aggregate(m=Max("order"))["m"] or 0) + 1


@transaction.atomic
def seed_default_curriculum(user):
    """Add the default domains/technologies/topics a user does not have yet.
    Safe to run many times: nothing is duplicated or overwritten.
    Returns a dict with the number of rows created."""
    created = {"domains": 0, "technologies": 0, "topics": 0, "content": 0}
    for d_name, d_desc, techs in DEFAULT_CURRICULUM:
        domain = Domain.objects.filter(user=user, name__iexact=d_name).first()
        if domain is None:
            domain = Domain.objects.create(user=user, name=d_name, description=d_desc,
                                           order=next_order(Domain.objects.filter(user=user)))
            created["domains"] += 1
        for t_name, topic_names in techs:
            tech = Technology.objects.filter(domain=domain, name__iexact=t_name).first()
            if tech is None:
                tech = Technology.objects.create(user=user, domain=domain, name=t_name,
                                                 order=next_order(Technology.objects.filter(domain=domain)))
                created["technologies"] += 1
            have = {n.lower() for n in tech.topics.values_list("name", flat=True)}
            start = next_order(tech.topics.all())
            new = [Topic(user=user, technology=tech, name=n, order=start + i)
                   for i, n in enumerate(x for x in topic_names if x.lower() not in have)]
            Topic.objects.bulk_create(new)
            created["topics"] += len(new)
    created["content"] = seed_topic_content(user)
    return created


def seed_topic_content(user):
    """Give default topics their lesson text. Topics that already have content
    (maybe edited by the user) are never touched. Returns how many were created."""
    count = 0
    for tech_name, lessons in CONTENT.items():
        topics = (Topic.objects.filter(user=user, technology__name__iexact=tech_name, content__isnull=True)
                  .select_related("technology"))
        rows = [LearningContent(user=user, topic=t, **lessons[t.name]) for t in topics if t.name in lessons]
        LearningContent.objects.bulk_create(rows)
        count += len(rows)
    return count


def set_topic_status(user, topic, status):
    progress, _ = LearningProgress.objects.get_or_create(user=user, topic=topic)
    progress.set_status(status)
    return progress


def _attach_percent(objects, total_attr="total_topics", done_attr="done_topics"):
    objects = list(objects)
    for obj in objects:
        obj.percent = percent(getattr(obj, done_attr), getattr(obj, total_attr))
    return objects


def domains_with_progress(user):
    qs = Domain.objects.filter(user=user).annotate(
        tech_count=Count("technologies", distinct=True),
        total_topics=Count("technologies__topics", distinct=True),
        done_topics=Count("technologies__topics", filter=DONE, distinct=True),
    )
    return _attach_percent(qs)


def technologies_with_progress(domain):
    qs = domain.technologies.annotate(
        total_topics=Count("topics", distinct=True),
        done_topics=Count("topics", filter=Q(topics__progress__status=LearningProgress.COMPLETED), distinct=True),
    )
    return _attach_percent(qs)


def overall_stats(user):
    topics = Topic.objects.filter(user=user)
    total = topics.count()
    counts = dict(LearningProgress.objects.filter(user=user).values_list("status").annotate(n=Count("id")))
    completed = counts.get(LearningProgress.COMPLETED, 0)
    in_progress = counts.get(LearningProgress.IN_PROGRESS, 0)
    return {
        "domains": Domain.objects.filter(user=user).count(),
        "technologies": Technology.objects.filter(user=user).count(),
        "topics": total,
        "completed": completed,
        "in_progress": in_progress,
        "not_started": max(total - completed - in_progress, 0),
        "percent": percent(completed, total),
    }
