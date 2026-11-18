from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from .models import Domain, LearningProgress, Technology, Topic
from .seed_data import DEFAULT_CURRICULUM
from .services import domains_with_progress, overall_stats, percent, seed_default_curriculum, set_topic_status

User = get_user_model()


def make_user(name="u1"):
    return User.objects.create_user(name, f"{name}@example.com", "StrongPass#2026", first_name=name.title())


def make_tree(user, domain="Tech", tech="Python", topics=("Loops", "Functions", "Lists")):
    d = Domain.objects.create(user=user, name=domain)
    t = Technology.objects.create(user=user, domain=d, name=tech)
    ts = [Topic.objects.create(user=user, technology=t, name=n, order=i) for i, n in enumerate(topics)]
    return d, t, ts


class ModelTests(TestCase):
    def setUp(self):
        self.user = make_user()

    def test_domain_name_unique_per_user_case_insensitive(self):
        Domain.objects.create(user=self.user, name="Python")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Domain.objects.create(user=self.user, name="python")

    def test_two_users_can_use_same_domain_name(self):
        Domain.objects.create(user=self.user, name="Python")
        Domain.objects.create(user=make_user("u2"), name="Python")

    def test_topic_status_defaults_to_not_started(self):
        _, _, topics = make_tree(self.user)
        self.assertEqual(topics[0].status, "not_started")
        self.assertIsNone(topics[0].completed_at)

    def test_deleting_domain_cascades(self):
        d, t, topics = make_tree(self.user)
        set_topic_status(self.user, topics[0], "completed")
        d.delete()
        self.assertEqual(Technology.objects.count(), 0)
        self.assertEqual(Topic.objects.count(), 0)
        self.assertEqual(LearningProgress.objects.count(), 0)

    def test_completing_twice_keeps_first_completion_time_and_one_row(self):
        _, _, topics = make_tree(self.user)
        first = set_topic_status(self.user, topics[0], "completed").completed_at
        second = set_topic_status(self.user, topics[0], "completed").completed_at
        self.assertEqual(first, second)
        self.assertEqual(LearningProgress.objects.filter(topic=topics[0]).count(), 1)

    def test_undo_clears_completion_time(self):
        _, _, topics = make_tree(self.user)
        set_topic_status(self.user, topics[0], "completed")
        p = set_topic_status(self.user, topics[0], "not_started")
        self.assertIsNone(p.completed_at)
        self.assertEqual(p.status, "not_started")

    def test_invalid_status_raises(self):
        _, _, topics = make_tree(self.user)
        with self.assertRaises(ValueError):
            set_topic_status(self.user, topics[0], "banana")


class SeedTests(TestCase):
    def test_seed_creates_default_curriculum(self):
        user = make_user()
        created = seed_default_curriculum(user)
        self.assertEqual(created["domains"], 4)
        self.assertEqual(Domain.objects.filter(user=user).count(), len(DEFAULT_CURRICULUM))
        python = Technology.objects.get(user=user, name="Python")
        self.assertEqual(python.topics.count(), 16)
        self.assertEqual(Technology.objects.filter(user=user).count(),
                         sum(len(d[2]) for d in DEFAULT_CURRICULUM))

    def test_seed_is_idempotent(self):
        user = make_user()
        seed_default_curriculum(user)
        before = Topic.objects.filter(user=user).count()
        again = seed_default_curriculum(user)
        self.assertEqual(again, {"domains": 0, "technologies": 0, "topics": 0, "content": 0})
        self.assertEqual(Topic.objects.filter(user=user).count(), before)

    def test_seed_restores_deleted_topic_without_touching_progress(self):
        user = make_user()
        seed_default_curriculum(user)
        loops = Topic.objects.get(user=user, technology__name="Python", name="Loops")
        done = Topic.objects.get(user=user, technology__name="Python", name="Functions")
        set_topic_status(user, done, "completed")
        loops.delete()
        created = seed_default_curriculum(user)
        self.assertEqual(created["topics"], 1)
        done.refresh_from_db()
        self.assertEqual(done.status, "completed")

    def test_seed_for_one_user_does_not_touch_another(self):
        a, b = make_user("a"), make_user("b")
        seed_default_curriculum(a)
        self.assertEqual(Domain.objects.filter(user=b).count(), 0)

    def test_management_command(self):
        user = make_user("cmd")
        out = StringIO()
        call_command("seed_defaults", "--username", "cmd", stdout=out)
        self.assertTrue(Domain.objects.filter(user=user).exists())
        self.assertIn("cmd", out.getvalue())

    def test_registration_seeds_curriculum(self):
        self.client.post(reverse("accounts:register"), {
            "username": "newbie", "first_name": "New", "email": "n@example.com",
            "password1": "StrongPass#2026", "password2": "StrongPass#2026"})
        user = User.objects.get(username="newbie")
        self.assertEqual(Domain.objects.filter(user=user).count(), 4)


class ProgressTests(TestCase):
    def test_percent_helper(self):
        self.assertEqual(percent(0, 0), 0)
        self.assertEqual(percent(1, 3), 33)
        self.assertEqual(percent(3, 3), 100)

    def test_domain_and_overall_progress(self):
        user = make_user()
        d, t, topics = make_tree(user)
        make_tree(user, domain="Other", tech="SQL", topics=("Joins",))
        set_topic_status(user, topics[0], "completed")
        set_topic_status(user, topics[1], "in_progress")
        domain = [x for x in domains_with_progress(user) if x.pk == d.pk][0]
        self.assertEqual((domain.total_topics, domain.done_topics, domain.percent), (3, 1, 33))
        stats = overall_stats(user)
        self.assertEqual((stats["topics"], stats["completed"], stats["in_progress"], stats["not_started"]),
                         (4, 1, 1, 2))
        self.assertEqual(stats["percent"], 25)

    def test_progress_not_mixed_between_users(self):
        a, b = make_user("a"), make_user("b")
        _, _, ta = make_tree(a)
        make_tree(b)
        set_topic_status(a, ta[0], "completed")
        self.assertEqual(overall_stats(b)["completed"], 0)


class AccessTests(TestCase):
    """Logged-out visitors are sent to login; other users' objects give 404."""

    def setUp(self):
        self.alice, self.bob = make_user("alice"), make_user("bob")
        self.d, self.t, self.topics = make_tree(self.alice)
        self.topic = self.topics[0]

    def test_anonymous_redirected(self):
        urls = [reverse("learning:domain_list"), reverse("learning:domain_create"),
                reverse("learning:domain_detail", args=[self.d.pk]),
                reverse("learning:technology_detail", args=[self.t.pk]),
                reverse("learning:topic_update", args=[self.topic.pk])]
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 302, url)
        self.assertEqual(self.client.post(reverse("learning:topic_set_status", args=[self.topic.pk]),
                                          {"status": "completed"}).status_code, 302)
        self.assertFalse(LearningProgress.objects.exists())

    def test_other_user_gets_404_everywhere(self):
        self.client.force_login(self.bob)
        gets = [("learning:domain_detail", self.d.pk), ("learning:domain_update", self.d.pk),
                ("learning:domain_delete", self.d.pk), ("learning:technology_create", self.d.pk),
                ("learning:technology_detail", self.t.pk), ("learning:technology_update", self.t.pk),
                ("learning:technology_delete", self.t.pk), ("learning:topic_create", self.t.pk),
                ("learning:topic_update", self.topic.pk), ("learning:topic_delete", self.topic.pk)]
        for name, pk in gets:
            self.assertEqual(self.client.get(reverse(name, args=[pk])).status_code, 404, name)
        # writes are refused too
        self.client.post(reverse("learning:domain_delete", args=[self.d.pk]))
        self.client.post(reverse("learning:topic_set_status", args=[self.topic.pk]), {"status": "completed"})
        self.assertTrue(Domain.objects.filter(pk=self.d.pk).exists())
        self.assertFalse(LearningProgress.objects.exists())

    def test_other_users_data_not_listed(self):
        self.client.force_login(self.bob)
        response = self.client.get(reverse("learning:domain_list"))
        self.assertNotContains(response, "Tech")
        self.assertNotContains(response, "Python")

    def test_cannot_add_technology_to_other_users_domain(self):
        self.client.force_login(self.bob)
        response = self.client.post(reverse("learning:technology_create", args=[self.d.pk]), {"name": "Hack"})
        self.assertEqual(response.status_code, 404)
        self.assertFalse(Technology.objects.filter(name="Hack").exists())


class DomainCrudTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_login(self.user)

    def test_create_edit_delete_domain(self):
        r = self.client.post(reverse("learning:domain_create"), {"name": "Cybersecurity", "description": "x"})
        d = Domain.objects.get(user=self.user, name="Cybersecurity")
        self.assertRedirects(r, reverse("learning:domain_detail", args=[d.pk]))
        self.client.post(reverse("learning:domain_update", args=[d.pk]), {"name": "Security", "description": ""})
        d.refresh_from_db()
        self.assertEqual(d.name, "Security")
        self.assertEqual(self.client.get(reverse("learning:domain_delete", args=[d.pk])).status_code, 200)
        self.assertTrue(Domain.objects.filter(pk=d.pk).exists())  # GET never deletes
        self.client.post(reverse("learning:domain_delete", args=[d.pk]))
        self.assertFalse(Domain.objects.filter(pk=d.pk).exists())

    def test_duplicate_domain_rejected_case_insensitive(self):
        Domain.objects.create(user=self.user, name="Python")
        r = self.client.post(reverse("learning:domain_create"), {"name": "  python ", "description": ""})
        self.assertContains(r, "already have a domain")
        self.assertEqual(Domain.objects.filter(user=self.user).count(), 1)

    def test_blank_name_rejected(self):
        r = self.client.post(reverse("learning:domain_create"), {"name": "   ", "description": ""})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Domain.objects.count(), 0)

    def test_can_keep_own_name_when_editing(self):
        d = Domain.objects.create(user=self.user, name="Python")
        r = self.client.post(reverse("learning:domain_update", args=[d.pk]), {"name": "Python", "description": "new"})
        self.assertEqual(r.status_code, 302)

    def test_new_items_get_increasing_order(self):
        for n in ("A", "B", "C"):
            self.client.post(reverse("learning:domain_create"), {"name": n, "description": ""})
        self.assertEqual(list(Domain.objects.filter(user=self.user).values_list("name", flat=True)), ["A", "B", "C"])

    def test_default_domains_are_deletable(self):
        seed_default_curriculum(self.user)
        d = Domain.objects.get(user=self.user, name="Aptitude")
        self.client.post(reverse("learning:domain_delete", args=[d.pk]))
        self.assertFalse(Domain.objects.filter(user=self.user, name="Aptitude").exists())

    def test_load_defaults_requires_post(self):
        self.assertEqual(self.client.get(reverse("learning:load_defaults")).status_code, 405)
        self.client.post(reverse("learning:load_defaults"))
        self.assertEqual(Domain.objects.filter(user=self.user).count(), 4)


class TechnologyAndTopicCrudTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_login(self.user)
        self.d, self.t, self.topics = make_tree(self.user)

    def test_technology_crud(self):
        self.client.post(reverse("learning:technology_create", args=[self.d.pk]), {"name": "Rust", "description": ""})
        rust = Technology.objects.get(domain=self.d, name="Rust")
        self.assertEqual(rust.user, self.user)
        self.client.post(reverse("learning:technology_update", args=[rust.pk]), {"name": "Rust Lang", "description": ""})
        rust.refresh_from_db()
        self.assertEqual(rust.name, "Rust Lang")
        r = self.client.post(reverse("learning:technology_delete", args=[rust.pk]))
        self.assertRedirects(r, reverse("learning:domain_detail", args=[self.d.pk]))
        self.assertFalse(Technology.objects.filter(pk=rust.pk).exists())

    def test_same_technology_name_allowed_in_different_domains_but_not_same(self):
        r = self.client.post(reverse("learning:technology_create", args=[self.d.pk]), {"name": "PYTHON", "description": ""})
        self.assertContains(r, "already have a technology")
        other = Domain.objects.create(user=self.user, name="Other")
        r = self.client.post(reverse("learning:technology_create", args=[other.pk]), {"name": "Python", "description": ""})
        self.assertEqual(r.status_code, 302)

    def test_topic_crud(self):
        self.client.post(reverse("learning:topic_create", args=[self.t.pk]), {"name": "Decorators"})
        topic = Topic.objects.get(technology=self.t, name="Decorators")
        self.client.post(reverse("learning:topic_update", args=[topic.pk]), {"name": "Generators"})
        topic.refresh_from_db()
        self.assertEqual(topic.name, "Generators")
        self.client.post(reverse("learning:topic_delete", args=[topic.pk]))
        self.assertFalse(Topic.objects.filter(pk=topic.pk).exists())

    def test_duplicate_topic_rejected(self):
        r = self.client.post(reverse("learning:topic_create", args=[self.t.pk]), {"name": "loops"})
        self.assertContains(r, "already have a topic")

    def test_technology_page_lists_topics_with_status(self):
        set_topic_status(self.user, self.topics[0], "completed")
        r = self.client.get(reverse("learning:technology_detail", args=[self.t.pk]))
        self.assertContains(r, "Loops")
        self.assertContains(r, "Completed")
        self.assertContains(r, "1/3 topics completed (33%)")


class StatusViewTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_login(self.user)
        self.d, self.t, self.topics = make_tree(self.user)
        self.url = reverse("learning:topic_set_status", args=[self.topics[0].pk])

    def test_get_not_allowed(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_start_complete_undo(self):
        self.client.post(self.url, {"status": "in_progress"})
        self.assertEqual(Topic.objects.get(pk=self.topics[0].pk).status, "in_progress")
        self.client.post(self.url, {"status": "completed"})
        topic = Topic.objects.get(pk=self.topics[0].pk)
        self.assertEqual(topic.status, "completed")
        self.assertIsNotNone(topic.completed_at)
        self.client.post(self.url, {"status": "not_started"})
        self.assertEqual(Topic.objects.get(pk=self.topics[0].pk).status, "not_started")

    def test_invalid_status_rejected(self):
        self.assertEqual(self.client.post(self.url, {"status": "banana"}).status_code, 400)
        self.assertEqual(self.client.post(self.url, {}).status_code, 400)

    def test_redirects_to_safe_next_only(self):
        back = reverse("learning:domain_list")
        self.assertRedirects(self.client.post(self.url, {"status": "completed", "next": back}), back)
        r = self.client.post(self.url, {"status": "completed", "next": "https://evil.example.com/"})
        self.assertRedirects(r, reverse("learning:technology_detail", args=[self.t.pk]))


class DashboardTests(TestCase):
    def setUp(self):
        self.user = make_user("priya")
        self.client.force_login(self.user)

    def test_empty_state_offers_defaults(self):
        r = self.client.get(reverse("dashboard:index"))
        self.assertContains(r, "Load default curriculum")
        self.assertContains(r, "Good ")

    def test_dashboard_shows_real_numbers(self):
        _, _, topics = make_tree(self.user)
        set_topic_status(self.user, topics[0], "completed")
        set_topic_status(self.user, topics[1], "in_progress")
        r = self.client.get(reverse("dashboard:index"))
        self.assertEqual(r.context["stats"]["completed"], 1)
        self.assertEqual(r.context["stats"]["percent"], 33)
        self.assertContains(r, "Loops")  # recently completed
        self.assertContains(r, "Functions")  # continue learning
        self.assertEqual(r.context["chart_data"]["overall"]["values"], [1, 1, 1])
        self.assertContains(r, 'id="chart-data"')

    def test_dashboard_never_shows_other_users_progress(self):
        other = make_user("other")
        _, _, topics = make_tree(other, topics=("SecretTopic",))
        set_topic_status(other, topics[0], "completed")
        r = self.client.get(reverse("dashboard:index"))
        self.assertNotContains(r, "SecretTopic")
        self.assertEqual(r.context["stats"]["topics"], 0)

    def test_sidebar_present_on_logged_in_pages(self):
        for name in ("dashboard:index", "learning:domain_list", "accounts:profile"):
            self.assertContains(self.client.get(reverse(name)), 'class="sidebar"')
