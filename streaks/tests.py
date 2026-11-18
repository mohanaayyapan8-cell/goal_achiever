from datetime import date, datetime, timedelta, timezone as dt_tz
from unittest import mock

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from accounts.utils import get_user_today
from aptitude import services as apt_services
from assessments import services as assess_services
from assessments.models import SpeakingAssessment, WrittenAssessment
from coding import services as coding_services
from coding.models import CodingProblem
from learning.models import Domain, Technology, Topic
from learning.services import set_topic_status
from notifications.models import Notification
from planner import services as planner
from planner.models import DailyGoal, DailyPlan

from . import services
from .badges import BADGES
from .models import Achievement, StreakRecord

User = get_user_model()
UTC = dt_tz.utc
D = lambda day: date(2026, 2, day)   # noqa: E731  dates of the fixed February used by most tests


def make_user(name="u1", tz=None):
    user = User.objects.create_user(name, f"{name}@example.com", "StrongPass#2026", first_name=name.title())
    if tz:
        user.profile.timezone = tz
        user.profile.save()
    return user


def start_challenge(user, start, created_before=True):
    """Plans for 40 days from `start`. By default the challenge counts from its first day."""
    planner.start_challenge(user, start)
    if created_before:
        DailyPlan.objects.filter(user=user).update(created_at=datetime(start.year, start.month, start.day, tzinfo=UTC) - timedelta(days=1))
    return {p.day_number: p for p in DailyPlan.objects.filter(user=user)}


def make_topic(user, tech="Python", name="Loops"):
    d, _ = Domain.objects.get_or_create(user=user, name="Tech")
    t, _ = Technology.objects.get_or_create(user=user, domain=d, name=tech)
    return Topic.objects.create(user=user, technology=t, name=name)


def submitted_assessments(user, moment, written=True, speaking=True):
    """Insert submitted assessments at an exact moment (for time-zone and date tests)."""
    if written:
        WrittenAssessment.objects.create(user=user, topic_name="x", status="submitted", submitted_at=moment, score=50)
    if speaking:
        SpeakingAssessment.objects.create(user=user, topic_name="x", question_text="q", status="submitted", submitted_at=moment)


class FixedToday(TestCase):
    """Base class: pretends today is 10 February 2026 so streak logic is deterministic."""

    TODAY = date(2026, 2, 10)

    def setUp(self):
        patcher = mock.patch("streaks.services.get_user_today", return_value=self.TODAY)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.user = make_user()
        self.plans = start_challenge(self.user, D(1))

    def C(self, day):
        return services.record_completed(self.user, D(day))[0]

    def M(self, day):
        return services.record_missed(self.user, D(day))[0]


class StreakRuleTests(FixedToday):
    def test_each_completed_day_adds_one(self):
        self.assertEqual([self.C(d).streak_after for d in (1, 2, 3)], [1, 2, 3])

    def test_one_missed_day_interrupts_but_does_not_lose_the_streak(self):
        self.C(1); self.C(2)
        m = self.M(3)
        self.assertEqual((m.streak_after, m.missed_run_after), (2, 1))
        self.assertEqual(self.C(4).streak_after, 3)          # the next completed day continues it

    def test_two_missed_days_in_a_row_reset_the_streak_to_zero(self):
        self.C(1); self.C(2); self.C(3)
        self.assertEqual(self.M(4).streak_after, 3)
        second = self.M(5)
        self.assertEqual((second.streak_after, second.missed_run_after), (0, 2))

    def test_more_missed_days_stay_at_zero_and_a_new_streak_starts_at_one(self):
        self.C(1); self.C(2)
        self.assertEqual([self.M(d).streak_after for d in (3, 4, 5)], [2, 0, 0])      # 1st miss keeps it, 2nd resets, then stays 0
        self.assertEqual(self.C(6).streak_after, 1)
        self.assertEqual(self.C(7).streak_after, 2)

    def test_a_completed_day_between_misses_stops_the_reset(self):
        self.C(1); self.M(2); self.C(3); self.M(4)
        self.assertEqual(self.C(5).streak_after, 3)         # never two misses in a row, so never reset

    def test_miss_before_any_completed_day_gives_zero(self):
        self.assertEqual(self.M(1).streak_after, 0)
        self.assertEqual(self.C(2).streak_after, 1)

    def test_longest_streak_and_history_survive_a_reset(self):
        for d in (1, 2, 3, 4): self.C(d)
        self.M(5); self.M(6)
        for d in (7, 8): self.C(d)
        st = services.status(self.user, D(9))
        self.assertEqual((st["streak"], st["longest"]), (2, 4))
        self.assertEqual(StreakRecord.objects.filter(user=self.user).count(), 8)      # nothing was deleted
        self.assertEqual(StreakRecord.objects.filter(user=self.user, status="completed").count(), 6)

    def test_the_same_date_can_never_add_to_the_streak_twice(self):
        first, created1 = services.record_completed(self.user, D(1))
        again, created2 = services.record_completed(self.user, D(1))
        self.assertEqual((created1, created2, again.pk, again.streak_after), (True, False, first.pk, 1))
        self.assertEqual(StreakRecord.objects.filter(user=self.user, date=D(1)).count(), 1)

    def test_database_enforces_one_record_per_date(self):
        self.C(1)
        with self.assertRaises(IntegrityError), transaction.atomic():
            StreakRecord.objects.create(user=self.user, date=D(1), status="completed", streak_after=9)

    def test_a_settled_missed_day_cannot_be_turned_into_a_completed_day(self):
        self.M(1)
        rec, created = services.record_completed(self.user, D(1))
        self.assertFalse(created)
        self.assertEqual(rec.status, "missed")

    def test_two_users_have_independent_streaks(self):
        other = make_user("other")
        start_challenge(other, D(1))
        self.C(1); self.C(2)
        self.assertEqual(services.record_completed(other, D(1))[0].streak_after, 1)


class StatusMessageTests(FixedToday):
    def test_states_and_messages(self):
        DailyPlan.objects.filter(user=self.user).update(created_at=datetime(2026, 2, 10, 1, 0, tzinfo=UTC))   # judge from today on
        self.assertEqual(services.status(self.user, D(10))["state"], "no_goals")
        goal = DailyGoal.objects.create(user=self.user, plan=self.plans[10], title="g")
        self.assertEqual(services.status(self.user, D(10))["state"], "in_progress")
        self.C(8); self.M(9)
        st = services.status(self.user, D(10))
        self.assertEqual(st["state"], "interrupted")
        self.assertIn("interrupted but not lost", st["message"])
        services.record_missed(self.user, D(10))
        self.assertEqual(services.status(self.user, D(10))["state"], "reset")
        self.assertIn("Don't give up", services.status(self.user, D(10))["message"])
        StreakRecord.objects.filter(user=self.user, date=D(10)).delete()
        services.record_completed(self.user, D(10))
        done = services.status(self.user, D(10))
        self.assertEqual(done["state"], "completed_today")
        self.assertEqual(done["message"], "Excellent work! You completed today's learning goals. Keep moving forward!")

    def test_no_challenge_and_not_started_and_over(self):
        lonely = make_user("lonely")
        self.assertEqual(services.status(lonely, D(10))["state"], "no_challenge")
        self.assertEqual(services.status(self.user, D(1) - timedelta(days=3))["state"], "not_started")
        self.assertEqual(services.status(self.user, D(1) + timedelta(days=60))["state"], "challenge_over")

    def test_records_dated_in_the_future_are_ignored_until_that_date(self):
        """After moving to an earlier time zone, a record for 'tomorrow' must not count yet."""
        self.C(1)
        services.record_completed(self.user, D(12))
        st = services.status(self.user, D(10))
        self.assertEqual(st["streak"], 1)
        self.assertEqual(services.status(self.user, D(12))["streak"], 2)


class DayCompletionTests(FixedToday):
    def setUp(self):
        super().setUp()
        self.goal = DailyGoal.objects.create(user=self.user, plan=self.plans[10], title="Learn loops")
        self.noon = datetime(2026, 2, 10, 6, 30, tzinfo=UTC)         # 12:00 in Asia/Kolkata

    def progress(self):
        return services.day_progress(self.user, D(10))

    def test_all_three_requirements_are_needed(self):
        self.assertFalse(self.progress()["complete"])
        planner.set_goal_completed(self.goal, True)
        p = self.progress()
        self.assertEqual((p["goals_ok"], p["written_ok"], p["speaking_ok"], p["complete"]), (True, False, False, False))
        submitted_assessments(self.user, self.noon, written=True, speaking=False)
        self.assertFalse(self.progress()["complete"])
        submitted_assessments(self.user, self.noon, written=False, speaking=True)
        self.assertTrue(self.progress()["complete"])

    def test_pending_goal_or_no_goal_blocks_the_day(self):
        submitted_assessments(self.user, self.noon)
        self.assertFalse(self.progress()["complete"])                   # goal still pending
        planner.set_goal_completed(self.goal, True)
        self.assertTrue(self.progress()["complete"])
        DailyGoal.objects.create(user=self.user, plan=self.plans[10], title="second goal")
        self.assertFalse(self.progress()["complete"])                   # a new unfinished goal
        DailyGoal.objects.filter(plan=self.plans[10]).delete()
        self.assertFalse(self.progress()["complete"])                   # zero goals never counts

    def test_in_progress_assessment_does_not_count(self):
        planner.set_goal_completed(self.goal, True)
        WrittenAssessment.objects.create(user=self.user, topic_name="x", status="in_progress")
        SpeakingAssessment.objects.create(user=self.user, topic_name="y", question_text="q", status="in_progress")
        p = self.progress()
        self.assertEqual((p["written"], p["speaking"], p["complete"]), (0, 0, False))

    def test_assessments_from_another_day_do_not_count(self):
        planner.set_goal_completed(self.goal, True)
        submitted_assessments(self.user, self.noon - timedelta(days=1))
        self.assertFalse(self.progress()["complete"])

    def test_other_users_assessments_do_not_count(self):
        planner.set_goal_completed(self.goal, True)
        submitted_assessments(make_user("other"), self.noon)
        self.assertFalse(self.progress()["complete"])

    def test_no_plan_day_gives_none(self):
        self.assertIsNone(services.day_progress(self.user, D(1) - timedelta(days=30)))

    def test_local_date_decides_which_day_an_assessment_belongs_to(self):
        """20:00 UTC on 10 Feb is already 11 Feb in India but still 10 Feb in New York."""
        moment = datetime(2026, 2, 10, 20, 0, tzinfo=UTC)
        ny = make_user("ny", tz="America/New_York")
        start_challenge(ny, D(1))
        submitted_assessments(self.user, moment)       # Asia/Kolkata
        submitted_assessments(ny, moment)
        self.assertEqual(services.day_progress(self.user, D(10))["written"], 0)
        self.assertEqual(services.day_progress(self.user, D(11))["written"], 1)
        self.assertEqual(services.day_progress(ny, D(10))["written"], 1)
        self.assertEqual(services.day_progress(ny, D(11))["written"], 0)

    def test_changing_time_zone_moves_the_day_boundary(self):
        moment = datetime(2026, 2, 10, 20, 0, tzinfo=UTC)
        submitted_assessments(self.user, moment)
        self.assertEqual(services.day_progress(self.user, D(11))["written"], 1)
        self.user.profile.timezone = "America/Los_Angeles"
        self.user.profile.save()
        user = User.objects.get(pk=self.user.pk)
        self.assertEqual(services.day_progress(user, D(10))["written"], 1)
        self.assertEqual(services.day_progress(user, D(11))["written"], 0)


class SyncTests(FixedToday):
    def test_finished_days_without_a_record_become_missed_but_today_is_not_judged(self):
        new = services.sync(self.user, D(10))
        self.assertEqual([r.date for r in new], [D(d) for d in range(1, 10)])
        self.assertFalse(StreakRecord.objects.filter(user=self.user, date=D(10)).exists())
        self.assertTrue(all(r.status == "missed" for r in new))
        self.assertEqual(new[-1].streak_after, 0)

    def test_sync_twice_adds_nothing_and_does_not_duplicate_notifications(self):
        services.sync(self.user, D(10))
        self.assertEqual(services.sync(self.user, D(10)), [])
        self.assertEqual(Notification.objects.filter(user=self.user, kind="warning").count(), 1)

    def test_completed_days_are_kept_and_following_misses_follow_the_rules(self):
        for d in (1, 2, 3):
            self.C(d)
        services.sync(self.user, D(8))                       # days 4..7 missed
        records = {r.date.day: r for r in StreakRecord.objects.filter(user=self.user)}
        self.assertEqual([records[d].status for d in (1, 2, 3)], ["completed"] * 3)
        self.assertEqual([records[d].streak_after for d in (4, 5, 6, 7)], [3, 0, 0, 0])

    def test_one_missed_day_creates_a_warning_and_two_create_a_reset_notice(self):
        self.C(1)
        services.sync(self.user, D(3))                       # only day 2 missed
        note = Notification.objects.get(user=self.user, dedupe_key=f"missed:{D(2)}")
        self.assertIn("interrupted, not lost", note.message)
        self.assertEqual(note.kind, "warning")
        services.sync(self.user, D(4))                       # day 3 missed too: reset
        reset = Notification.objects.get(user=self.user, dedupe_key=f"reset:{D(3)}")
        self.assertIn("back to 0", reset.message)
        self.assertIn("safe", reset.message)

    def test_days_before_the_challenge_was_created_are_never_judged(self):
        user = make_user("late")
        start_challenge(user, D(1), created_before=False)           # created "now" (real time), start date in the past
        services.sync(user, D(10))
        self.assertEqual(StreakRecord.objects.filter(user=user, date__lt=D(10)).count(), 0)

    def test_tracking_starts_on_the_day_the_challenge_was_created(self):
        user = make_user("mid")
        start_challenge(user, D(1), created_before=False)
        DailyPlan.objects.filter(user=user).update(created_at=datetime(2026, 2, 7, 12, 0, tzinfo=UTC))
        services.sync(user, D(10))
        self.assertEqual([r.date.day for r in StreakRecord.objects.filter(user=user)], [7, 8, 9])

    def test_user_without_challenge_is_untouched(self):
        self.assertEqual(services.sync(make_user("nochallenge"), D(10)), [])


class EvaluateTodayFlowTests(FixedToday):
    """Today's record appears when the day is complete and is withdrawn if it stops being complete."""

    def setUp(self):
        super().setUp()
        self.goal = DailyGoal.objects.create(user=self.user, plan=self.plans[10], title="g")
        self.noon = datetime(2026, 2, 10, 6, 30, tzinfo=UTC)

    def complete_everything(self):
        planner.set_goal_completed(self.goal, True)
        submitted_assessments(self.user, self.noon)

    def test_completing_goal_and_both_assessments_records_the_day(self):
        self.assertFalse(StreakRecord.objects.filter(user=self.user, date=D(10)).exists())
        self.complete_everything()                                    # signals do the work
        rec = StreakRecord.objects.get(user=self.user, date=D(10))
        self.assertEqual((rec.status, rec.goals_total, rec.goals_done, rec.written_count, rec.speaking_count, rec.day_number),
                         ("completed", 1, 1, 1, 1, 10))

    def test_earlier_unrecorded_days_are_settled_first(self):
        self.complete_everything()
        self.assertEqual(StreakRecord.objects.filter(user=self.user, status="missed").count(), 9)
        self.assertEqual(StreakRecord.objects.get(user=self.user, date=D(10)).streak_after, 1)

    def test_a_day_completed_twice_only_counts_once(self):
        self.complete_everything()
        services.evaluate_today(self.user, D(10))
        services.on_activity(self.user)
        planner.set_goal_completed(self.goal, True)
        self.assertEqual(StreakRecord.objects.filter(user=self.user, date=D(10)).count(), 1)
        self.assertEqual(StreakRecord.objects.get(user=self.user, date=D(10)).streak_after, 1)

    def test_day_complete_notification_is_created_once(self):
        self.complete_everything()
        services.evaluate_today(self.user, D(10))
        notes = Notification.objects.filter(user=self.user, dedupe_key=f"day-complete:{D(10)}")
        self.assertEqual(notes.count(), 1)
        self.assertIn("Excellent work!", notes[0].message)

    def test_undoing_a_goal_the_same_day_withdraws_todays_record_but_not_badges(self):
        self.complete_everything()
        self.assertTrue(Achievement.objects.filter(user=self.user, key="first_day").exists())
        planner.set_goal_completed(self.goal, False)
        self.assertFalse(StreakRecord.objects.filter(user=self.user, date=D(10)).exists())
        self.assertTrue(Achievement.objects.filter(user=self.user, key="first_day").exists())      # badges are permanent
        planner.set_goal_completed(self.goal, True)
        self.assertTrue(StreakRecord.objects.filter(user=self.user, date=D(10), status="completed").exists())

    def test_adding_another_goal_later_today_withdraws_the_record(self):
        self.complete_everything()
        DailyGoal.objects.create(user=self.user, plan=self.plans[10], title="extra")
        self.assertFalse(StreakRecord.objects.filter(user=self.user, date=D(10)).exists())

    def test_past_records_are_never_withdrawn(self):
        StreakRecord.objects.filter(user=self.user).delete()      # clean slate (setUp already settled earlier days)
        self.C(3)
        planner.set_goal_completed(self.goal, False)       # activity today must not touch day 3
        self.assertEqual(StreakRecord.objects.get(user=self.user, date=D(3)).status, "completed")

    def test_deleting_the_last_pending_goal_does_not_crash(self):
        self.goal.delete()
        self.assertFalse(StreakRecord.objects.filter(user=self.user, date=D(10), status="completed").exists())


class BadgeTests(TestCase):
    def setUp(self):
        self.user = make_user()

    def keys(self):
        return set(Achievement.objects.filter(user=self.user).values_list("key", flat=True))

    def test_badge_keys_are_unique_and_described(self):
        self.assertEqual(len({b.key for b in BADGES}), len(BADGES))
        self.assertTrue(all(b.title and b.description and b.icon for b in BADGES))

    def test_first_topic_badge_and_notification(self):
        topic = make_topic(self.user)
        set_topic_status(self.user, topic, "completed")
        self.assertIn("first_topic", self.keys())
        note = Notification.objects.get(user=self.user, dedupe_key="badge:first_topic")
        self.assertEqual(note.kind, "badge")
        self.assertIn("New badge", note.title)

    def test_badges_are_awarded_once_and_notified_once(self):
        topic = make_topic(self.user)
        set_topic_status(self.user, topic, "completed")
        set_topic_status(self.user, topic, "completed")
        services.award_badges(self.user)
        self.assertEqual(Achievement.objects.filter(user=self.user, key="first_topic").count(), 1)
        self.assertEqual(Notification.objects.filter(user=self.user, dedupe_key="badge:first_topic").count(), 1)

    def test_assessment_aptitude_and_coding_badges(self):
        topic = make_topic(self.user)
        a, _ = assess_services.start_written(self.user, topic)
        post = {}
        for ans in a.answers.all():
            post[f"text_{ans.pk}"] = ans.question_data["model_answer"]
            post[f"code_{ans.pk}"] = ans.question_data.get("model_code", "")
        assess_services.submit_written(a, post)
        s, _ = assess_services.start_speaking(self.user, topic)
        assess_services.submit_speaking(s, "A for loop repeats a block of code for each item in a sequence or a range. For example, for i in range(3) prints three numbers, because range stops early.", "", "typed", 0)
        att, _ = apt_services.start_attempt(self.user, "verbal", "Grammar", 5, 5)
        apt_services.finalize(att, {str(i): q["correct"] for i, q in enumerate(att.questions)})
        hard = CodingProblem.objects.get(difficulty="hard", slug="permutations")
        coding_services.record_manual(self.user, hard, "code", solved=True)
        for key in ("first_written", "written_90", "first_speaking", "first_aptitude", "aptitude_80", "first_solve", "hard_solved"):
            self.assertIn(key, self.keys(), key)

    def test_five_solved_problems_give_problem_solver(self):
        for p in CodingProblem.objects.all()[:5]:
            coding_services.record_manual(self.user, p, "c", solved=True)
        self.assertIn("solves_5", self.keys())

    def test_failed_or_saved_attempts_earn_nothing(self):
        p = CodingProblem.objects.first()
        coding_services.record_manual(self.user, p, "c", solved=False)
        self.assertNotIn("first_solve", self.keys())

    def test_streak_badges_use_the_longest_streak_and_survive_resets(self):
        start_challenge(self.user, D(1))
        for d in range(1, 4):
            services.record_completed(self.user, D(d))
        with mock.patch("streaks.services.get_user_today", return_value=D(10)):
            services.award_badges(self.user)
        self.assertIn("streak_3", self.keys())
        services.record_missed(self.user, D(4)); services.record_missed(self.user, D(5))
        services.award_badges(self.user)
        self.assertIn("streak_3", self.keys())
        self.assertEqual(services.status(self.user, D(6))["streak"], 0)

    def test_comeback_badge_after_a_missed_day(self):
        start_challenge(self.user, D(1))
        services.record_completed(self.user, D(1))
        services.record_missed(self.user, D(2))
        services.record_completed(self.user, D(3))
        services.award_badges(self.user)
        self.assertIn("comeback", self.keys())

    def test_badges_are_per_user(self):
        set_topic_status(self.user, make_topic(self.user), "completed")
        self.assertEqual(Achievement.objects.filter(user=make_user("other")).count(), 0)


class StatsAndHeatmapTests(FixedToday):
    def test_weekly_consistency(self):
        for d in (5, 6, 7):
            self.C(d)
        self.M(8)
        w = services.weekly_consistency(self.user, D(10))
        self.assertEqual((w["completed"], w["days"], w["percent"]), (3, 6, 50))        # days 4..9 count; today (10) only once completed
        services.record_completed(self.user, D(10))
        self.assertEqual(services.weekly_consistency(self.user, D(10))["percent"], 57)  # 4 of 7

    def test_weekly_consistency_without_plan_days_is_none(self):
        self.assertIsNone(services.weekly_consistency(make_user("x"), D(10))["percent"])

    def test_overview_stats(self):
        self.C(1); self.C(2)
        planner.set_goal_completed(DailyGoal.objects.create(user=self.user, plan=self.plans[1], title="g"), True)
        s = services.overview_stats(self.user, D(10))
        self.assertEqual((s["completed_days"], s["goals_done"]), (2, 1))
        self.assertGreaterEqual(s["active_days"], 1)

    def test_active_days_count_any_activity_by_local_date(self):
        goal = DailyGoal.objects.create(user=self.user, plan=self.plans[2], title="g")
        planner.set_goal_completed(goal, True)
        DailyGoal.objects.filter(pk=goal.pk).update(completed_at=datetime(2026, 2, 3, 20, 0, tzinfo=UTC))    # 4 Feb 01:30 in India
        submitted_assessments(self.user, datetime(2026, 2, 5, 6, 0, tzinfo=UTC), speaking=False)
        self.assertEqual(services.activity_dates(self.user), {D(4), D(5)})

    def test_heatmap_cell_states(self):
        DailyPlan.objects.filter(user=self.user).update(created_at=datetime(2026, 2, 10, 1, 0, tzinfo=UTC))   # no automatic misses
        self.C(1); self.M(2)
        submitted_assessments(self.user, datetime(2026, 2, 4, 6, 0, tzinfo=UTC), speaking=False)    # partial activity
        weeks = services.heatmap(self.user, 2026, 2, D(10))
        cells = {c["number"]: c for w in weeks for c in w if c}
        self.assertEqual((cells[1]["state"], cells[2]["state"], cells[4]["state"]), ("completed", "missed", "partial"))
        self.assertEqual((cells[10]["state"], cells[12]["state"], cells[3]["state"]), ("today", "upcoming", "none"))
        self.assertTrue(cells[10]["is_today"])
        self.assertEqual(len(cells), 28)
        self.assertEqual(weeks[0][:6].count(None), 6)                    # 1 Feb 2026 is a Sunday
        self.assertTrue(all(len(w) == 7 for w in weeks))

    def test_heatmap_for_a_month_outside_the_challenge_is_empty(self):
        cells = [c for w in services.heatmap(self.user, 2025, 6, D(10)) for c in w if c]
        self.assertTrue(all(c["state"] == "none" for c in cells))


class DeleteUserTests(TestCase):
    def test_deleting_a_user_with_streak_data_works(self):
        user = make_user()
        plans = start_challenge(user, get_user_today(user))
        goal = DailyGoal.objects.create(user=user, plan=plans[1], title="g")
        planner.set_goal_completed(goal, True)
        services.record_missed(user, get_user_today(user) - timedelta(days=1))
        user.delete()
        self.assertEqual(StreakRecord.objects.count(), 0)
        self.assertEqual(DailyGoal.objects.count(), 0)


class RealFlowTests(TestCase):
    """No fake dates: the whole chain with the real clock."""

    def test_goal_plus_both_assessments_complete_today_and_start_a_streak(self):
        user = make_user()
        today = get_user_today(user)
        planner.start_challenge(user, today)
        plan = DailyPlan.objects.get(user=user, day_number=1)
        topic = make_topic(user)
        goal = DailyGoal.objects.create(user=user, plan=plan, topic=topic, title="Learn loops")
        self.assertEqual(services.status(user)["state"], "in_progress")
        planner.set_goal_completed(goal, True)
        self.assertEqual(services.status(user)["streak"], 0)
        a, _ = assess_services.start_written(user, topic)
        assess_services.submit_written(a)
        self.assertEqual(services.status(user)["streak"], 0)                    # still missing the speaking stage
        s, _ = assess_services.start_speaking(user, topic)
        assess_services.submit_speaking(s, "A loop repeats code.", "", "typed", 0)
        st = services.status(user)
        self.assertEqual((st["streak"], st["state"]), (1, "completed_today"))
        self.assertTrue(Achievement.objects.filter(user=user, key="first_day").exists())
        self.assertTrue(Notification.objects.filter(user=user, dedupe_key=f"day-complete:{today}").exists())

    def test_a_new_challenge_starting_in_the_past_does_not_punish_the_user(self):
        user = make_user()
        planner.start_challenge(user, get_user_today(user) - timedelta(days=5))
        services.refresh(user)
        self.assertEqual(StreakRecord.objects.filter(user=user).count(), 0)
        self.assertEqual(services.status(user)["state"], "no_goals")


class StreakViewTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_login(self.user)
        self.today = get_user_today(self.user)

    def test_page_without_a_challenge(self):
        r = self.client.get(reverse("streaks:overview"))
        self.assertContains(r, "Start your 40-day challenge")
        self.assertContains(r, "Badges")
        self.assertContains(r, "How streaks work")

    def test_page_shows_stats_heatmap_badges_and_history(self):
        yesterday = self.today - timedelta(days=1)
        start_challenge(self.user, yesterday)                       # a settled past day (today's record would be provisional)
        services.record_completed(self.user, yesterday)
        r = self.client.get(reverse("streaks:overview"))
        for text in ("Current streak", "Longest streak", "Active learning days", "Goals completed", "Weekly consistency",
                     "heatmap", "First Step", "Recent days", "both assessments"):
            self.assertContains(r, text)
        self.assertEqual(len(r.context["weeks"][0]), 7)
        self.assertEqual(r.context["stats"]["completed_days"], 1)

    def test_month_parameter_navigation_and_bad_values(self):
        planner.start_challenge(self.user, self.today)
        r = self.client.get(reverse("streaks:overview") + "?month=2030-01")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.context["is_current_month"] is False)
        for bad in ("abc", "2026-13", "9999-01", "0000-00", ""):
            self.assertEqual(self.client.get(reverse("streaks:overview") + f"?month={bad}").status_code, 200, bad)
        near = self.client.get(reverse("streaks:overview") + f"?month={self.today.year}-{self.today.month:02d}")
        self.assertTrue(near.context["is_current_month"])

    def test_page_requires_login_and_shows_only_own_data(self):
        planner.start_challenge(self.user, self.today)
        services.record_completed(self.user, self.today)
        other = make_user("bob")
        self.client.force_login(other)
        r = self.client.get(reverse("streaks:overview"))
        self.assertEqual(r.context["stats"]["completed_days"], 0)
        self.client.logout()
        self.assertEqual(self.client.get(reverse("streaks:overview")).status_code, 302)

    def test_missed_day_warning_is_visible(self):
        planner.start_challenge(self.user, self.today - timedelta(days=1))
        DailyPlan.objects.filter(user=self.user).update(created_at=datetime.now(UTC) - timedelta(days=5))
        r = self.client.get(reverse("streaks:overview"))
        self.assertEqual(r.context["status"]["state"], "interrupted")
        self.assertContains(r, "missed yesterday")

    def test_dashboard_shows_streak_card_and_checklist(self):
        planner.start_challenge(self.user, self.today)
        DailyGoal.objects.create(user=self.user, plan=DailyPlan.objects.get(user=self.user, day_number=1), title="g")
        r = self.client.get(reverse("dashboard:index"))
        self.assertContains(r, "day streak")
        self.assertContains(r, "Written assessment submitted")
        self.assertContains(r, "Speaking assessment submitted")
        self.assertEqual(r.context["streak"]["state"], "in_progress")

    def test_sidebar_and_bell_links_present(self):
        r = self.client.get(reverse("dashboard:index"))
        self.assertContains(r, reverse("streaks:overview"))
        self.assertContains(r, reverse("notifications:list"))
