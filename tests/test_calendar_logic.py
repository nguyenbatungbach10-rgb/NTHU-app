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


# ---------- việc cần làm hiện trên lịch ----------

def test_build_month_places_tasks_on_their_due_day_and_flags_overdue():
    from datetime import date
    from calendar_logic import build_month
    tasks = [{"id": 2, "title": "B", "due_date": "2026-11-20"},
             {"id": 1, "title": "A", "due_date": "2026-11-20"},
             {"id": 3, "title": "Late", "due_date": "2026-11-10"}]
    weeks = build_month(2026, 11, [], date(2026, 11, 18), tasks)
    cells = {c["iso"]: c for week in weeks for c in week if c}
    assert [t["title"] for t in cells["2026-11-20"]["tasks"]] == ["A", "B"]      # xếp theo id
    assert cells["2026-11-20"]["tasks"][0]["overdue"] is False
    assert cells["2026-11-10"]["tasks"][0]["overdue"] is True
    assert cells["2026-11-18"]["tasks"] == []
    assert "overdue" not in tasks[0]                                              # không sửa dữ liệu gốc


def test_build_month_without_tasks_still_works():
    from datetime import date
    from calendar_logic import build_month
    weeks = build_month(2026, 11, [], date(2026, 11, 18))
    assert all(c["tasks"] == [] for week in weeks for c in week if c)


def test_task_due_today_is_not_overdue_on_the_calendar():
    from datetime import date
    from calendar_logic import build_month
    tasks = [{"id": 1, "title": "Today", "due_date": "2026-11-18"},
             {"id": 2, "title": "Yesterday", "due_date": "2026-11-17"}]
    cells = {c["iso"]: c for week in build_month(2026, 11, [], date(2026, 11, 18), tasks) for c in week if c}
    assert cells["2026-11-18"]["tasks"][0]["overdue"] is False
    assert cells["2026-11-17"]["tasks"][0]["overdue"] is True


# ---------- mark_saved dùng ngày trong tiêu đề ----------

def test_mark_saved_uses_date_found_in_title_and_matches_saved_events():
    from calendar_logic import mark_saved
    items = [{"title": "Application deadline: Nov 20", "date": "2026-11-01"},
             {"title": "Dorm news", "date": "2026-11-02"}]
    marked = mark_saved(items, {("Application deadline: Nov 20", "2026-11-20")})
    assert marked[0]["event_date"] == "2026-11-20" and marked[0]["date_from_title"] is True
    assert marked[0]["saved"] is True                     # sự kiện đã lưu đúng ngày hạn
    assert marked[1]["event_date"] == "2026-11-02" and marked[1]["date_from_title"] is False
    assert marked[1]["saved"] is False
    assert "event_date" not in items[0]                    # không sửa dữ liệu gốc (cache dùng chung)


def test_mark_saved_old_event_on_posted_date_is_not_considered_saved():
    from calendar_logic import mark_saved
    items = [{"title": "Application deadline: Nov 20", "date": "2026-11-01"}]
    assert mark_saved(items, {("Application deadline: Nov 20", "2026-11-01")})[0]["saved"] is False


# ---------- xem cả năm ----------
from calendar_logic import MAX_YEAR, MIN_YEAR, build_year, parse_year, year_bounds  # noqa: E402


def test_parse_year_accepts_four_digit_years_in_range():
    assert parse_year("2026") == 2026
    assert parse_year(str(MIN_YEAR)) == MIN_YEAR and parse_year(str(MAX_YEAR)) == MAX_YEAR


def test_parse_year_rejects_bad_input():
    for bad in [None, "", "26", "20266", "abc", "2026-11", " 2026", "-2026", str(MIN_YEAR - 1), str(MAX_YEAR + 1), "0000", 2026]:
        assert parse_year(bad) is None


def test_year_bounds():
    assert year_bounds(2026) == ("2026-01-01", "2027-01-01")
    assert year_bounds(999) == ("0999-01-01", "1000-01-01")


def test_build_year_has_twelve_months_in_order():
    months = build_year(2026, [], date(2026, 11, 18))
    assert [m["month"] for m in months] == list(range(1, 13))
    assert months[0]["name"] == "January" and months[11]["name"] == "December"
    assert months[10]["iso"] == "2026-11"
    assert all(m["count"] == 0 for m in months)


def test_build_year_marks_current_month_and_today_only():
    months = build_year(2026, [], date(2026, 11, 18))
    assert [m["month"] for m in months if m["is_current"]] == [11]
    today_cells = [c for m in months for w in m["weeks"] for c in w if c and c["is_today"]]
    assert [c["iso"] for c in today_cells] == ["2026-11-18"]
    # năm khác: không có tháng "hiện tại" và không có ô "hôm nay"
    other = build_year(2025, [], date(2026, 11, 18))
    assert not any(m["is_current"] for m in other)
    assert not any(c and c["is_today"] for m in other for w in m["weeks"] for c in w)


def test_build_year_counts_events_and_tasks_per_day():
    events = [{"date": "2026-03-05"}, {"date": "2026-03-05"}, {"date": "2026-04-01"}]
    tasks = [{"due_date": "2026-03-05"}, {"due_date": "2026-12-31"}]
    months = build_year(2026, events, date(2026, 1, 1), tasks)
    by_iso = {c["iso"]: c["count"] for m in months for w in m["weeks"] for c in w if c}
    assert by_iso["2026-03-05"] == 3 and by_iso["2026-04-01"] == 1 and by_iso["2026-12-31"] == 1
    assert by_iso["2026-03-06"] == 0
    assert months[2]["count"] == 3 and months[3]["count"] == 1 and months[11]["count"] == 1


def test_build_year_grid_shape_and_leap_february():
    leap = build_year(2028, [], date(2028, 1, 1))[1]
    plain = build_year(2027, [], date(2027, 1, 1))[1]
    days = lambda m: sum(1 for w in m["weeks"] for c in w if c)  # noqa: E731
    assert days(leap) == 29 and days(plain) == 28
    assert all(len(w) == 7 for w in leap["weeks"])
    # 1/12/2026 là thứ Ba: ô đầu tiên (thứ Hai) để trống
    dec = build_year(2026, [], date(2026, 1, 1))[11]
    assert dec["weeks"][0][0] is None and dec["weeks"][0][1]["day"] == 1


def test_build_year_does_not_change_inputs():
    events = [{"date": "2026-03-05", "title": "x"}]
    tasks = [{"due_date": "2026-03-05", "title": "t"}]
    build_year(2026, events, date(2026, 1, 1), tasks)
    assert events == [{"date": "2026-03-05", "title": "x"}]
    assert tasks == [{"due_date": "2026-03-05", "title": "t"}]
