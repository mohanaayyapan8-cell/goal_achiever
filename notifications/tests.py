from datetime import date, datetime, time, timedelta, timezone as dt_tz
from io import StringIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.utils import get_user_today
from planner import services as planner
from planner.models import DailyGoal, DailyPlan
from streaks import services as streaks

from . import services
from .models import Notification

User = get_user_model()
UTC = dt_tz.utc


def make_user(name="u1", tz=None, email=True):
    user = User.objects.create_user(name, f"{name}@example.com" if email else "", "StrongPass#2026", first_name=name.title())
    if tz:
        user.profile.timezone = tz
        user.profile.save()
    return user


def with_reminder(user, at=time(0, 0), email=False, browser=False):
    p = user.profile
    p.daily_reminder_time, p.email_reminders, p.browser_reminders = at, email, browser
    p.save()


def challenge_today(user, goals=1):
    planner.start_challenge(user, get_user_today(user))
    plan = DailyPlan.objects.get(user=user, day_number=1)
    for i in range(goals):
        DailyGoal.objects.create(user=user, plan=plan, title=f"goal {i}")
    return plan


class ServiceTests(TestCase):
    def setUp(self):
        self.user = make_user()

    def test_notify_creates_and_counts(self):
        n, created = services.notify(self.user, "info", "Hello", "World", "/x/")
        self.assertTrue(created)
        self.assertEqual((n.kind, n.title, n.link, n.is_read), ("info", "Hello", "/x/", False))
        self.assertEqual(services.unread_count(self.user), 1)

    def test_same_key_never_creates_a_second_notification(self):
        a, c1 = services.notify(self.user, "info", "A", key="k1")
        b, c2 = services.notify(self.user, "info", "B", key="k1")
        self.assertEqual((c1, c2, a.pk, b.pk), (True, False, a.pk, a.pk))
        self.assertEqual(Notification.objects.count(), 1)

    def test_database_enforces_key_uniqueness_but_allows_many_without_key(self):
        services.notify(self.user, "info", "A", key="k1")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Notification.objects.create(user=self.user, title="dup", dedupe_key="k1")
        services.notify(self.user, "info", "no key 1")
        services.notify(self.user, "info", "no key 2")
        self.assertEqual(Notification.objects.count(), 3)

    def test_same_key_for_different_users_is_fine(self):
        services.notify(self.user, "info", "A", key="k1")
        services.notify(make_user("other"), "info", "A", key="k1")
        self.assertEqual(Notification.objects.count(), 2)

    def test_mark_read_one_or_all_and_only_for_that_user(self):
        a, _ = services.notify(self.user, "info", "A")
        b, _ = services.notify(self.user, "info", "B")
        theirs, _ = services.notify(make_user("other"), "info", "C")
        self.assertEqual(services.mark_read(self.user, a.pk), 1)
        self.assertEqual(services.unread_count(self.user), 1)
        self.assertEqual(services.mark_read(self.user), 1)
        theirs.refresh_from_db()
        self.assertFalse(theirs.is_read)

    def test_mark_read_twice_changes_nothing(self):
        a, _ = services.notify(self.user, "info", "A")
        services.mark_read(self.user, a.pk)
        stamp = Notification.objects.get(pk=a.pk).read_at
        self.assertEqual(services.mark_read(self.user, a.pk), 0)
        self.assertEqual(Notification.objects.get(pk=a.pk).read_at, stamp)


class ReminderLogicTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.plan = challenge_today(self.user)
        with_reminder(self.user)

    def test_reminder_created_once_per_day_when_time_has_passed(self):
        n = streaks.ensure_reminder(self.user)
        self.assertEqual((n.kind, n.dedupe_key), ("reminder", f"reminder:{get_user_today(self.user)}"))
        self.assertIn("still to do: 1 goal, the written assessment and the speaking assessment", n.message)
        self.assertIn("written assessment", n.message)
        self.assertIn("speaking assessment", n.message)
        streaks.ensure_reminder(self.user)
        self.assertEqual(Notification.objects.filter(user=self.user, kind="reminder").count(), 1)

    def test_no_reminder_before_the_reminder_time_in_the_users_time_zone(self):
        tokyo = make_user("tokyo", tz="Asia/Tokyo")
        start = datetime(2026, 3, 11, tzinfo=UTC).date()
        planner.start_challenge(tokyo, start)
        DailyGoal.objects.create(user=tokyo, plan=DailyPlan.objects.get(user=tokyo, day_number=1), title="g")
        with_reminder(tokyo, at=time(8, 0))
        early = datetime(2026, 3, 10, 22, 0, tzinfo=UTC)        # 07:00 on 11 March in Tokyo
        late = datetime(2026, 3, 10, 23, 30, tzinfo=UTC)         # 08:30 on 11 March in Tokyo
        self.assertIsNone(streaks.ensure_reminder(tokyo, early))
        n = streaks.ensure_reminder(tokyo, late)
        self.assertIsNotNone(n)
        self.assertEqual(n.dedupe_key, "reminder:2026-03-11")

    def test_no_reminder_without_a_time_or_a_plan_or_when_the_day_is_complete(self):
        with_reminder(self.user, at=None)
        self.assertIsNone(streaks.ensure_reminder(self.user))
        with_reminder(self.user)
        self.assertIsNone(streaks.ensure_reminder(make_user("noplan")))
        planner.set_goal_completed(self.plan.goals.first(), True)
        with mock.patch("streaks.services.day_progress", return_value={"complete": True}):
            self.assertIsNone(streaks.ensure_reminder(self.user))

    def test_reminder_without_any_goal_asks_to_add_goals(self):
        DailyGoal.objects.all().delete()
        n = streaks.ensure_reminder(self.user)
        self.assertIn("still to do: add today's goals, the written assessment and the speaking assessment", n.message)

    def test_reminder_links_to_todays_tasks(self):
        self.assertEqual(streaks.ensure_reminder(self.user).link, reverse("planner:today"))


class SendRemindersCommandTests(TestCase):
    def setUp(self):
        self.a = make_user("alice")
        self.b = make_user("bob")
        for u in (self.a, self.b):
            challenge_today(u)
            with_reminder(u, email=True)

    def run_command(self):
        out = StringIO()
        call_command("send_reminders", stdout=out)
        return out.getvalue()

    def test_emails_each_user_once_with_a_link(self):
        out = self.run_command()
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual({m.to[0] for m in mail.outbox}, {"alice@example.com", "bob@example.com"})
        self.assertIn("2 reminder e-mail(s) sent", out)
        body = mail.outbox[0].body
        self.assertIn("Day 1", body)
        self.assertIn("http://127.0.0.1:8000/planner/today/", body)
        self.assertIn("Hi ", body)

    def test_running_again_does_not_send_duplicates(self):
        self.run_command()
        self.run_command()
        self.assertEqual(len(mail.outbox), 2)
        self.assertTrue(all(n.emailed_at for n in Notification.objects.filter(kind="reminder")))

    def test_email_is_off_by_default_per_user(self):
        with_reminder(self.b, email=False)
        self.run_command()
        self.assertEqual([m.to[0] for m in mail.outbox], ["alice@example.com"])
        self.assertTrue(Notification.objects.filter(user=self.b, kind="reminder").exists())     # in-app reminder still created

    def test_completed_day_gets_no_reminder_email(self):
        with mock.patch("streaks.services.day_progress", return_value={"complete": True, "day_number": 1}):
            self.run_command()
        self.assertEqual(len(mail.outbox), 0)

    def test_users_without_an_email_address_are_skipped_safely(self):
        quiet = make_user("noemail", email=False)
        challenge_today(quiet)
        with_reminder(quiet, email=True)
        self.run_command()
        self.assertEqual(len(mail.outbox), 2)

    def test_one_failing_email_does_not_stop_the_others(self):
        calls = []

        def flaky(subject, body, sender, recipients):
            calls.append(recipients[0])
            if len(calls) == 1:
                raise OSError("smtp down")
            return 1

        err = StringIO()
        with mock.patch("notifications.services.send_mail", side_effect=flaky):
            call_command("send_reminders", stdout=StringIO(), stderr=err)
        self.assertEqual(len(calls), 2)
        self.assertIn("Could not e-mail", err.getvalue())
        failed = Notification.objects.filter(kind="reminder", emailed_at__isnull=True)
        self.assertEqual(failed.count(), 1)         # the failed one is retried by the next run

    @override_settings(SITE_URL="https://goals.example.org")
    def test_links_use_the_configured_site_url(self):
        self.run_command()
        self.assertIn("https://goals.example.org/planner/today/", mail.outbox[0].body)

    def test_command_also_settles_missed_days_and_warns(self):
        user = make_user("sleepy")
        planner.start_challenge(user, get_user_today(user) - timedelta(days=3))
        DailyPlan.objects.filter(user=user).update(created_at=datetime.now(UTC) - timedelta(days=10))
        self.run_command()
        self.assertTrue(Notification.objects.filter(user=user, kind="warning").exists())


class ViewTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_login(self.user)

    def test_list_shows_notifications_newest_first_and_filters_unread(self):
        a, _ = services.notify(self.user, "info", "Older one")
        b, _ = services.notify(self.user, "success", "Newer one")
        services.mark_read(self.user, a.pk)
        r = self.client.get(reverse("notifications:list"))
        self.assertContains(r, "Older one")
        self.assertContains(r, "Newer one")
        unread = self.client.get(reverse("notifications:list") + "?show=unread")
        self.assertContains(unread, "Newer one")
        self.assertNotContains(unread, "Older one")

    def test_empty_state(self):
        self.assertContains(self.client.get(reverse("notifications:list")), "No notifications yet")

    def test_mark_read_mark_all_and_delete_need_post(self):
        n, _ = services.notify(self.user, "info", "A")
        for name, args in (("notifications:read", [n.pk]), ("notifications:read_all", []), ("notifications:delete", [n.pk])):
            self.assertEqual(self.client.get(reverse(name, args=args)).status_code, 405, name)
        self.client.post(reverse("notifications:read", args=[n.pk]))
        n.refresh_from_db(); self.assertTrue(n.is_read)
        m, _ = services.notify(self.user, "info", "B")
        self.client.post(reverse("notifications:read_all"))
        m.refresh_from_db(); self.assertTrue(m.is_read)
        self.client.post(reverse("notifications:delete", args=[n.pk]))
        self.assertFalse(Notification.objects.filter(pk=n.pk).exists())

    def test_other_users_notifications_are_invisible_and_untouchable(self):
        theirs, _ = services.notify(make_user("bob"), "info", "Bobs secret")
        self.assertNotContains(self.client.get(reverse("notifications:list")), "Bobs secret")
        self.assertEqual(self.client.post(reverse("notifications:read", args=[theirs.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("notifications:delete", args=[theirs.pk])).status_code, 404)
        self.client.post(reverse("notifications:read_all"))
        theirs.refresh_from_db()
        self.assertFalse(theirs.is_read)
        self.assertTrue(Notification.objects.filter(pk=theirs.pk).exists())

    def test_anonymous_users_are_sent_to_login(self):
        self.client.logout()
        for name in ("notifications:list", "notifications:settings", "notifications:poll"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 302, name)

    def test_notification_text_is_escaped(self):
        services.notify(self.user, "info", "<script>alert(1)</script>", "<img src=x onerror=alert(2)>")
        page = self.client.get(reverse("notifications:list"))
        self.assertNotContains(page, "<script>alert(1)</script>")
        self.assertNotContains(page, "<img src=x")

    def test_bell_shows_unread_count_on_every_page(self):
        services.notify(self.user, "info", "A"); services.notify(self.user, "info", "B")
        page = self.client.get(reverse("learning:domain_list"))
        self.assertEqual(page.context["unread_notifications"], 2)
        self.assertContains(page, 'id="bell-count"')
        services.mark_read(self.user)
        self.assertEqual(self.client.get(reverse("learning:domain_list")).context["unread_notifications"], 0)

    def test_page_carries_poll_url_and_browser_flag_only_for_logged_in_users(self):
        page = self.client.get(reverse("dashboard:index"))
        self.assertContains(page, f'data-poll-url="{reverse("notifications:poll")}"')
        self.assertContains(page, 'data-browser-notify="0"')
        with_reminder(self.user, browser=True)
        self.assertContains(self.client.get(reverse("dashboard:index")), 'data-browser-notify="1"')
        self.client.logout()
        self.assertNotContains(self.client.get(reverse("dashboard:home")), "data-poll-url")


class PollTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_login(self.user)

    def test_poll_returns_unread_items_as_json(self):
        services.notify(self.user, "badge", "New badge: Test", "msg", "/streaks/")
        data = self.client.get(reverse("notifications:poll")).json()
        self.assertEqual(data["unread"], 1)
        self.assertEqual(set(data["items"][0]), {"id", "kind", "title", "message", "link"})

    def test_poll_creates_a_due_reminder_while_the_page_is_open(self):
        challenge_today(self.user)
        with_reminder(self.user)
        data = self.client.get(reverse("notifications:poll")).json()
        self.assertTrue(any(i["kind"] == "reminder" for i in data["items"]))
        again = self.client.get(reverse("notifications:poll")).json()
        self.assertEqual(sum(1 for i in again["items"] if i["kind"] == "reminder"), 1)

    def test_poll_only_lists_own_unread_items_and_is_get_only(self):
        services.notify(make_user("bob"), "info", "Bobs")
        read, _ = services.notify(self.user, "info", "Already read")
        services.mark_read(self.user, read.pk)
        data = self.client.get(reverse("notifications:poll")).json()
        self.assertEqual((data["unread"], data["items"]), (0, []))
        self.assertEqual(self.client.post(reverse("notifications:poll")).status_code, 405)

    def test_poll_returns_at_most_ten_items(self):
        for i in range(15):
            services.notify(self.user, "info", f"n{i}")
        data = self.client.get(reverse("notifications:poll")).json()
        self.assertEqual((data["unread"], len(data["items"])), (15, 10))


class SettingsTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_login(self.user)
        self.url = reverse("notifications:settings")

    def test_page_explains_the_browser_notification_limits_honestly(self):
        page = self.client.get(self.url)
        self.assertContains(page, "only <u>while Goal Achiever is open in a browser tab</u>")
        self.assertContains(page, "service worker")
        self.assertContains(page, "send_reminders")
        self.assertContains(page, "perm-btn")

    def test_save_time_and_switches(self):
        r = self.client.post(self.url, {"daily_reminder_time": "07:30", "email_reminders": "on", "browser_reminders": "on"})
        self.assertRedirects(r, self.url)
        p = User.objects.get(pk=self.user.pk).profile
        self.assertEqual((p.daily_reminder_time, p.email_reminders, p.browser_reminders), (time(7, 30), True, True))

    def test_email_or_browser_reminders_need_a_time(self):
        for field in ("email_reminders", "browser_reminders"):
            r = self.client.post(self.url, {field: "on", "daily_reminder_time": ""})
            self.assertContains(r, "Choose a reminder time")
        p = User.objects.get(pk=self.user.pk).profile
        self.assertEqual((p.email_reminders, p.browser_reminders), (False, False))

    def test_everything_can_be_turned_off(self):
        with_reminder(self.user, at=time(9, 0), email=True, browser=True)
        self.client.post(self.url, {"daily_reminder_time": ""})
        p = User.objects.get(pk=self.user.pk).profile
        self.assertEqual((p.daily_reminder_time, p.email_reminders, p.browser_reminders), (None, False, False))

    def test_invalid_time_rejected(self):
        self.assertEqual(self.client.post(self.url, {"daily_reminder_time": "25:99"}).status_code, 200)

    def test_settings_only_change_the_logged_in_users_profile(self):
        other = make_user("bob")
        self.client.post(self.url, {"daily_reminder_time": "06:00", "email_reminders": "on"})
        self.assertIsNone(User.objects.get(pk=other.pk).profile.daily_reminder_time)
