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
   /schedule/import: paste the 課表 table copied from 校務資訊系統 -> timetable_import.py (time rows, TAB cells,
   header weekdays, merge periods <= 20 min apart, skip 落選/停修) -> Preview, then Import (re-parsed, validate_class,
   duplicates skipped, optional replace). Sample: tests/nthu_timetable_copy.txt.
   Home "Classes today": Now/Next chips (schedule_logic.class_states) and the walk to the next class
   (map_logic.day_route/walk_leg: haversine x DETOUR 1.3 / 80 m per min; red when longer than the break).
2. Study planning - DONE (/study page: tasks with subtasks and due dates, subjects with
   materials, study-time log; study_logic.py + /api/subjects, /api/tasks, /api/sessions).
   Open tasks with a due date are also shown (read-only) on the Calendar.
3. Credit & GPA tracking - DONE (/gpa page: courses per semester, weighted GPA,
   credit progress, needed average for a target GPA; gpa_logic.py + /api/courses, /api/goals).
4. Campus Announcements & Deadline Tracker - fetch from the NTHU Data API,
   filter by office (grouped by parent unit, "group:<unit>" filters a whole unit) keyword, language and
   category (Scholarship / Dorm / Careers / Admissions / Registration / Exchange / Campus notices /
   Events / Other, guessed from the title by classify(); English keywords match whole words),
   latest 5 on the home page, "Save to Calendar" button. Dates are cleaned (clean_date) and
   duplicates (office, title, date) dropped in normalize(). Tabs ?view=deadlines / ?view=events
   (upcoming_dates(kind="deadline"|"event"): next 60 days; is_deadline = DEADLINE_WORDS in title, otherwise the
   title date is just when a talk/event happens). Home page block "Upcoming events" shows only talks/events (HOME_EVENT_DAYS = 14).
   The button saves on the date found in the title (deadline_logic.suggest_date: Republic of
   China years like 115年10月08日, 2026-11-20, 11月20日, "Nov 20"...), else on the posted date,
   and the page says "date found in the title" so users can check the guess.
   If the API cannot be reached (PythonAnywhere free plan blocks api.nthusa.tw), fetch_announcements()
   falls back to data/announcements_snapshot.json (made by python tools/save_announcements.py), then to
   sample data; it returns (items, notice) with notice None / {"kind": "snapshot"|"sample", ...}.
   Auto update: .github/workflows/update-announcements.yml (twice a day) runs save_announcements.py --output
   and tools/upload_snapshot.py, which uploads to instance/announcements_snapshot.json via the PythonAnywhere
   files API (secrets PA_USERNAME, PA_TOKEN). load_snapshot() uses the newer of data/ and instance/ (by saved_at).
5. Campus map - DONE (/map: MapLibre GL JS + OpenFreeMap tiles, 2D/3D toggle, search by name,
   abbreviation or room ("Delta 205", "綜三 B101", course-system codes "PHYS物 019" via ROOM_CODES), category filter, nearest food / bus / shop,
   today's classes linked to buildings; map_logic.py + /api/places, /api/places/search, /api/places/<id>).
   Place data: data/nthu_osm.csv from OpenStreetMap (refresh with python tools/fetch_map_data.py).
Accounts: sign-up / log-in / log-out with sessions. Login lockout: 5 failures per email+IP or 20 per IP
   in 15 minutes -> 429 (login_guard.py decides, db.login_failures stores). PRODUCTION=1 env var ->
   Secure cookies + ProxyFix (real client IP on PythonAnywhere) + HSTS.
   "Remember me" checkbox -> session.permanent (30 days). /account: change password (current password required)
   and delete account (password + tick box; ON DELETE CASCADE). Sessions carry auth = account_logic.auth_tag
   (HMAC of the password hash); a mismatch logs the session out, so changing the password logs out other devices.
   g.user never contains password_hash (kept in g.password_hash).
Security headers on every response (app.SECURITY_HEADERS): X-Frame-Options DENY, CSP frame-ancestors 'none',
   nosniff, Referrer-Policy. Snapshot notice: quiet "Updated ..." line unless older than nthu_api.STALE_HOURS (48).
Dates: "today" is always calendar_logic.today_tw() (Asia/Taipei, UTC+8); never date.today().
Errors: 404/500 -> templates/error.html (JSON for /api/). Home: one-line onboarding strip (home_logic.py, Hide -> cookie "onboarding"),
   name suggestions <datalist> on GPA/Study.
UI: hamburger dropdown menu (base.html), one colour per feature (body.theme-*), home page
   "today" panel (classes today + tasks due, study_logic.due_today).
Phone layout (<= 720px, see GIAI_THICH_MOBILE.md): bottom tab bar (home_logic.TABS/current_tab; "More" opens the
   menu as a sheet; no backdrop-filter on the top bar there), tiles hidden, Calendar shows week strip + day agenda
   (calendar_logic.week_strip/day_agenda, ?day=YYYY-MM-DD) instead of the month grid, FAB to add.
   Announcements: search bar, category chips, "More filters", nthu_api.highlight -> <mark>, "Added" toast.
   GPA cards: gpa_logic.goal_status/grades_needed/credits_by_year, target slider. Study analytics:
   study_logic.analytics (daily bars, conic-gradient donut, % vs previous period, streak).
   Calendar sync: ics_export.py, table calendar_feeds (secret token), /calendar/feed/<token>.ics (one-way).
   Google Calendar shown INSIDE the app (update 23): ics_import.py parses a secret iCal link or an uploaded .ics
   (RRULE DAILY/WEEKLY/MONTHLY/YEARLY, EXDATE, RECURRENCE-ID, TZID); tables calendar_imports + imported_events;
   POST /account/calendar-import (connect/sync/upload/disconnect); refresh every 30 min when Calendar opens.
   Imported events are read-only (negative ids). SSRF guard: https only, hosts calendar.google.com,
   outlook.office365.com, outlook.live.com, *.icloud.com; redirects re-checked; max 3 MB.
   Map "My location": MapLibre GeolocateControl + POST /api/places/near (map_logic.near_me); position not stored.
   Notifications bell: home_logic.notifications, /notifications.
Languages: English + Traditional Chinese (i18n.py ZH dict, {{ _('...') }} in templates, cookie "lang",
   Accept-Language fallback, API errors translated in after_request, JS strings via window.I18N).
PWA: /manifest.webmanifest (pwa.py, translated), /sw.js (static/sw.js + CACHE_VERSION/OFFLINE_FILES from pwa.py;
   only serves /offline when the network fails, never caches personal pages), icons in static/icons/.
Themes: light / dark / auto (cookie "theme", <html data-theme>, CSS light-dark() tokens). POST /settings saves both.
Speed (see GIAI_THICH_TOCDO.md): snapshot parsed once per file mtime (nthu_api._read_snapshot, same list object so
   upcoming_dates memo stays valid), failed API retried after API_RETRY_SECONDS (1 h) with API_TIMEOUT (3, 10),
   classify uses one combined regex per category, app.warm_caches() on start when PRODUCTION=1.
   Static URLs get ?v=<mtime> (app.add_static_version) and are cached 1 year immutable (cache_static).
   Google Fonts loaded non-blocking (media=print onload). Speculation rules prerender same-site links on hover/touch
   (excludes /logout, /calendar/feed/*, /static/*). PythonAnywhere already gzips responses.

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
home_logic.py           onboarding checklist, course/subject name suggestions (pure Python)
login_guard.py          login lockout rules (pure Python)
account_logic.py        password rules, session auth tag, remember-me length (pure Python)
timetable_import.py     parse the timetable copied from 校務資訊系統 (pure Python)
pwa.py                  web app manifest and offline cache list (pure Python)
ics_export.py           build the .ics calendar file for Google / Apple Calendar (pure Python)
ics_import.py           read an .ics file / Google Calendar secret link into events (pure Python)
i18n.py                 translations (zh-TW), language detection, dates/durations per language (pure Python)
map_logic.py            load/classify OSM places, search, room -> building, distances (pure Python)
data/nthu_osm.csv       NTHU places from OpenStreetMap (Overpass API, 2026-11-18)
tools/fetch_map_data.py downloads a fresh data/nthu_osm.csv from the Overpass API
tools/save_announcements.py  saves real announcements to data/announcements_snapshot.json (or --output PATH), Taiwan time
tools/upload_snapshot.py     uploads a snapshot to PythonAnywhere (files API); run by GitHub Actions
.github/workflows/update-announcements.yml  daily announcements update
db.py                   SQLite: users, events, courses, goals, subjects, tasks,
                        study_sessions, classes, login_failures, calendar_feeds, calendar_imports, imported_events tables, all SQL
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
GIAI_THICH_TOCDO.md     explanation of the speed work (caches, static versioning, prerender)
GIAI_THICH_MOBILE.md    explanation of the phone layout / mockup features (tabs, agenda, analytics, sync, bell)
GIAI_THICH_CAITIEN.md   explanation of the post-review fixes (dates, deadlines view, offices, onboarding, lockout)
templates/              base, home, announcements, calendar, calendar_year, schedule, gpa, study, map, login, signup, account, error, schedule_import, offline, notifications,
                        _macros.html (announcement macro), _icons.html (SVG icon macro)
static/                 style.css (design tokens at the top), app.js, map.js (map page only), sw.js, icons/
tests/                  pytest (570 tests): logic, auth, CSRF, API, data isolation

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
Before deploying, set the SECRET_KEY and PRODUCTION=1 environment variables (WSGI file) and turn on Force HTTPS.

## Conventions
- Keep functions short, with a one-line docstring (Vietnamese or English).
- Keep the Python share of the code above 50% (HTML/CSS/JS count against it); measured ~56% of non-blank lines (2026-11-19, without tests).
- Add a test for every new behaviour, especially security-related ones.
