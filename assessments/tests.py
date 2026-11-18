import io
import json
import os
import tempfile
from unittest import mock

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from learning.models import Domain, LearningContent, Technology, Topic
from learning.services import set_topic_status

from . import ai, services
from .evaluation import evaluate_answer, strip_comments
from .models import SpeakingAnswer, SpeakingAssessment, WrittenAnswer, WrittenAssessment
from .question_bank import SPOKEN, WRITTEN, ck
from .speaking_eval import evaluate_speaking

User = get_user_model()


def make_user(name="u1"):
    return User.objects.create_user(name, f"{name}@example.com", "StrongPass#2026")


def make_topic(user, tech="Python", name="Loops", domain="Tech"):
    d, _ = Domain.objects.get_or_create(user=user, name=domain)
    t, _ = Technology.objects.get_or_create(user=user, domain=d, name=tech)
    return Topic.objects.create(user=user, technology=t, name=name)


def q_of(topic, qtype):
    return next(q for q in WRITTEN["python"][topic] if q["type"] == qtype)


class QuestionBankTests(TestCase):
    def test_every_model_answer_scores_high_and_blank_or_junk_scores_low(self):
        count = 0
        for topic, questions in WRITTEN["python"].items():
            for q in questions:
                count += 1
                label = f"{topic}: {q['type']}"
                self.assertGreaterEqual(evaluate_answer(q, q["model_answer"], q["model_code"])["score"], 85, label)
                self.assertEqual(evaluate_answer(q, "", "")["score"], 0, label)
                self.assertLessEqual(evaluate_answer(q, "I do not know", "x = ")["score"], 35, label)
                if q["type"] == "debug":   # handing the buggy code back must not earn marks
                    self.assertLessEqual(evaluate_answer(q, "", q["code"])["score"], 10, label)
        self.assertEqual(count, 48)

    def test_all_six_question_types_are_present(self):
        types = {q["type"] for qs in WRITTEN["python"].values() for q in qs}
        self.assertEqual(types, {"explain", "program", "predict_output", "debug", "explain_logic", "practical"})

    def test_spoken_bank_covers_all_python_topics(self):
        self.assertEqual(set(SPOKEN["python"]), set(WRITTEN["python"]))
        self.assertIn("for loop", SPOKEN["python"]["loops"]["prompt"])


class WrittenEvaluationTests(TestCase):
    def test_predict_output_exact_partial_and_extra_lines(self):
        q = q_of("operators", "predict_output")  # expected "3 2 8\nTrue"
        self.assertEqual(evaluate_answer(q, "3 2 8\nTrue", "")["score"], 100)
        self.assertEqual(evaluate_answer(q, "3 2 8  \r\nTrue\n", "")["score"], 100)      # whitespace tolerant
        self.assertEqual(evaluate_answer(q, "3 2 8\nFalse", "")["score"], 50)             # line-by-line credit
        self.assertEqual(evaluate_answer(q, "3 2 8\nTrue\nextra", "")["score"], 66.7)     # extra line costs marks
        self.assertEqual(evaluate_answer(q, "", "")["score"], 0)

    def test_code_is_never_executed(self):
        marker = os.path.join(tempfile.gettempdir(), "ga_should_not_exist.txt")
        if os.path.exists(marker):
            os.remove(marker)
        evil = f"open({marker!r}, 'w').write('x')\nimport os\nos.system('touch {marker}')"
        q = q_of("loops", "program")
        result = evaluate_answer(q, "", evil)
        self.assertFalse(os.path.exists(marker))
        self.assertTrue(any("valid Python" in d["label"] and d["passed"] for d in result["details"]))  # parsed only

    def test_syntax_error_is_reported(self):
        q = q_of("operators", "program")
        r = evaluate_answer(q, "", "if x print(1")
        self.assertTrue(any("Syntax problem" in f for f in r["feedback"]))
        self.assertLess(r["criteria"]["technical_correctness"], 60)

    def test_comments_do_not_satisfy_code_checks(self):
        q = q_of("loops", "program")
        r = evaluate_answer(q, "", "# for i in range(5): while True: print(1)\nx = 1")
        passed = {d["label"]: d["passed"] for d in r["details"] if d["group"] == "Code checks"}
        self.assertFalse(passed["A while loop"])
        self.assertEqual(strip_comments("x = 1  # while loop").strip(), "x = 1")

    def test_hash_inside_a_string_is_kept(self):
        self.assertIn('"#"', strip_comments('print("#")  # note'))

    def test_must_not_check_penalises_forbidden_function(self):
        q = q_of("lists", "program")
        using_max = "numbers = [4, 9, 2, 7]\nprint(max(numbers))"
        r = evaluate_answer(q, "", using_max)
        passed = {d["label"]: d["passed"] for d in r["details"] if d["group"] == "Code checks"}
        self.assertFalse(passed["Does not use max()"])

    def test_unchanged_buggy_code_gets_zero_code_marks(self):
        q = q_of("functions", "debug")
        r = evaluate_answer(q, "", q["code"] + "  # tried")
        self.assertEqual((r["criteria"]["technical_correctness"], r["criteria"]["code_logic"]), (0.0, 0.0))

    def test_key_points_are_listed_as_covered_or_missing(self):
        q = q_of("tuples", "explain")
        r = evaluate_answer(q, "A tuple is immutable so it cannot change.", "")
        labels = {d["label"]: d["passed"] for d in r["details"] if d["group"] == "Key points"}
        self.assertTrue(labels["A tuple is immutable (cannot be changed)"])
        self.assertFalse(labels["Tuples suit fixed data, such as coordinates or dictionary keys"])
        self.assertTrue(any(f.startswith("Missing key points") for f in r["feedback"]))

    def test_short_answer_gets_length_feedback_and_lower_quality(self):
        q = q_of("lists", "explain")
        short = evaluate_answer(q, "A list is ordered.", "")
        full = evaluate_answer(q, q["model_answer"], "")
        self.assertLess(short["criteria"]["explanation_quality"], full["criteria"]["explanation_quality"])
        self.assertTrue(any("fuller explanation" in f for f in short["feedback"]))

    def test_example_is_required_when_asked(self):
        q = q_of("operators", "explain")
        no_example = "The slash does float division and double slash does floor division and percent gives the remainder in Python."
        self.assertTrue(any("Add a short example" in f for f in evaluate_answer(q, no_example, "")["feedback"]))

    def test_scores_stay_between_0_and_100(self):
        for qs in WRITTEN["python"].values():
            for q in qs:
                for text, code in (("", ""), ("x" * 5000, "y" * 10000), (q["model_answer"], q["model_code"])):
                    s = evaluate_answer(q, text, code)["score"]
                    self.assertTrue(0 <= s <= 100)

    def test_pathological_code_does_not_crash_the_checker(self):
        q = q_of("loops", "program")
        for code in ("(" * 8000, "\x00bad", "def f(:\n" * 50):
            result = evaluate_answer(q, "", code)
            self.assertTrue(0 <= result["score"] <= 100)

    def test_generic_question_is_labelled_basic_and_checks_relevance(self):
        user = make_user()
        topic = make_topic(user, tech="SQL", name="Joins")
        q = services.written_questions_for(topic)[0]
        self.assertTrue(q["basic_only"])
        on_topic = evaluate_answer(q, "A join combines rows from two tables. For example, SELECT * FROM a JOIN b. It is used in SQL.", "")
        off_topic = evaluate_answer(q, "I like cricket and football and many sports to play in the evening with friends.", "")
        self.assertGreater(on_topic["score"], off_topic["score"])
        self.assertIsNone(on_topic["criteria"]["technical_correctness"])


class SpeakingEvaluationTests(TestCase):
    Q = SPOKEN["python"]["loops"]
    GOOD = ("A for loop in Python repeats a block of code for each item in a sequence or a range. The loop variable takes "
            "each value one by one. For example, to print the numbers 1 to 5, I write for i in range(1, 6) and print i, "
            "because range stops before the end value. So the loop repeats five times.")
    POOR = "um i think loop is like basically doing things many time and it is more better. they is useful and i dont know much"

    def test_good_answer_beats_poor_answer_and_empty_is_zero(self):
        good, poor = evaluate_speaking(self.Q, self.GOOD), evaluate_speaking(self.Q, self.POOR)
        self.assertGreater(good["overall"], 85)
        self.assertLess(poor["overall"], 60)
        empty = evaluate_speaking(self.Q, "")
        self.assertEqual(empty["overall"], 0)
        self.assertEqual(set(good["criteria"]), {"concept_clarity", "relevance", "grammar", "sentence_formation",
                                                 "vocabulary", "fluency", "completeness"})

    def test_loop_variable_i_is_not_flagged_but_pronoun_i_is(self):
        issues = [i["message"] for i in evaluate_speaking(self.Q, self.GOOD)["details"]["issues"]]
        self.assertEqual(issues, [])
        bad = evaluate_speaking(self.Q, "i think a for loop repeats code.", "typed")
        self.assertTrue(any("capital letter" in i["message"] for i in bad["details"]["issues"]))

    def test_common_grammar_mistakes_are_found(self):
        text = "They is learning. She don't know it. It is more better. We have an book and a apple."
        messages = " ".join(i["message"] for i in evaluate_speaking(self.Q, text)["details"]["issues"])
        for expected in ("are", "doesn't", "comparative", "“a” before a consonant", "“an” before a vowel"):
            self.assertIn(expected, messages)

    def test_speech_without_punctuation_is_not_punished_for_missing_punctuation(self):
        text = "a for loop repeats a block of code for each item in a range for example range one to six because it stops early"
        speech = evaluate_speaking(self.Q, text, "speech", 25)
        typed = evaluate_speaking(self.Q, text, "typed")
        self.assertEqual(speech["criteria"]["grammar"], 100)
        self.assertLess(typed["criteria"]["grammar"], 100)          # typed text without full stops is flagged
        self.assertTrue(any("not judged" in n for n in speech["details"]["notes"]["grammar"]))

    def test_filler_words_reduce_fluency(self):
        clean = evaluate_speaking(self.Q, self.GOOD)["criteria"]["fluency"]
        filler = evaluate_speaking(self.Q, "Um, a for loop is, uh, basically, you know, a loop. Um, it repeats, like, code.")["criteria"]["fluency"]
        self.assertLess(filler, clean)

    def test_pace_is_only_measured_for_speech_with_a_duration(self):
        words = " ".join(["loop"] * 60)
        fast = evaluate_speaking(self.Q, words, "speech", 10)["details"]["stats"]["wpm"]
        self.assertEqual(fast, 360)
        self.assertIsNone(evaluate_speaking(self.Q, words, "typed", 10)["details"]["stats"]["wpm"])
        self.assertIsNone(evaluate_speaking(self.Q, words, "speech", 3)["details"]["stats"]["wpm"])

    def test_result_is_honest_about_what_is_not_measured(self):
        text = evaluate_speaking(self.Q, self.GOOD)["details"]["limitations"].lower()
        for word in ("pronunciation", "confidence", "not measured"):
            self.assertIn(word, text)

    def test_missing_example_is_called_out(self):
        r = evaluate_speaking(self.Q, "A for loop repeats code for each item in a sequence.", "typed")
        self.assertTrue(any("example" in t.lower() for t in r["details"]["tips"]))


class ServiceTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.topic = make_topic(self.user)

    def test_start_written_builds_three_questions_from_the_bank(self):
        a, created = services.start_written(self.user, self.topic)
        self.assertTrue(created)
        self.assertEqual([x.question_type for x in a.answers.all()], ["explain", "predict_output", "program"])
        self.assertEqual((a.topic_name, a.technology_name, a.attempt_number), ("Loops", "Python", 1))

    def test_starting_again_resumes_the_same_open_attempt(self):
        first, _ = services.start_written(self.user, self.topic)
        again, created = services.start_written(self.user, self.topic)
        self.assertEqual((again.pk, created), (first.pk, False))
        self.assertEqual(WrittenAssessment.objects.count(), 1)
        self.assertEqual(WrittenAnswer.objects.count(), 3)

    def test_database_refuses_two_open_attempts_for_one_topic(self):
        services.start_written(self.user, self.topic)
        with self.assertRaises(IntegrityError), transaction.atomic():
            WrittenAssessment.objects.create(user=self.user, topic=self.topic, topic_name="Loops", attempt_number=9)

    def test_retake_after_submit_creates_attempt_two(self):
        a, _ = services.start_written(self.user, self.topic)
        services.submit_written(a)
        b, created = services.start_written(self.user, self.topic)
        self.assertTrue(created)
        self.assertEqual(b.attempt_number, 2)

    def test_submit_scores_locks_and_cannot_run_twice(self):
        a, _ = services.start_written(self.user, self.topic)
        post = {}
        for ans in a.answers.all():
            q = ans.question_data
            post[f"text_{ans.pk}"] = q["model_answer"]
            post[f"code_{ans.pk}"] = q.get("model_code", "")
        a, done = services.submit_written(a, post)
        self.assertTrue(done)
        self.assertGreaterEqual(a.score, 90)
        self.assertTrue(a.is_submitted)
        first_score = a.score
        # a second submit with different (empty) data must change nothing
        again, done2 = services.submit_written(a, {f"text_{x.pk}": "" for x in a.answers.all()})
        self.assertFalse(done2)
        again.refresh_from_db()
        self.assertEqual(again.score, first_score)

    def test_blank_submit_scores_zero(self):
        a, _ = services.start_written(self.user, self.topic)
        a, _ = services.submit_written(a, {})
        self.assertEqual(a.score, 0)

    def test_too_long_answer_is_rejected_and_nothing_saved(self):
        a, _ = services.start_written(self.user, self.topic)
        first = a.answers.first()
        with self.assertRaises(ValueError):
            services.apply_written_post(a, {f"text_{first.pk}": "x" * 5001})
        first.refresh_from_db()
        self.assertEqual(first.answer_text, "")

    def test_history_survives_topic_deletion(self):
        a, _ = services.start_written(self.user, self.topic)
        services.submit_written(a)
        self.topic.delete()
        a.refresh_from_db()
        self.assertIsNone(a.topic)
        self.assertEqual(a.topic_name, "Loops")
        self.assertEqual(a.answers.count(), 3)

    def test_generic_topic_uses_lesson_interview_question_when_available(self):
        topic = make_topic(self.user, tech="SQL", name="Joins")
        LearningContent.objects.create(user=self.user, topic=topic, definition="A join combines rows.",
                                       interview_questions="- What is an inner join?\n- What is a left join?")
        qs = services.written_questions_for(topic)
        self.assertEqual(len(qs), 3)
        self.assertEqual(qs[2]["prompt"], "Interview question: What is an inner join?")
        self.assertIn("A join combines rows.", qs[0]["model_answer"])

    def test_speaking_start_resume_and_submit(self):
        s, created = services.start_speaking(self.user, self.topic)
        self.assertTrue(created)
        self.assertIn("for loop", s.question_text)
        self.assertEqual(services.start_speaking(self.user, self.topic), (s, False))
        s, done = services.submit_speaking(s, SpeakingEvaluationTests.GOOD, "raw text", "speech", 30)
        self.assertTrue(done)
        self.assertEqual((s.answer.input_method, s.answer.speaking_seconds, s.answer.raw_transcript), ("speech", 30, "raw text"))
        self.assertGreater(s.answer.overall, 80)

    def test_speaking_double_submit_creates_one_answer(self):
        s, _ = services.start_speaking(self.user, self.topic)
        services.submit_speaking(s, "A for loop repeats code.", "", "typed", 0)
        _, done = services.submit_speaking(s, "Something else entirely.", "", "typed", 0)
        self.assertFalse(done)
        self.assertEqual(SpeakingAnswer.objects.count(), 1)

    def test_speaking_validation_and_clamping(self):
        s, _ = services.start_speaking(self.user, self.topic)
        with self.assertRaises(ValueError):
            services.submit_speaking(s, "   ")
        with self.assertRaises(ValueError):
            services.submit_speaking(s, "x " * 3000)
        s, _ = services.submit_speaking(s, "A for loop repeats code.", "", "hacked", 999999)
        self.assertEqual((s.answer.input_method, s.answer.speaking_seconds), ("typed", 1800))

    def test_generic_spoken_question_names_the_topic(self):
        topic = make_topic(self.user, tech="SQL", name="Joins")
        q = services.spoken_question_for(topic)
        self.assertIn("Joins", q["prompt"])
        self.assertIn("real-time example", q["prompt"])

    def test_overview_stats_are_separate_for_written_and_speaking(self):
        a, _ = services.start_written(self.user, self.topic)
        services.submit_written(a)
        s, _ = services.start_speaking(self.user, self.topic)
        services.submit_speaking(s, SpeakingEvaluationTests.GOOD, "", "typed", 0)
        stats = services.overview_stats(self.user)
        self.assertEqual((stats["written_count"], stats["written_avg"]), (1, 0))
        self.assertEqual(stats["speaking_count"], 1)
        self.assertGreater(stats["speaking_avg"], 80)


class WrittenViewTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.topic = make_topic(self.user)
        self.client.force_login(self.user)

    def start(self):
        r = self.client.post(reverse("assessments:written_start", args=[self.topic.pk]))
        a = WrittenAssessment.objects.get(user=self.user, status="in_progress")
        self.assertRedirects(r, reverse("assessments:written_detail", args=[a.pk]))
        return a

    def test_start_requires_post(self):
        self.assertEqual(self.client.get(reverse("assessments:written_start", args=[self.topic.pk])).status_code, 405)

    def test_take_page_has_code_editor_and_all_questions(self):
        a = self.start()
        r = self.client.get(reverse("assessments:written_detail", args=[a.pk]))
        self.assertContains(r, "Question 3")
        self.assertContains(r, "data-code")
        self.assertContains(r, "never run")
        self.assertContains(r, "Predict the output")

    def test_debug_question_prefills_the_buggy_code(self):
        topic = make_topic(self.user, name="Functions")
        self.client.post(reverse("assessments:written_start", args=[topic.pk]))
        a = WrittenAssessment.objects.get(topic=topic)
        r = self.client.get(reverse("assessments:written_detail", args=[a.pk]))
        self.assertContains(r, "n * n")

    def test_save_draft_keeps_answers_and_stays_open(self):
        a = self.start()
        ans = a.answers.first()
        r = self.client.post(reverse("assessments:written_detail", args=[a.pk]),
                             {"action": "save", f"text_{ans.pk}": "My draft answer"})
        self.assertRedirects(r, reverse("assessments:written_detail", args=[a.pk]))
        ans.refresh_from_db(); a.refresh_from_db()
        self.assertEqual(ans.answer_text, "My draft answer")
        self.assertEqual(a.status, "in_progress")
        self.assertContains(self.client.get(reverse("assessments:written_detail", args=[a.pk])), "My draft answer")

    def test_submit_then_result_page_shows_scores_feedback_and_model_answer(self):
        a = self.start()
        post = {"action": "submit"}
        for ans in a.answers.all():
            post[f"text_{ans.pk}"] = ans.question_data["model_answer"]
            post[f"code_{ans.pk}"] = ans.question_data.get("model_code", "")
        r = self.client.post(reverse("assessments:written_detail", args=[a.pk]), post)
        self.assertRedirects(r, reverse("assessments:written_result", args=[a.pk]))
        page = self.client.get(reverse("assessments:written_result", args=[a.pk]))
        for text in ("Technical correctness", "Show model answer", "Key points", "Code checks", "indicative score"):
            self.assertContains(page, text)
        # locked: the take page now redirects to the results
        self.assertRedirects(self.client.get(reverse("assessments:written_detail", args=[a.pk])),
                             reverse("assessments:written_result", args=[a.pk]))

    def test_result_before_submit_redirects_to_take_page(self):
        a = self.start()
        self.assertRedirects(self.client.get(reverse("assessments:written_result", args=[a.pk])),
                             reverse("assessments:written_detail", args=[a.pk]))

    def test_submitting_twice_does_not_rescore(self):
        a = self.start()
        url = reverse("assessments:written_detail", args=[a.pk])
        self.client.post(url, {"action": "submit"})
        a.refresh_from_db()
        stamp = a.submitted_at
        self.client.post(url, {"action": "submit", f"text_{a.answers.first().pk}": "late edit"})
        a.refresh_from_db()
        self.assertEqual(a.submitted_at, stamp)
        self.assertEqual(a.answers.first().answer_text, "")

    def test_answer_text_is_escaped_on_the_result_page(self):
        a = self.start()
        ans = a.answers.first()
        self.client.post(reverse("assessments:written_detail", args=[a.pk]),
                         {"action": "submit", f"text_{ans.pk}": "<script>alert(1)</script>"})
        page = self.client.get(reverse("assessments:written_result", args=[a.pk]))
        self.assertNotContains(page, "<script>alert(1)</script>")
        self.assertContains(page, "&lt;script&gt;alert(1)&lt;/script&gt;")

    def test_too_long_answer_shows_error_and_keeps_assessment_open(self):
        a = self.start()
        ans = a.answers.first()
        r = self.client.post(reverse("assessments:written_detail", args=[a.pk]),
                             {"action": "submit", f"text_{ans.pk}": "x" * 6000})
        self.assertContains(r, "too long")
        a.refresh_from_db()
        self.assertEqual(a.status, "in_progress")


class SpeakingViewTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.topic = make_topic(self.user)
        self.client.force_login(self.user)
        self.client.post(reverse("assessments:speaking_start", args=[self.topic.pk]))
        self.a = SpeakingAssessment.objects.get(user=self.user)
        self.url = reverse("assessments:speaking_detail", args=[self.a.pk])

    def test_page_has_question_and_speech_controls(self):
        r = self.client.get(self.url)
        for text in ("Explain how a for loop works", "btn-start", "btn-stop", "Read the question aloud", "Typing is always allowed"):
            self.assertContains(r, text)

    def test_typed_submit_shows_result_with_limits(self):
        r = self.client.post(self.url, {"final_text": SpeakingEvaluationTests.GOOD, "input_method": "typed",
                                        "raw_transcript": "", "speaking_seconds": "0"})
        self.assertRedirects(r, reverse("assessments:speaking_result", args=[self.a.pk]))
        page = self.client.get(reverse("assessments:speaking_result", args=[self.a.pk]))
        for text in ("Concept clarity", "Grammar", "Fluency", "Pronunciation", "not measured"):
            self.assertContains(page, text)

    def test_speech_submit_records_transcript_and_edits(self):
        self.client.post(self.url, {"final_text": "A for loop repeats code.", "input_method": "speech",
                                    "raw_transcript": "a for loop repeat code", "speaking_seconds": "12"})
        page = self.client.get(reverse("assessments:speaking_result", args=[self.a.pk]))
        self.assertContains(page, "Original speech-to-text")
        self.assertContains(page, "a for loop repeat code")

    def test_empty_answer_rejected_and_text_kept_on_error(self):
        r = self.client.post(self.url, {"final_text": "  "})
        self.assertContains(r, "Please speak or type")
        self.a.refresh_from_db()
        self.assertEqual(self.a.status, "in_progress")

    def test_xss_in_transcript_is_escaped(self):
        self.client.post(self.url, {"final_text": "<img src=x onerror=alert(1)> loop"})
        page = self.client.get(reverse("assessments:speaking_result", args=[self.a.pk]))
        self.assertNotContains(page, "<img src=x")

    def test_submitted_page_redirects_to_result(self):
        self.client.post(self.url, {"final_text": "A loop repeats code."})
        self.assertRedirects(self.client.get(self.url), reverse("assessments:speaking_result", args=[self.a.pk]))


class HubAndAccessTests(TestCase):
    def setUp(self):
        self.alice, self.bob = make_user("alice"), make_user("bob")
        self.topic = make_topic(self.alice)
        a, _ = services.start_written(self.alice, self.topic)
        services.submit_written(a)
        s, _ = services.start_speaking(self.alice, self.topic)
        services.submit_speaking(s, "A for loop repeats code.", "", "typed", 0)
        self.w, self.s = a, s

    def test_anonymous_redirected(self):
        for name, arg in (("assessments:overview", None), ("assessments:topic_hub", self.topic.pk),
                          ("assessments:written_result", self.w.pk), ("assessments:speaking_result", self.s.pk)):
            url = reverse(name, args=[arg] if arg else [])
            self.assertEqual(self.client.get(url).status_code, 302, name)

    def test_other_user_gets_404(self):
        self.client.force_login(self.bob)
        for name, pk in (("assessments:topic_hub", self.topic.pk), ("assessments:written_detail", self.w.pk),
                         ("assessments:written_result", self.w.pk), ("assessments:speaking_detail", self.s.pk),
                         ("assessments:speaking_result", self.s.pk)):
            self.assertEqual(self.client.get(reverse(name, args=[pk])).status_code, 404, name)
        self.assertEqual(self.client.post(reverse("assessments:written_start", args=[self.topic.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("assessments:speaking_start", args=[self.topic.pk])).status_code, 404)
        answer = self.w.answers.first()
        self.assertEqual(self.client.post(reverse("assessments:written_ai", args=[answer.pk])).status_code, 404)

    def test_bobs_lists_never_show_alices_attempts(self):
        self.client.force_login(self.bob)
        page = self.client.get(reverse("assessments:overview"))
        self.assertNotContains(page, "Loops")
        self.assertEqual(page.context["stats"]["written_count"], 0)

    def test_hub_shows_separate_scores_and_history(self):
        self.client.force_login(self.alice)
        page = self.client.get(reverse("assessments:topic_hub", args=[self.topic.pk]))
        self.assertContains(page, "Stage 1: Written assessment")
        self.assertContains(page, "Stage 2: English speaking")
        self.assertContains(page, "Review answers")
        self.assertContains(page, "Review answer")
        self.assertContains(page, "Retake written test")

    def test_overview_lists_completed_topics_that_still_need_assessing(self):
        fresh = make_topic(self.alice, name="Functions")
        set_topic_status(self.alice, fresh, "completed")
        set_topic_status(self.alice, self.topic, "completed")   # fully assessed: should not be listed
        self.client.force_login(self.alice)
        page = self.client.get(reverse("assessments:overview"))
        names = [t.name for t in page.context["ready"]]
        self.assertEqual(names, ["Functions"])

    def test_dashboard_shows_assessment_averages(self):
        self.client.force_login(self.alice)
        page = self.client.get(reverse("dashboard:index"))
        self.assertEqual(page.context["assess"]["written_count"], 1)
        self.assertContains(page, "Written average")

    def test_topic_page_links_to_assessments(self):
        self.client.force_login(self.alice)
        page = self.client.get(reverse("learning:topic_detail", args=[self.topic.pk]))
        self.assertContains(page, reverse("assessments:topic_hub", args=[self.topic.pk]))


class AIFeedbackTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.topic = make_topic(self.user)
        a, _ = services.start_written(self.user, self.topic)
        services.submit_written(a)
        self.a = a
        self.answer = a.answers.first()
        self.client.force_login(self.user)
        self.url = reverse("assessments:written_ai", args=[self.answer.pk])

    def test_disabled_by_default_and_button_hidden(self):
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": ""}):
            page = self.client.get(reverse("assessments:written_result", args=[self.a.pk]))
            self.assertNotContains(page, "Get AI feedback")
            r = self.client.post(self.url, follow=True)
            self.assertContains(r, "AI feedback is not set up")

    def test_enabled_saves_feedback_without_changing_the_score(self):
        score = self.answer.score
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}), \
             mock.patch("assessments.views.ai.get_ai_feedback", return_value="Nice start. Add an example."):
            page = self.client.get(reverse("assessments:written_result", args=[self.a.pk]))
            self.assertContains(page, "Get AI feedback")
            r = self.client.post(self.url, follow=True)
            self.assertContains(r, "Nice start. Add an example.")
            self.assertContains(r, "not part of your score")
        self.answer.refresh_from_db()
        self.assertEqual(self.answer.score, score)

    def test_ai_error_is_shown_politely(self):
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "k"}), \
             mock.patch("assessments.views.ai.get_ai_feedback", side_effect=ai.AIError("The AI service could not be reached.")):
            r = self.client.post(self.url, follow=True)
            self.assertContains(r, "could not be reached")

    def test_ai_text_is_escaped(self):
        self.answer.ai_feedback = "<script>x</script>"
        self.answer.save()
        page = self.client.get(reverse("assessments:written_result", args=[self.a.pk]))
        self.assertNotContains(page, "<script>x</script>")

    def test_get_ai_feedback_builds_a_proper_request_and_parses_the_reply(self):
        captured = {}

        class FakeResponse(io.BytesIO):
            def __enter__(self): return self
            def __exit__(self, *a): return False

        def fake_urlopen(req, timeout=0):
            captured["url"], captured["headers"] = req.full_url, dict(req.header_items())
            captured["body"] = json.loads(req.data)
            return FakeResponse(json.dumps({"content": [{"type": "text", "text": "Good answer."}]}).encode())

        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "secret-key"}), \
             mock.patch("assessments.ai.urllib.request.urlopen", fake_urlopen):
            self.assertEqual(ai.get_ai_feedback("Q?", "my text", "print(1)"), "Good answer.")
        self.assertEqual(captured["url"], "https://api.anthropic.com/v1/messages")
        self.assertEqual(captured["headers"]["X-api-key"], "secret-key")
        self.assertIn("my text", captured["body"]["messages"][0]["content"])

    def test_network_failure_becomes_ai_error(self):
        import urllib.error
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "k"}), \
             mock.patch("assessments.ai.urllib.request.urlopen", side_effect=urllib.error.URLError("down")):
            with self.assertRaises(ai.AIError):
                ai.get_ai_feedback("Q", "a", "")
