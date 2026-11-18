# NTHU Campus & Daily Life Assistant

A website that helps NTHU students plan their days, track their studies and
keep up with campus announcements and deadlines. I2P Final Project.

## Features
- Accounts: sign up, log in, log out
- Personal Calendar: month view, add / edit / delete events
- Weekly Schedule: class timetable on the NTHU period grid (1-4, n, 5-9, a-d), with warnings when two classes overlap
- English / 繁體中文 and light / dark mode (switch in the top bar or the menu)
- Campus map: 2D/3D map of both Hsinchu campuses with search, categories, nearby food/bus stops and today's classes (data from OpenStreetMap)
- Campus Announcements & Deadline Tracker: live data from the NTHU Data API,
  filter by category, office, language or keyword, and save a deadline to your
  calendar with one click (the date is read from the title when it contains one)
- Credits & GPA: add courses per semester, weighted GPA on the NTHU scale (A+ = 4.3),
  credit progress, and the average grade you need to reach a target GPA
- Study planning: tasks that can be broken into steps (with due dates and overdue marks),
  subjects with their materials (links, notes), and a study-time log with weekly totals;
  task due dates also show up on the calendar

## Run locally
```
python -m venv venv
venv\Scripts\Activate.ps1      # Windows PowerShell
pip install -r requirements.txt
python app.py
```
Open http://127.0.0.1:5000

The SQLite database is created automatically in `instance/app.db`.
For deployment, set the `SECRET_KEY` environment variable.

## Tests
```
pip install pytest
python -m pytest
```

## Docs
- `CALENDAR_API.md`: the Calendar API
- `GIAI_THICH.md`, `GIAI_THICH_ACCOUNT_CALENDAR.md`, `GIAI_THICH_GPA.md`, `GIAI_THICH_STUDY.md`, `GIAI_THICH_SCHEDULE.md`, `GIAI_THICH_DEADLINE.md`: code walkthroughs (Vietnamese)

## Team
Nguyen Ba Tung Bach, Nguyen Duy Manh, Lam Trong Nhan
