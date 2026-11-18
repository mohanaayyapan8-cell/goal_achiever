# GOAL ACHIEVER

Personal learning and placement-preparation platform (Django + SQLite).
Built in 10 phases. **Current status: Phase 8 complete (resume builder, PDF export and ATS-style review).**

## Run it (VS Code, Windows/macOS/Linux)
1. Install Python 3.12 and VS Code (with the "Python" extension).
2. Open this folder in VS Code (`File > Open Folder`), then open the terminal (`Ctrl+``).
3. Create and activate a virtual environment:
   - Windows: `python -m venv .venv` then `.venv\Scripts\activate`
   - macOS/Linux: `python3 -m venv .venv` then `source .venv/bin/activate`
4. `pip install -r requirements.txt`
5. Copy `.env.example` to `.env` (Windows: `copy .env.example .env`).
6. `python manage.py migrate`
7. `python manage.py createsuperuser`  (for the admin site)
8. `python manage.py runserver`
9. Open http://127.0.0.1:8000/

Run tests: `python manage.py test` (and the Node checks described in `tests_js/README.md`)

Existing users (e.g. your superuser) can get the starter curriculum and the Python lessons from the **Learning** page button, or with `python manage.py seed_defaults`.

Charts use Chart.js (MIT licence) and the coding sandbox uses Pyodide 0.26.4 (MPL-2.0), both bundled in `static/js/vendor/` so no internet is needed. The question banks (aptitude and coding) are loaded automatically every time you run `migrate`.

Password-reset emails are printed in the terminal while developing (console email backend).

## Docs
See `docs/ARCHITECTURE.md`, `docs/DATABASE_DESIGN.md`, `docs/CHECKLIST.md`.

## Git
```
git init
git add .
git commit -m "Phase 1: project setup"
```
Never commit `.env` or `db.sqlite3` (already in `.gitignore`).


## Reminders (optional)
- **In-app reminders** and the bell work automatically: they appear when you open the site, and every minute while a tab is open.
- **Browser pop-ups** work only while the site is open in a tab (turn on in Notifications > Reminder settings and allow the permission).
  They cannot reach you when the site is closed: that needs a service worker and a push service, which this project does not include.
- **E-mail reminders** need the command below to run regularly, because nothing else wakes the server up:
  `python manage.py send_reminders`
  - Linux/macOS (cron, every 15 minutes): `*/15 * * * * cd /path/to/goal_achiever && .venv/bin/python manage.py send_reminders`
  - Windows: Task Scheduler > create a task that runs `.venv\Scripts\python.exe manage.py send_reminders` every 15 minutes.
  - Set `EMAIL_BACKEND` and SMTP settings in `.env` to send real e-mail (in development the e-mail is printed in the terminal), and `SITE_URL` for the links.


## Resume module: privacy notes
- Uploaded resumes are stored in `private_media/` (outside any public folder, ignored by Git) under random file names, and are only sent to their owner through a login-protected page. Deleting an upload or an account deletes the files.
- Uploads are checked by extension AND content (real PDF/DOCX/TXT, 2 MB limit, zip-bomb limits). They are never executed.
- Back up `private_media/` together with the database. Some hosts have temporary disks that are wiped on restart; when you deploy (Phase 10) use a persistent disk or object storage, otherwise uploads will disappear.
- The review score is an **indicative checklist score**, not an ATS score. Your text is analysed on your own server only.
