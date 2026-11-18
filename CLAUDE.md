# Campus & Daily Life Assistant (NTHU) - I2P Final Project

## Project
3-person team, course "Introduction to Programming" (Python).
Website helping NTHU students with study and daily life.
Course rule: at least 50% of the code must be Python.
TA allows AI-written code as long as we understand it well enough to explain
it and to build the core features ourselves. When you write code, explain it
in simple words (the owner is a beginner), so we can answer TA questions.

## Features
1. Personal Calendar & General Schedule - DONE (month view with events and task deadlines,
   quick month/year jump, /calendar/year 12-month overview;
   /schedule weekly timetable on the NTHU period grid (PERIODS 1-4, n, 5-9, a-d) with overlap
   warnings and side-by-side lanes; schedule_logic.py build_timetable + /api/classes).
2. Study planning - DONE (/study page: tasks with subtasks and due dates, subjects with
   materials, study-time log; study_logic.py + /api/subjects, /api/tasks, /api/sessions).
   Open tasks with a due date are also shown (read-only) on the Calendar.
3. Credit & GPA tracking - DONE (/gpa page: courses per semester, weighted GPA,
   credit progress, needed average for a target GPA; gpa_logic.py + /api/courses, /api/goals).
4. Campus Announcements & Deadline Tracker - fetch from the NTHU Data API,
   filter by office, keyword, language and category (Scholarship / Dorm /
   Careers / Registration / Events / Other, guessed from the title by
   classify()), latest 5 on the home page, "Save to Calendar" button.
   The button saves on the date found in the title (deadline_logic.suggest_date: Republic of
   China years like 115年10月08日, 2026-11-20, 11月20日, "Nov 20"...), else on the posted date,
   and the page says "date found in the title" so users can check the guess.
   If the API cannot be reached (PythonAnywhere free plan blocks api.nthusa.tw), fetch_announcements()
   falls back to data/announcements_snapshot.json (made by python tools/save_announcements.py), then to
   sample data; it returns (items, notice) with notice None / {"kind": "snapshot"|"sample", ...}.
5. Campus map - DONE (/map: MapLibre GL JS + OpenFreeMap tiles, 2D/3D toggle, search by name,
   abbreviation or room ("Delta 205", "綜三 B101"), category filter, nearest food / bus / shop,
   today's classes linked to buildings; map_logic.py + /api/places, /api/places/search, /api/places/<id>).
   Place data: data/nthu_osm.csv from OpenStreetMap (refresh with python tools/fetch_map_data.py).
Accounts: sign-up / log-in / log-out with sessions.
UI: hamburger dropdown menu (base.html), one colour per feature (body.theme-*), home page
   "today" panel (classes today + tasks due, study_logic.due_today).
Languages: English + Traditional Chinese (i18n.py ZH dict, {{ _('...') }} in templates, cookie "lang",
   Accept-Language fallback, API errors translated in after_request, JS strings via window.I18N).
Themes: light / dark / auto (cookie "theme", <html data-theme>, CSS light-dark() tokens). POST /settings saves both.

## Stack
Flask, Jinja2 template inheritance + macros, requests, sqlite3 (stdlib, no ORM),
plain HTML/CSS (colour per feature, Google Fonts with system fallback), a little vanilla JavaScript (static/app.js).
Password hashing: werkzeug.security. No other packages without asking the team.

## Architecture rules (keep these)
- Python decides, JavaScript only displays. All validation lives in Python.
- SQL only in db.py, always parameterized (?). Every query on events includes
  user_id so users can never touch each other's data.
- Grade scale and passing rules live ONLY in gpa_logic.py (GRADE_POINTS, PASSING_POINTS).
  Courses and goals queries also include user_id.
- Study: any subject_id / parent_id sent by the client must be checked to belong to the
  current user (subject_exists(), get_task) before saving. Subtasks have one level only.
- Every POST/PUT/DELETE needs the CSRF token (form field csrf_token or header
  X-CSRF-Token). API errors are JSON {"error": "..."}.
- Never mutate the shared announcements cache; use copies (see mark_saved()).
- Every user-facing string goes through _() (templates) or t() (JS, keys in i18n.JS_KEYS) and needs a
  zh-TW entry in i18n.ZH; tests/test_i18n.py fails on a missing one. Never build sentences by concatenation.
- Colours: only CSS variables from the top of style.css (light-dark()); no new hard-coded colours.
- Map: classification, search, room matching and distances live in map_logic.py; static/map.js only
  draws. OpenStreetMap data is ODbL: keep the "© OpenStreetMap contributors" credit on /map.

## Folder structure
app.py                  routes, login/session, CSRF
nthu_api.py             fetch / normalize / classify / filter announcements
calendar_logic.py       validate_event, month grid, year overview, mark_saved (pure Python)
deadline_logic.py       read deadline/event dates from announcement titles (pure Python)
schedule_logic.py       validate_class, weekly timetable, overlap detection (pure Python)
study_logic.py          validate subject/task/session, task tree, week totals (pure Python)
gpa_logic.py            GPA maths, grade scale, validate_course / validate_goals (pure Python)
i18n.py                 translations (zh-TW), language detection, dates/durations per language (pure Python)
map_logic.py            load/classify OSM places, search, room -> building, distances (pure Python)
data/nthu_osm.csv       NTHU places from OpenStreetMap (Overpass API, 2026-11-18)
tools/fetch_map_data.py downloads a fresh data/nthu_osm.csv from the Overpass API
tools/save_announcements.py  saves real announcements to data/announcements_snapshot.json (run where the API is reachable)
db.py                   SQLite: users, events, courses, goals, subjects, tasks,
                        study_sessions, classes tables, all SQL
inspect_api.py          saves a short sample of the real API JSON to api_sample.json
CALENDAR_API.md         the Calendar API contract (implemented)
GIAI_THICH.md           explanation of the announcements part (Vietnamese)
GIAI_THICH_ACCOUNT_CALENDAR.md  explanation of accounts, database, calendar
GIAI_THICH_GPA.md       explanation of the Credit & GPA feature
GIAI_THICH_STUDY.md     explanation of the Study planning feature
GIAI_THICH_SCHEDULE.md  explanation of the weekly timetable
GIAI_THICH_DEADLINE.md  explanation of reading dates from announcement titles
GIAI_THICH_GIAODIEN.md  explanation of the year view, month jump, menu, colours, today panel
GIAI_THICH_MAP.md       explanation of the campus map
GIAI_THICH_NGONNGU.md   explanation of the two languages and light/dark mode
templates/              base, home, announcements, calendar, calendar_year, schedule, gpa, study, map, login, signup,
                        _macros.html (announcement macro), _icons.html (SVG icon macro)
static/                 style.css (design tokens at the top), app.js, map.js (map page only)
tests/                  pytest (385 tests): logic, auth, CSRF, API, data isolation

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
- Keep the Python share of the code above 50% (HTML/CSS/JS count against it); measured ~54% (2026-11-18, without tests).
- Add a test for every new behaviour, especially security-related ones.
