"""Test đồng bộ lịch: file .ics đúng chuẩn và link bí mật."""
from datetime import date, datetime

import pytest

import ics_export as ix

TODAY = date(2026, 11, 19)
NOW = datetime(2026, 11, 18, 18, 0)
CLASSES = [{"id": 1, "weekday": 3, "start": "08:00", "end": "09:50", "name": "計算機程式設計", "room": "DELTA台達217"}]
EVENTS = [{"id": 2, "date": "2026-11-20", "time": "", "title": "Scholarship, deadline; apply", "description": "a\nb",
           "source_url": "https://example.com"},
          {"id": 3, "date": "2026-11-21", "time": "20:00", "title": "Project meeting", "description": "", "source_url": ""}]
TASKS = [{"id": 4, "due_date": "2026-11-22", "title": "Lab 7"}]


def test_helpers():
    assert ix.escape_text("a,b;c\\d\ne") == r"a\,b\;c\\d\ne"
    assert ix.utc_stamp(TODAY, "08:00") == "20261119T000000Z" and ix.utc_stamp(TODAY, "06:30") == "20261118T223000Z"
    assert ix.semester_end(TODAY) == date(2027, 1, 20) and ix.semester_end(date(2027, 1, 5)) == date(2027, 1, 20)
    assert ix.semester_end(date(2027, 3, 1)) == date(2027, 6, 30)
    assert ix.first_class_day(TODAY, 0) == date(2026, 11, 16) and ix.first_class_day(TODAY, 4) == date(2026, 11, 20)


def test_fold_line_keeps_lines_short_and_characters_whole():
    folded = ix.fold_line("SUMMARY:" + "致命優雅" * 20)
    lines = folded.split("\r\n")
    assert len(lines) > 1 and all(len(line.encode("utf-8")) <= 75 for line in lines)
    assert "".join(line[1:] if i else line for i, line in enumerate(lines)) == "SUMMARY:" + "致命優雅" * 20
    assert ix.fold_line("short") == "short"


def test_calendar_is_valid_icalendar():
    icalendar = pytest.importorskip("icalendar")         # thư viện chỉ dùng để kiểm tra, web không cần
    text = ix.build_calendar("NTHU", TODAY, NOW, CLASSES, EVENTS, TASKS)
    assert text.endswith("\r\n") and "\r\n" in text
    cal = icalendar.Calendar.from_ical(text)
    items = {str(e["UID"]): e for e in cal.walk("VEVENT")}
    lesson = items["class-1@nthu-campus-assistant"]
    assert str(lesson["SUMMARY"]) == "計算機程式設計" and str(lesson["LOCATION"]) == "DELTA台達217"
    assert lesson["DTSTART"].dt.isoformat() == "2026-11-19T00:00:00+00:00"
    assert lesson["RRULE"]["FREQ"] == ["WEEKLY"]
    assert str(items["event-2@nthu-campus-assistant"]["SUMMARY"]) == "Scholarship, deadline; apply"
    assert items["event-2@nthu-campus-assistant"]["DTSTART"].dt == date(2026, 11, 20)
    assert items["event-3@nthu-campus-assistant"]["DTEND"].dt.isoformat() == "2026-11-21T13:00:00+00:00"
    assert str(items["task-4@nthu-campus-assistant"]["SUMMARY"]) == "Due: Lab 7"


def turn_on(b, **choices):
    data = {"csrf_token": b.token(), "action": "save"}
    data.update({k: "1" for k, v in choices.items() if v})
    return b.client.post("/account/calendar-sync", data=data)


def feed_path(b):
    html = b.client.get("/account").get_data(as_text=True)
    url = html.split('id="feed-url" type="text" readonly value="')[1].split('"')[0]
    return url.split("localhost", 1)[1]


def test_feed_flow(browser, make_browser):
    browser.api("POST", "/api/classes", {"name": "Calculus", "weekday": 1, "start": "10:10", "end": "12:00"})
    browser.api("POST", "/api/events", {"title": "Club", "date": "2026-11-20", "time": "18:30"})
    browser.api("POST", "/api/tasks", {"title": "Lab 7", "due_date": "2026-11-22"})
    assert "Turn on calendar sync" in browser.client.get("/account").get_data(as_text=True)
    assert turn_on(browser, classes=True, events=True).status_code == 302
    path = feed_path(browser)
    assert path.startswith("/calendar/feed/") and path.endswith(".ics")
    html = browser.client.get("/account").get_data(as_text=True)
    assert "webcal://" in html and "calendar.google.com/calendar/r?cid=webcal" in html

    visitor = make_browser().client                                   # app lịch không có cookie đăng nhập
    response = visitor.get(path)
    body = response.get_data(as_text=True)
    assert response.status_code == 200 and response.mimetype == "text/calendar"
    assert "SUMMARY:Calculus" in body and "SUMMARY:Club" in body and "Lab 7" not in body

    turn_on(browser, classes=False, events=False, tasks=True)        # đổi lựa chọn, link giữ nguyên
    body = visitor.get(path).get_data(as_text=True)
    assert "Calculus" not in body and "SUMMARY:Due: Lab 7" in body


def test_new_link_and_off_stop_old_link(browser, make_browser):
    turn_on(browser, classes=True)
    old = feed_path(browser)
    browser.client.post("/account/calendar-sync", data={"csrf_token": browser.token(), "action": "reset", "classes": "1"})
    new = feed_path(browser)
    visitor = make_browser().client
    assert new != old and visitor.get(old).status_code == 404 and visitor.get(new).status_code == 200
    browser.client.post("/account/calendar-sync", data={"csrf_token": browser.token(), "action": "off"})
    assert visitor.get(new).status_code == 404
    assert "Turn on calendar sync" in browser.client.get("/account").get_data(as_text=True)


def test_feed_needs_login_to_change_and_unknown_token(make_browser):
    client = make_browser().client
    assert client.post("/account/calendar-sync", data={"action": "save"}).status_code in (302, 400)
    assert client.get("/calendar/feed/not-a-real-token.ics").status_code == 404


def test_feed_is_private_per_user(browser, make_browser):
    browser.api("POST", "/api/events", {"title": "Mine", "date": "2026-11-20", "time": ""})
    other = make_browser()
    other.signup("b@example.com")
    other.api("POST", "/api/events", {"title": "Theirs", "date": "2026-11-20", "time": ""})
    turn_on(other, events=True)
    body = make_browser().client.get(feed_path(other)).get_data(as_text=True)
    assert "Theirs" in body and "Mine" not in body
