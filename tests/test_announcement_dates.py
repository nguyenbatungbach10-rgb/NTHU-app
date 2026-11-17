"""Trang Announcements: nút Save to Calendar dùng ngày đọc từ tiêu đề."""
import app as app_module

ITEMS = [
    {"title": "Scholarship application deadline: Nov 20", "link": "http://a", "date": "2026-11-01",
     "office": "Student Affairs", "language": "en", "category": "Scholarship"},
    {"title": "Dormitory news", "link": "http://b", "date": "2026-11-02",
     "office": "Housing", "language": "en", "category": "Dorm"},
]


def use_items(monkeypatch):
    monkeypatch.setattr(app_module, "fetch_announcements", lambda: (ITEMS, None))


def test_save_button_carries_date_from_title(browser, monkeypatch):
    use_items(monkeypatch)
    html = browser.client.get("/announcements").data.decode()
    assert 'data-date="2026-11-20"' in html                      # ngày hạn trong tiêu đề
    assert 'data-date="2026-11-02"' in html                      # không có ngày: dùng ngày đăng
    assert "Will be saved on 2026-11-20 (date found in the title)" in html
    assert html.count("date found in the title") == 1


def test_saved_state_follows_the_title_date(browser, monkeypatch):
    use_items(monkeypatch)
    page = browser.client.get("/announcements").data.decode()
    assert page.count("Save to Calendar") == 2 and "Saved &#10003;" not in page
    # lưu đúng như nút gửi: tiêu đề + ngày hạn
    response = browser.api("POST", "/api/events", {"title": ITEMS[0]["title"], "date": "2026-11-20"})
    assert response.status_code == 201
    page = browser.client.get("/announcements").data.decode()
    assert page.count("Saved &#10003;") == 1


def test_other_users_saved_state_is_not_shared(browser, make_browser, monkeypatch):
    use_items(monkeypatch)
    browser.api("POST", "/api/events", {"title": ITEMS[0]["title"], "date": "2026-11-20"})
    other = make_browser()
    other.signup("b@example.com")
    assert "Saved &#10003;" not in other.client.get("/announcements").data.decode()
    assert not hasattr(ITEMS[0], "saved") and "event_date" not in ITEMS[0]      # cache dùng chung không bị sửa
