"""Test Calendar API, trang Calendar và việc cô lập dữ liệu giữa các người dùng."""
from datetime import date
from calendar_logic import today_tw  # noqa: E402

EVENT = {"title": "Midterm exam", "date": "2026-11-20", "time": "09:00",
         "description": "Room 101", "source_url": "https://www.nthu.edu.tw/x"}


def test_create_event_returns_201_with_id(browser):
    response = browser.api("POST", "/api/events", EVENT)
    assert response.status_code == 201
    data = response.get_json()
    assert data["id"] >= 1
    assert {k: data[k] for k in EVENT} == EVENT


def test_create_event_validation_errors_return_400(browser):
    cases = [
        ({"title": "x"}, "title and date are required"),
        ({"title": "x", "date": "2026-02-30"}, "YYYY-MM-DD"),
        ({"title": "x", "date": "2026-11-20", "time": "99:99"}, "HH:MM"),
        ({"title": "x", "date": "2026-11-20", "source_url": "javascript:alert(1)"}, "http"),
    ]
    for payload, expected in cases:
        response = browser.api("POST", "/api/events", payload)
        assert response.status_code == 400
        assert expected in response.get_json()["error"]
    # body không phải JSON
    response = browser.client.post("/api/events", data="not json",
                                   headers={"X-CSRF-Token": browser.token()})
    assert response.status_code == 400


def test_list_events_sorted_and_filtered_by_month(browser):
    browser.api("POST", "/api/events", {"title": "B", "date": "2026-11-20", "time": "10:00"})
    browser.api("POST", "/api/events", {"title": "A", "date": "2026-11-20", "time": "08:00"})
    browser.api("POST", "/api/events", {"title": "Dec", "date": "2026-12-01"})

    everything = browser.api("GET", "/api/events").get_json()
    assert [e["title"] for e in everything] == ["A", "B", "Dec"]

    november = browser.api("GET", "/api/events?month=2026-11").get_json()
    assert [e["title"] for e in november] == ["A", "B"]

    assert browser.api("GET", "/api/events?month=nope").status_code == 400


def test_update_event(browser):
    created = browser.api("POST", "/api/events", EVENT).get_json()
    changed = dict(EVENT, title="Final exam", date="2026-12-25")
    response = browser.api("PUT", f"/api/events/{created['id']}", changed)
    assert response.status_code == 200
    assert response.get_json()["title"] == "Final exam"
    assert browser.api("GET", "/api/events").get_json()[0]["date"] == "2026-12-25"

    bad = browser.api("PUT", f"/api/events/{created['id']}", {"title": ""})
    assert bad.status_code == 400
    assert browser.api("PUT", "/api/events/999", EVENT).status_code == 404


def test_delete_event(browser):
    created = browser.api("POST", "/api/events", EVENT).get_json()
    assert browser.api("DELETE", f"/api/events/{created['id']}").status_code == 204
    assert browser.api("GET", "/api/events").get_json() == []
    assert browser.api("DELETE", f"/api/events/{created['id']}").status_code == 404


def test_users_cannot_see_edit_or_delete_each_others_events(browser, make_browser):
    mine = browser.api("POST", "/api/events", EVENT).get_json()

    other = make_browser()
    other.signup("other@example.com", "password123")
    assert other.api("GET", "/api/events").get_json() == []
    assert other.api("PUT", f"/api/events/{mine['id']}", dict(EVENT, title="hacked")).status_code == 404
    assert other.api("DELETE", f"/api/events/{mine['id']}").status_code == 404

    # sự kiện của tôi vẫn nguyên vẹn
    still = browser.api("GET", "/api/events").get_json()
    assert [e["title"] for e in still] == ["Midterm exam"]


def test_api_post_without_csrf_header_is_rejected(browser):
    response = browser.client.post("/api/events", json=EVENT)  # không gửi X-CSRF-Token
    assert response.status_code == 400
    assert response.get_json() == {"error": "Invalid or missing CSRF token"}
    assert browser.api("GET", "/api/events").get_json() == []


def test_calendar_page_shows_events_by_month(browser):
    browser.api("POST", "/api/events", {"title": "Physics quiz", "date": "2026-11-20"})
    browser.api("POST", "/api/events", {"title": "December party", "date": "2026-12-05"})

    november = browser.client.get("/calendar?month=2026-11").get_data(as_text=True)
    assert "November 2026" in november
    assert "Physics quiz" in november and "December party" not in november

    december = browser.client.get("/calendar?month=2026-12").get_data(as_text=True)
    assert "December party" in december and "Physics quiz" not in december

    # tháng không hợp lệ -> rơi về tháng hiện tại, không lỗi
    assert browser.client.get("/calendar?month=garbage").status_code == 200


def test_calendar_page_escapes_html_in_titles(browser):
    browser.api("POST", "/api/events", {"title": "<script>alert(1)</script>", "date": "2026-11-20"})
    html = browser.client.get("/calendar?month=2026-11").get_data(as_text=True)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_home_shows_my_upcoming_events(browser):
    today = today_tw().isoformat()
    browser.api("POST", "/api/events", {"title": "Study group", "date": today})
    html = browser.client.get("/").get_data(as_text=True)
    assert "Coming up" in html and "Study group" in html


def test_home_for_visitors_prompts_login(make_browser):
    html = make_browser().client.get("/").get_data(as_text=True)
    assert "Create a free account" in html and "Classes today" not in html


def test_announcements_save_button_states(browser, make_browser):
    # chưa đăng nhập: thấy "Log in to save"
    visitor = make_browser().client.get("/announcements").get_data(as_text=True)
    assert "Log in to save" in visitor and "data-save" not in visitor

    # đã đăng nhập, chưa lưu: có nút Save
    html = browser.client.get("/announcements").get_data(as_text=True)
    assert html.count("data-save") == 3

    # lưu đúng như nút Save sẽ gửi (title, date, office, link)
    saved = browser.api("POST", "/api/events", {
        "title": "Scholarship news", "date": "2026-11-20",
        "description": "Student Affairs", "source_url": "http://a"})
    assert saved.status_code == 201

    html = browser.client.get("/announcements").get_data(as_text=True)
    assert html.count("data-save") == 2 and "&#10003; Added" in html

    # người khác không thấy trạng thái "Saved" của tôi (cache dùng chung không bị làm bẩn)
    other = make_browser()
    other.signup("other@example.com", "password123")
    assert "&#10003; Added" not in other.client.get("/announcements").get_data(as_text=True)
