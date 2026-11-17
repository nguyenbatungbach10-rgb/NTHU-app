"""Test logic GPA thuần Python. Mọi con số đã tính tay trước (xem chú thích)."""
from datetime import date

import pytest

import gpa_logic as g


def course(name="X", credits=3, semester="115-1", grade="", id=1):
    return {"id": id, "name": name, "credits": credits, "semester": semester, "grade": grade}


# ---------- GPA ----------

def test_gpa_weighted_by_credits():
    # A (4.0) x 3 + B+ (3.3) x 3 = 12 + 9.9 = 21.9; chia 6 = 3.65
    assert g.gpa([course(grade="A"), course(grade="B+")]) == pytest.approx(3.65)
    # Trọng số: A x 4 + C x 1 = 16 + 2 = 18; chia 5 = 3.6 (không phải trung bình đơn 3.0)
    assert g.gpa([course(credits=4, grade="A"), course(credits=1, grade="C")]) == pytest.approx(3.6)


def test_gpa_ignores_planned_and_pass_courses():
    courses = [course(grade="A"), course(grade=""), course(grade="P")]
    assert g.gpa(courses) == pytest.approx(4.0)


def test_gpa_none_when_no_graded_course():
    assert g.gpa([]) is None
    assert g.gpa([course(grade=""), course(grade="P")]) is None


def test_failed_grades_count_zero_in_gpa_but_earn_no_credit():
    courses = [course(grade="A"), course(grade="E")]
    assert g.gpa(courses) == pytest.approx(2.0)       # (12 + 0) / 6
    assert g.credits_earned(courses) == 3             # chỉ môn A


def test_credits_earned_rules():
    assert g.credits_earned([course(grade="C-")]) == 3   # C- là đạt
    assert g.credits_earned([course(grade="D")]) == 0    # D chưa đạt
    assert g.credits_earned([course(grade="X")]) == 0
    assert g.credits_earned([course(grade="P")]) == 3    # pass/fail có tín chỉ
    assert g.credits_earned([course(grade="")]) == 0     # chưa có điểm


def test_zero_credit_course_does_not_change_gpa():
    assert g.gpa([course(grade="A"), course(credits=0, grade="E")]) == pytest.approx(4.0)


# ---------- cần bao nhiêu điểm ----------

def test_required_average_possible():
    # Có 6 tín chỉ, điểm 21.9. Muốn 3.7 sau 6 tín chỉ nữa: (3.7 x 12 - 21.9) / 6 = 22.5 / 6 = 3.75
    done = [course(grade="A"), course(grade="B+")]
    result = g.required_average(done, 3.7, 6)
    assert result == {"status": "possible", "needed": 3.75, "letter": "A"}


def test_required_average_impossible():
    # Muốn 4.3 sau 3 tín chỉ nữa: (4.3 x 9 - 21.9) / 3 = 16.8 / 3 = 5.6 > 4.3
    done = [course(grade="A"), course(grade="B+")]
    result = g.required_average(done, 4.3, 3)
    assert result["status"] == "impossible"
    assert result["needed"] == 5.6


def test_required_average_already_achieved():
    # Muốn 2.0, đã có 3.65: chỉ cần qua môn
    done = [course(grade="A"), course(grade="B+")]
    result = g.required_average(done, 2.0, 6)
    assert result["status"] == "achieved"
    assert result["letter"] == "C-"


def test_required_average_without_remaining_credits():
    assert g.required_average([course(grade="A")], 3.5, 0)["status"] == "no_credits"


def test_required_average_with_no_history():
    # Chưa có điểm nào: cần đúng bằng mục tiêu
    assert g.required_average([], 3.5, 10) == {"status": "possible", "needed": 3.5, "letter": "A-"}


def test_letter_for_returns_lowest_letter_that_is_enough():
    assert g.letter_for(3.75) == "A"     # A- = 3.7 chưa đủ
    assert g.letter_for(3.7) == "A-"
    assert g.letter_for(4.3) == "A+"
    assert g.letter_for(4.31) is None


# ---------- học kỳ và tổng quan ----------

def test_semester_summary_orders_and_accumulates():
    courses = [
        course("B", 3, "115-2", "B", id=2),
        course("A", 3, "115-1", "A", id=1),
        course("C", 3, "115-2", "", id=3),
    ]
    summary = g.semester_summary(courses)
    assert [s["semester"] for s in summary] == ["115-1", "115-2"]
    assert summary[0]["gpa"] == pytest.approx(4.0)
    assert summary[1]["gpa"] == pytest.approx(3.0)
    assert summary[1]["cumulative_gpa"] == pytest.approx(3.5)   # (12 + 9) / 6
    assert summary[1]["credits_planned"] == 3
    assert summary[1]["credits_earned"] == 3


def test_overview_progress_and_remaining():
    courses = [course(credits=3, grade="A"), course(credits=3, grade=""),
               course(credits=2, semester="114-2", grade="P")]
    o = g.overview(courses, 3.5, 128)
    assert o["credits_earned"] == 5
    assert o["credits_planned"] == 3
    assert o["credits_remaining"] == 123
    assert o["progress_percent"] == 4          # 5 / 128 = 3.9%
    assert o["semesters_left"] == 7            # 114-2 xong; 115-1 còn môn chưa có điểm
    assert o["credits_per_semester"] == 18     # ceil(123 / 7)


def test_overview_never_negative_when_over_requirement():
    o = g.overview([course(credits=12, grade="A")], 3.5, 10)
    assert o["credits_remaining"] == 0
    assert o["progress_percent"] == 100
    assert o["needed_overall"]["status"] == "no_credits"


def test_current_semester():
    assert g.current_semester(date(2026, 11, 18)) == "115-1"
    assert g.current_semester(date(2026, 8, 1)) == "115-1"
    assert g.current_semester(date(2027, 1, 10)) == "115-1"   # tháng 1 vẫn thuộc học kỳ 1
    assert g.current_semester(date(2027, 3, 1)) == "115-2"
    assert g.current_semester(date(2027, 7, 31)) == "115-2"


# ---------- kiểm tra dữ liệu ----------

@pytest.mark.parametrize("payload,fragment", [
    ({}, "required"),
    ({"name": " ", "credits": 3, "semester": "115-1"}, "required"),
    ({"name": "x", "credits": 3.5, "semester": "115-1"}, "whole number"),
    ({"name": "x", "credits": -1, "semester": "115-1"}, "whole number"),
    ({"name": "x", "credits": 13, "semester": "115-1"}, "whole number"),
    ({"name": "x", "credits": True, "semester": "115-1"}, "whole number"),
    ({"name": "x", "credits": "3", "semester": "115-1"}, "whole number"),
    ({"name": "x", "credits": 3, "semester": "2026-1"}, "semester"),
    ({"name": "x", "credits": 3, "semester": "115-4"}, "semester"),
    ({"name": "x", "credits": 3, "semester": "115-1", "grade": "Z"}, "grade"),
    ({"name": "x" * 101, "credits": 3, "semester": "115-1"}, "at most"),
])
def test_validate_course_rejects_bad_data(payload, fragment):
    cleaned, error = g.validate_course(payload)
    assert cleaned is None and fragment in error


def test_validate_course_accepts_and_cleans():
    cleaned, error = g.validate_course(
        {"name": "  Calculus ", "credits": 3.0, "semester": "115-1", "grade": "A+"})
    assert error is None
    assert cleaned == {"name": "Calculus", "credits": 3, "semester": "115-1", "grade": "A+"}
    assert g.validate_course({"name": "x", "credits": 0, "semester": "115-2", "grade": "P"})[1] is None
    assert g.validate_course({"name": "x", "credits": 2, "semester": "115-1", "grade": None})[0]["grade"] == ""
    assert g.validate_course("not a dict")[1] == "JSON body must be an object"


@pytest.mark.parametrize("payload", [
    {}, {"target_gpa": 5, "credits_required": 128}, {"target_gpa": -1, "credits_required": 128},
    {"target_gpa": "3.5", "credits_required": 128}, {"target_gpa": True, "credits_required": 128},
    {"target_gpa": 3.5, "credits_required": 0}, {"target_gpa": 3.5, "credits_required": 301},
    {"target_gpa": 3.5, "credits_required": 120.5},
])
def test_validate_goals_rejects_bad_data(payload):
    assert g.validate_goals(payload)[0] is None


def test_validate_goals_accepts():
    assert g.validate_goals({"target_gpa": 3.456, "credits_required": 130}) == (
        {"target_gpa": 3.46, "credits_required": 130}, None)
