from django.contrib.auth import get_user_model
from django.template import Context, Template
from django.test import TestCase
from django.urls import reverse

from .content_data import CONTENT
from .models import LearningContent, Topic, UserNote
from .services import seed_default_curriculum, seed_topic_content

User = get_user_model()


def make_user(name="u1"):
    return User.objects.create_user(name, f"{name}@example.com", "StrongPass#2026")


class ContentSeedTests(TestCase):
    def test_all_16_python_topics_have_all_10_sections(self):
        self.assertEqual(len(CONTENT["Python"]), 16)
        for name, lesson in CONTENT["Python"].items():
            self.assertEqual(len(lesson), 10, name)
            self.assertTrue(all(v.strip() for v in lesson.values()), name)

    def test_seed_creates_content_for_python_topics(self):
        user = make_user()
        created = seed_default_curriculum(user)
        self.assertEqual(created["content"], 16)
        self.assertEqual(LearningContent.objects.filter(user=user).count(), 16)

    def test_seed_never_overwrites_edited_content(self):
        user = make_user()
        seed_default_curriculum(user)
        c = LearningContent.objects.get(user=user, topic__name="Loops")
        c.introduction = "My own intro"
        c.save()
        self.assertEqual(seed_topic_content(user), 0)
        c.refresh_from_db()
        self.assertEqual(c.introduction, "My own intro")

    def test_backfill_for_users_created_before_phase_4(self):
        user = make_user()
        seed_default_curriculum(user)
        LearningContent.objects.filter(user=user).delete()  # simulate a Phase 3 account
        self.assertEqual(seed_default_curriculum(user)["content"], 16)


class TopicPageTests(TestCase):
    def setUp(self):
        self.user = make_user()
        seed_default_curriculum(self.user)
        self.client.force_login(self.user)
        self.loops = Topic.objects.get(user=self.user, technology__name="Python", name="Loops")

    def test_lesson_page_shows_ten_sections(self):
        r = self.client.get(reverse("learning:topic_detail", args=[self.loops.pk]))
        self.assertEqual(r.status_code, 200)
        for label in ("1. Topic introduction", "4. Syntax", "7. Common mistakes", "10. Quick revision notes"):
            self.assertContains(r, label)
        self.assertContains(r, "range(1, 6)")

    def test_prev_next_navigation(self):
        r = self.client.get(reverse("learning:topic_detail", args=[self.loops.pk]))
        self.assertContains(r, "Conditional Statements")  # previous
        self.assertContains(r, "Functions")               # next

    def test_topic_without_lesson_offers_to_write_one(self):
        sql = Topic.objects.get(user=self.user, technology__name="SQL", name="Joins")
        r = self.client.get(reverse("learning:topic_detail", args=[sql.pk]))
        self.assertContains(r, "No lesson written")
        self.assertContains(r, "W3Schools SQL")

    def test_write_and_edit_own_lesson(self):
        sql = Topic.objects.get(user=self.user, technology__name="SQL", name="Joins")
        url = reverse("learning:content_edit", args=[sql.pk])
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertFalse(LearningContent.objects.filter(topic=sql).exists())  # viewing creates nothing
        data = {f: "" for f, _, _ in LearningContent.SECTIONS}
        data.update(introduction="Joins combine rows.", syntax="SELECT * FROM a JOIN b;")
        self.assertRedirects(self.client.post(url, data), reverse("learning:topic_detail", args=[sql.pk]))
        self.assertContains(self.client.get(reverse("learning:topic_detail", args=[sql.pk])), "Joins combine rows.")

    def test_lesson_text_is_html_escaped(self):
        c = LearningContent.objects.get(topic=self.loops)
        c.introduction = "<script>alert('x')</script>\n- <b>bold</b> item"
        c.save()
        r = self.client.get(reverse("learning:topic_detail", args=[self.loops.pk]))
        self.assertNotContains(r, "<script>alert")
        self.assertContains(r, "&lt;script&gt;")
        self.assertContains(r, "<li>&lt;b&gt;bold&lt;/b&gt; item</li>")

    def test_rich_text_filter_bullets_and_paragraphs(self):
        out = Template("{% load content_extras %}{{ t|rich_text }}").render(
            Context({"t": "Intro line\n\n- one\n- two\nafter"}))
        self.assertEqual(out, "<p>Intro line</p><ul><li>one</li><li>two</li></ul><p>after</p>")


class NoteTests(TestCase):
    def setUp(self):
        self.user = make_user()
        seed_default_curriculum(self.user)
        self.client.force_login(self.user)
        self.topic = Topic.objects.get(user=self.user, technology__name="Python", name="Loops")

    def test_note_crud(self):
        self.client.post(reverse("learning:note_create", args=[self.topic.pk]), {"body": "Remember range stops early"})
        note = UserNote.objects.get(user=self.user)
        self.assertEqual(note.topic, self.topic)
        self.assertContains(self.client.get(reverse("learning:topic_detail", args=[self.topic.pk])), "range stops early")
        self.client.post(reverse("learning:note_update", args=[note.pk]), {"body": "Edited"})
        note.refresh_from_db()
        self.assertEqual(note.body, "Edited")
        self.client.post(reverse("learning:note_delete", args=[note.pk]))
        self.assertEqual(UserNote.objects.count(), 0)

    def test_empty_note_rejected(self):
        self.client.post(reverse("learning:note_create", args=[self.topic.pk]), {"body": "   "})
        self.assertEqual(UserNote.objects.count(), 0)

    def test_note_create_requires_post(self):
        self.assertEqual(self.client.get(reverse("learning:note_create", args=[self.topic.pk])).status_code, 405)

    def test_other_user_cannot_see_or_touch_notes_or_topics(self):
        note = UserNote.objects.create(user=self.user, topic=self.topic, body="private")
        self.client.force_login(make_user("mallory"))
        for name, pk in (("learning:topic_detail", self.topic.pk), ("learning:content_edit", self.topic.pk),
                         ("learning:note_update", note.pk), ("learning:note_delete", note.pk)):
            self.assertEqual(self.client.get(reverse(name, args=[pk])).status_code, 404, name)
        self.assertEqual(self.client.post(reverse("learning:note_create", args=[self.topic.pk]),
                                          {"body": "x"}).status_code, 404)
        self.client.post(reverse("learning:note_delete", args=[note.pk]))
        self.assertTrue(UserNote.objects.filter(pk=note.pk).exists())

    def test_anonymous_redirected(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("learning:topic_detail", args=[self.topic.pk])).status_code, 302)
