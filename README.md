# NTHU Campus & Daily Life Assistant

A website that helps NTHU students plan their days, track their studies and
keep up with campus announcements and deadlines. I2P Final Project.

## Features
- Accounts: sign up, log in, log out
- Personal Calendar: month view, add / edit / delete events
- Campus Announcements & Deadline Tracker: live data from the NTHU Data API,
  filter by category, office, language or keyword, and save a deadline to your
  calendar with one click
- Study planning and GPA tracking (in progress)

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
- `GIAI_THICH.md`, `GIAI_THICH_ACCOUNT_CALENDAR.md`: code walkthroughs (Vietnamese)

## Team
Nguyen Ba Tung Bach, Nguyen Duy Manh, Lam Trong Nhan
