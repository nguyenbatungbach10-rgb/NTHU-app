# Campus & Daily Life Assistant (NTHU) - I2P Final Project

## Project
3-person team, course "Introduction to Programming" (Python).
Website helping NTHU students with study and daily life.
Course rule: at least 50% of the code must be Python.
TA allows AI-written code as long as we understand it well enough to explain
it and to build the core features ourselves. When you write code, explain it
in simple words (the owner is a beginner), so we can answer TA questions.

## Team and modules
- Bach: Announcements & Deadline Tracker (NTHU Data API, JSON, Jinja2)
- Manh: database (SQLite), sign-up/login, Calendar API
- Nhan: base layout, dashboard, Personal Calendar UI

## Features
1. Personal Calendar & General Schedule
2. Study planning (not built yet)
3. Credit & GPA tracking (not built yet)
4. Campus Announcements & Deadline Tracker: fetch from the NTHU Data API,
   filter by office, keyword, language and category (Scholarship / Dorm /
   Careers / Registration / Events / Other, guessed from the title by
   classify()), latest 5 on the home page, save important deadlines to the
   Calendar (contract in CALENDAR_API.md).

## Stack
Flask, Jinja2 template inheritance, requests, plain HTML/CSS (purple theme).
SQLite and session login are Manh's part (not in this repo yet).

## Folder structure
app.py                  Flask routes
nthu_api.py             fetch / normalize / filter announcements (pure Python)
inspect_api.py          saves a short sample of the real API JSON to api_sample.json
CALENDAR_API.md         contract for the Calendar API (Save to Calendar button)
templates/              base.html, home.html, announcements.html,
                        _macros.html (Jinja macro shared by home and announcements)
static/style.css        purple theme
tests/                  pytest: test_nthu_api.py (logic), test_app.py (routes)

## NTHU Data API (GET https://api.nthusa.tw/announcements)
Returns a list of DEPARTMENTS. Each has title, link, language ("zh-tw"/"en"),
department, and articles: [{title, link, date}]. nthu_api.normalize() flattens
every article into {title, link, date, office, language}, newest first.
A real sample is in tests/api_sample.json.

## Run
python -m venv venv
venv\Scripts\Activate.ps1     (Windows PowerShell)
pip install -r requirements.txt
python app.py                 -> http://127.0.0.1:5000

## Conventions
- Keep logic in Python files; JavaScript only for small UI behaviour.
- Keep functions short, with a one-line docstring.
- No new packages without asking the team.
