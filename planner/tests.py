from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.utils import get_user_today
from learning.models import Domain, Technology, Topic
from learning.services import seed_default_curriculum, set_topic_status

from . import services
from .models import DailyGoal, DailyPlan

User = get_user_model()


def make_user(name="u1"):
    return User.objects.create_user(name, f"{name}@example.com", "StrongPass#2026")


def started(user, start=date(2026, 1, 1)):
    services.start_challenge(user, start)
    return {p.day_number: p for p in DailyPlan.objects.filter(user=user)}


def goal(user, plan, title="Goal", **kw):
    return DailyGoal.objects.create(user=user, plan=plan, title=title, **kw)


class ChallengeSetupTests(TestCase):
    def test_start_creates_40_consecutive_days(self):
        user = make_user()
        plans = started(user, date(2026, 3, 30))
        self.assertEqual(len(plans), 40)
        self.assertEqual(plans[1].date, date(2026, 3, 30))
        self.assertEqual(plans[2].date, date(2026, 3, 31))
        self.assertEqual(plans[40].date, date(2026, 3, 30) + timedelta(days=39))

    def test_cannot_start_twice(self):
        user = make_user()
        started(user)
        with self.assertRaises(ValueError):
            services.start_challenge(user, date(2026, 2, 1))
        self.assertEqual(DailyPlan.objects.filter(user=user).count(), 40)

    def test_shift_start_date_keeps_goals_on_their_day_numbers(self):
        user = make_user()
        plans = started(user)
        g = goal(user, plans[3])
        services.shift_start_date(user, date(2026, 6, 1))
        g.refresh_from_db()
        self.assertEqual(g.plan.day_number, 3)
        self.assertEqual(g.plan.date, date(2026, 6, 3))
        self.assertEqual(DailyPlan.objects.get(user=user, day_number=40).date, date(2026, 6, 1) + timedelta(days=39))

    def test_two_users_have_separate_challenges(self):
        a, b = make_user("a"), make_user("b")
        started(a)
        started(b, date(2026, 5, 5))
        self.assertEqual(DailyPlan.objects.count(), 80)


class DayStateTests(TestCase):
    def test_states(self):
        user = make_user()
        plans = started(user, date(2026, 1, 1))
        today = date(2026, 1, 5)
        st = lambda n, t, d: services.day_state(plans[n], today, t, d)
        self.assertEqual(st(5, 0, 0), "today")
        self.assertEqual(st(9, 2, 0), "upcoming")
        self.assertEqual(st(2, 0, 0), "empty")
        self.assertEqual(st(2, 3, 2), "incomplete")   # missed goal stays visible as incomplete
        self.assertEqual(st(2, 3, 3), "done")
        self.assertEqual(st(9, 1, 1), "done")          # finished early

    def test_calendar_weeks_pad_first_row_and_hold_40_days(self):
        user = make_user()
        started(user, date(2026, 1, 1))  # a Thursday
        weeks = services.calendar_weeks(user, date(2026, 1, 1))
        self.assertEqual(weeks[0][:3], [None, None, None])
        self.assertEqual(weeks[0][3].day_number, 1)
        self.assertEqual(sum(1 for w in weeks for c in w if c), 40)
        self.assertTrue(all(len(w) == 7 for w in weeks))

    def test_summary_numbers(self):
        user = make_user()
        plans = started(user, date(2026, 1, 1))
        g1 = goal(user, plans[1], estimated_minutes=60)
        goal(user, plans[1], estimated_minutes=30)
        goal(user, plans[2])
        services.set_goal_completed(g1, True)
        s = services.challenge_summary(user, date(2026, 1, 2))
        self.assertEqual((s["goals_total"], s["goals_done"], s["goals_pending"]), (3, 1, 2))
        self.assertEqual(s["goal_percent"], 33)
        self.assertEqual((s["phase"], s["current_day"]), ("running", 2))
        self.assertEqual(s["minutes_done"], 60)
        self.assertEqual(services.challenge_summary(user, date(2025, 12, 1))["phase"], "not_started")
        self.assertEqual(services.challenge_summary(user, date(2026, 3, 1))["phase"], "finished")

    def test_no_summary_without_challenge(self):
        self.assertIsNone(services.challenge_summary(make_user(), date(2026, 1, 1)))


class GoalCompletionTests(TestCase):
    def test_complete_twice_keeps_first_time_and_uncomplete_clears(self):
        user = make_user()
        g = goal(user, started(user)[1])
        services.set_goal_completed(g, True)
        first = g.completed_at
        services.set_goal_completed(g, True)
        self.assertEqual(g.completed_at, first)
        services.set_goal_completed(g, False)
        g.refresh_from_db()
        self.assertEqual((g.status, g.completed_at), ("pending", None))


class RescheduleTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.plans = started(self.user, date(2026, 1, 1))

    def test_unfinished_goals_are_listed_and_never_deleted(self):
        g = goal(self.user, self.plans[1])
        today = date(2026, 1, 10)
        self.assertEqual(list(services.overdue_goals(self.user, today)), [g])
        services.overdue_goals(self.user, today)  # reading changes nothing
        self.assertTrue(DailyGoal.objects.filter(pk=g.pk).exists())
        services.set_goal_completed(g, True)
        self.assertEqual(list(services.overdue_goals(self.user, today)), [])

    def test_reschedule_moves_goal_and_records_original_day(self):
        g = goal(self.user, self.plans[1])
        services.reschedule_goal(g, self.plans[5])
        g.refresh_from_db()
        self.assertEqual((g.plan.day_number, g.rescheduled_from.day_number, g.reschedule_count), (5, 1, 1))
        services.reschedule_goal(g, self.plans[8])
        g.refresh_from_db()
        self.assertEqual((g.plan.day_number, g.rescheduled_from.day_number, g.reschedule_count), (8, 1, 2))

    def test_cannot_reschedule_completed_goal_or_to_same_day(self):
        g = goal(self.user, self.plans[1])
        with self.assertRaises(ValueError):
            services.reschedule_goal(g, self.plans[1])
        services.set_goal_completed(g, True)
        with self.assertRaises(ValueError):
            services.reschedule_goal(g, self.plans[2])

    def test_cannot_reschedule_into_another_users_day(self):
        other = make_user("other")
        other_plans = started(other)
        g = goal(self.user, self.plans[1])
        with self.assertRaises(ValueError):
            services.reschedule_goal(g, other_plans[2])


class AutoScheduleTests(TestCase):
    def setUp(self):
        self.user = make_user()
        seed_default_curriculum(self.user)
        self.plans = started(self.user)
        self.python = Technology.objects.get(user=self.user, name="Python")

    def test_spreads_topics_over_days(self):
        created, left = services.auto_schedule(self.user, self.python, per_day=2, first_day=1, minutes=45)
        self.assertEqual((created, left), (16, 0))
        per_day = {n: p.goals.count() for n, p in self.plans.items() if p.goals.exists()}
        self.assertEqual(per_day, {d: 2 for d in range(1, 9)})
        first = DailyGoal.objects.filter(plan=self.plans[1]).first()
        self.assertEqual((first.title, first.estimated_minutes), ("Learn: Introduction to Python", 45))

    def test_skips_completed_and_already_planned_topics(self):
        topics = list(self.python.topics.all())
        set_topic_status(self.user, topics[0], "completed")
        services.auto_schedule(self.user, self.python, 1, 1, 30)
        self.assertEqual(DailyGoal.objects.filter(user=self.user).count(), 15)
        again = services.auto_schedule(self.user, self.python, 1, 1, 30)
        self.assertEqual(again, (0, 0))  # nothing duplicated

    def test_stops_at_day_40_and_reports_leftovers(self):
        created, left = services.auto_schedule(self.user, self.python, per_day=1, first_day=35, minutes=30)
        self.assertEqual((created, left), (6, 10))
        self.assertFalse(DailyGoal.objects.filter(plan__day_number__lt=35).exists())


class PlannerAccessTests(TestCase):
    def setUp(self):
        self.alice, self.bob = make_user("alice"), make_user("bob")
        self.plans = started(self.alice)
        self.goal = goal(self.alice, self.plans[3], "Alice secret goal")
        started(self.bob)

    def test_anonymous_redirected(self):
        for name, args in (("planner:overview", []), ("planner:day_detail", [1]), ("planner:goal_create", []),
                           ("planner:goal_update", [self.goal.pk]), ("planner:auto_schedule", [])):
            self.assertEqual(self.client.get(reverse(name, args=args)).status_code, 302, name)

    def test_other_user_gets_404_and_cannot_change_goal(self):
        self.client.force_login(self.bob)
        for name in ("planner:goal_update", "planner:goal_delete", "planner:goal_reschedule"):
            self.assertEqual(self.client.get(reverse(name, args=[self.goal.pk])).status_code, 404, name)
        self.client.post(reverse("planner:goal_toggle", args=[self.goal.pk]))
        self.client.post(reverse("planner:goal_delete", args=[self.goal.pk]))
        self.goal.refresh_from_db()
        self.assertEqual(self.goal.status, "pending")

    def test_day_page_shows_only_own_goals(self):
        self.client.force_login(self.bob)
        r = self.client.get(reverse("planner:day_detail", args=[3]))
        self.assertNotContains(r, "Alice secret goal")
        self.assertContains(r, "No goals on this day")

    def test_cannot_attach_another_users_topic_or_day(self):
        seed_default_curriculum(self.alice)
        alice_topic = Topic.objects.filter(user=self.alice).first()
        self.client.force_login(self.bob)
        r = self.client.post(reverse("planner:goal_create"), {
            "plan": self.plans[1].pk, "title": "x", "topic": alice_topic.pk, "estimated_minutes": 30})
        self.assertEqual(r.status_code, 200)  # form error, nothing created
        self.assertFalse(DailyGoal.objects.filter(user=self.bob).exists())

    def test_pages_redirect_to_start_when_no_challenge(self):
        carol = make_user("carol")
        self.client.force_login(carol)
        self.assertRedirects(self.client.get(reverse("planner:day_detail", args=[1])), reverse("planner:overview"))
        self.assertContains(self.client.get(reverse("planner:overview")), "Start your 40-day challenge")


class PlannerViewTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_login(self.user)
        self.today = get_user_today(self.user)

    def test_start_via_form_then_today_redirect(self):
        r = self.client.post(reverse("planner:start"), {"start_date": self.today.isoformat()})
        self.assertRedirects(r, reverse("planner:overview"))
        self.assertEqual(DailyPlan.objects.filter(user=self.user).count(), 40)
        self.assertRedirects(self.client.get(reverse("planner:today")), reverse("planner:day_detail", args=[1]))

    def test_goal_crud_and_toggle(self):
        plans = started(self.user, self.today)
        r = self.client.post(reverse("planner:goal_create"), {
            "plan": plans[1].pk, "title": "Read loops", "topic": "", "estimated_minutes": 40})
        self.assertRedirects(r, reverse("planner:day_detail", args=[1]))
        g = DailyGoal.objects.get(user=self.user)
        self.assertEqual(g.estimated_minutes, 40)
        self.client.post(reverse("planner:goal_update", args=[g.pk]), {"title": "Read loops well", "estimated_minutes": 50})
        g.refresh_from_db()
        self.assertEqual((g.title, g.estimated_minutes), ("Read loops well", 50))
        self.client.post(reverse("planner:goal_toggle", args=[g.pk]))
        g.refresh_from_db()
        self.assertTrue(g.is_completed)
        self.assertContains(self.client.get(reverse("planner:day_detail", args=[1])), "1/1 completed (100%)")
        self.assertEqual(self.client.get(reverse("planner:goal_delete", args=[g.pk])).status_code, 200)
        self.assertTrue(DailyGoal.objects.filter(pk=g.pk).exists())  # GET never deletes
        self.client.post(reverse("planner:goal_delete", args=[g.pk]))
        self.assertFalse(DailyGoal.objects.filter(pk=g.pk).exists())

    def test_goal_title_defaults_to_topic_and_blank_is_rejected(self):
        plans = started(self.user, self.today)
        seed_default_curriculum(self.user)
        topic = Topic.objects.get(user=self.user, technology__name="Python", name="Loops")
        self.client.post(reverse("planner:goal_create"), {
            "plan": plans[1].pk, "title": "", "topic": topic.pk, "estimated_minutes": 30})
        self.assertEqual(DailyGoal.objects.get().title, "Study: Loops")
        r = self.client.post(reverse("planner:goal_create"), {
            "plan": plans[1].pk, "title": "", "topic": "", "estimated_minutes": 30})
        self.assertContains(r, "Enter a title or choose a topic")

    def test_invalid_minutes_rejected(self):
        plans = started(self.user, self.today)
        for bad in ("0", "9999", "abc"):
            r = self.client.post(reverse("planner:goal_create"), {
                "plan": plans[1].pk, "title": "x", "estimated_minutes": bad})
            self.assertEqual(r.status_code, 200, bad)
        self.assertFalse(DailyGoal.objects.exists())

    def test_missed_day_shows_incomplete_and_can_be_rescheduled_to_today(self):
        plans = started(self.user, self.today - timedelta(days=3))  # today is Day 4
        missed = goal(self.user, plans[1], "Missed goal")
        r = self.client.get(reverse("planner:overview"))
        self.assertContains(r, "Unfinished goals (1)")
        self.assertContains(r, "Missed goal")
        r = self.client.post(reverse("planner:goal_reschedule", args=[missed.pk]), {
            "plan": plans[4].pk, "next": reverse("planner:overview")})
        self.assertRedirects(r, reverse("planner:overview"))
        missed.refresh_from_db()
        self.assertEqual((missed.plan.day_number, missed.rescheduled_from.day_number), (4, 1))
        self.assertNotContains(self.client.get(reverse("planner:overview")), "Unfinished goals")
        self.assertContains(self.client.get(reverse("planner:day_detail", args=[4])), "moved from Day 1")

    def test_reschedule_form_excludes_current_day(self):
        plans = started(self.user, self.today)
        g = goal(self.user, plans[2])
        r = self.client.get(reverse("planner:goal_reschedule", args=[g.pk]))
        self.assertContains(r, "Day 1 ·")
        self.assertNotContains(r, "Day 2 ·")

    def test_reschedule_to_same_day_rejected_by_form(self):
        plans = started(self.user, self.today)
        g = goal(self.user, plans[2])
        self.client.post(reverse("planner:goal_reschedule", args=[g.pk]), {"plan": plans[2].pk})
        g.refresh_from_db()
        self.assertEqual(g.reschedule_count, 0)

    def test_next_redirect_is_safe(self):
        plans = started(self.user, self.today)
        g = goal(self.user, plans[1])
        r = self.client.post(reverse("planner:goal_toggle", args=[g.pk]), {"next": "https://evil.example.com/"})
        self.assertRedirects(r, reverse("planner:day_detail", args=[1]))

    def test_day_page_bounds_and_title(self):
        started(self.user, self.today)
        self.assertEqual(self.client.get(reverse("planner:day_detail", args=[41])).status_code, 404)
        self.assertEqual(self.client.get(reverse("planner:day_detail", args=[0])).status_code, 404)
        self.client.post(reverse("planner:day_title", args=[2]), {"title": "Python basics day"})
        self.assertContains(self.client.get(reverse("planner:day_detail", args=[2])), "Python basics day")

    def test_auto_schedule_view(self):
        started(self.user, self.today)
        seed_default_curriculum(self.user)
        tech = Technology.objects.get(user=self.user, name="Python")
        r = self.client.post(reverse("planner:auto_schedule"), {
            "technology": tech.pk, "topics_per_day": 2, "first_day": 1, "minutes_per_topic": 30})
        self.assertRedirects(r, reverse("planner:overview"))
        self.assertEqual(DailyGoal.objects.filter(user=self.user).count(), 16)

    def test_change_start_date_view(self):
        started(self.user, self.today)
        new = self.today + timedelta(days=10)
        self.client.post(reverse("planner:change_start_date"), {"start_date": new.isoformat()})
        self.assertEqual(DailyPlan.objects.get(user=self.user, day_number=1).date, new)

    def test_dashboard_shows_todays_goals_and_challenge(self):
        plans = started(self.user, self.today)
        g = goal(self.user, plans[1], "Dashboard goal")
        r = self.client.get(reverse("dashboard:index"))
        self.assertContains(r, "Dashboard goal")
        self.assertContains(r, "Day 1")
        self.assertEqual(r.context["today_percent"], 0)
        services.set_goal_completed(g, True)
        self.assertEqual(self.client.get(reverse("dashboard:index")).context["today_percent"], 100)

    def test_dashboard_warns_about_unfinished_goals(self):
        plans = started(self.user, self.today - timedelta(days=2))
        goal(self.user, plans[1])
        r = self.client.get(reverse("dashboard:index"))
        self.assertEqual(r.context["overdue_count"], 1)
        self.assertContains(r, "unfinished goal")

    def test_dashboard_without_challenge_offers_start(self):
        self.assertContains(self.client.get(reverse("dashboard:index")), "Start the challenge")
