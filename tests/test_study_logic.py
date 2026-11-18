"""Test logic Study planning thuần Python."""
from datetime import date

import pytest

import study_logic as s


def task(id, title="t", due="", done=False, subject=None, parent=None):
    return {"id": id, "title": title, "due_date": due, "done": done,
            "subject_id": subject, "parent_id": parent}


def sess(date_="2026-11-18", minutes=60, subject=None):
    return {"date": date_, "minutes": minutes, "subject_id": subject}


# ---------- hạn nộp, cây việc ----------

def test_overdue_rules():
    assert s.is_overdue(task(1, due="2026-11-17"), "2026-11-18")
    assert not s.is_overdue(task(1, due="2026-11-18"), "2026-11-18")            # hôm nay chưa quá hạn
    assert not s.is_overdue(task(1, due="2026-11-17", done=True), "2026-11-18")  # đã xong
    assert not s.is_overdue(task(1, due=""), "2026-11-18")                      # không có hạn


def test_tree_nests_children_and_counts_progress():
    tasks = [task(1, "Report", subject=7), task(2, "Outline", parent=1, done=True),
             task(3, "Draft", parent=1), task(4, "Read ch.3")]
    tree = s.build_task_tree(tasks, "2026-11-18", {7: "Calculus"})
    report = next(t for t in tree if t["id"] == 1)
    assert [c["id"] for c in report["children"]] == [3, 2]       # việc chưa xong trước
    assert (report["subtasks_done"], report["subtasks_total"]) == (1, 2)
    assert report["children"][0]["subject_name"] == "Calculus"   # việc con lấy môn của cha
    assert next(t for t in tree if t["id"] == 4)["subtasks_total"] == 0
    assert all(t["parent_id"] is None for t in tree)             # chỉ việc cha ở cấp trên


def test_tree_sorting_open_first_then_due_date_then_no_due():
    tasks = [task(1, due="2026-12-01"), task(2, done=True, due="2026-11-01"),
             task(3, due=""), task(4, due="2026-11-20")]
    assert [t["id"] for t in s.build_task_tree(tasks, "2026-11-18")] == [4, 1, 3, 2]


def test_tree_does_not_mutate_input():
    tasks = [task(1), task(2, parent=1)]
    s.build_task_tree(tasks, "2026-11-18")
    assert "children" not in tasks[0] and "overdue" not in tasks[0]


def test_tree_flags_overdue():
    tree = s.build_task_tree([task(1, due="2026-11-01"), task(2, due="2026-12-01")], "2026-11-18")
    assert {t["id"]: t["overdue"] for t in tree} == {1: True, 2: False}


# ---------- thời gian học ----------

def test_week_bounds_start_on_monday():
    assert s.week_bounds(date(2026, 11, 18)) == ("2026-11-16", "2026-11-23")   # thứ Tư
    assert s.week_bounds(date(2026, 11, 16)) == ("2026-11-16", "2026-11-23")   # chính thứ Hai
    assert s.week_bounds(date(2026, 11, 22)) == ("2026-11-16", "2026-11-23")   # Chủ nhật
    assert s.week_bounds(date(2026, 12, 31)) == ("2026-12-28", "2027-01-04")   # qua năm


def test_total_minutes_range_is_half_open():
    sessions = [sess("2026-11-15", 10), sess("2026-11-16", 20), sess("2026-11-22", 30), sess("2026-11-23", 40)]
    assert s.total_minutes(sessions) == 100
    assert s.total_minutes(sessions, "2026-11-16", "2026-11-23") == 50   # 23 không tính


def test_minutes_by_subject_sorted_with_no_subject_group():
    sessions = [sess(minutes=30, subject=1), sess(minutes=90, subject=2),
                sess(minutes=45, subject=None), sess(minutes=30, subject=1)]
    rows = s.minutes_by_subject(sessions, {1: "Physics", 2: "Calculus"})
    assert [(r["name"], r["minutes"]) for r in rows] == [("Calculus", 90), ("Physics", 60), ("No subject", 45)]


def test_minutes_by_subject_respects_range():
    sessions = [sess("2026-11-10", 50, 1), sess("2026-11-17", 20, 1)]
    rows = s.minutes_by_subject(sessions, {1: "P"}, "2026-11-16", "2026-11-23")
    assert rows == [{"subject_id": 1, "name": "P", "minutes": 20}]


@pytest.mark.parametrize("minutes,text", [(0, "0m"), (45, "45m"), (60, "1h"), (90, "1h 30m"), (125, "2h 5m")])
def test_format_minutes(minutes, text):
    assert s.format_minutes(minutes) == text


def test_overview():
    tasks = [task(1, due="2026-11-10"), task(2, done=True), task(3, due="2026-12-01"),
             task(4, parent=3, due="2026-01-01")]       # việc con không được đếm
    sessions = [sess("2026-11-18", 60), sess("2026-11-17", 30), sess("2026-11-18", 15), sess("2026-11-10", 99)]
    o = s.overview(tasks, sessions, date(2026, 11, 18))
    assert (o["open"], o["done"], o["overdue"]) == (2, 1, 1)
    assert o["today_minutes"] == 75
    assert o["week_minutes"] == 105
    assert o["days_studied_this_week"] == 2


# ---------- kiểm tra dữ liệu ----------

def test_validate_subject():
    assert s.validate_subject({"name": " Calculus ", "notes": " ch1 "}) == ({"name": "Calculus", "notes": "ch1"}, None)
    assert s.validate_subject({"name": "x"})[0]["notes"] == ""
    for bad in [{}, {"name": " "}, {"name": 5}, {"name": "x" * 101}, {"name": "x", "notes": "n" * 1001},
                {"name": "x", "notes": 5}, "nope"]:
        assert s.validate_subject(bad)[0] is None


def test_validate_task():
    ok, err = s.validate_task({"title": " Report ", "due_date": "2026-11-20", "subject_id": 3, "parent_id": None})
    assert err is None
    assert ok == {"title": "Report", "due_date": "2026-11-20", "done": False, "subject_id": 3, "parent_id": None}
    assert s.validate_task({"title": "x", "subject_id": ""})[0]["subject_id"] is None
    for bad in [{}, {"title": ""}, {"title": "x" * 201}, {"title": "x", "due_date": "2026-02-30"},
                {"title": "x", "due_date": 5}, {"title": "x", "done": "yes"}, {"title": "x", "done": 1},
                {"title": "x", "subject_id": 0}, {"title": "x", "subject_id": True},
                {"title": "x", "parent_id": "1"}, {"title": "x", "parent_id": -2}]:
        assert s.validate_task(bad)[0] is None, bad


def test_validate_session():
    ok, err = s.validate_session({"date": "2026-11-18", "minutes": 90, "subject_id": 2, "note": " ch.3 "})
    assert err is None and ok == {"date": "2026-11-18", "minutes": 90, "subject_id": 2, "note": "ch.3"}
    for bad in [{}, {"date": "2026-11-18"}, {"date": "bad", "minutes": 5}, {"date": "2026-11-18", "minutes": 0},
                {"date": "2026-11-18", "minutes": 1441}, {"date": "2026-11-18", "minutes": 1.5},
                {"date": "2026-11-18", "minutes": True}, {"date": "2026-11-18", "minutes": "30"},
                {"date": "2026-11-18", "minutes": 5, "subject_id": "x"},
                {"date": "2026-11-18", "minutes": 5, "note": "n" * 301}]:
        assert s.validate_session(bad)[0] is None, bad
    assert s.validate_session({"date": "2026-11-18", "minutes": 1440})[1] is None


# ---------- due_today (trang chủ) ----------
from study_logic import due_today  # noqa: E402


def _t(id, due, done=False, parent=None, title="t"):
    return {"id": id, "due_date": due, "done": done, "parent_id": parent, "title": title}


def test_due_today_keeps_open_main_tasks_due_today_or_earlier():
    tasks = [_t(1, "2026-11-18"), _t(2, "2026-11-10"), _t(3, "2026-11-19"), _t(4, ""),
             _t(5, "2026-11-18", done=True), _t(6, "2026-11-18", parent=1)]
    result = due_today(tasks, "2026-11-18")
    assert [t["id"] for t in result] == [2, 1]          # cũ nhất trước; bỏ việc tương lai, không hạn, đã xong, việc con
    assert [t["overdue"] for t in result] == [True, False]


def test_due_today_limit_and_copies():
    tasks = [_t(i, "2026-11-01") for i in range(1, 9)]
    result = due_today(tasks, "2026-11-18", limit=3)
    assert [t["id"] for t in result] == [1, 2, 3]
    assert "overdue" not in tasks[0]                      # không sửa dữ liệu gốc
    assert due_today([], "2026-11-18") == []
