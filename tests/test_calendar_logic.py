"""Test cho calendar_logic.py (logic thuần Python, không cần Flask hay database)."""
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from calendar_logic import (  # noqa: E402
    MAX_TITLE,
    build_month,
    is_hhmm,
    is_iso_date,
    mark_saved,
    month_bounds,
    parse_month,
    shift_month,
    shorten_title,
    validate_event,
)


# ---------- validate_event ----------

def test_validate_event_accepts_minimal_and_full_input():
    event, error = validate_event({"title": "  Exam  ", "date": "2026-11-30"})
    assert error is None
    assert event == {"title": "Exam", "date": "2026-11-30", "time": "",
                     "description": "", "source_url": ""}

    event, error = validate_event({
        "title": "Deadline", "date": "2026-12-01", "time": "23:59",
        "description": "Student Affairs", "source_url": "https://www.nthu.edu.tw/x",
    })
    assert error is None
    assert event["time"] == "23:59"


def test_validate_event_requires_title_and_date():
    for bad in ({}, {"title": "x"}, {"date": "2026-11-30"}, {"title": "   ", "date": "2026-11-30"}):
        assert validate_event(bad)[1] == "title and date are required"


def test_validate_event_rejects_wrong_types_and_non_objects():
    assert validate_event(None)[1] == "JSON body must be an object"
    assert validate_event([1, 2])[1] == "JSON body must be an object"
    assert validate_event({"title": 5, "date": "2026-11-30"})[1] == "title and date are required"
    assert validate_event({"title": "x", "date": "2026-11-30", "time": 5})[0] is None


def test_validate_event_rejects_bad_dates_and_times():
    assert "YYYY-MM-DD" in validate_event({"title": "x", "date": "30/11/2026"})[1]
    assert "YYYY-MM-DD" in validate_event({"title": "x", "date": "2026-02-30"})[1]
    assert "YYYY-MM-DD" in validate_event({"title": "x", "date": "20261130"})[1]
    assert "HH:MM" in validate_event({"title": "x", "date": "2026-11-30", "time": "25:00"})[1]
    assert "HH:MM" in validate_event({"title": "x", "date": "2026-11-30", "time": "9:00"})[1]


def test_validate_event_rejects_too_long_text():
    assert "title" in validate_event({"title": "x" * (MAX_TITLE + 1), "date": "2026-11-30"})[1]
    assert "description" in validate_event(
        {"title": "x", "date": "2026-11-30", "description": "y" * 1001})[1]


def test_validate_event_blocks_dangerous_urls():
    for url in ("javascript:alert(1)", "data:text/html,hi", "ftp://x", "//evil.com"):
        event, error = validate_event({"title": "x", "date": "2026-11-30", "source_url": url})
        assert event is None and "http" in error


def test_is_iso_date_and_is_hhmm():
    assert is_iso_date("2026-11-30") and not is_iso_date("2026-13-01")
    assert is_hhmm("00:00") and is_hhmm("23:59") and not is_hhmm("24:00")


# ---------- tháng ----------

def test_parse_month():
    assert parse_month("2026-11") == (2026, 11)
    for bad in (None, "", "2026-13", "2026-1", "november", "2026-11-01", 5):
        assert parse_month(bad) is None


def test_shift_month_crosses_year_boundaries():
    assert shift_month(2026, 11, 1) == (2026, 12)
    assert shift_month(2026, 12, 1) == (2027, 1)
    assert shift_month(2026, 1, -1) == (2025, 12)
    assert shift_month(2026, 3, -14) == (2025, 1)


def test_month_bounds():
    assert month_bounds(2026, 11) == ("2026-11-01", "2026-12-01")
    assert month_bounds(2026, 12) == ("2026-12-01", "2027-01-01")


def test_build_month_layout_for_november_2026():
    weeks = build_month(2026, 11, [], date(2026, 11, 18))
    assert len(weeks) == 6
    assert all(len(week) == 7 for week in weeks)
    # 1/11/2026 là Chủ nhật -> 6 ô trống rồi mới tới ngày 1
    assert weeks[0][:6] == [None] * 6
    assert weeks[0][6]["day"] == 1
    assert weeks[-1][0]["day"] == 30 and weeks[-1][1:] == [None] * 6
    today_cells = [c for week in weeks for c in week if c and c["is_today"]]
    assert [c["iso"] for c in today_cells] == ["2026-11-18"]


def test_build_month_places_and_sorts_events():
    events = [
        {"id": 1, "title": "late", "date": "2026-11-18", "time": "15:00"},
        {"id": 2, "title": "all day", "date": "2026-11-18", "time": ""},
        {"id": 3, "title": "early", "date": "2026-11-18", "time": "08:30"},
        {"id": 4, "title": "other", "date": "2026-11-02", "time": ""},
    ]
    weeks = build_month(2026, 11, events, date(2026, 11, 1))
    cells = {c["iso"]: c for week in weeks for c in week if c}
    assert [e["title"] for e in cells["2026-11-18"]["events"]] == ["all day", "early", "late"]
    assert [e["title"] for e in cells["2026-11-02"]["events"]] == ["other"]
    assert cells["2026-11-03"]["events"] == []


# ---------- đánh dấu đã lưu ----------

def test_shorten_title():
    assert shorten_title("short") == "short"
    long_title = "x" * 500
    assert len(shorten_title(long_title)) == MAX_TITLE


def test_mark_saved_copies_items_and_marks_saved():
    items = [{"title": "A", "date": "2026-11-01"}, {"title": "B", "date": "2026-11-02"}]
    result = mark_saved(items, {("A", "2026-11-01")})
    assert [r["saved"] for r in result] == [True, False]
    assert result[0]["event_title"] == "A"
    assert "saved" not in items[0]  # danh sách gốc (cache dùng chung) không bị sửa
