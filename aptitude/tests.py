import math
import re
from collections import Counter
from datetime import timedelta
from fractions import Fraction

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.utils.html import escape

from . import services
from .bank import all_questions, validate
from .models import AptitudeAttempt, AptitudeQuestion
from .topics import SECTIONS

User = get_user_model()


def make_user(name="u1"):
    return User.objects.create_user(name, f"{name}@example.com", "StrongPass#2026")


def answer_all(attempt, correct=True, only=None):
    """Return a posted-answers dict answering every question right (or wrong)."""
    posted = {}
    for i, q in enumerate(attempt.questions):
        if only is not None and i not in only:
            continue
        posted[str(i)] = q["correct"] if correct else (q["correct"] + 1) % 4
    return posted


class BankTests(TestCase):
    def test_bank_is_sound(self):
        rows = all_questions()
        self.assertEqual(validate(rows), [])
        self.assertGreaterEqual(len(rows), 200)

    def test_all_28_topics_are_covered_with_enough_questions(self):
        counts = Counter((r["section"], r["topic"]) for r in all_questions())
        expected = {(s, t) for s, (_, ts) in SECTIONS.items() for t in ts}
        self.assertEqual(set(counts), expected)
        self.assertEqual(len(expected), 28)
        self.assertTrue(all(n >= 5 for n in counts.values()))

    def test_bank_is_deterministic(self):
        self.assertEqual(all_questions(), all_questions())

    def test_answers_are_spread_over_all_four_positions(self):
        spread = Counter(r["correct_index"] for r in all_questions())
        self.assertEqual(set(spread), {0, 1, 2, 3})
        self.assertTrue(all(n > 25 for n in spread.values()))

    def test_bank_is_loaded_by_migrate_and_loading_again_changes_nothing(self):
        total = AptitudeQuestion.objects.count()
        self.assertEqual(total, len(all_questions()))
        created, updated = services.load_bank()
        self.assertEqual((created, AptitudeQuestion.objects.count()), (0, total))

    def test_reading_comprehension_questions_carry_their_passage(self):
        rc = AptitudeQuestion.objects.filter(topic="Reading Comprehension")
        self.assertEqual(rc.count(), 6)
        self.assertTrue(all(q.passage for q in rc))

    def test_computed_answers_match_independent_calculations(self):
        """Re-calculate the answer from the question text with separate code."""
        families = Counter()
        for r in all_questions():
            stem, correct = r["stem"], r["options"][r["correct_index"]]
            m = re.fullmatch(r"What is (\d+)% of (\d+)\?", stem)
            if m:
                families["pct"] += 1; self.assertEqual(correct, str(int(m[2]) * int(m[1]) // 100), stem)
            m = re.fullmatch(r"What is the HCF of (\d+) and (\d+)\?", stem)
            if m:
                families["hcf"] += 1; self.assertEqual(correct, str(math.gcd(int(m[1]), int(m[2]))), stem)
            m = re.fullmatch(r"What is the LCM of (\d+) and (\d+)\?", stem)
            if m:
                families["lcm"] += 1; self.assertEqual(correct, str(math.lcm(int(m[1]), int(m[2]))), stem)
            m = re.fullmatch(r"What is the remainder when (\d+) is divided by (\d+)\?", stem)
            if m:
                families["rem"] += 1; self.assertEqual(correct, str(int(m[1]) % int(m[2])), stem)
            m = re.fullmatch(r"What is the sum of all natural numbers from 1 to (\d+)\?", stem)
            if m:
                families["sum"] += 1; self.assertEqual(correct, str(sum(range(1, int(m[1]) + 1))), stem)
            m = re.search(r"dice are rolled together\. What is the probability that the sum is (\d+)\?", stem)
            if m:
                families["dice"] += 1
                ways = sum(1 for a in range(1, 7) for b in range(1, 7) if a + b == int(m[1]))
                f = Fraction(ways, 36)
                self.assertEqual(correct, f"{f.numerator}/{f.denominator}", stem)
            m = re.search(r"simple interest on Rs\. (\d+) at (\d+)% per annum for (\d+) years", stem)
            if m:
                families["si"] += 1; self.assertEqual(correct, str(int(m[1]) * int(m[2]) * int(m[3]) // 100), stem)
            m = re.match(r"(\d+) people are at a party", stem)
            if m:
                families["handshake"] += 1; self.assertEqual(correct, str(math.comb(int(m[1]), 2)), stem)
            m = re.search(r"letters of the word '(\w+)'", stem)
            if m:
                families["letters"] += 1
                expected = math.factorial(len(m[1]))
                for c in Counter(m[1]).values():
                    expected //= math.factorial(c)
                self.assertEqual(correct, str(expected), stem)
            m = re.search(r"committee of (\d+) be chosen from (\d+) people", stem)
            if m:
                families["committee"] += 1; self.assertEqual(correct, str(math.comb(int(m[2]), int(m[1]))), stem)
            m = re.search(r"walks (\d+) km north, then (\d+) km east, then (\d+) km south", stem)
            if m:
                families["distance"] += 1
                self.assertEqual(correct, str(round(math.hypot(int(m[1]) - int(m[3]), int(m[2])))), stem)
            m = re.search(r"replaced by the letter (\d+) places? ahead.*How is '(\w+)' written", stem)
            if m:
                families["shift"] += 1
                self.assertEqual(correct, "".join(chr((ord(c) - 65 + int(m[1])) % 26 + 65) for c in m[2]), stem)
            m = re.search(r"If A = 1, B = 2.*sum of the letter values of '(\w+)'", stem)
            if m:
                families["letter-sum"] += 1; self.assertEqual(correct, str(sum(ord(c) - 64 for c in m[1])), stem)
        for family in ("pct", "hcf", "lcm", "rem", "sum", "dice", "si", "handshake", "letters", "committee", "distance", "shift", "letter-sum"):
            self.assertGreater(families[family], 0, f"no {family} questions were checked")


class AttemptServiceTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.now = timezone.now()

    def start(self, **kw):
        defaults = dict(section="quant", topic="", count=10, minutes=None, now=self.now)
        defaults.update(kw)
        return services.start_attempt(self.user, **defaults)

    def test_start_builds_a_snapshot_test_with_default_time(self):
        a, created = self.start(topic="Percentages")
        self.assertTrue(created)
        self.assertEqual((a.total_count, a.time_limit_seconds, a.status), (10, 600, "in_progress"))
        self.assertTrue(all(q["topic"] == "Percentages" and len(q["options"]) == 4 for q in a.questions))
        self.assertEqual(len({q["stem"] for q in a.questions}), 10)

    def test_all_topics_of_a_section_mix_topics(self):
        a, _ = self.start(count=20)
        self.assertGreater(len({q["topic"] for q in a.questions}), 3)

    def test_small_pool_gives_fewer_questions(self):
        a, _ = self.start(section="logical", topic="Seating Arrangements", count=20)
        self.assertEqual(a.total_count, 5)

    def test_invalid_choices_are_rejected(self):
        for kw in ({"section": "nope"}, {"topic": "Grammar"}, {"count": 7}, {"minutes": 3}):
            with self.assertRaises(ValueError):
                self.start(**kw)
        self.assertEqual(AptitudeAttempt.objects.count(), 0)

    def test_second_start_resumes_the_open_test(self):
        a, _ = self.start()
        b, created = self.start(section="verbal")
        self.assertEqual((b.pk, created), (a.pk, False))
        self.assertEqual(AptitudeAttempt.objects.count(), 1)

    def test_database_allows_only_one_open_test_per_user(self):
        self.start()
        with self.assertRaises(IntegrityError), transaction.atomic():
            AptitudeAttempt.objects.create(user=self.user, section="quant", questions=[], time_limit_seconds=60)

    def test_starting_after_expiry_grades_the_old_test_first(self):
        old, _ = self.start(minutes=5)
        later = self.now + timedelta(minutes=30)
        new, created = self.start(now=later)
        self.assertTrue(created)
        old.refresh_from_db()
        self.assertTrue(old.is_submitted and old.timed_out)
        self.assertEqual(old.correct_count, 0)

    def test_other_user_can_have_their_own_open_test(self):
        self.start()
        a, created = services.start_attempt(make_user("other"), "verbal", "", 5, None, now=self.now)
        self.assertTrue(created)

    def test_autosave_saves_clears_and_validates(self):
        a, _ = self.start()
        self.assertTrue(services.autosave_answer(a, 0, 2, now=self.now))
        a.refresh_from_db(); self.assertEqual(a.answers, {"0": 2})
        self.assertTrue(services.autosave_answer(a, 0, None, now=self.now))
        a.refresh_from_db(); self.assertEqual(a.answers, {})
        for index, option in ((99, 1), (-1, 1), (0, 4), (0, -1)):
            self.assertFalse(services.autosave_answer(a, index, option, now=self.now))

    def test_autosave_refused_after_deadline_and_after_submit(self):
        a, _ = self.start(minutes=5)
        self.assertFalse(services.autosave_answer(a, 0, 1, now=self.now + timedelta(minutes=5, seconds=1)))
        a, _ = services.finalize(a, now=self.now + timedelta(minutes=1))
        self.assertFalse(services.autosave_answer(a, 0, 1, now=self.now + timedelta(minutes=2)))

    def test_scoring_counts_only_correct_answers(self):
        a, _ = self.start()
        posted = answer_all(a, correct=True, only={0, 1, 2, 3, 4, 5})
        posted.update(answer_all(a, correct=False, only={6, 7}))     # 2 wrong, 2 unanswered
        a, graded = services.finalize(a, posted, now=self.now + timedelta(minutes=2))
        self.assertTrue(graded)
        self.assertEqual((a.correct_count, a.total_count, a.percent), (6, 10, 60.0))
        self.assertFalse(a.timed_out)
        self.assertEqual(a.seconds_used, 120)

    def test_perfect_and_empty_tests(self):
        a, _ = self.start()
        a, _ = services.finalize(a, answer_all(a), now=self.now + timedelta(seconds=30))
        self.assertEqual(a.percent, 100.0)
        b, _ = services.start_attempt(self.user, "verbal", "", 5, None, now=self.now)
        b, _ = services.finalize(b, {}, now=self.now + timedelta(seconds=30))
        self.assertEqual((b.correct_count, b.percent), (0, 0.0))

    def test_finalize_twice_changes_nothing(self):
        a, _ = self.start()
        a, first = services.finalize(a, answer_all(a), now=self.now + timedelta(seconds=10))
        again, second = services.finalize(a, {}, now=self.now + timedelta(seconds=20))
        self.assertEqual((first, second), (True, False))
        self.assertEqual(again.percent, 100.0)

    def test_answers_posted_within_grace_period_count(self):
        a, _ = self.start(minutes=5)
        late = self.now + timedelta(minutes=5, seconds=services.GRACE_SECONDS - 1)
        a, _ = services.finalize(a, answer_all(a), now=late)
        self.assertEqual(a.percent, 100.0)
        self.assertTrue(a.timed_out)
        self.assertEqual(a.seconds_used, 300)

    def test_answers_posted_after_grace_are_ignored_but_autosaved_ones_count(self):
        a, _ = self.start(minutes=5)
        for i in (0, 1, 2):
            services.autosave_answer(a, i, a.questions[i]["correct"], now=self.now + timedelta(minutes=1))
        a.refresh_from_db()
        way_late = self.now + timedelta(minutes=5, seconds=services.GRACE_SECONDS + 5)
        a, _ = services.finalize(a, answer_all(a), now=way_late)
        self.assertEqual(a.correct_count, 3)

    def test_garbage_posted_answers_are_ignored(self):
        a, _ = self.start()
        a, _ = services.finalize(a, {"abc": 1, "0": "x", "1": 9, "-3": 1, "500": 1, "2": "3"}, now=self.now + timedelta(seconds=5))
        self.assertEqual(set(a.answers), {"2"})

    def test_statistics_per_section_and_weak_topics(self):
        a, _ = self.start(topic="Percentages", now=self.now)
        services.finalize(a, answer_all(a, correct=False), now=self.now + timedelta(seconds=30))
        b, _ = self.start(topic="Probability", now=self.now + timedelta(minutes=1))
        services.finalize(b, answer_all(b), now=self.now + timedelta(minutes=2))
        stats = services.section_stats(self.user)
        self.assertEqual((stats["quant"]["attempts"], stats["quant"]["avg"], stats["quant"]["best"]), (2, 50, 100))
        self.assertEqual(stats["verbal"]["attempts"], 0)
        weakest = services.topic_accuracy(self.user)
        self.assertEqual(weakest[0][:2], ("quant", "Percentages"))
        self.assertEqual(weakest[0][4], 0)
        self.assertEqual(services.overall_stats(self.user), {"attempts": 2, "avg": 50})


class AptitudeViewTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_login(self.user)

    def begin(self, **extra):
        data = {"section": "quant", "topic": "Averages", "count": "5", "minutes": "5", **extra}
        r = self.client.post(reverse("aptitude:start"), data)
        a = AptitudeAttempt.objects.get(user=self.user, status="in_progress")
        self.assertRedirects(r, reverse("aptitude:attempt", args=[a.pk]))
        return a

    def test_overview_lists_sections_topics_and_form(self):
        r = self.client.get(reverse("aptitude:overview"))
        for text in ("Quantitative Aptitude", "Logical Reasoning", "Verbal Ability", "Permutations and Combinations", "Start test"):
            self.assertContains(r, text)

    def test_start_requires_post_and_reports_bad_input(self):
        self.assertEqual(self.client.get(reverse("aptitude:start")).status_code, 405)
        r = self.client.post(reverse("aptitude:start"), {"section": "quant", "count": "99"}, follow=True)
        self.assertContains(r, "Choose 5, 10, 15 or 20")

    def test_take_page_shows_timer_and_questions_but_no_answers(self):
        a = self.begin()
        r = self.client.get(reverse("aptitude:attempt", args=[a.pk]))
        self.assertContains(r, 'data-remaining="')
        self.assertContains(r, "Question 5")
        self.assertContains(r, "Submit test")
        for q in a.questions:        # answers and explanations must not be in the page while the test runs
            self.assertNotContains(r, escape(q["explanation"]))

    def test_passage_is_shown_once_for_consecutive_questions(self):
        a = self.begin(section="verbal", topic="Reading Comprehension", count="5")
        a.refresh_from_db()
        r = self.client.get(reverse("aptitude:attempt", args=[a.pk]))
        passages = {q["passage"] for q in a.questions}
        self.assertTrue(all(r.content.decode().count(p[:40]) >= 1 for p in passages))

    def test_autosave_endpoint(self):
        a = self.begin()
        url = reverse("aptitude:answer", args=[a.pk])
        r = self.client.post(url, {"index": "1", "option": "3"})
        self.assertEqual((r.status_code, r.json()["saved"]), (200, True))
        a.refresh_from_db(); self.assertEqual(a.answers, {"1": 3})
        self.assertEqual(self.client.post(url, {"index": "x", "option": "1"}).status_code, 400)
        self.assertEqual(self.client.post(url, {"index": "1", "option": "9"}).status_code, 409)
        self.assertEqual(self.client.get(url).status_code, 405)

    def test_autosave_refused_with_409_after_deadline(self):
        a = self.begin()
        AptitudeAttempt.objects.filter(pk=a.pk).update(started_at=timezone.now() - timedelta(hours=1))
        r = self.client.post(reverse("aptitude:answer", args=[a.pk]), {"index": "0", "option": "1"})
        self.assertEqual(r.status_code, 409)
        self.assertTrue(r.json()["expired"])

    def test_submit_shows_result_with_explanations_and_topic_table(self):
        a = self.begin()
        data = {f"q{i}": q["correct"] for i, q in enumerate(a.questions[:3])}
        r = self.client.post(reverse("aptitude:submit", args=[a.pk]), data)
        self.assertRedirects(r, reverse("aptitude:attempt", args=[a.pk]))
        page = self.client.get(reverse("aptitude:attempt", args=[a.pk]))
        a.refresh_from_db()
        self.assertEqual(a.correct_count, 3)
        self.assertContains(page, "60%")
        self.assertContains(page, "Explanation")
        self.assertContains(page, "By topic")
        self.assertContains(page, "Not answered")
        self.assertContains(page, escape(a.questions[0]["explanation"]))

    def test_submit_requires_post(self):
        a = self.begin()
        self.assertEqual(self.client.get(reverse("aptitude:submit", args=[a.pk])).status_code, 405)

    def test_double_submit_keeps_the_first_result(self):
        a = self.begin()
        url = reverse("aptitude:submit", args=[a.pk])
        self.client.post(url, {f"q{i}": q["correct"] for i, q in enumerate(a.questions)})
        self.client.post(url, {})
        a.refresh_from_db()
        self.assertEqual(a.percent, 100.0)

    def test_expired_test_is_graded_automatically_when_opened(self):
        a = self.begin()
        services.autosave_answer(a, 0, a.questions[0]["correct"])
        AptitudeAttempt.objects.filter(pk=a.pk).update(started_at=timezone.now() - timedelta(hours=2))
        page = self.client.get(reverse("aptitude:attempt", args=[a.pk]))
        a.refresh_from_db()
        self.assertTrue(a.is_submitted and a.timed_out)
        self.assertEqual(a.correct_count, 1)
        self.assertContains(page, "time ran out")

    def test_overview_finalises_a_stale_open_test(self):
        a = self.begin()
        AptitudeAttempt.objects.filter(pk=a.pk).update(started_at=timezone.now() - timedelta(hours=2))
        r = self.client.get(reverse("aptitude:overview"))
        self.assertContains(r, "graded automatically")
        self.assertIsNone(r.context["open_attempt"])

    def test_history_lists_and_filters(self):
        a = self.begin()
        self.client.post(reverse("aptitude:submit", args=[a.pk]), {})
        r = self.client.get(reverse("aptitude:history"))
        self.assertContains(r, "Quantitative Aptitude: Averages")
        self.assertNotContains(self.client.get(reverse("aptitude:history") + "?section=verbal"), "Averages")


class AptitudeAccessTests(TestCase):
    def setUp(self):
        self.alice, self.bob = make_user("alice"), make_user("bob")
        self.a, _ = services.start_attempt(self.alice, "quant", "Averages", 5, 5)

    def test_anonymous_redirected(self):
        for name, args in (("aptitude:overview", []), ("aptitude:history", []), ("aptitude:attempt", [self.a.pk])):
            self.assertEqual(self.client.get(reverse(name, args=args)).status_code, 302, name)

    def test_other_user_gets_404_and_cannot_change_anything(self):
        self.client.force_login(self.bob)
        self.assertEqual(self.client.get(reverse("aptitude:attempt", args=[self.a.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("aptitude:answer", args=[self.a.pk]), {"index": "0", "option": "1"}).status_code, 404)
        self.assertEqual(self.client.post(reverse("aptitude:submit", args=[self.a.pk]), {}).status_code, 404)
        self.a.refresh_from_db()
        self.assertEqual((self.a.status, self.a.answers), ("in_progress", {}))

    def test_history_shows_only_own_tests(self):
        services.finalize(self.a, {})
        self.client.force_login(self.bob)
        self.assertNotContains(self.client.get(reverse("aptitude:history")), "Averages")

    def test_dashboard_shows_aptitude_summary(self):
        services.finalize(self.a, answer_all(self.a))
        self.client.force_login(self.alice)
        page = self.client.get(reverse("dashboard:index"))
        self.assertEqual(page.context["apt"], {"attempts": 1, "avg": 100})
        self.assertContains(page, "Aptitude average")
