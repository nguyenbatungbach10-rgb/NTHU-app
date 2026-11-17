# Campus & Daily Life Assistant (NTHU) - I2P Final Project

## Project
3-person team, course "Introduction to Programming" (Python).
Website helping NTHU students with study and daily life.
Course rule: at least 50% of the code must be Python.
TA allows AI-written code as long as we understand it well enough to explain
it and to build the core features ourselves. When you write code, explain it
in simple words (the owner is a beginner), so we can answer TA questions.

## Features
1. Personal Calendar & General Schedule - DONE (month view, add/edit/delete).
2. Study planning - not built yet.
3. Credit & GPA tracking - DONE (/gpa page: courses per semester, weighted GPA,
   credit progress, needed average for a target GPA; gpa_logic.py + /api/courses, /api/goals).
4. Campus Announcements & Deadline Tracker - fetch from the NTHU Data API,
   filter by office, keyword, language and category (Scholarship / Dorm /
   Careers / Registration / Events / Other, guessed from the title by
   classify()), latest 5 on the home page, "Save to Calendar" button.
   Reading the real deadline from the title is a possible next step.
Accounts: sign-up / log-in / log-out with sessions.

## Stack
Flask, Jinja2 template inheritance + macros, requests, sqlite3 (stdlib, no ORM),
plain HTML/CSS (purple theme), a little vanilla JavaScript (static/app.js).
Password hashing: werkzeug.security. No other packages without asking the team.

## Architecture rules (keep these)
- Python decides, JavaScript only displays. All validation lives in Python.
- SQL only in db.py, always parameterized (?). Every query on events includes
  user_id so users can never touch each other's data.
- Grade scale and passing rules live ONLY in gpa_logic.py (GRADE_POINTS, PASSING_POINTS).
  Courses and goals queries also include user_id.
- Every POST/PUT/DELETE needs the CSRF token (form field csrf_token or header
  X-CSRF-Token). API errors are JSON {"error": "..."}.
- Never mutate the shared announcements cache; use copies (see mark_saved()).

## Folder structure
app.py                  routes, login/session, CSRF
nthu_api.py             fetch / normalize / classify / filter announcements
calendar_logic.py       validate_event, month grid, mark_saved (pure Python)
gpa_logic.py            GPA maths, grade scale, validate_course / validate_goals (pure Python)
db.py                   SQLite: users, events, courses, goals tables, all SQL
inspect_api.py          saves a short sample of the real API JSON to api_sample.json
CALENDAR_API.md         the Calendar API contract (implemented)
GIAI_THICH.md           explanation of the announcements part (Vietnamese)
GIAI_THICH_ACCOUNT_CALENDAR.md  explanation of accounts, database, calendar
GIAI_THICH_GPA.md       explanation of the Credit & GPA feature
templates/              base, home, announcements, calendar, gpa, login, signup,
                        _macros.html (Jinja macro shared by home and announcements)
static/                 style.css (purple theme), app.js
tests/                  pytest (105 tests): logic, auth, CSRF, API, data isolation

## NTHU Data API (GET https://api.nthusa.tw/announcements)
Returns a list of DEPARTMENTS. Each has title, link, language ("zh-tw"/"en"),
department, and articles: [{title, link, date}]. nthu_api.normalize() flattens
every article into {title, link, date, office, language, category}, newest first.
A real sample is in tests/api_sample.json.

## Run
python -m venv venv
venv\Scripts\Activate.ps1     (Windows PowerShell; first run
                               Set-ExecutionPolicy -Scope Process Bypass)
pip install -r requirements.txt
python app.py                 -> http://127.0.0.1:5000
python -m pytest              -> all tests
The database is created automatically in instance/app.db (not committed).
Before deploying, set the SECRET_KEY environment variable.

## Conventions
- Keep functions short, with a one-line docstring (Vietnamese or English).
- Add a test for every new behaviour, especially security-related ones.
