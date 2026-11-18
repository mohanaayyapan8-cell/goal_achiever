# Architecture

## Pattern
Django MVT (Model - View - Template). Models define data, views hold logic,
templates draw HTML. Each feature area is its own Django "app".

## Folder structure
```
goal_achiever/
├── manage.py
├── requirements.txt / .env.example / .gitignore / README.md
├── config/              project settings, root URLs, wsgi/asgi
├── templates/           shared templates (base.html, partials/, dashboard/)
├── static/              css/, js/ (Chart.js and speech JS added later)
├── docs/                architecture, database design, checklist
├── accounts/            registration, login, profile, timezone      (Phase 2)
├── dashboard/           landing page, dashboard                      (Phase 1, 3)
├── learning/            domains, technologies, topics, content, notes(Phase 3-4)
├── planner/             40-day plan, daily goals, rescheduling       (Phase 4)
├── assessments/         written + speaking assessments               (Phase 5)
├── aptitude/            quant, reasoning, verbal tests               (Phase 6)
├── coding/              DSA problems, submissions, sandbox mode      (Phase 6)
├── streaks/             streak rules, achievements                   (Phase 7)
├── notifications/       in-app + email reminders                     (Phase 7)
└── resume_builder/      resume, ATS checklist, PDF                   (Phase 8)
```
Each app will get its own `models.py`, `views.py`, `forms.py`, `urls.py`,
`tests.py` and a `templates/<app>/` folder.

## Key decisions
| Decision | Reason |
|---|---|
| Apps at top level (not nested) | Simplest for a beginner to navigate in VS Code |
| `.env` via python-dotenv | Secrets never reach GitHub |
| `dj-database-url` | Switch SQLite to PostgreSQL by editing one line in `.env` |
| WhiteNoise | Serves static files in production without extra servers |
| Private `MEDIA_ROOT` outside static | Resumes are only served through login-checked views |
| CSS variables for theme | Dark/light toggle needs no page reload |
| `USE_TZ = True` | Required for correct streak/day maths; per-user timezone in Phase 2 |
| Owner field on every user-data model | Every query filters by `request.user` so users never see each other's data |

## Security rule used everywhere
Every view that shows or changes user data is `@login_required` and fetches
objects with `get_object_or_404(Model, pk=pk, user=request.user)`. Permission
tests for this are written in each phase.

## Known technical limits (decided up front)
- **Speech**: Web Speech API works mainly in Chrome/Edge; a typed fallback is always provided. Pronunciation/confidence will NOT be claimed.
- **Code execution**: user code is never run inside Django. Phase 6 ships a safe write-and-manual-test mode; real test execution needs a separate sandbox (optional).
- **Background push notifications**: need service worker + push service; in-app and email reminders come first.
- **AI evaluation**: rubric-based scoring first, AI as optional integration.
- **ATS score**: only an indicative checklist score, clearly labelled.

## Phase 2 additions
- `accounts.UserProfile` (1:1 with User, auto-created by a signal): timezone, college, target role, bio, reminder time, email-reminder flag.
- `accounts.middleware.UserTimezoneMiddleware` activates the user's timezone each request.
- `accounts.utils.get_user_today(user)` is THE function every streak/daily-goal calculation must use for "today".
- Auth pages use Django's built-in, well-tested views (login, logout, password change/reset); only registration and profile are custom.

## Phase 3 additions
- `learning` models: Domain -> Technology -> Topic, plus LearningProgress (one row per topic: not_started / in_progress / completed, with the ORIGINAL completion time kept if completed twice). Every row has a `user` FK; names are unique per parent, case-insensitively, at database level.
- `learning/services.py` holds the logic (seeding, progress percentages); views stay thin.
- Default curriculum (`learning/seed_data.py`) is COPIED into each user's account on registration, so every default can be edited or deleted. "Load default curriculum" only adds what is missing.
- `base_app.html` + `partials/sidebar.html` = layout for logged-in pages. Future sections appear in the sidebar as disabled labels (no dead links).
- Dashboard charts: `static/js/dashboard.js`; data is passed with `json_script`; charts re-colour on dark/light toggle.
- Security: every view uses `get_object_or_404(..., user=request.user)`; deletes and status changes are POST-only; the `next` redirect is checked to stay on this site.

## Phase 4 additions
- `learning.LearningContent` (1:1 with Topic, 10 text sections) and `learning.UserNote`. Lessons are COPIED to each user (so they can edit them). `learning/content_data.py` holds the original Python lessons; other technologies get lessons by writing their own (Write lesson button) or by adding to this file. Lesson text is HTML-escaped before display (`rich_text` filter).
- `planner.DailyPlan` (40 rows per user, each with a calendar date) and `planner.DailyGoal` (title, optional topic, estimated minutes, pending/completed, reschedule history).
- Rules: goals are NEVER deleted or moved automatically. A past day with pending goals is shown as "incomplete" and the goals appear in an "Unfinished goals" list with Move/Done actions. Rescheduling remembers the ORIGINAL day and counts moves. Completed goals cannot be moved.
- `planner/services.py` takes `today` as a parameter (the user's local date from `accounts.utils.get_user_today`) so daily logic is testable and timezone-safe.
- Day completion for STREAKS (Phase 7) will additionally require both assessments (Phase 5).

## Phase 5 additions (assessments)
- Models: `WrittenAssessment` / `WrittenAnswer` (question + rubric stored as a snapshot in JSON, so old results never change) and `SpeakingAssessment` / `SpeakingAnswer`. Topic is SET_NULL with a name snapshot, so history survives deleting a topic. A partial unique constraint allows only ONE unfinished attempt per topic (no duplicate assessments); a retake is a new attempt number.
- `question_bank.py`: 48 written questions (6 types) and 16 spoken questions for the Python topics, each with a visible rubric. Other topics get generic questions (or the interview questions from the user's own lesson) marked "basic checks only".
- `evaluation.py` (written) and `speaking_eval.py` (spoken) are pure functions. WRITTEN: key-point regexes, code pattern checks and `ast.parse` syntax check; code is NEVER executed. SPOKEN: scored from transcript text only (concept, relevance, grammar, sentences, vocabulary, fluency, completeness); pronunciation and confidence are explicitly NOT measured; punctuation is not judged for speech transcripts.
- `ai.py`: optional AI feedback, off unless `ANTHROPIC_API_KEY` is set; shown separately; never changes the score; sends the answer to the Anthropic API.
- `static/js/speaking.js`: Web Speech API (dictation) + speechSynthesis (read aloud) with typed fallback.
- Phase 7 (streaks) will count a day only when the written AND speaking assessments for the day's topic are submitted: use `WrittenAssessment.submitted_at` / `SpeakingAssessment.submitted_at`.

## Phase 6 additions (aptitude + DSA)
### Aptitude
- `AptitudeQuestion` is a SHARED bank (216 questions, 28 topics). 128 are COMPUTED by `generators.py` (each calculates its own answer, fixed seeds, unique stems), 88 are hand-written in `bank_text.py`. The bank is (re)loaded by a `post_migrate` hook, so `migrate` is all you need.
- `AptitudeAttempt` copies the questions into the attempt (JSON), so old results never change. One unfinished test per user (partial unique constraint).
- Time limit is enforced on the SERVER: answers are autosaved while the clock runs; the endpoint refuses saves after the deadline; a final submit within a 20 s grace period counts; later posts are ignored (autosaved answers still count). A test left open is graded automatically when next opened.
- Answers and explanations are never sent to the browser until the test is submitted.
### DSA coding practice
- `CodingProblem` is a SHARED bank (26 problems, 9 topics, easy/medium/hard); `CodingSubmission` stores each attempt.
- SAFETY DESIGN: the Django server NEVER runs submitted code (a test scans the server modules for exec/eval/subprocess and proves a code-writing-a-file submission does nothing). Options for running tests:
  1. **Browser sandbox**: `coding_worker.js` loads Pyodide (Python compiled to WebAssembly, bundled in `static/js/vendor/pyodide/`) in a Web Worker in the student's own browser and runs `coding/harness.py`. A 10 s timeout terminates the worker (stops infinite loops). The browser reports pass/fail counts; these are SELF-REPORTED, labelled as such, and a report that skips tests can never mark a problem solved.
  2. **Manual mode**: save code; run the downloadable local test script on your own computer; optionally mark solved ("self-checked").
- `harness.py` is the single test runner used by the browser, the local script, and the project's own tests (trusted reference solutions only).
- A real server-side judge would need a container sandbox (Docker/gVisor/nsjail) or an external service; the `CodingSubmission.mode` field leaves room for that later.

## Phase 7 additions (streaks, badges, notifications)
- **What makes a day "complete"** (`streaks.services.day_progress`): the day's plan has at least one goal, every goal is done, AND at least one written and one speaking assessment were submitted on that LOCAL date (user's timezone, daylight-saving safe).
- **Rules** (documented at the top of `streaks/services.py`): each completed day = +1; ONE missed day interrupts the streak (warning) but keeps it; TWO missed days in a row reset it to 0; a new streak starts at the next completed day; nothing is ever deleted. `StreakRecord` (unique per user+date) stores `streak_after` and `missed_run_after`, so the streak is a chain of immutable rows and the same date can never count twice.
- **Immutability**: past days are settled once (completed when they happen, or "missed" by `sync()` after they are over) and never change. Today's own record is provisional and is withdrawn if the day stops being complete before midnight; badges are never withdrawn.
- **Fairness**: only days from when the challenge was created (`DailyPlan.created_at`) are judged, so starting a challenge with a past start date never creates instant misses. Records dated after "today" (possible after a timezone change) are ignored until that date arrives.
- **Wiring**: `streaks/signals.py` re-checks everything after any save of goals, assessments, aptitude attempts, coding submissions or topic progress (and is skipped when an account is being deleted). Pages and the poll endpoint also call `refresh()`.
- **Badges** (`streaks/badges.py`, 24 badges) are awarded idempotently with a notification each.
- **Notifications**: `Notification` has a `dedupe_key` (unique per user) so one event never notifies twice. The bell count comes from a context processor; `static/js/notifications.js` polls `/notifications/poll/` every minute (this also creates due reminders while a tab is open) and shows browser pop-ups only when the user turned them on AND the browser allowed them.
- **Reminders**: time in the user's profile; in-app reminder once per day if the day is incomplete; e-mail only through `manage.py send_reminders` (retries failed sends on its next run).
- **Known limits**: moving unfinished goals to another day can make a day count as complete (rescheduling is allowed by design); changing time zone mid-day can shift which date a day belongs to.

## Phase 8 additions (resume builder, PDF, uploads, review)
- **Models**: `Resume` + repeatable sections (`Education`, `Experience`, `Project`, `Certification`, `Achievement`, each with an `order`), `ResumeUpload` (private file), `ResumeReview` (saved result; keeps a name snapshot if the resume is later deleted; newest 50 kept).
- **One content source** (`content.py`): the preview page, the PDF and the plain text used by the review all come from `resume_content()`, so they always match. Layout "student" puts Education first, "professional" puts Experience first.
- **PDF** (`pdf.py`, reportlab): one column, real selectable text, standard Helvetica, standard headings, no tables/images/icons. Typographic characters are mapped; characters the font cannot show are listed on the preview page and appear as "?" (a known limit; the font is not Unicode).
- **Uploads** (`uploads.py`): extension + content sniffing, 2 MB limit, docx zip limits, random storage names, owner-only download via `FileResponse` (attachment, nosniff, no-store), file deleted with the record or account. Text extraction reads at most 10 PDF pages and 100,000 characters; damaged or password-protected files give friendly errors.
- **Review engine** (`ats.py`): pure functions; checks sections/headings (30 pts), contact details (10), formatting (15), bullet quality (20), writing (5) and, only with a job description, keyword coverage (20). Not-applicable checks are excluded from the total, so the score is always out of the applicable points. Every check shows points, detail and advice. Stores NO contact values (only booleans). Skill suggestions combine the job description, the target role and what the user practised in this app (topics completed, problems solved).
- **Honesty**: the UI and the stored result say "indicative checklist score, NOT an ATS score".
- Two new badges (Resume Started, Checklist Checked) through the existing signal mechanism.
