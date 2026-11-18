"""Test thẻ "GPA goal" và "Graduation credits" (giống mockup)."""
import gpa_logic as gl


def course(name, credits, grade, semester="115-1"):
    return {"id": hash(name) % 1000, "name": name, "credits": credits, "grade": grade, "semester": semester}


COURSES = [course("Calculus", 4, "A"), course("Programming", 3, "A+"), course("Physics", 3, "A-"),
           course("Discrete", 3, "B+"), course("Chinese", 2, "")]


def test_goal_status():
    assert gl.goal_status([], 3.8) == {"projected": None, "status": "no_grades", "gap": None}
    status = gl.goal_status(COURSES, 3.8)
    assert status["status"] == "on_track" and status["projected"] == round(gl.gpa(COURSES), 2)
    assert gl.goal_status(COURSES, 3.95)["status"] == "close"
    assert gl.goal_status(COURSES, 4.2)["status"] == "behind"


def test_grades_needed_for_planned_courses():
    needed = gl.grades_needed(COURSES, 3.8)
    assert [c["name"] for c in needed] == ["Chinese"] and needed[0]["credits"] == 2
    assert needed[0]["letter"] == gl.required_average(COURSES, 3.8, 2)["letter"]
    assert gl.grades_needed(COURSES, 4.3)[0]["letter"] is None          # không thể đạt
    assert gl.grades_needed([course("A", 3, "A")], 3.8) == []


def test_year_targets_and_credits_by_year():
    assert gl.year_targets(128) == [32, 32, 32, 32] and gl.year_targets(130) == [33, 33, 32, 32]
    rows = gl.credits_by_year(COURSES + [course("Old", 3, "A", "116-2"), course("Fail", 3, "F")], 128, "115-1")
    assert [(r["year"], r["earned"], r["planned"]) for r in rows] == [(1, 13, 2), (2, 3, 0), (3, 0, 0), (4, 0, 0)]
    assert rows[0]["percent"] == round(15 * 100 / 32)
    late = gl.credits_by_year([course("X", 3, "A", "115-1"), course("Y", 2, "A", "121-1")], 128, "115-1")
    assert late[3]["earned"] == 2                                        # năm 7 cộng vào năm 4
    assert gl.credits_by_year([], 128, "115-1")[0]["earned"] == 0


def test_gpa_page_shows_new_cards(browser):
    for c in COURSES:
        browser.api("POST", "/api/courses", {k: c[k] for k in ("name", "credits", "semester", "grade")})
    browser.api("PUT", "/api/goals", {"target_gpa": 3.8, "credits_required": 128})
    html = browser.client.get("/gpa").get_data(as_text=True)
    assert "GPA goal" in html and "On track" in html and 'type="range"' in html
    assert "Grades you need" in html and "Graduation credits" in html and "Year 1" in html and "15 / 32" in html
    assert 'form="goal-form"' in html
