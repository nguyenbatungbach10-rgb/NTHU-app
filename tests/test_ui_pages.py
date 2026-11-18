"""Test trang lịch cả năm, bảng chọn nhanh tháng, menu 3 gạch và khối "hôm nay" ở trang chủ."""
from datetime import date, timedelta
from calendar_logic import today_tw  # noqa: E402


def _get(browser, url):
    return browser.client.get(url).get_data(as_text=True)


# ---------- lịch cả năm ----------

def test_year_page_requires_login(make_browser):
    response = make_browser().client.get("/calendar/year")
    assert response.status_code == 302 and "/login" in response.headers["Location"]


def test_year_page_links_to_all_twelve_months(browser):
    html = _get(browser, "/calendar/year?year=2026")
    for month in range(1, 13):
        assert f"/calendar?month=2026-{month:02d}" in html
    assert "<h1>2026</h1>" in html


def test_year_page_counts_events_and_deadlines(browser):
    browser.api("POST", "/api/events", {"title": "Exam", "date": "2026-03-05"})
    browser.api("POST", "/api/tasks", {"title": "Report", "due_date": "2026-03-05"})
    html = _get(browser, "/calendar/year?year=2026")
    assert "2 events and deadlines" in html
    assert 'title="2 event(s) and deadline(s)"' in html


def test_year_page_bad_or_out_of_range_year_falls_back_to_this_year(browser):
    this_year = today_tw().year
    for bad in ["garbage", "", "99999", "1800", "-1", "20.5"]:
        response = browser.client.get(f"/calendar/year?year={bad}")
        assert response.status_code == 200
        assert f"<h1>{this_year}</h1>" in response.get_data(as_text=True)


def test_year_page_edge_years_hide_missing_neighbour(browser):
    assert "1969" not in _get(browser, "/calendar/year?year=1970").split('class="year-go"')[0]
    assert "2101" not in _get(browser, "/calendar/year?year=2100").split('class="year-go"')[0]


def test_year_page_only_shows_my_data(browser, make_browser):
    browser.api("POST", "/api/events", {"title": "Mine", "date": "2026-03-05"})
    other = make_browser()
    other.signup("b@example.com")
    html = _get(other, "/calendar/year?year=2026")
    assert "0 events and deadlines" in html and "mini-count" not in html


# ---------- chọn nhanh tháng/năm ở lịch tháng ----------

def test_month_page_has_quick_jump_panel(browser):
    html = _get(browser, "/calendar?month=2026-12")
    assert "December 2026" in html
    assert "/calendar/year?year=2026" in html                     # nút xem cả năm
    assert "/calendar?month=2025-12" in html and "/calendar?month=2027-12" in html   # năm trước / sau, cùng tháng
    for month in range(1, 13):
        assert f"/calendar?month=2026-{month:02d}" in html
    assert 'class="on"' in html


# ---------- menu ----------

def test_menu_lists_every_page_and_marks_current(browser):
    html = _get(browser, "/study")
    assert 'id="menu-button"' in html and 'aria-expanded="false"' in html
    for path in ["/", "/calendar", "/schedule", "/announcements", "/gpa", "/study"]:
        assert f'href="{path}"' in html
    assert html.count('aria-current="page"') == 1
    assert "theme-coral" in html


def test_menu_current_page_for_year_view_is_calendar(browser):
    html = _get(browser, "/calendar/year")
    assert html.count('aria-current="page"') == 1 and "theme-violet" in html


def test_menu_shows_log_out_when_logged_in_and_log_in_when_not(browser, make_browser):
    assert "Log out" in _get(browser, "/") and "Sign up" not in _get(browser, "/")
    visitor = _get(make_browser(), "/")
    assert "Log out" not in visitor and "Sign up" in visitor


def test_each_feature_page_has_its_own_theme(browser):
    expected = {"/calendar": "violet", "/schedule": "teal", "/gpa": "green", "/study": "coral", "/announcements": "blue"}
    for path, color in expected.items():
        assert f"theme-{color}" in _get(browser, path)


# ---------- khối "hôm nay" ở trang chủ ----------

def test_home_today_panel_shows_todays_classes_and_due_tasks(browser):
    today = today_tw()
    yesterday = (today - timedelta(days=1)).isoformat()
    tomorrow = (today + timedelta(days=1)).isoformat()
    browser.api("POST", "/api/classes", {"name": "Calculus", "weekday": today.weekday(), "start": "10:10", "end": "12:00", "room": "R101"})
    other_day = (today.weekday() + 1) % 7
    browser.api("POST", "/api/classes", {"name": "Other day class", "weekday": other_day, "start": "08:00", "end": "09:00"})
    browser.api("POST", "/api/tasks", {"title": "Due now", "due_date": today.isoformat()})
    browser.api("POST", "/api/tasks", {"title": "Was due", "due_date": yesterday})
    browser.api("POST", "/api/tasks", {"title": "Later task", "due_date": tomorrow})
    html = _get(browser, "/")
    assert "Calculus" in html and "10:10" in html and "R101" in html
    assert "Other day class" not in html
    assert "Due now" in html and "Was due" in html and "Overdue" in html
    assert "Later task" not in html


def test_home_today_panel_empty_states(browser):
    html = _get(browser, "/")
    assert "No classes today." in html and "Nothing due." in html


def test_home_today_panel_hides_other_users_data(browser, make_browser):
    today = today_tw()
    browser.api("POST", "/api/classes", {"name": "Secret class", "weekday": today.weekday(), "start": "10:10", "end": "12:00"})
    browser.api("POST", "/api/tasks", {"title": "Secret task", "due_date": today.isoformat()})
    other = make_browser()
    other.signup("b@example.com")
    html = _get(other, "/")
    assert "Secret class" not in html and "Secret task" not in html
