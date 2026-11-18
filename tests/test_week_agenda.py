"""Test lịch tuần + lịch trong ngày (giao diện điện thoại của trang Calendar)."""
from datetime import date

import calendar_logic as cl

DAY = date(2026, 11, 19)   # Thứ Năm
CLASSES = [{"id": 1, "weekday": 3, "start": "10:10", "end": "11:00", "name": "Calculus", "room": "GEN IV綜四224"},
           {"id": 2, "weekday": 3, "start": "08:00", "end": "09:50", "name": "Programming", "room": "DELTA台達217"},
           {"id": 3, "weekday": 0, "start": "08:00", "end": "09:50", "name": "Monday class", "room": ""}]
EVENTS = [{"id": 1, "date": "2026-11-19", "time": "18:30", "title": "Club meeting", "description": "SAC"},
          {"id": 2, "date": "2026-11-19", "time": "", "title": "Holiday", "description": ""},
          {"id": 3, "date": "2026-11-20", "time": "20:00", "title": "Project", "description": ""}]
TASKS = [{"id": 1, "due_date": "2026-11-19", "title": "I2P Lab 7"}]


def test_parse_day_and_week_start():
    assert cl.parse_day("2026-11-19") == DAY
    assert cl.parse_day("2026-13-01") is None and cl.parse_day("") is None and cl.parse_day(None) is None
    assert cl.parse_day("0001-01-01") is None
    assert cl.week_start(DAY) == date(2026, 11, 16) and cl.week_start(date(2026, 11, 16)) == date(2026, 11, 16)


def test_day_agenda_order_and_kinds():
    agenda = cl.day_agenda(DAY, CLASSES, EVENTS, TASKS)
    assert [(a["kind"], a["start"], a["title"]) for a in agenda] == [
        ("event", "", "Holiday"), ("class", "08:00", "Programming"), ("class", "10:10", "Calculus"),
        ("event", "18:30", "Club meeting"), ("deadline", "", "I2P Lab 7")]
    assert agenda[1]["sub"] == "DELTA台達217"
    assert cl.agenda_summary(agenda) == [("class", 2), ("event", 2), ("deadline", 1)]
    assert cl.agenda_summary([]) == []


def test_week_strip_counts():
    week = cl.week_strip(DAY, DAY, CLASSES, EVENTS, TASKS)
    assert [d["day"] for d in week] == [16, 17, 18, 19, 20, 21, 22]
    assert week[0]["counts"] == {"class": 1, "event": 0, "deadline": 0}
    assert week[3]["counts"] == {"class": 2, "event": 2, "deadline": 1} and week[3]["is_selected"] and week[3]["is_today"]
    assert week[4]["counts"]["event"] == 1 and not week[4]["is_selected"]


def test_calendar_page_shows_day_agenda(browser):
    browser.api("POST", "/api/classes", {"name": "Programming", "weekday": 3, "start": "08:00", "end": "09:50",
                                         "room": "DELTA台達217"})
    browser.api("POST", "/api/events", {"title": "Club meeting", "date": "2026-11-19", "time": "18:30"})
    browser.api("POST", "/api/tasks", {"title": "I2P Lab 7", "due_date": "2026-11-19"})
    html = browser.client.get("/calendar?day=2026-11-19").get_data(as_text=True)
    week = html.split('class="week-view"')[1].split('class="cal-wrap"')[0]
    assert "Programming" in week and "Club meeting" in week and "I2P Lab 7" in week
    assert "1 class" in week and "1 event" in week and "1 deadline" in week
    assert 'aria-current="date"' in week and "day=2026-11-12" in week and "day=2026-11-26" in week
    assert "November 2026" in html                                  # tháng theo ngày đã chọn


def test_calendar_day_crossing_month_and_bad_day(browser):
    browser.api("POST", "/api/events", {"title": "December thing", "date": "2026-12-01", "time": ""})
    html = browser.client.get("/calendar?day=2026-11-30").get_data(as_text=True)
    week = html.split('class="week-view"')[1].split('class="cal-wrap"')[0]
    assert "k-event" in week                                        # chấm của 1/12 vẫn hiện trong tuần
    assert browser.client.get("/calendar?day=hello").status_code == 200
