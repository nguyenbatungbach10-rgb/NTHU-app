"""Test hướng dẫn người mới và gợi ý tên môn."""
from datetime import date

import home_logic


def test_onboarding_counts_steps_and_hides_when_done():
    result = home_logic.onboarding({"classes": 2, "goals": 0, "events": 1})
    assert [s["done"] for s in result["steps"]] == [True, False, True, False]
    assert (result["done"], result["total"], result["show"]) == (2, 4, True)
    assert home_logic.onboarding({"classes": 1, "goals": 1, "events": 1, "tasks": 1})["show"] is False
    assert home_logic.onboarding({})["done"] == 0


def test_name_suggestions():
    assert home_logic.name_suggestions(["Calculus", " physics", ""], ["calculus", "微積分"], [None]) == \
        ["Calculus", "physics", "微積分"]
    assert len(home_logic.name_suggestions([f"c{i}" for i in range(80)])) == 50


def test_home_onboarding_for_new_user_then_progress(browser):
    html = browser.client.get("/").get_data(as_text=True)
    assert "Get started" in html and "0 of 4 done" in html and "/announcements?view=deadlines" in html
    browser.api("POST", "/api/classes", {"name": "Calculus", "weekday": 0, "start": "10:10", "end": "12:00"})
    browser.api("PUT", "/api/goals", {"target_gpa": 3.5, "credits_required": 128})
    assert "2 of 4 done" in browser.client.get("/").get_data(as_text=True)
    browser.api("POST", "/api/events", {"title": "x", "date": "2026-12-01"})
    browser.api("POST", "/api/tasks", {"title": "t"})
    assert "Get started" not in browser.client.get("/").get_data(as_text=True)


def test_onboarding_counts_only_my_data(browser, make_browser):
    browser.api("POST", "/api/classes", {"name": "Calculus", "weekday": 0, "start": "10:10", "end": "12:00"})
    other = make_browser()
    other.signup("b@example.com")
    assert "0 of 4 done" in other.client.get("/").get_data(as_text=True)


def test_visitor_has_no_onboarding(make_browser):
    assert "Get started" not in make_browser().client.get("/").get_data(as_text=True)


def test_name_suggestions_on_gpa_and_study(browser):
    browser.api("POST", "/api/classes", {"name": "Linear Algebra", "weekday": 1, "start": "10:10", "end": "12:00"})
    for page, list_id in (("/gpa", "course-names"), ("/study", "subject-names")):
        html = browser.client.get(page).get_data(as_text=True)
        assert f'list="{list_id}"' in html and '<option value="Linear Algebra">' in html
