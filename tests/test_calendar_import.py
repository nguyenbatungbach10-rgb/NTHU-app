"""Test hiện lịch Google (file .ics) ngay trong app: đọc file, kiểm tra link, tải về, hiện trên Calendar."""
import io
from datetime import date

import pytest
import requests

import app as app_module
import db
import ics_import as ii

TODAY = date(2026, 11, 23)
ICS = "\r\n".join([
    "BEGIN:VCALENDAR", "VERSION:2.0",
    "BEGIN:VEVENT", "UID:a", "DTSTART;TZID=Asia/Taipei:20261116T101000", "DTEND;TZID=Asia/Taipei:20261116T120000",
    "RRULE:FREQ=WEEKLY;BYDAY=MO,TH;UNTIL=20261204T155959Z", "EXDATE;TZID=Asia/Taipei:20261123T101000",
    "SUMMARY:Calculus\\, lecture", "LOCATION:GEN IV", "BEGIN:VALARM", "TRIGGER:-PT10M", "END:VALARM", "END:VEVENT",
    "BEGIN:VEVENT", "UID:a", "RECURRENCE-ID;TZID=Asia/Taipei:20261126T101000",
    "DTSTART;TZID=Asia/Taipei:20261126T140000", "DTEND;TZID=Asia/Taipei:20261126T150000", "SUMMARY:Calculus (moved)",
    "END:VEVENT",
    "BEGIN:VEVENT", "UID:b", "DTSTART;VALUE=DATE:20261125", "DTEND;VALUE=DATE:20261126", "SUMMARY:Holiday", "END:VEVENT",
    "BEGIN:VEVENT", "UID:c", "DTSTART:20261120T120000Z", "DURATION:PT2H", "SUMMARY:UTC meeting", "END:VEVENT",
    "BEGIN:VEVENT", "UID:d", "DTSTART:20261121T120000Z", "STATUS:CANCELLED", "SUMMARY:Cancelled", "END:VEVENT",
    "BEGIN:VEVENT", "UID:e", "DTSTART;VALUE=DATE:20250101", "SUMMARY:Too old", "END:VEVENT",
    "BEGIN:VEVENT", "UID:f", "DTSTART;TZID=America/New_York:20261201T090000", "SUMMARY:New York call",
    "DESCRIPTION:a very long des", " cription folded", "END:VEVENT",
    "END:VCALENDAR", ""])


# ---------- đọc file ----------

# Windows không có sẵn dữ liệu múi giờ (cần gói tzdata): khi đó giờ New York bị coi là giờ Đài Loan.
NEW_YORK_KNOWN = ii._zone("America/New_York") is not ii.TAIPEI


def test_parse_calendar_expands_repeats_and_converts_time():
    rows = ii.parse_calendar(ICS, TODAY)
    got = [(r["date"], r["time"], r["end_time"], r["title"]) for r in rows]
    assert got == [
        ("2026-11-16", "10:10", "12:00", "Calculus, lecture"),
        ("2026-11-19", "10:10", "12:00", "Calculus, lecture"),
        ("2026-11-20", "20:00", "22:00", "UTC meeting"),                  # 12:00 UTC = 20:00 Đài Loan
        ("2026-11-25", "", "", "Holiday"),                                # cả ngày
        ("2026-11-26", "14:00", "15:00", "Calculus (moved)"),             # buổi bị dời thay buổi gốc
        ("2026-11-30", "10:10", "12:00", "Calculus, lecture"),
        ("2026-12-01", "22:00" if NEW_YORK_KNOWN else "09:00", "", "New York call"),   # 09:00 New York = 22:00 Đài Loan
        ("2026-12-03", "10:10", "12:00", "Calculus, lecture"),            # UNTIL 4/12: hết sau buổi này
    ]                                                                     # 23/11 bị EXDATE bỏ; Cancelled, Too old: bỏ
    assert rows[0]["location"] == "GEN IV"


def test_parse_helpers():
    assert ii.unfold("A:1\r\n B\r\nC:2") == ["A:1B", "C:2"]
    assert ii.parse_line("DTSTART;TZID=Asia/Taipei:20261119T080000") == ("DTSTART", {"TZID": "Asia/Taipei"}, "20261119T080000")
    assert ii.unescape(r"a\, b\; c\nd\\e") == "a, b; c\nd\\e"
    assert ii.parse_duration("PT1H30M").seconds == 5400 and ii.parse_duration("P1D").days == 1 and ii.parse_duration("x") is None
    assert ii.parse_when("garbage", {}) == (None, False)
    assert ii.looks_like_calendar("BEGIN:VCALENDAR\n") and not ii.looks_like_calendar("<html>")


def test_repeat_rules():
    from datetime import datetime
    start, end = datetime(2026, 11, 2, 9, 0), datetime(2027, 1, 1)
    daily = ii.occurrences(start, {"FREQ": "DAILY", "COUNT": "3"}, end, set())
    assert [d.day for d in daily] == [2, 3, 4]
    every_other = ii.occurrences(start, {"FREQ": "WEEKLY", "INTERVAL": "2", "COUNT": "3"}, end, set())
    assert [d.isoformat()[:10] for d in every_other] == ["2026-11-02", "2026-11-16", "2026-11-30"]
    monthly = ii.occurrences(datetime(2026, 10, 31), {"FREQ": "MONTHLY"}, end, set())
    assert [d.isoformat()[:10] for d in monthly] == ["2026-10-31", "2026-12-31"]      # 31/11 không có: bỏ
    assert ii.occurrences(start, {"FREQ": "HOURLY"}, end, set()) == [start]         # không hỗ trợ: lần đầu


# ---------- link (chống SSRF) ----------

@pytest.mark.parametrize("url", [
    "https://calendar.google.com/calendar/ical/abc%40group.calendar.google.com/private-x/basic.ics",
    "webcal://p52-caldav.icloud.com/published/2/abc", "https://outlook.office365.com/owa/calendar/x/reachcalendar.ics"])
def test_allowed_links(url):
    clean, error = ii.normalize_feed_url(url)
    assert error is None and clean.startswith("https://")


@pytest.mark.parametrize("url", [
    "http://calendar.google.com/x", "https://evil.com/calendar.google.com.ics", "https://calendar.google.com.evil.com/x",
    "https://calendar.google.com:8443/x", "https://user:pw@calendar.google.com/x", "file:///etc/passwd",
    "https://127.0.0.1/x", "", "https://evilicloud.com/x"])
def test_blocked_links(url):
    assert ii.normalize_feed_url(url)[0] is None


# ---------- route ----------

class FakeResponse:
    def __init__(self, body=b"", status=200, location=None):
        self.status_code, self.headers = status, ({"Location": location} if location else {})
        self.is_redirect = location is not None
        self.raw = io.BytesIO(body)
        self.raw.read = lambda n, decode_content=True, _r=self.raw.read: _r(n)


GOOGLE = "https://calendar.google.com/calendar/ical/me/private-abc/basic.ics"


def connect(b, url=GOOGLE):
    return b.client.post("/account/calendar-import", data={"csrf_token": b.token(), "action": "connect", "url": url})


def test_connect_shows_events_on_calendar(browser, monkeypatch):
    calls = []
    monkeypatch.setattr(app_module.requests, "get", lambda url, **kw: calls.append(url) or FakeResponse(ICS.encode()))
    monkeypatch.setattr(app_module, "today_tw", lambda: TODAY)
    assert connect(browser).status_code == 302 and calls == [GOOGLE]
    account = browser.client.get("/account").get_data(as_text=True)
    assert "Connected to calendar.google.com" in account and "private-abc" not in account   # không lộ link bí mật
    page = browser.client.get("/calendar?day=2026-11-19").get_data(as_text=True)
    assert "Calculus, lecture" in page and 'class="pill imported"' in page and "Showing your Google Calendar" in page
    week = page.split('class="week-view"')[1].split('class="cal-wrap"')[0]
    assert "from-google" in week and 'data-event data-id="-' not in week       # chỉ để xem, không sửa được
    browser.client.get("/calendar")                                            # chưa tới 30 phút: không tải lại
    assert len(calls) == 1
    browser.client.post("/account/calendar-import", data={"csrf_token": browser.token(), "action": "sync"})
    assert len(calls) == 2


def test_bad_link_and_blocked_server(browser, monkeypatch):
    monkeypatch.setattr(app_module.requests, "get", lambda *a, **k: pytest.fail("must not fetch a bad link"))
    page = connect(browser, "https://evil.example.com/cal.ics")
    assert page.status_code == 302 and db_import(browser) is None

    def blocked(*a, **k):
        raise requests.ConnectionError("403 Forbidden by proxy")
    monkeypatch.setattr(app_module.requests, "get", blocked)
    connect(browser)
    account = browser.client.get("/account").get_data(as_text=True)
    assert "could not reach that calendar" in account and "Upload" in account


def test_redirect_only_to_allowed_hosts(browser, monkeypatch):
    def redirect_out(url, **kw):
        return FakeResponse(status=302, location="https://attacker.example/steal")
    monkeypatch.setattr(app_module.requests, "get", redirect_out)
    connect(browser)
    assert "Only Google Calendar" in browser.client.get("/account").get_data(as_text=True)


def test_upload_file_and_disconnect(browser, monkeypatch):
    monkeypatch.setattr(app_module, "today_tw", lambda: TODAY)
    data = {"csrf_token": browser.token(), "action": "upload", "ics_file": (io.BytesIO(ICS.encode()), "cal.ics")}
    assert browser.client.post("/account/calendar-import", data=data, content_type="multipart/form-data").status_code == 302
    assert "Holiday" in browser.client.get("/calendar?day=2026-11-25").get_data(as_text=True)
    bad = {"csrf_token": browser.token(), "action": "upload", "ics_file": (io.BytesIO(b"<html>"), "x.ics")}
    browser.client.post("/account/calendar-import", data=bad, content_type="multipart/form-data")
    browser.client.post("/account/calendar-import", data={"csrf_token": browser.token(), "action": "disconnect"})
    assert "Holiday" not in browser.client.get("/calendar?day=2026-11-25").get_data(as_text=True)


def test_imported_events_are_private(browser, make_browser, monkeypatch):
    monkeypatch.setattr(app_module, "today_tw", lambda: TODAY)
    data = {"csrf_token": browser.token(), "action": "upload", "ics_file": (io.BytesIO(ICS.encode()), "cal.ics")}
    browser.client.post("/account/calendar-import", data=data, content_type="multipart/form-data")
    other = make_browser()
    other.signup("b@example.com")
    assert "Holiday" not in other.client.get("/calendar?day=2026-11-25").get_data(as_text=True)
    assert other.client.post("/account/calendar-import", data={"action": "disconnect"}).status_code == 400   # thiếu CSRF


def db_import(b):
    with app_module.app.app_context():
        return db.get_db().execute("SELECT * FROM calendar_imports").fetchone()
