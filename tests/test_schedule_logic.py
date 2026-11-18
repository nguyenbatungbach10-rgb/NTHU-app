"""Test logic thời khóa biểu tuần (thuần Python)."""
import pytest

import schedule_logic as s


def cls(id, name="X", weekday=0, start="09:00", end="10:00", room=""):
    return {"id": id, "name": name, "weekday": weekday, "start": start, "end": end, "room": room}


# ---------- trùng giờ ----------

def test_overlaps_rules():
    assert s.overlaps(cls(1, start="09:00", end="11:00"), cls(2, start="10:00", end="12:00"))
    assert s.overlaps(cls(1, start="09:00", end="12:00"), cls(2, start="10:00", end="11:00"))   # nằm gọn bên trong
    assert not s.overlaps(cls(1, start="09:00", end="10:00"), cls(2, start="10:00", end="11:00"))  # nối tiếp thì không trùng
    assert not s.overlaps(cls(1, start="09:00", end="10:00"), cls(2, start="13:00", end="14:00"))


def test_overlap_compares_times_not_strings():
    # "9:00" kiểu chuỗi sẽ lớn hơn "10:00"; so sánh theo phút thì đúng
    assert s.to_minutes("09:30") == 570
    assert s.overlaps(cls(1, start="09:30", end="10:30"), cls(2, start="10:00", end="11:00"))


def test_find_conflicts_only_same_weekday():
    classes = [cls(1, weekday=0, start="09:00", end="11:00"),
               cls(2, weekday=0, start="10:00", end="12:00"),
               cls(3, weekday=1, start="10:00", end="12:00"),     # khác thứ: không trùng
               cls(4, weekday=0, start="12:00", end="13:00")]     # nối tiếp môn 2: không trùng
    assert s.find_conflicts(classes) == {1, 2}
    assert s.find_conflicts([]) == set()


# ---------- dựng tuần ----------

def test_build_week_groups_sorts_and_flags_conflicts():
    classes = [cls(1, "Late", 2, "14:00", "15:00"), cls(2, "Early", 2, "08:00", "09:00"),
               cls(3, "A", 0, "09:00", "11:00"), cls(4, "B", 0, "10:00", "12:00")]
    days = s.build_week(classes)
    assert [d["name"] for d in days] == s.WEEKDAYS
    assert [c["name"] for c in days[2]["classes"]] == ["Early", "Late"]
    assert [c["conflict"] for c in days[0]["classes"]] == [True, True]
    assert days[2]["classes"][0]["conflict"] is False
    assert days[1]["classes"] == []


def test_build_week_does_not_mutate_input():
    classes = [cls(1)]
    s.build_week(classes)
    assert "conflict" not in classes[0]


def test_visible_days_hides_empty_weekend():
    days = s.build_week([cls(1, weekday=2)])
    assert [d["weekday"] for d in s.visible_days(days)] == [0, 1, 2, 3, 4]
    days = s.build_week([cls(1, weekday=5)])
    assert [d["weekday"] for d in s.visible_days(days)] == [0, 1, 2, 3, 4, 5]
    days = s.build_week([cls(1, weekday=6), cls(2, weekday=5)])
    assert [d["weekday"] for d in s.visible_days(days)] == [0, 1, 2, 3, 4, 5, 6]


def test_classes_on_and_weekly_minutes():
    classes = [cls(1, "B", 3, "13:00", "14:30"), cls(2, "A", 3, "09:00", "10:00"), cls(3, "C", 4)]
    assert [c["name"] for c in s.classes_on(classes, 3)] == ["A", "B"]
    assert s.classes_on(classes, 0) == []
    assert s.weekly_minutes(classes) == 90 + 60 + 60
    assert s.weekly_minutes([]) == 0


# ---------- kiểm tra dữ liệu ----------

def test_validate_class_accepts_and_cleans():
    ok, err = s.validate_class({"name": " Calculus ", "weekday": 0, "start": "10:10", "end": "12:00", "room": " R101 "})
    assert err is None
    assert ok == {"name": "Calculus", "weekday": 0, "start": "10:10", "end": "12:00", "room": "R101"}
    assert s.validate_class({"name": "x", "weekday": 6, "start": "00:00", "end": "23:59"})[0]["room"] == ""


@pytest.mark.parametrize("payload,fragment", [
    ({}, "name"),
    ({"name": " ", "weekday": 0, "start": "09:00", "end": "10:00"}, "name"),
    ({"name": "x" * 101, "weekday": 0, "start": "09:00", "end": "10:00"}, "name"),
    ({"name": "x", "weekday": 7, "start": "09:00", "end": "10:00"}, "weekday"),
    ({"name": "x", "weekday": -1, "start": "09:00", "end": "10:00"}, "weekday"),
    ({"name": "x", "weekday": "1", "start": "09:00", "end": "10:00"}, "weekday"),
    ({"name": "x", "weekday": True, "start": "09:00", "end": "10:00"}, "weekday"),
    ({"name": "x", "weekday": 0, "start": "25:00", "end": "26:00"}, "times"),
    ({"name": "x", "weekday": 0, "start": "9:00", "end": "10:00"}, "times"),
    ({"name": "x", "weekday": 0, "start": "09:00"}, "times"),
    ({"name": "x", "weekday": 0, "start": "10:00", "end": "10:00"}, "later"),
    ({"name": "x", "weekday": 0, "start": "11:00", "end": "10:00"}, "later"),
    ({"name": "x", "weekday": 0, "start": "09:00", "end": "10:00", "room": "r" * 101}, "room"),
    ({"name": "x", "weekday": 0, "start": "09:00", "end": "10:00", "room": 5}, "room"),
])
def test_validate_class_rejects_bad_data(payload, fragment):
    cleaned, error = s.validate_class(payload)
    assert cleaned is None and fragment in error


def test_validate_class_rejects_non_object():
    assert s.validate_class("nope") == (None, "JSON body must be an object")


# ---------- thời khóa biểu theo tiết ----------
from schedule_logic import PERIODS, build_timetable, class_periods  # noqa: E402


def _c(id, weekday, start, end, name="x"):
    return {"id": id, "name": name, "weekday": weekday, "start": start, "end": end, "room": ""}


def test_periods_are_in_order_and_do_not_overlap():
    ids = [p["id"] for p in PERIODS]
    assert ids == ["1", "2", "3", "4", "n", "5", "6", "7", "8", "9", "a", "b", "c", "d"]
    for a, b in zip(PERIODS, PERIODS[1:]):
        assert a["start"] < a["end"] <= b["start"]


def test_class_periods_exact_and_multiple_periods():
    assert class_periods(_c(1, 0, "08:00", "08:50")) == (0, 0)
    assert class_periods(_c(1, 0, "10:10", "12:00")) == (2, 3)          # tiết 3 và 4
    assert class_periods(_c(1, 0, "13:20", "15:10")) == (5, 6)
    assert class_periods(_c(1, 0, "08:00", "22:20")) == (0, 13)


def test_class_periods_partial_overlap_counts_the_period():
    assert class_periods(_c(1, 0, "08:30", "09:10")) == (0, 1)          # chạm cả tiết 1 và 2
    assert class_periods(_c(1, 0, "09:50", "10:11")) == (2, 2)          # 09:50 vừa hết tiết 2, 10:11 chạm tiết 3


def test_class_periods_touching_edge_does_not_count():
    # kết thúc đúng lúc tiết sau bắt đầu: không chạm tiết sau (giống quy tắc overlaps)
    assert class_periods(_c(1, 0, "09:00", "10:10")) == (1, 1)
    assert class_periods(_c(1, 0, "07:10", "08:00")) is None


def test_class_periods_none_when_outside_every_period():
    assert class_periods(_c(1, 0, "06:00", "07:00")) is None
    assert class_periods(_c(1, 0, "22:30", "23:30")) is None
    assert class_periods(_c(1, 0, "12:00", "12:10")) is None            # kẽ hở giữa tiết 4 và tiết n


def test_build_timetable_blocks_rows_and_spans():
    days = build_timetable([_c(1, 0, "10:10", "12:00"), _c(2, 2, "08:00", "08:50")])
    mon = days[0]["blocks"][0]
    assert (mon["row"], mon["span"], mon["lane"], mon["lanes"]) == (2, 2, 0, 1)
    assert days[0]["short"] == "Mon" and days[2]["blocks"][0]["row"] == 0
    assert days[0]["outside"] == [] and days[1]["blocks"] == []


def test_build_timetable_overlapping_classes_go_side_by_side():
    days = build_timetable([_c(1, 0, "09:00", "11:00", "A"), _c(2, 0, "10:10", "12:00", "B"), _c(3, 0, "13:20", "14:10", "C")])
    by_name = {b["name"]: b for b in days[0]["blocks"]}
    assert by_name["A"]["lanes"] == by_name["B"]["lanes"] == 2
    assert {by_name["A"]["lane"], by_name["B"]["lane"]} == {0, 1}
    assert by_name["C"]["lanes"] == 1 and by_name["C"]["lane"] == 0       # môn riêng không bị chia hẹp
    assert by_name["A"]["conflict"] and by_name["B"]["conflict"] and not by_name["C"]["conflict"]


def test_build_timetable_three_way_and_reused_lane():
    # A (tiết 1-2) và B (tiết 2-3) chồng; C (tiết 3) chồng B nhưng không chồng A -> dùng lại làn 0
    days = build_timetable([_c(1, 0, "08:00", "09:50", "A"), _c(2, 0, "09:00", "11:00", "B"), _c(3, 0, "10:10", "11:00", "C")])
    by = {b["name"]: b for b in days[0]["blocks"]}
    assert by["A"]["lane"] == 0 and by["B"]["lane"] == 1 and by["C"]["lane"] == 0
    assert all(b["lanes"] == 2 for b in by.values())


def test_build_timetable_classes_outside_periods_listed_separately():
    days = build_timetable([_c(1, 1, "06:00", "07:00", "Early"), _c(2, 1, "08:00", "08:50", "Normal")])
    assert [c["name"] for c in days[1]["outside"]] == ["Early"]
    assert [b["name"] for b in days[1]["blocks"]] == ["Normal"]
    assert [c["name"] for c in days[1]["classes"]] == ["Early", "Normal"]  # danh sách đầy đủ vẫn còn


def test_build_timetable_does_not_change_input():
    classes = [_c(1, 0, "09:00", "11:00"), _c(2, 0, "10:10", "12:00")]
    before = [dict(c) for c in classes]
    build_timetable(classes)
    assert classes == before
