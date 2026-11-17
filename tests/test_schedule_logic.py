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
